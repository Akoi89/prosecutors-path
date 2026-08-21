# -*- coding: utf-8 -*-
"""Nintendo LZ11 (0x11) decompressor - used by GK2's graphic archives."""
def decompress(d):
    assert d[0] == 0x11, hex(d[0])
    size = int.from_bytes(d[1:4], 'little')
    if size == 0:
        size = int.from_bytes(d[4:8], 'little'); p = 8
    else:
        p = 4
    out = bytearray()
    while len(out) < size and p < len(d):
        flags = d[p]; p += 1
        for bit in range(8):
            if len(out) >= size: break
            if not (flags & (0x80 >> bit)):
                out.append(d[p]); p += 1
                continue
            a = d[p]; p += 1
            kind = a >> 4
            if kind == 0:
                b = d[p]; p += 1; c = d[p]; p += 1
                cnt = ((a & 0xF) << 4 | b >> 4) + 0x11
                disp = ((b & 0xF) << 8 | c) + 1
            elif kind == 1:
                b = d[p]; p += 1; c = d[p]; p += 1; e = d[p]; p += 1
                cnt = ((a & 0xF) << 12 | b << 4 | c >> 4) + 0x111
                disp = ((c & 0xF) << 8 | e) + 1
            else:
                b = d[p]; p += 1
                cnt = kind + 1
                disp = ((a & 0xF) << 8 | b) + 1
            for _ in range(cnt):
                out.append(out[-disp])
    return bytes(out)
