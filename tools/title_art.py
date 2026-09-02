# -*- coding: utf-8 -*-
"""Export the episode-title graphics for redrawing, and list the glyphs that are missing.

The five episode names appear as artwork in two places, both stored as OAM cells
(see ncer.py):

    splash card   jpn/opening_local.bin  cell entry 2, cells 0-4     208x40, 16 colours
    select button jpn/save_local.bin     cell entry 1, cells 14-18   224x64, 64 colours

Capcom renamed every episode. Redrawing the titles needs letters the fan patch
never drew, so this writes an artist's pack: each piece as an INDEXED PNG that
keeps the game's palette (edit it without introducing new colours and it can go
straight back in), a 4x preview, the palettes, the OAM layout as JSON, and the
measured list of missing glyphs.

    python tools/title_art.py OUTDIR

Reads dump/ds_fan only. Writes no game data beyond the title strips themselves.
"""
import sys, os, json, struct
sys.path.insert(0, os.path.dirname(__file__))
from lz11 import decompress
from nitro import _sections, ncgr
from ncer import ncer
from episode_titles import OFFICIAL
from PIL import Image

BOUNDARY = 4          # mappingMode 0x2 in both cell banks

SURFACES = [
    # tag,      file,                             cell entry, tile entry, pal entry, cell ids
    ('splash',  'dump/ds_fan/jpn/opening_local.bin', 2, 0, 1, [0, 1, 2, 3, 4]),
    ('button',  'dump/ds_fan/jpn/save_local.bin',    1, 2, 3, [14, 15, 16, 17, 18]),
]
FAN_TITLES = ['Turnabout Target', 'The Imprisoned Turnabout', 'The Inherited Turnabout',
              'The Forgotten Turnabout', 'The Grand Turnabout']


def entries(path):
    d = open(path, 'rb').read()
    n = struct.unpack_from('<I', d, 0)[0] // 8
    offs = [struct.unpack_from('<II', d, i * 8)[0] for i in range(n)] + [len(d)]
    return [d[offs[i]:offs[i + 1]] for i in range(n)]


def dec(b):
    try:
        return decompress(b)
    except Exception:
        return b


def palette(blob):
    """Full palette as a list of (r,g,b). PLTT data starts at body offset 16."""
    p = _sections(dec(blob))[b'TTLP'][2]
    _bd, _pad, dsize, _cper = struct.unpack_from('<IIII', p, 0)
    raw = p[16:16 + dsize]
    out = []
    for i in range(0, len(raw) - 1, 2):
        v = struct.unpack_from('<H', raw, i)[0]
        r = (v & 31) << 3; g = ((v >> 5) & 31) << 3; b = ((v >> 10) & 31) << 3
        out.append((r | r >> 5, g | g >> 5, b | b >> 5))
    return out


