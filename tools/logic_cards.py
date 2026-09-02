# -*- coding: utf-8 -*-
"""Render Capcom's Logic keyword names into the DS keyword card images.

jpn/logic_keyword_local.bin holds 266 cards in two styles, one pair per keyword:
  style A  entries   1..133  (k = e - 1)    80x40, blue card, white 2-line text
  style B  entries 135..267  (k = e - 135) 160x16, white 1-line banner on transparent
Palettes are shared at file level (entry 0 for A, entry 134 for B). Each card is
a sub-container (u32 offset table) holding RECN + RNAN + RGCN; only the RGCN
tile data is rewritten here, the cells stay as they are.

The fan patch drew its own English into these; the official names come from
tools/logic_names.py (Collection string tables). Where a DS keyword has no
official name (6 real ones + 30 dummies) the fan card is left alone.

    python tools/logic_cards.py OUTDIR [--rom in.nds out.nds]
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(__file__))
from collections import Counter
from lz11 import decompress
from nitro import ncgr, nclr
from ncer import ncer
from title_art import cell_indices
from title_text import repack, write_sprites
from PIL import Image, ImageDraw, ImageFont

SRC = 'dump/ds_fan/jpn/logic_keyword_local.bin'
FONT = os.path.join('dump', 'title', 'fonts', 'FOT-UDKAKUGO_SMALLPR6-M.otf')
A_RANGE = range(1, 134)
B_RANGE = range(135, 268)
SUB_MAGIC = bytes([0x0c, 0, 0, 0])
BLUES = {3, 4, 5, 6, 7, 8}     # the card interior is a vertical gradient of these
A_INK = 9                      # white text on style A
A_SHADOW = 8                   # darkest interior blue, used as a 1px drop shadow
B_INK = 1                      # white on transparent (style B)
ROW_FILL = {}                  # y -> gradient shade, learned from all style-A cards


def table(d):
    n = struct.unpack_from('<I', d, 0)[0] // 8
    offs = [struct.unpack_from('<II', d, i * 8) for i in range(n)]
    live = sorted(o for o, s in offs if o)
    out = []
    for o, s in offs:
        if not o:
            out.append(b''); continue
        nxt = [q for q in live if q > o]
        b = d[o:(nxt[0] if nxt else len(d))]
        if b[:1] == b'\x11' and (s & 0x80000000):
            b = decompress(b)
        out.append(b)
    return out


def sub_split(b):
    first = struct.unpack_from('<I', b, 0)[0]; n = first // 4
    offs = [struct.unpack_from('<I', b, i * 4)[0] for i in range(n)] + [len(b)]
    return [b[offs[i]:offs[i + 1]] for i in range(n)]


def sub_join(parts):
    n = len(parts); offs = []; body = bytearray(); pos = 4 * n
    for p in parts:
        while pos % 4:
            body += b'\x00'; pos += 1
        offs.append(pos); body += p; pos += len(p)
    return b''.join(struct.pack('<I', o) for o in offs) + bytes(body)


def card_rows(E, e):
    parts = sub_split(E[e])
    gi = next(i for i, p in enumerate(parts) if p[:4] == b'RGCN')
    rec = next(p for p in parts if p[:4] == b'RECN')
    cells, _ = ncer(rec)
    objs = next(c for c in cells if c)
    tiles, bpp, cnt, _, _ = ncgr(parts[gi])
    tiles = bytearray(tiles)
    rows, origin = cell_indices(objs, tiles, bpp)
    return parts, gi, objs, tiles, bpp, rows, origin


def learn_row_fill(E):
    votes = {}
    for e in A_RANGE:
        if not E[e] or E[e][:4] != SUB_MAGIC:
            continue
        _, _, _, _, _, rows, _ = card_rows(E, e)
        for y, r in enumerate(rows):
            for v in r:
                if v in BLUES:
                    votes.setdefault(y, Counter())[v] += 1
    ROW_FILL.clear()
    ROW_FILL.update({y: c.most_common(1)[0][0] for y, c in votes.items()})


def render_text(text, px):
    f = ImageFont.truetype(FONT, px)
    bb = f.getbbox(text)
    im = Image.new('L', (bb[2] - bb[0] + 2, bb[3] - bb[1] + 2), 0)
    ImageDraw.Draw(im).text((1 - bb[0], 1 - bb[1]), text, font=f, fill=255)
    return im


def paint_1bit(rows, img, x, y, ink, region, thresh=128, shadow=None):
    """Threshold `img` (L) into index `ink` at (x, y), inside `region` only.
    With `shadow`, the same shape is painted first at (+1,+1) in that index."""
    if shadow is not None:
        paint_1bit(rows, img, x + 1, y + 1, shadow, region, thresh)
    px = img.load(); H, W = len(rows), len(rows[0])
    x0, y0, x1, y1 = region
    lost = 0
    for yy in range(img.height):
        for xx in range(img.width):
            if px[xx, yy] < thresh:
                continue
            X, Y = x + xx, y + yy
            if x0 <= X <= x1 and y0 <= Y <= y1 and 0 <= X < W and 0 <= Y < H:
                rows[Y][X] = ink
            else:
                lost += 1
    return lost


def wrap_words(text, px, max_w):
    words = text.split(); lines = []; cur = ''
    for w in words:
        t = (cur + ' ' + w).strip()
        if render_text(t, px).width <= max_w or not cur:
            cur = t
        else:
            lines.append(cur); cur = w
    if cur:
        lines.append(cur)
    return lines


def card_A(rows, name, log):
    """Repaint the interior of a style-A card with `name` on up to two lines."""
    H, W = len(rows), len(rows[0])
    blue = [(x, y) for y in range(H) for x in range(W) if rows[y][x] in BLUES]
    if not blue:
        return False
    bx0 = min(x for x, y in blue); bx1 = max(x for x, y in blue)
    by0 = min(y for x, y in blue); by1 = max(y for x, y in blue)
    region = (bx0 + 3, by0 + 2, bx1 - 3, by1 - 2)
    # wipe the interior row by row to that row's gradient shade (text, outline
    # and shadow all go; clearing only the white pixels leaves ghosts)
    for y in range(region[1], region[3] + 1):
        fill = ROW_FILL.get(y)
        if fill is None:
            shades = [rows[y][x] for x in range(W) if rows[y][x] in BLUES]
            if not shades:
                continue
            fill = max(set(shades), key=shades.count)
        for x in range(region[0], region[2] + 1):
            rows[y][x] = fill
    max_w = region[2] - region[0] + 1
    max_h = region[3] - region[1] + 1
    for px_size in (9,):
        lines = wrap_words(name, px_size, max_w)
        if len(lines) > 2:
            continue
        imgs = [render_text(l, px_size) for l in lines]
        imgs = [im.resize((max_w, im.height)) if im.width > max_w else im for im in imgs]
        total_h = sum(im.height for im in imgs) + (len(imgs) - 1)
        if total_h > max_h:
            continue
        y = region[1] + (max_h - total_h) // 2
        lost = 0
        for im in imgs:
            x = region[0] + (max_w - im.width) // 2
            lost += paint_1bit(rows, im, x, y, A_INK, region, thresh=100, shadow=A_SHADOW)
            y += im.height + 1
        log.append('A %-28s %dpx %d line(s) lost=%d' % (name, px_size, len(lines), lost))
        return True
    # last resort: two lines at 9px, split as evenly as possible, the wider one condensed
    words = name.split(); best = None
    for cut in range(1, len(words)):
        l1, l2 = ' '.join(words[:cut]), ' '.join(words[cut:])
        w = max(render_text(l1, 9).width, render_text(l2, 9).width)
        if best is None or w < best[0]:
            best = (w, l1, l2)
    if best:
        imgs = [render_text(l, 9) for l in (best[1], best[2])]
        imgs = [im.resize((min(im.width, max_w), im.height)) for im in imgs]
        total_h = sum(im.height for im in imgs) + 1
        y = region[1] + max(0, (max_h - total_h) // 2); lost = 0
        for im in imgs:
            x = region[0] + (max_w - im.width) // 2
            lost += paint_1bit(rows, im, x, y, A_INK, region, thresh=100, shadow=A_SHADOW)
            y += im.height + 1
        log.append('A %-28s 9px 2 lines CONDENSED lost=%d' % (name, lost))
        return True
    log.append('A %-28s DOES NOT FIT (interior %dx%d)' % (name, max_w, max_h))
    return False


def card_B(rows, name, log):
    H, W = len(rows), len(rows[0])
    for y in range(H):
        for x in range(W):
            rows[y][x] = 0
    region = (0, 0, W - 1, H - 1)
    for px_size in (10,):
        im = render_text(name, px_size)
        if im.width > W - 4:
            im = im.resize((W - 4, im.height))        # condense, as the fan did
        if im.height > H:
            continue
        x = (W - im.width) // 2; y = (H - im.height) // 2
        lost = paint_1bit(rows, im, x, y, B_INK, region, thresh=100)
        log.append('B %-28s %dpx lost=%d' % (name, px_size, lost))
        return True
    log.append('B %-28s DOES NOT FIT' % name)
    return False


def build(outdir, names):
    data = open(SRC, 'rb').read()
    E = table(data)
    pals = {0: nclr(E[0]), 134: nclr(E[134])}
    learn_row_fill(E)
    repl, log, prev_a, prev_b = {}, [], [], []
    for k, v in sorted(names.items()):
        name = v['en']
        for e, style in ((k + 1, 'A'), (k + 135, 'B')):
            if not E[e] or E[e][:4] != SUB_MAGIC:
                continue
            parts, gi, objs, tiles, bpp, rows, origin = card_rows(E, e)
            ok = card_A(rows, name, log) if style == 'A' else card_B(rows, name, log)
            if not ok:
                continue
            write_sprites(tiles, objs, rows, origin, bpp)
            gfx = bytearray(parts[gi])
            doff = struct.unpack_from('<I', gfx, 0x18 + 20)[0]
            dsize = struct.unpack_from('<I', gfx, 0x18 + 16)[0]
            gfx[0x18 + doff:0x18 + doff + dsize] = tiles[:dsize]
            newparts = list(parts); newparts[gi] = bytes(gfx)
            repl[e] = sub_join(newparts)
            bucket = prev_a if style == 'A' else prev_b
            if len(bucket) < 40:
                pal = pals[0 if style == 'A' else 134]
                im = Image.new('RGB', (len(rows[0]), len(rows)), (0, 255, 0)); px = im.load()
                for yy, r in enumerate(rows):
                    for xx, val in enumerate(r):
                        if val:
                            px[xx, yy] = pal[val]
                bucket.append(im)
    new = repack(data, repl)
    os.makedirs(outdir, exist_ok=True)
    out = os.path.join(outdir, 'logic_keyword_local.bin')
    open(out, 'wb').write(new)
    for name, prev, cw, ch, cols in (('logic_cards_preview3x.png', prev_a, 84, 44, 5), ('logic_banners_preview3x.png', prev_b, 164, 20, 2)):
        if not prev:
            continue
        rows_n = (len(prev) + cols - 1) // cols
        sheet = Image.new('RGB', (cols * cw, rows_n * ch), (60, 60, 60))
        for i, im in enumerate(prev):
            sheet.paste(im, ((i % cols) * cw, (i // cols) * ch))
        sheet.resize((sheet.width * 3, sheet.height * 3), Image.NEAREST).save(os.path.join(outdir, name))
    return out, repl, log


if __name__ == '__main__':
    outdir = sys.argv[1]
    from logic_names import keyword_names
    names, n = keyword_names()
    out, repl, log = build(outdir, names)
    print('\n'.join(log))
    print('cards rewritten: %d (of %d keywords with official names)' % (len(repl), len(names)))
    if '--rom' in sys.argv:
        from title_logo import splice
        i = sys.argv.index('--rom')
        rom = splice(open(sys.argv[i + 1], 'rb').read(), 'jpn/logic_keyword_local.bin', open(out, 'rb').read())
        open(sys.argv[i + 2], 'wb').write(rom)
        print('wrote', sys.argv[i + 2])
