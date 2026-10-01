# -*- coding: utf-8 -*-
"""Render Capcom's Logic keyword names into the DS keyword card images.

jpn/logic_keyword_local.bin holds 266 cards in two styles, one pair per keyword:
  style A  entries   1..133  (k = e - 1)    80x40, blue card, white text, up to 3 lines
  style B  entries 135..267  (k = e - 135) 160x16 (11 are 192x16), white 1-line banner
Palettes are shared at file level (entry 0 for A, entry 134 for B). Each card is
a sub-container (u32 offset table) holding RECN + RNAN + RGCN; only the RGCN
tile data is rewritten here, the cells stay as they are.

Banners 242, 244 and 246 have six 32x16 OBJs (192 px) but the fan's RGCN declares only 1280 of
the 1536 tile bytes, with the rest of its phrase stored after the declared data; the game shows
those bytes. The whole OBJ extent is therefore drawn and written back (tile_area, build), and
each rewritten card is read back and compared with the canvas drawn, so no fan byte survives.

The fan patch drew its own English into these; the official names come from
tools/logic_names.py (Collection string tables). Where a DS keyword has no
official name (the 30 dummy slots) the fan card is left alone.

Since 1.8.5 the names are drawn in the fan's OWN pixel faces, on the fan's own text-free
card, with the fan's spacing and layout - all harvested from the user's ROM by
tools/logic_font.py, which says how each part was proven. Before that they were the
Collection's vector font thresholded to one bit, which a tester rightly called odd.

    python tools/logic_cards.py OUTDIR [--rom in.nds out.nds]
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(__file__))
from lz11 import decompress
from nitro import ncgr, nclr
from ncer import ncer
from title_art import cell_indices, BOUNDARY
from title_text import repack, write_sprites
from PIL import Image

SRC = 'dump/ds_fan/jpn/logic_keyword_local.bin'
A_RANGE = range(1, 134)
B_RANGE = range(135, 268)
SUB_MAGIC = bytes([0x0c, 0, 0, 0])
BLUES = {3, 4, 5, 6, 7, 8}     # the card interior is a diagonal gradient of these
A_INK = 9                      # white text on style A
B_INK = 1                      # white on transparent (style B)

# Banners are one line only. Two official names are wider than any banner even with the
# spaces narrowed (173 and 179 px against 158), so the banner carries a shorter form while
# the card keeps Capcom's full name on three lines. Widths measured in the fan's banner
# face; the wording is a review call, recorded in RELEASE_NOTES.
BANNER_SHORT = {
    'Sound of something breaking': 'Something breaking',            # 115 px
    'Festival at Sunshine Coliseum': 'Festival at the Coliseum',    # 144 px
}


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


class LogicCardError(ValueError):
    """A rewritten keyword card would display bytes the tool did not write."""


def obj_extent(objs, bpp):
    """Bytes of tile data the cell's OBJs address (the same mapping cell_indices reads)."""
    per = 64 if bpp == 8 else 32
    return max((o['tile'] * BOUNDARY + (o['w'] // 8) * (o['h'] // 8)) * per for o in objs)


def tile_area(gfx, tiles, objs, bpp):
    """The tile bytes the display can reach. Normally the RGCN's declared data. The fan
    patch's banners 242, 244 and 246 have six 32x16 OBJs (1536 bytes) but declare 1280, and
    store the other 256 bytes after the declared data, holding the tail of its longer phrases;
    the game draws them as the sixth OBJ. When the cell reaches past the declared data and
    the part physically holds those bytes, the OBJ extent is the tile area. If the part does
    not hold them the declared data is returned and the caller's check raises."""
    need = obj_extent(objs, bpp)
    if need <= len(tiles):
        return tiles
    start = 0x18 + struct.unpack_from('<I', gfx, 0x18 + 20)[0]
    if start + need > len(gfx):
        return tiles
    return bytearray(gfx[start:start + need])


def card_from_sub(sub, extend=False):
    parts = sub_split(sub)
    gi = next(i for i, p in enumerate(parts) if p[:4] == b'RGCN')
    rec = next(p for p in parts if p[:4] == b'RECN')
    cells, _ = ncer(rec)
    objs = next(c for c in cells if c)
    tiles, bpp, cnt, _, _ = ncgr(parts[gi])
    tiles = bytearray(tiles)
    if extend:
        tiles = tile_area(parts[gi], tiles, objs, bpp)
    rows, origin = cell_indices(objs, tiles, bpp)
    return parts, gi, objs, tiles, bpp, rows, origin


def card_rows(E, e, extend=False):
    """extend=False reads only the declared tile data (the harvest of the fan's faces is
    keyed to exactly that); extend=True reads the full OBJ extent, as the game displays it."""
    return card_from_sub(E[e], extend)


def build(outdir, names):
    from logic_font import LogicFont
    data = open(SRC, 'rb').read()
    E = table(data)
    pals = {0: nclr(E[0]), 134: nclr(E[134])}
    font = LogicFont(E, lambda e: card_rows(E, e)[5])
    repl, log, prev_a, prev_b = {}, [], [], []
    log.append('fan faces harvested from %d card lines and %d banner lines'
               % (font.usedA, font.usedB))
    for k, v in sorted(names.items()):
        name = v['en']
        for e, style in ((k + 1, 'A'), (k + 135, 'B')):
            if not E[e] or E[e][:4] != SUB_MAGIC:
                continue
            parts, gi, objs, tiles, bpp, rows, origin = card_rows(E, e, True)
            if style == 'A':
                res = font.draw_card(rows, name)
            else:
                res = font.draw_banner(rows, BANNER_SHORT.get(name, name))
            if res is None:
                log.append('%s %-30s DOES NOT FIT (fan card kept)' % (style, name))
                continue
            log.append(res)
            write_sprites(tiles, objs, rows, origin, bpp)
            gfx = bytearray(parts[gi])
            doff = struct.unpack_from('<I', gfx, 0x18 + 20)[0]
            dsize = struct.unpack_from('<I', gfx, 0x18 + 16)[0]
            # write the whole area the OBJs reach (dsize, or the OBJ extent when larger), so
            # no fan byte is left where the display can see it; header fields stay the fan's
            need = obj_extent(objs, bpp)
            n = max(dsize, need)
            if len(tiles) < n or 0x18 + doff + n > len(gfx):
                raise LogicCardError('card %d: its OBJs reach byte %d but the RGCN part holds %d '
                                     'tile bytes (%d declared)' % (e, need, len(gfx) - 0x18 - doff, dsize))
            gfx[0x18 + doff:0x18 + doff + n] = tiles[:n]
            newparts = list(parts); newparts[gi] = bytes(gfx)
            repl[e] = sub_join(newparts)
            # read the new bytes back as the display would (full OBJ extent) and require
            # exactly the canvas just drawn: nothing the tool did not write may show
            back = card_from_sub(repl[e], True)[5]
            if back != rows:
                bad = sum(1 for ra, rb in zip(back, rows) for a, b in zip(ra, rb) if a != b)
                raise LogicCardError('card %d: %d pixels read back from the rewritten card differ '
                                     'from the canvas drawn' % (e, bad))
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
    for name, prev, cw, ch, cols in (('logic_cards_preview3x.png', prev_a, 84, 44, 5),
                                     ('logic_banners_preview3x.png', prev_b, 196, 20, 2)):
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
