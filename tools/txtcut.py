# -*- coding: utf-8 -*-
"""Render Capcom's close-up text screens (gk2_txtcut_en) into the DS close-up CGs.

jpn/upcut_local.bin holds full-screen 256x192 8bpp images, each followed by its
own RLCN palette (GPGP...). 39 of them are text on a flat ground that the fan
patch drew in its own pixel face; the Collection ships the same screens as
strings, so this re-renders each screen from Capcom's row in that same face.

The face is tools/txtcut_font.json, harvested from the fan screens themselves
(2-colour renders, so the glyphs are exact). Layout copies the fan screens:
body text at x=11, bullets at x=6 with the text at 17, right edge 244, first
cap-top at y=9, 13 px line pitch, paragraphs justified except their last line,
a 6 px gap on a blank line, centred titles with an 18 px gap under them.

Capcom's rows were set for a wide card (up to 64 chars a line), so paragraphs
are re-flowed: consecutive lines that share an indent and are not fields
("Label: ...") or bullets are joined and re-wrapped to the DS width.

    python tools/txtcut.py OUTDIR [--rom in.nds out.nds]

OUTDIR gets upcut_local.bin, one 3x preview per screen, and a contact sheet.
"""
import sys, os, re, struct, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lz11 import decompress
from nitro import ncgr, nclr, _sections
from title_text import repack
from PIL import Image

SRC = 'dump/ds_fan/jpn/upcut_local.bin'
LOC = 'dump/loc_en.json'
FONT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'txtcut_font.json')
W, H = 256, 192
X_BODY, X_BULLET, X_RIGHT = 11, 6, 244
Y_TOP, CAP = 9, 8            # first cap-top row; baseline = cap-top + 8
PITCH, PARA_GAP, TITLE_GAP = 13, 6, 18
INDENT_PX = 3                # per leading ASCII space in Capcom's row
BULLETS = ('■', '•', '*')

# DS entry -> gk2_txtcut_en row (TXTCUT_MAPPING.md)
ROWS = {28: 3, 34: 5, 72: 0, 74: 1, 76: 2, 98: 15, 108: 16, 110: 17, 112: 18, 120: 19,
        122: 20, 124: 21, 126: 22, 128: 23, 212: 25, 222: 27, 228: 28, 240: 31, 248: 32,
        250: 33, 254: 35, 256: 36, 258: 37, 266: 6, 270: 7, 284: 8, 286: 9, 288: 10,
        290: 11, 292: 7, 294: 12, 296: 13,
        32: 4, 94: 14, 130: 24, 214: 26, 230: 29, 232: 30, 252: 34}
# rows whose indented lines are list items, not sentences broken for the card
LIST_ROWS = {15, 32}


def load_font():
    f = json.load(open(FONT, encoding='utf-8'))
    return f['font'], f['space']


def table(d):
    n = struct.unpack_from('<I', d, 0)[0] // 8
    out = []
    for i in range(n):
        o, s = struct.unpack_from('<II', d, i * 8)
        s &= 0x7FFFFFFF
        b = d[o:o + s]
        if s and b[:1] == b'\x11':
            b = decompress(b)
        out.append(b)
    return out


# ---------------------------------------------------------------- text model
def parse_row(s):
    """Capcom row -> list of lines: {'indent': n_spaces, 'wide': bool, 'align': str,
    'runs': [(text, style)]} with <style> spans carried across lines."""
    lines = []
    style = None
    align = None
    for raw in s.split('\n'):
        t = raw
        la = None
        m = re.match(r'^<align="(\w+)">(.*)</align>\s*$', t)
        if m:
            la, t = m.group(1), m.group(2)
        wide = t.startswith('　')
        t = t.lstrip('　')
        n = len(t) - len(t.lstrip(' '))
        t = t.strip()
        runs = []
        pos = 0
        for tag in re.finditer(r'<(/?)style(?:="([^"]+)")?>', t):
            seg = t[pos:tag.start()]
            if seg:
                runs.append((seg, style))
            if tag.group(1):
                style = None
            else:
                st = tag.group(2)
                if st == 'TxtCut_Red':
                    style = 'red'
                elif st == 'TxtCut_LightBlue':
                    style = 'blue'
                # TxtCut_Subtitle: no size change on the DS
            pos = tag.end()
        seg = t[pos:]
        if seg:
            runs.append((seg, style))
        lines.append({'indent': n, 'wide': wide, 'align': la, 'runs': runs,
                      'blank': not runs})
    return lines


def is_field(text):
    return bool(re.match(r'^[A-Z][A-Za-z. \']{0,28}:(\s|$)', text))


