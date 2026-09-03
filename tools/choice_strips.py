# -*- coding: utf-8 -*-
"""Redraw the choice/prompt strips of jpn/idlocal.bin with Capcom's English.

The ~300 option buttons the game shows on choice menus ("John Doe / Tabby
Lloyd / Neither of them", topic lists, deductions) are graphics: entries
364-532 (224x32) and 534-670 (144x32), each a sprite bundle (RECN+RNAN+RGCN,
one cell of 64x32 objects) drawn on the cream plate of palette bank 0 (fill
index 4, dark-brown text core 7, an anti-aliasing ramp through 8-15/1-3/6).
The fan patch lettered them by hand; select_strips.json maps every strip to
its Collection string id (derived from the retail Japanese strips, see the
project notes), and the English is read from the player's own Collection
dump at build time, like the script. Text is set in the Collection's UD
Kakugo M, faux-bold, 14px, condensed up to 12% before stepping down a size,
and snapped to the plate's own palette by luminance.
"""
import sys, os, io, json, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lz11 import decompress
from nitro import ncgr, tile_pixels
from ncer import ncer
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
MAP = os.path.join(HERE, 'select_strips.json')
FONT = os.path.join('dump', 'title', 'fonts', 'FOT-UDKAKUGO_SMALLPR6-M.otf')

FILL, CORE = 4, 7
ROWS = range(2, 24)                 # plate interior
MARGIN = 4                          # px kept clear at each end of the interior
SIZES = (14, 13, 12, 11, 10)
CONDENSE = 0.88                     # narrowest allowed before stepping down
PALETTE_ENTRY = {'long': 363, 'short': 533}


