# -*- coding: utf-8 -*-
"""Index-grid views of every graphic entry of the DS picture containers, read
with the repo's own readers (choice_strips.Idlocal for the table, nitro for the
tile banks and palettes, ncer for the cell banks).

A view is an integer grid of RAW palette indices (-1 where nothing is drawn),
one per picture the game can show from an entry:

  composite  an entry that starts with the 12-byte offset triple (cells,
             animation, tiles): one view per non-empty cell
  bundle     an RGCN tile bank with its RECN cell bank one or two entries
             before it (idlocal, com/mapobj, com/idcom): one view per cell
  raw        an RGCN tile bank with no cell bank (full-screen pictures such as
             jpn/upcut_local.bin 264): the tiles laid out `w` tiles wide

The detector (bigg_detect.py) and the re-lettering step (bigg_building.py) both
read pictures through here, so what is matched is what is written.
"""
import os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from nitro import ncgr, nclr, nscr, _sections
from ncer import ncer

K = {b'RLCN': 'P', b'RGCN': 'G', b'RECN': 'E', b'RNAN': 'N', b'RCSN': 'S', b'': '.'}


def kind(b):
    if b[:4] == b'\x0c\x00\x00\x00':
        return 'C'
    return K.get(b[:4], '?')


def linear_flag(rg):
    """RAHC body offset 12: 0 tiled, 1 linear raster bitmap (com/mapobj)."""
    return struct.unpack_from('<I', _sections(rg)[b'RAHC'][2], 12)[0]