def cell_indices(objs, tiles, bpp):
    """Paint a cell to a 2-D array of GLOBAL palette indices (bank*16 + colour).
    Index 0 is transparent. Returns (rows, (x0, y0))."""
    x0 = min(o['x'] for o in objs); y0 = min(o['y'] for o in objs)
    x1 = max(o['x'] + o['w'] for o in objs); y1 = max(o['y'] + o['h'] for o in objs)
    W, H = x1 - x0, y1 - y0
    img = [[0] * W for _ in range(H)]
    per = 64 if bpp == 8 else 32
    for o in reversed(objs):                       # OAM 0 is topmost
        tw, th = o['w'] // 8, o['h'] // 8
        start = o['tile'] * BOUNDARY
        for ty in range(th):
            for tx in range(tw):
                off = (start + ty * tw + tx) * per
                if off + per > len(tiles):
                    continue
                blk = tiles[off:off + per]
                for yy in range(8):
                    for xx in range(8):
                        if bpp == 4:
                            b = blk[yy * 4 + xx // 2]
                            c = (b >> 4) if (xx & 1) else (b & 0xF)
                            g = c + o['pal'] * 16
                        else:
                            c = blk[yy * 8 + xx]; g = c
                        if c == 0:
                            continue
                        sx = tx * 8 + xx; sy = ty * 8 + yy
                        if o['hflip']: sx = tw * 8 - 1 - sx
                        if o['vflip']: sy = th * 8 - 1 - sy
                        X = o['x'] - x0 + sx; Y = o['y'] - y0 + sy
                        if 0 <= X < W and 0 <= Y < H:
                            img[Y][X] = g
    return img, (x0, y0)


def to_indexed_png(rows, pal, path):
    H, W = len(rows), len(rows[0])
    im = Image.new('P', (W, H))
    flat = [v for r in rows for v in r]
    im.putdata(flat)
    p = []
    for i in range(256):
        p.extend(pal[i] if i < len(pal) else (0, 0, 0))
    im.putpalette(p)
    im.save(path, transparency=0)


def preview(rows, pal, scale=4, bg=(96, 96, 96)):
    H, W = len(rows), len(rows[0])
    im = Image.new('RGB', (W, H), bg)
    px = im.load()
    for y in range(H):
        for x in range(W):
            v = rows[y][x]
            if v:
                px[x, y] = pal[v] if v < len(pal) else (255, 0, 255)
    return im.resize((W * scale, H * scale), Image.NEAREST)


def glyph_report():
    """Which characters the official titles need that no fan title (or 'Episode N') has."""
    have = set(''.join(FAN_TITLES)) | set('Episode 12345')
    need = set(''.join(OFFICIAL[t] for t in FAN_TITLES))
    missing = sorted(c for c in (need - have) if c != ' ')
    lines = ["MISSING GLYPHS (measured: letters in the five official titles that appear in",
             "no fan title and not in 'Episode 1..5'). Case matters; the art is case-specific.", ""]
    lines.append("  " + '  '.join(missing) + "    (%d)" % len(missing))
    lines.append("")
    lines.append("Per title:")
    for fan in FAN_TITLES:
        off = OFFICIAL[fan]
        m = sorted(set(off) - have - {' '})
        lines.append("  %-26s -> %-24s needs new: %s" % (fan, off, ' '.join(m) if m else '(nothing)'))
    return missing, '\n'.join(lines)


def main(out):
    os.makedirs(out, exist_ok=True)
    layout = {}
    for tag, path, ci, gi, pi, ids in SURFACES:
        e = entries(path)
        cells, _ = ncer(dec(e[ci]))
        tiles, bpp, cnt, _, _ = ncgr(dec(e[gi]))
        pal = palette(e[pi])
        # palette swatch + text
        with open(os.path.join(out, '%s_palette.txt' % tag), 'w') as f:
            f.write("%s: %d colours, index 0 is transparent\n" % (tag, len(pal)))
            for i, (r, g, b) in enumerate(pal):
                f.write("  %3d  #%02X%02X%02X\n" % (i, r, g, b))
        sw = Image.new('RGB', (len(pal) * 12, 24))
        for i, c in enumerate(pal):
            sw.paste(c, (i * 12, 0, i * 12 + 12, 24))
        sw.save(os.path.join(out, '%s_palette.png' % tag))
        strip = []
        for n, cid in enumerate(ids, 1):
            rows, origin = cell_indices(cells[cid], tiles, bpp)
            used = sorted({v for r in rows for v in r if v})
            base = '%s_ep%d' % (tag, n)
            to_indexed_png(rows, pal, os.path.join(out, base + '.png'))
            pv = preview(rows, pal); strip.append(pv)
            pv.save(os.path.join(out, base + '_preview4x.png'))
            layout[base] = dict(file=os.path.basename(path), cell_entry=ci, cell=cid,
                                tile_entry=gi, palette_entry=pi, bpp=bpp, size=[len(rows[0]), len(rows)],
                                origin=list(origin), palette_indices_used=used,
                                fan_title=FAN_TITLES[n - 1], official_title=OFFICIAL[FAN_TITLES[n - 1]],
                                oam=cells[cid])
            print("  %-12s %3dx%-3d  indices used: %s" % (base, len(rows[0]), len(rows), used))
        W = max(i.width for i in strip); H = sum(i.height + 8 for i in strip)
        sheet = Image.new('RGB', (W, H), (40, 40, 40)); y = 0
        for i in strip:
            sheet.paste(i, (0, y)); y += i.height + 8
        sheet.save(os.path.join(out, '%s_all_preview4x.png' % tag))
    with open(os.path.join(out, 'layout.json'), 'w') as f:
        json.dump(layout, f, indent=1)
    missing, rep = glyph_report()
    with open(os.path.join(out, 'missing_glyphs.txt'), 'w') as f:
        f.write(rep + '\n')
    print(rep)
    return missing


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'out/title_art')