# ---- container ----------------------------------------------------------
class Idlocal(object):
    def __init__(self, data):
        self.D = data
        self.n = struct.unpack_from('<I', data, 0)[0] // 8
        self.ents = [struct.unpack_from('<II', data, k * 8) for k in range(self.n)]

    def blob(self, i):
        o, s = self.ents[i]
        nxt = min([e[0] for e in self.ents if e[0] > o] + [len(self.D)])
        b = self.D[o:nxt]
        return decompress(b) if b[:1] == b'\x11' and (s & 0x80000000) else b

    def palette(self, i):
        b = self.blob(i)
        o = b.find(b'RLCN'); q = b.find(b'TTLP', o)
        plen = struct.unpack_from('<I', b, q + 16)[0]
        off = struct.unpack_from('<I', b, q + 20)[0]
        base = q + 8 + off
        cols = [struct.unpack_from('<H', b, base + 2 * k)[0] for k in range(plen // 2)]
        return [((c & 31) * 8, ((c >> 5) & 31) * 8, ((c >> 10) & 31) * 8) for c in cols]


def _parts(b):
    o = struct.unpack_from('<3I', b, 0)
    cells, mapping = ncer(b[o[0]:])
    data, bpp, cnt, _, _ = ncgr(b[o[2]:])
    boundary = 1 << (mapping & 3) if (mapping & 3) else 1
    return cells[0], data, bpp, cnt, boundary, o[2]


def grid(b):
    """Sprite bundle -> index grid (rows x cols) via the cell layout."""
    objs, data, bpp, cnt, boundary, _ = _parts(b)
    x0 = min(q['x'] for q in objs); y0 = min(q['y'] for q in objs)
    x1 = max(q['x'] + q['w'] for q in objs); y1 = max(q['y'] + q['h'] for q in objs)
    g = [[0] * (x1 - x0) for _ in range(y1 - y0)]
    for q in reversed(objs):
        tw, th = q['w'] // 8, q['h'] // 8
        for ty in range(th):
            for tx in range(tw):
                ti = q['tile'] * boundary + ty * tw + tx
                tp = tile_pixels(data, ti, bpp)
                for yy in range(8):
                    for xx in range(8):
                        c = tp[yy][xx]
                        if c:
                            g[q['y'] - y0 + ty * 8 + yy][q['x'] - x0 + tx * 8 + xx] = c
    return g


def encode(b, g):
    """Write index grid g back into bundle b's RGCN tiles (inverse of grid)."""
    objs, data, bpp, cnt, boundary, goff = _parts(b)
    assert bpp == 4
    out = bytearray(b)
    pos = bytes(b).find(data, goff)
    assert pos > 0
    x0 = min(q['x'] for q in objs); y0 = min(q['y'] for q in objs)
    for q in objs:
        tw, th = q['w'] // 8, q['h'] // 8
        for ty in range(th):
            for tx in range(tw):
                ti = q['tile'] * boundary + ty * tw + tx
                for yy in range(8):
                    for xx in range(0, 8, 2):
                        Y = q['y'] - y0 + ty * 8 + yy
                        X = q['x'] - x0 + tx * 8 + xx
                        lo = g[Y][X]; hi = g[Y][X + 1]
                        out[pos + ti * 32 + yy * 4 + xx // 2] = (hi << 4) | lo
    return bytes(out)


# ---- lettering ----------------------------------------------------------
def _lum(c):
    return 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]


def text_image(text, px, fontfile):
    f = ImageFont.truetype(fontfile, px)
    im = Image.new('L', (int(f.getlength(text)) + 8, px + 10), 0)
    d = ImageDraw.Draw(im)
    d.text((3, 2), text, font=f, fill=255)
    d.text((4, 2), text, font=f, fill=255)          # faux bold, as the fan's weight
    bb = im.getbbox()
    return im.crop(bb) if bb else im


def fit(text, limit, fontfile):
    """-> (image, px, scale): largest size that fits, condensing up to CONDENSE."""
    for px in SIZES:
        im = text_image(text, px, fontfile)
        if im.width <= limit:
            return im, px, 1.0
        if im.width * CONDENSE <= limit:
            return im.resize((limit, im.height), Image.LANCZOS), px, limit / im.width
    im = text_image(text, SIZES[-1], fontfile)
    return im.resize((limit, im.height), Image.LANCZOS), SIZES[-1], limit / im.width


def letter(g, text, pal, fontfile):
    """Clear the plate interior of g and set `text` on it. Returns (px, scale)."""
    W = len(g[0])
    for y in ROWS:
        for x in range(3, W - 3):
            g[y][x] = FILL
    limit = W - 6 - 2 * MARGIN
    im, px, sc = fit(text, limit, fontfile)
    if im.height > len(ROWS) - 2:
        im = im.resize((im.width, len(ROWS) - 2), Image.LANCZOS)
    ramp = sorted([k for k in range(1, 16) if k != FILL], key=lambda k: _lum(pal[k]))
    lf, lc = _lum(pal[FILL]), _lum(pal[CORE])
    x0 = (W - im.width) // 2
    y0 = ROWS[0] + (len(ROWS) - im.height) // 2
    p = im.load()
    for y in range(im.height):
        for x in range(im.width):
            a = p[x, y] / 255.0
            if a < 0.1:
                continue
            t = lf * (1 - a) + lc * a
            g[y0 + y][x0 + x] = min(ramp, key=lambda k: abs(_lum(pal[k]) - t))
    return px, sc


# ---- driver -------------------------------------------------------------
def load_map():
    return json.load(io.open(MAP, encoding='utf-8'))['strips']


def english(loc_en):
    out = {}
    for key in ('gk2_select_long_en', 'gk2_select_short_en'):
        for sid, s in loc_en[key]:
            out[sid] = s
    return out


def replacements(idlocal_bytes, loc_en, fontfile=FONT, log=None):
    """-> ({entry: new bundle bytes}, stats). Untouched: empties and rows
    whose English is missing from the player's Collection."""
    import re
    idl = Idlocal(idlocal_bytes)
    en = english(loc_en)
    pal = {k: idl.palette(v)[:16] for k, v in PALETTE_ENTRY.items()}
    out, stats = {}, dict(drawn=0, skipped=0, condensed=0, stepped=0)
    for key, row in load_map().items():
        i = int(key)
        if row.get('empty'):
            continue
        sid = row.get('twin') or row['id']
        text = en.get(sid)
        if not text:
            stats['skipped'] += 1
            continue
        text = re.sub(r'<[^>]*>', '', text).strip()
        b = idl.blob(i)
        g = grid(b)
        px, sc = letter(g, text, pal[row['block']], fontfile)
        if sc < 1.0: stats['condensed'] += 1
        if px < SIZES[0]: stats['stepped'] += 1
        out[i] = encode(b, g)
        stats['drawn'] += 1
        if log and (px < SIZES[0] or sc < 0.95):
            log('  strip %d: %dpx x%.2f  %s' % (i, px, sc, text))
    return out, stats


def preview(idlocal_bytes, loc_en, outdir, fontfile=FONT, per=14):
    """Write review sheets of every redrawn strip in true colour."""
    idl = Idlocal(idlocal_bytes)
    repl, stats = replacements(idlocal_bytes, loc_en, fontfile)
    pal = {k: idl.palette(v)[:16] for k, v in PALETTE_ENTRY.items()}
    os.makedirs(outdir, exist_ok=True)
    items = sorted(repl.items())
    rows_map = load_map()
    n = 0
    for s in range(0, len(items), per):
        tiles = []
        for i, b in items[s:s + per]:
            g = grid(b); P = pal[rows_map[str(i)]['block']]
            im = Image.new('RGB', (len(g[0]), len(g)), (40, 40, 40)); px = im.load()
            for y in range(len(g)):
                for x in range(len(g[0])):
                    if g[y][x]: px[x, y] = P[g[y][x]]
            tiles.append((i, im))
        W = max(t.width for _, t in tiles) + 48; H = sum(t.height + 4 for _, t in tiles) + 4
        sheet = Image.new('RGB', (W, H), (20, 20, 20)); d = ImageDraw.Draw(sheet); y = 2
        for i, t in tiles:
            d.text((2, y + 10), str(i), fill=(255, 120, 120)); sheet.paste(t, (44, y)); y += t.height + 4
        sheet.resize((W * 2, H * 2), Image.NEAREST).save(os.path.join(outdir, 'strips_%02d.png' % n)); n += 1
    return stats, n


def rebuild(idlocal_bytes, repl):
    """New idlocal container with `repl` entries replaced (stored as
    literal-only LZ11, as plates.py does); every other entry keeps its bytes."""
    idl = Idlocal(idlocal_bytes)
    n, ents = idl.n, idl.ents
    order = sorted(range(n), key=lambda i: ents[i][0])
    ext = {}
    for k, i in enumerate(order):
        ext[i] = (ents[i][0], ents[order[k + 1]][0] if k + 1 < n else len(idlocal_bytes))
    table = bytearray(n * 8)
    body = bytearray()
    for i in range(n):
        o, s = ents[i]
        comp = s & 0x80000000
        stored = idlocal_bytes[ext[i][0]:ext[i][1]]
        size = s & 0x7FFFFFFF
        if i in repl:
            raw = repl[i]
            out = bytearray(b'\x11' + len(raw).to_bytes(3, 'little'))
            for p in range(0, len(raw), 8):
                out.append(0); out += raw[p:p + 8]
            stored = bytes(out); size = len(raw); comp = 0x80000000
        while (n * 8 + len(body)) % 4:
            body += b'\x00'
        struct.pack_into('<II', table, i * 8, n * 8 + len(body), size | comp)
        body += stored
    return bytes(table) + bytes(body)


def rom_file(rom, path):
    """Bytes of `path` inside a ROM image (FAT lookup via inject.file_id)."""
    from inject import file_id
    fid = file_id(rom, path)
    fat = struct.unpack_from('<I', rom, 0x48)[0]
    a, b = struct.unpack_from('<II', rom, fat + fid * 8)
    return bytes(rom[a:b])


def apply_to_rom(rom, loc_en, fontfile=FONT, log=None):
    """Redraw the strips inside a ROM image; returns (rom, stats)."""
    import title_logo
    cur = rom_file(rom, 'jpn/idlocal.bin')
    repl, stats = replacements(cur, loc_en, fontfile, log)
    return title_logo.splice(rom, 'jpn/idlocal.bin', rebuild(cur, repl)), stats


def selftest(idlocal_bytes):
    """encode(grid(b)) must reproduce b byte for byte on untouched strips."""
    idl = Idlocal(idlocal_bytes)
    for i in (364, 400, 532, 534, 600, 670):
        b = idl.blob(i)
        assert encode(b, grid(b)) == b, 'round trip failed on %d' % i
    return True


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    data = open('dump/ds_fan/jpn/idlocal.bin', 'rb').read()
    print('round trip:', selftest(data))
    loc = json.load(io.open('dump/loc_en.json', encoding='utf-8'))
    stats, n = preview(data, loc, sys.argv[1] if len(sys.argv) > 1 else 'out/strip_preview')
    print(stats, n, 'sheets')