def _boundary(mapping, bpp):
    return max(1, (32 << (mapping & 3)) // (64 if bpp == 8 else 32))


def cell_grid(objs, rgcn, mapping):
    """Index grid of one cell (first OBJ on top). -> (grid, (x0, y0), palette bank per pixel)."""
    data, bpp, cnt, _w, _h = ncgr(rgcn)
    lin = linear_flag(rgcn)
    boundary = _boundary(mapping, bpp)
    per = 64 if bpp == 8 else 32
    x0 = min(o['x'] for o in objs); y0 = min(o['y'] for o in objs)
    x1 = max(o['x'] + o['w'] for o in objs); y1 = max(o['y'] + o['h'] for o in objs)
    a = np.full((y1 - y0, x1 - x0), -1, np.int32)
    bank = np.zeros((y1 - y0, x1 - x0), np.int32)
    for o in reversed(objs):
        w, h = o['w'], o['h']
        if lin:
            unit = 32 << (mapping & 3)
            base = o['tile'] * unit
            n = w * h
            if bpp == 8:
                raw = np.zeros(n, np.int32)
                seg = np.frombuffer(data[base:base + n], np.uint8)
                raw[:len(seg)] = seg
            else:
                seg = np.frombuffer(data[base:base + (n + 1) // 2], np.uint8)
                raw = np.zeros(n, np.int32)
                pairs = np.stack([seg & 15, seg >> 4], axis=-1).reshape(-1)
                raw[:min(n, len(pairs))] = pairs[:n]
            blk = raw.reshape(h, w)
        else:
            tw, th = w // 8, h // 8
            blk = np.zeros((h, w), np.int32)
            for ty in range(th):
                for tx in range(tw):
                    t = o['tile'] * boundary + ty * tw + tx
                    off = t * per
                    if off + per > len(data):
                        continue
                    chunk = data[off:off + per]
                    if bpp == 8:
                        tile = np.frombuffer(chunk, np.uint8).reshape(8, 8)
                    else:
                        arr = np.frombuffer(chunk, np.uint8)
                        tile = np.empty((8, 8), np.int32)
                        tile = np.stack([arr & 15, arr >> 4], axis=-1).reshape(8, 8)
                    blk[ty * 8:ty * 8 + 8, tx * 8:tx * 8 + 8] = tile
        if o['hflip']:
            blk = blk[:, ::-1]
        if o['vflip']:
            blk = blk[::-1, :]
        sub = a[o['y'] - y0:o['y'] - y0 + h, o['x'] - x0:o['x'] - x0 + w]
        # index 0 is transparent for sprites: it does not overwrite what lies under it
        sel = (blk != 0) | (sub == -1)
        sub[sel] = blk[sel]
        bsub = bank[o['y'] - y0:o['y'] - y0 + h, o['x'] - x0:o['x'] - x0 + w]
        bsub[sel] = o['pal'] if bpp == 4 else 0
    return a, (x0, y0), bank


def raw_grid(rgcn, cols=None):
    data, bpp, cnt, tw, th = ncgr(rgcn)
    if cols is None:
        cols = tw if 0 < tw < 256 else 32
    rows = (cnt + cols - 1) // cols
    per = 64 if bpp == 8 else 32
    a = np.zeros((rows * 8, cols * 8), np.int32)
    for t in range(cnt):
        chunk = data[t * per:(t + 1) * per]
        if bpp == 8:
            tile = np.frombuffer(chunk, np.uint8).reshape(8, 8)
        else:
            arr = np.frombuffer(chunk, np.uint8)
            tile = np.stack([arr & 15, arr >> 4], axis=-1).reshape(8, 8)
        bx, by = (t % cols) * 8, (t // cols) * 8
        a[by:by + 8, bx:bx + 8] = tile
    return a


def screen_grid(nscr_blob, rgcn):
    """A background screen (RCSN map over an RGCN tile bank): the tiles placed by the map, with flips,
    as an index grid (raw values, the map's palette bank ignored)."""
    w, h, ents = nscr(nscr_blob)
    data, bpp, cnt, _tw, _th = ncgr(rgcn)
    cols = w // 8 if w else 32
    rows = len(ents) // cols
    per = 64 if bpp == 8 else 32
    a = np.zeros((rows * 8, cols * 8), np.int32)
    for k, e in enumerate(ents[:cols * rows]):
        t = e & 0x3FF
        if t >= cnt:
            continue
        chunk = data[t * per:(t + 1) * per]
        if bpp == 8:
            tile = np.frombuffer(chunk, np.uint8).reshape(8, 8).astype(np.int32)
        else:
            arr = np.frombuffer(chunk, np.uint8)
            tile = np.stack([arr & 15, arr >> 4], axis=-1).reshape(8, 8).astype(np.int32)
        if e & 0x400:
            tile = tile[:, ::-1]
        if e & 0x800:
            tile = tile[::-1, :]
        a[(k // cols) * 8:(k // cols) * 8 + 8, (k % cols) * 8:(k % cols) * 8 + 8] = tile
    return a


def entry_views(blobs, e):
    """All views of entry e of a decoded container (blobs: list of bytes).
    -> list of (label, grid, info) with label 'c<k>' (cell k) or 'raw'."""
    b = blobs[e]
    k = kind(b)
    out = []
    if k == 'C':
        o = struct.unpack_from('<3I', b, 0)
        cells, mapping = ncer(b[o[0]:])
        rg = b[o[2]:]
        if rg[:4] != b'RGCN':
            return out
        for ci, objs in enumerate(cells):
            if objs:
                g, org, bank = cell_grid(objs, rg, mapping)
                out.append(('c%d' % ci, g, dict(kind='C', org=org, bank=bank)))
    elif k == 'S':
        for j in (e - 1, e - 2, e + 1, e + 2):
            if 0 <= j < len(blobs) and kind(blobs[j]) == 'G':
                try:
                    out.append(('screen', screen_grid(blobs[e], blobs[j]), dict(kind='S', org=(0, 0), tiles_entry=j)))
                except Exception:
                    pass
                break
    elif k == 'G':
        recn = None
        for j in (e - 1, e - 2):
            if j >= 0 and kind(blobs[j]) == 'E':
                recn = j
                break
        if recn is not None:
            cells, mapping = ncer(blobs[recn])
            for ci, objs in enumerate(cells):
                if objs:
                    g, org, bank = cell_grid(objs, b, mapping)
                    out.append(('c%d' % ci, g, dict(kind='G+E', org=org, cells_entry=recn, bank=bank)))
        else:
            out.append(('raw', raw_grid(b), dict(kind='G', org=(0, 0))))
    return out


def palette_of(blobs, e, pref='before'):
    """(entry, palette) of the nearest RLCN before/after entry e."""
    def before():
        for j in range(e - 1, -1, -1):
            if kind(blobs[j]) == 'P':
                return j
    def after():
        for j in range(e + 1, len(blobs)):
            if kind(blobs[j]) == 'P':
                return j
    for f in ((before, after) if pref == 'before' else (after, before)):
        j = f()
        if j is not None:
            try:
                return j, nclr(blobs[j])
            except Exception:
                pass
    return None, [(i, i, i) for i in range(256)]


def to_rgb(grid, pal, bank=None, bg=(70, 90, 120)):
    lut = np.array([pal[i] if i < len(pal) else (255, 0, 255) for i in range(512)], np.uint8)
    out = np.empty(grid.shape + (3,), np.uint8)
    m = grid >= 0
    out[~m] = bg
    idx = grid + (bank * 16 if bank is not None else 0)
    out[m] = lut[idx[m] & 511]
    return out