def starts_item(text):
    return text.startswith(BULLETS) or bool(re.match(r'^(\d+\.|[IVX]+\.?|Promise [IVX]+)(\s|$)', text))


TERMINAL = '.!?:"\'-'          # a trailing -- is an interruption, keep the break


def paragraphs(lines, listy=False):
    """Group lines into paragraphs to re-flow. Each paragraph: {'x': px, 'align',
    'runs': [(text, style)], 'gap_before': px, 'title': bool}.

    A line joins the paragraph before it when it continues a sentence: it
    starts lowercase, or the previous line ended without terminal punctuation.
    Item headers ("Promise I", "■Rules:") never take a continuation, and on
    list rows (listy) only a lowercase start or a deeper hanging indent joins,
    so "Delicia Scone / Judy Bound" stay two items."""
    paras = []
    prev = None
    pending_gap = 0
    for ln in lines:
        if ln['blank']:
            pending_gap = PARA_GAP
            prev = None
            continue
        text = ''.join(t for t, _ in ln['runs'])
        if text[:1] in BULLETS and text[1:2] == ' ':
            # the fan set the square flush against its word
            t0, s0 = ln['runs'][0]
            ln['runs'][0] = (t0[0] + t0[2:], s0)
            text = text[0] + text[2:]
        x = X_BODY
        under_square = bool(paras) and paras[-1]['x'] in (X_BULLET, X_BODY + 6)
        if text.startswith(BULLETS):
            x = X_BULLET
        elif ln['wide']:
            x = X_BODY
        elif ln['indent'] and under_square:
            # the fan hung everything under a square at the square's text column
            x = X_BODY + 6
        elif ln['indent']:
            x = X_BODY + INDENT_PX * ln['indent']
        # deeper-indented lines under a numbered item or a "Notes: ..." field
        # are its hanging continuation, whatever their punctuation
        hanging = (prev is not None and (prev.get('item') or (prev.get('field') and not prev.get('field_only')))
                   and x > prev['x'] and not ln['align'])
        lower = text[:1].islower()
        if prev is None or ln['align'] or prev['align'] or starts_item(text) or is_field(text) \
                or prev.get('field_only') or prev.get('header'):
            newpara = True
        elif hanging:
            newpara = False
        elif x != prev['x'] or ln['wide'] != prev['wide']:
            newpara = True
        elif lower:
            newpara = False
        elif prev.get('field') or listy:
            newpara = True
        else:
            newpara = prev['last'].rstrip()[-1:] in TERMINAL
        if newpara:
            p = {'x': x, 'x2': X_BODY if x == X_BULLET else x, 'wide': ln['wide'],
                 'align': ln['align'], 'runs': list(ln['runs']), 'gap_before': pending_gap,
                 'title': ln['align'] == 'center', 'field_only': is_field(text) and text.rstrip().endswith(':'),
                 'joined': 0, 'item': starts_item(text), 'field': is_field(text), 'last': text,
                 'header': (starts_item(text) or text.startswith(BULLETS)) and len(text) <= 24
                           and text.rstrip()[-1:] not in '.!?'}
            paras.append(p)
            prev = p
            pending_gap = 0
        else:
            prev['runs'].append((' ', None))
            prev['runs'].extend(ln['runs'])
            prev['joined'] += 1
            prev['last'] = text
    return paras


# ---------------------------------------------------------------- measuring
def glyph_adv(font, c, space):
    if c == ' ':
        return space
    if c == '"':
        return 2 * font['"']['adv']
    return font[c]['adv'] if c in font else font['?']['adv']


def text_width(font, space, text):
    return sum(glyph_adv(font, c, space) for c in text)


def wrap(font, space, runs, width):
    """runs -> list of lines, each a list of (word, style) tokens with spaces as
    their own tokens; word widths measured in the face."""
    tokens = []
    for text, style in runs:
        for part in re.split(r'( )', text):
            if part:
                tokens.append((part, style))
    lines, cur, curw = [], [], 0
    for tok, style in tokens:
        w = text_width(font, space, tok)
        if tok == ' ':
            if cur:
                cur.append((tok, style)); curw += w
            continue
        if cur and curw + w > width:
            while cur and cur[-1][0] == ' ':
                curw -= space; cur.pop()
            lines.append(cur); cur, curw = [], 0
        cur.append((tok, style)); curw += w
    while cur and cur[-1][0] == ' ':
        cur.pop()
    if cur:
        lines.append(cur)
    return lines


