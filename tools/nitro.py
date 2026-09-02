# -*- coding: utf-8 -*-
"""Minimal Nintendo NCGR / NCLR / NSCR readers (GK2 uses these inside LZ11 blobs)."""
import struct

def _sections(d):
    n = struct.unpack_from('<H', d, 14)[0]
    p, out = 16, {}
    for _ in range(n):
        magic = d[p:p+4]
        size = struct.unpack_from('<I', d, p+4)[0]
        out[magic] = (p, size, d[p+8:p+size])
        p += size
    return out

def ncgr(d):
    """-> (tiles bytes, bpp, tile_count)"""
    s = _sections(d)[b'RAHC']
    body = s[2]
    h, w, fmt = struct.unpack_from('<HHI', body, 0)
    bpp = 8 if fmt == 4 else 4
    dsize = struct.unpack_from('<I', body, 16)[0]
    doff = struct.unpack_from('<I', body, 20)[0]
    data = body[doff:doff + dsize]
    per = 64 if bpp == 8 else 32
    return data, bpp, len(data) // per, w, h

def nclr(d):
    # PLTT body: u32 bit depth, u32 padding, u32 data size, u32 colours per
    # palette, then the BGR555 data at offset 16. The old reader treated the
    # fourth field as a data offset and started 4 bytes (2 colours) late, which
    # scrambled every colour on 8bpp screens (title_local.bin). 4bpp glyph work
    # never noticed because plates.py compares shapes, not colours.
    s = _sections(d)[b'TTLP'][2]
    dsize = struct.unpack_from('<I', s, 8)[0]
    raw = s[16:16 + dsize]
    pal = []
    for i in range(0, len(raw) - 1, 2):
        v = struct.unpack_from('<H', raw, i)[0]
        r = (v & 31) << 3; g = ((v >> 5) & 31) << 3; b = ((v >> 10) & 31) << 3
        pal.append((r | r >> 5, g | g >> 5, b | b >> 5))
    return pal

def nscr(d):
    s = _sections(d)[b'NRCS'][2]
    w, h = struct.unpack_from('<HH', s, 0)
    doff = struct.unpack_from('<I', s, 8)[0]
    raw = s[12:12+doff] if doff else s[12:]
    ents = [struct.unpack_from('<H', raw, i)[0] for i in range(0, len(raw) - 1, 2)]
    return w, h, ents

def tile_pixels(data, idx, bpp):
    if bpp == 4:
        t = data[idx*32:(idx+1)*32]
        return [[(t[y*4+x//2] >> (4 if x & 1 else 0)) & 0xF for x in range(8)] for y in range(8)]
    t = data[idx*64:(idx+1)*64]
    return [[t[y*8+x] for x in range(8)] for y in range(8)]
