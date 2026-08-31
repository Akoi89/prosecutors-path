# -*- coding: utf-8 -*-
"""Minimal NCER (cell bank) reader + renderer, for the GK2 episode-title sprites.

The title art in jpn/opening_local.bin and jpn/save_local.bin is stored as OAM
cells rather than a screen, so the tile bank alone cannot be laid out correctly.
Each cell is a list of hardware sprites (OAM entries): position, size, tile id,
palette bank and flip flags.
"""
import struct

# OAM shape/size -> (width, height) in pixels
DIMS = {
    (0, 0): (8, 8),   (0, 1): (16, 16), (0, 2): (32, 32), (0, 3): (64, 64),
    (1, 0): (16, 8),  (1, 1): (32, 8),  (1, 2): (32, 16), (1, 3): (64, 32),
    (2, 0): (8, 16),  (2, 1): (8, 32),  (2, 2): (16, 32), (2, 3): (32, 64),
}


def _sections(d):
    n = struct.unpack_from('<H', d, 14)[0]
    p, out = 16, {}
    for _ in range(n):
        magic = d[p:p + 4]
        size = struct.unpack_from('<I', d, p + 4)[0]
        out[magic] = d[p + 8:p + size]
        p += size
    return out


def ncer(d):
    """-> (cells, mapping_mode). Each cell is a list of OAM dicts."""
    s = _sections(d)[b'KBEC']
    n_cells, attr = struct.unpack_from('<HH', s, 0)
    cell_off, mapping = struct.unpack_from('<II', s, 4)
    rec = 16 if (attr & 1) else 8
    # cell_off is relative to the start of the section body, and the OAM block
    # follows the cell array directly.
    base = cell_off
    cells = []
    oam_base = base + n_cells * rec
    for i in range(n_cells):
        p = base + i * rec
        n_oam = struct.unpack_from('<H', s, p)[0]
        oam_off = struct.unpack_from('<I', s, p + 4)[0]
        objs = []
        for j in range(n_oam):
            q = oam_base + oam_off + j * 6
            if q + 6 > len(s):
                break
            a0, a1, a2 = struct.unpack_from('<HHH', s, q)
            y = a0 & 0xFF
            shape = (a0 >> 14) & 3
            is256 = bool(a0 & 0x2000)
            x = a1 & 0x1FF
            hf, vf = bool(a1 & 0x1000), bool(a1 & 0x2000)
            size = (a1 >> 14) & 3
            tid = a2 & 0x3FF
            pal = (a2 >> 12) & 0xF
            w, h = DIMS.get((shape, size), (8, 8))
            if y >= 128:
                y -= 256
            if x >= 256:
                x -= 512
            objs.append(dict(x=x, y=y, w=w, h=h, tile=tid, pal=pal,
                             hflip=hf, vflip=vf, is256=is256))
        cells.append(objs)
    return cells, mapping


def render_cell(objs, tiles, bpp, pal, boundary=1, bg=(0, 0, 0, 0)):
    """Assemble one cell into an RGBA PIL image. Returns (image, (ox, oy))."""
    from PIL import Image
    if not objs:
        return Image.new('RGBA', (1, 1), bg), (0, 0)
    x0 = min(o['x'] for o in objs)
    y0 = min(o['y'] for o in objs)
    x1 = max(o['x'] + o['w'] for o in objs)
    y1 = max(o['y'] + o['h'] for o in objs)
    img = Image.new('RGBA', (x1 - x0, y1 - y0), bg)
    px = img.load()
    per = 64 if bpp == 8 else 32
    # OAM index 0 is the highest priority sprite, so paint back-to-front.
    for o in reversed(objs):
        tw, th = o['w'] // 8, o['h'] // 8
        start = o['tile'] * boundary
        for ty in range(th):
            for tx in range(tw):
                # 1D mapping: tiles run left-to-right, top-to-bottom within the sprite
                t_index = start + ty * tw + tx
                off = t_index * per
                if off + per > len(tiles):
                    continue
                blk = tiles[off:off + per]
                for yy in range(8):
                    for xx in range(8):
                        if bpp == 4:
                            b = blk[yy * 4 + xx // 2]
                            c = (b >> 4) if (xx & 1) else (b & 0xF)
                            idx = c + o['pal'] * 16
                        else:
                            c = blk[yy * 8 + xx]
                            idx = c
                        if c == 0:
                            continue          # index 0 is transparent for sprites
                        sx = tx * 8 + (7 - xx if o['hflip'] else xx)
                        sy = ty * 8 + (7 - yy if o['vflip'] else yy)
                        if o['hflip']:
                            sx = (tw * 8 - 1) - (tx * 8 + xx)
                        if o['vflip']:
                            sy = (th * 8 - 1) - (ty * 8 + yy)
                        X = o['x'] - x0 + sx
                        Y = o['y'] - y0 + sy
                        if 0 <= X < img.width and 0 <= Y < img.height:
                            px[X, Y] = pal[idx] + (255,) if idx < len(pal) else (255, 0, 255, 255)
    return img, (x0, y0)