# ---------------------------------------------------------------- rendering
def blit(px, font, c, x, base, idx):
    g = font[c] if c in font else font['?']
    bottom = base + g['desc']
    top = bottom - (g['h'] - 1)
    for ry, row in enumerate(g['bits']):
        for rx, ch in enumerate(row):
            if ch == '1':
                X, Y = x + rx, top + ry
                if 0 <= X < W and 0 <= Y < H:
                    px[X, Y] = idx


def draw_line(px, font, space, toks, x, base, width, justify, colours, align):
    words = [t for t in toks if t[0] != ' ']
    nsp = sum(1 for t in toks if t[0] == ' ')
    ink = sum(text_width(font, space, t) for t, _ in toks)
    extra = 0.0
    if justify and nsp:
        # the fan's word gaps run 6..11 px on a natural 8, so a line that would
        # need more than +4 per gap is left ragged instead of stretched
        extra = (width - ink) / float(nsp)
        if extra > 4:
            extra = 0.0
    if align == 'center':
        x = (W - ink) // 2
    elif align == 'right':
        x = X_RIGHT + 1 - ink
    acc = 0.0
    pen = x
    for tok, style in toks:
        if tok == ' ':
            acc += extra
            pen += space + int(acc)
            acc -= int(acc)
            continue
        idx = colours.get(style, colours[None])
        for c in tok:
            if c == '"':
                blit(px, font, '"', pen, base, idx)
                blit(px, font, '"', pen + font['"']['adv'], base, idx)
                pen += 2 * font['"']['adv']
                continue
            blit(px, font, c, pen, base, idx)
            pen += glyph_adv(font, c, space)
    return pen


def layout(font, space, paras):
    """-> list of (toks, x, align, justify, width) lines and per-line gaps, with
    the pitch/gaps squeezed if the screen would overflow."""
    out = []
    for p in paras:
        width = X_RIGHT + 1 - p['x']
        if p['align'] in ('center', 'right'):
            lines = wrap(font, space, p['runs'], W - 2 * X_BODY)
        else:
            lines = wrap(font, space, p['runs'], width)
        for i, toks in enumerate(lines):
            gap = p['gap_before'] if i == 0 else 0
            x = p['x'] if i == 0 else p['x2']
            # the fan justified prose paragraphs and left wrapped single lines
            # (fields, labels) ragged
            out.append({'toks': toks, 'x': x, 'align': p['align'], 'width': X_RIGHT + 1 - x,
                        'justify': i < len(lines) - 1 and not p['align'] and p['joined'] > 0, 'gap': gap,
                        'title': p['title'] and i == len(lines) - 1})
    return out


def total_height(lines, pitch, para_gap, title_gap):
    h = 0
    for i, ln in enumerate(lines):
        if i:
            h += pitch
        h += para_gap if ln['gap'] else 0
        if ln['title']:
            h += title_gap - pitch if i < len(lines) - 1 else 0
    return h


def render(entry, row_text, font, space, colours, log):
    """-> 256x192 index image (list of rows) for one screen."""
    im = Image.new('P', (W, H), colours['bg'])
    px = im.load()
    paras = paragraphs(parse_row(row_text), listy=ROWS[entry] in LIST_ROWS)
    lines = layout(font, space, paras)
    pitch, para_gap, title_gap, top = PITCH, PARA_GAP, TITLE_GAP, Y_TOP
    # budget runs from the first baseline to the last one; the last line keeps
    # its 3 descender rows plus one clear row above the screen edge
    def avail():
        return H - (top + CAP) - 4
    squeeze = []
    ladder = [('gap', 3), ('pitch', 12), ('top', 6), ('pitch', 11), ('top', 4)]
    while total_height(lines, pitch, para_gap, title_gap) > avail() and ladder:
        what, val = ladder.pop(0)
        if what == 'gap' and para_gap > val:
            para_gap = val
        elif what == 'pitch' and pitch > val:
            pitch = val
        elif what == 'top' and top > val:
            top = val
        else:
            continue
        squeeze.append('%s %d' % (what, val))
    height = total_height(lines, pitch, para_gap, title_gap)
    over = height - avail()
    squeeze = ' '.join(squeeze)
    # a lone centred line (the era card) sits mid-screen like the fan's
    if len(lines) == 1 and lines[0]['align'] == 'center':
        base = H // 2 + 4
    else:
        base = top + CAP
        if lines and lines[0]['title']:
            base = top - 1 + CAP
    for i, ln in enumerate(lines):
        if ln['gap']:
            base += para_gap
        draw_line(px, font, space, ln['toks'], ln['x'], base, ln['width'], ln['justify'], colours, ln['align'])
        base += title_gap if ln['title'] else pitch
    # pen position minus the last glyph's 2 px bearing = last ink column + 1
    widest = max((sum(text_width(font, space, t) for t, _ in ln['toks']) + ln['x'] - 2 for ln in lines), default=0)
    log.append('entry %3d row %2d: %2d lines, height %3d/%d %s%s' % (
        entry, ROWS[entry], len(lines), height, avail(), squeeze, ' OVERFLOW %d' % over if over > 0 else ''))
    if widest > X_RIGHT + 1:
        log.append('   entry %d: ink runs to x=%d (limit %d)' % (entry, widest - 1, X_RIGHT))
    return im


