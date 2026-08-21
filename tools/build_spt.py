# -*- coding: utf-8 -*-
"""Write a DS-variant ( TPS) SPT file.

The file holds n+1 strings: string 0 is described by the header (offset 0x0C,
length 0x0E), strings 1..n by the 8-byte record table. header[0x08] is the
longest length across ALL of them (verified on all 443 DS entries).
"""
import struct
KEY = 0x55AA

def _enc(u):
    return b''.join(struct.pack('<H', (v ^ KEY) & 0xFFFF) for v in list(u) + [0])

def build_ds(s0, records, trailer=0xFFFFFFFF, scale=1, min_longest=0):
    """s0: units of string 0.  records: list of (A, units).
    trailer: the 4-byte field between the record table and the data; it is NOT
    always 0xFFFFFFFF (102 of 443 DS entries carry another value), so it must be
    carried over from the source entry rather than synthesised."""
    n = len(records)
    dstart = 16 + n * 8 + 4
    blobs = [_enc(s0)] + [_enc(u) for a, u in records]
    offs, pos = [], dstart
    for b in blobs:
        offs.append(pos); pos += len(b)
    if pos // scale > 0xFFFF:
        raise OverflowError('SPT exceeds u16 offset limit: %d bytes (scale %d)' % (pos, scale))
    # header[0x08] is a buffer-size hint; never let it be smaller than reality
    longest = max([len(s0), min_longest] + [len(u) for a, u in records])
    out = bytearray()
    out += b' TPS'
    out += struct.pack('<HHHHHH', 0x0100, n + 1, longest, 0x55AA, dstart // scale, len(s0))
    for (a, u), o in zip(records, offs[1:]):
        out += struct.pack('<IHH', a, o // scale, len(u))
    out += struct.pack('<I', trailer)
    for b in blobs:
        out += b
    return bytes(out)

def build_archive(entries):
    n = max(entries) + 1
    tbl = bytearray(n * 8)
    body = bytearray()
    base = n * 8
    for i in range(n):
        d = entries.get(i)
        if d is None:
            struct.pack_into('<II', tbl, i * 8, base + len(body), 0)
            continue
        # the original archives are packed tight - no alignment, no gaps
        struct.pack_into('<II', tbl, i * 8, base + len(body), len(d))
        body += d
    return bytes(tbl) + bytes(body)