# ---------------------------------------------------------------- palettes
def screen_colours(gfx, pal_blob):
    """Index of the ground, the text colour and the accent from the fan tiles."""
    data, bpp, cnt, tw, th = ncgr(gfx)
    from collections import Counter
    c = Counter(data)
    order = [i for i, _ in c.most_common()]
    pal = nclr(pal_blob)
    bg = order[0]
    fg = order[1]
    accent = order[2] if len(order) > 2 else fg
    cols = {'bg': bg, None: fg, 'red': fg, 'blue': fg}
    # the accent is red on the two statute screens and blue on the era card
    if len(order) > 2:
        r, g, b = pal[accent]
        if r > 150 and b < 100:
            cols['red'] = accent
        elif b > 150 and r < 150:
            cols['blue'] = accent
    if len(order) == 2:
        r, g, b = pal[fg]
        if b > 150 and r < 150:
            cols['blue'] = fg
    return cols, pal


def write_gfx(gfx, im):
    """Replace the RAHC tile data of an RGCN with the 256x192 index image."""
    sec = _sections(gfx)[b'RAHC']
    p, size, body = sec
    dsize = struct.unpack_from('<I', body, 16)[0]
    doff = struct.unpack_from('<I', body, 20)[0]
    tw = W // 8
    tiles = bytearray(dsize)
    px = im.load()
    for t in range(dsize // 64):
        bx, by = (t % tw) * 8, (t // tw) * 8
        for y in range(8):
            for x in range(8):
                tiles[t * 64 + y * 8 + x] = px[bx + x, by + y]
    out = bytearray(gfx)
    start = p + 8 + doff
    out[start:start + dsize] = tiles
    return bytes(out)


def build(outdir, only=None):
    font, space = load_font()
    rows = json.load(open(LOC, encoding='utf-8'))['gk2_txtcut_en']
    data = open(SRC, 'rb').read()
    E = table(data)
    repl, log, previews = {}, [], []
    os.makedirs(outdir, exist_ok=True)
    for entry, row in sorted(ROWS.items()):
        if only and entry not in only:
            continue
        gfx, palb = E[entry], E[entry + 1]
        assert gfx[:4] == b'RGCN' and palb[:4] == b'RLCN', entry
        colours, pal = screen_colours(gfx, palb)
        im = render(entry, rows[row][1], font, space, colours, log)
        repl[entry] = write_gfx(gfx, im)
        flat = [c for rgb in pal for c in rgb]
        im.putpalette(flat + [0] * (768 - len(flat)))
        rgb = im.convert('RGB')
        rgb.resize((W * 3, H * 3), Image.NEAREST).save(os.path.join(outdir, 'txtcut_%03d_preview3x.png' % entry))
        previews.append((entry, rgb))
    new = repack(data, repl)
    out = os.path.join(outdir, 'upcut_local.bin')
    open(out, 'wb').write(new)
    cols = 4
    rows_n = (len(previews) + cols - 1) // cols
    sheet = Image.new('RGB', (cols * W, rows_n * H), (60, 60, 60))
    for i, (e, im) in enumerate(previews):
        sheet.paste(im, ((i % cols) * W, (i // cols) * H))
    sheet.save(os.path.join(outdir, 'txtcut_sheet.png'))
    return out, repl, log


if __name__ == '__main__':
    outdir = sys.argv[1]
    only = None
    if '--only' in sys.argv:
        only = {int(v) for v in sys.argv[sys.argv.index('--only') + 1].split(',')}
    out, repl, log = build(outdir, only)
    print('\n'.join(log))
    print('screens rewritten: %d' % len(repl))
    if '--rom' in sys.argv:
        from title_logo import splice
        i = sys.argv.index('--rom')
        rom = splice(open(sys.argv[i + 1], 'rb').read(), 'jpn/upcut_local.bin', open(out, 'rb').read())
        open(sys.argv[i + 2], 'wb').write(rom)
        print('wrote', sys.argv[i + 2])
