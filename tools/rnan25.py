# -*- coding: utf-8 -*-
"""RNAN (NANR, Nitro cell animation) parser/serialiser for idlocal.bin entry 25
(the Mind Chess banner sprite bundle).

This is a TRIMMED copy of a fuller analysis tool (which also loaded ROMs by
path, printed per-sequence tables and round-tripped several reference files
to prove this layout against them); only what mindchess_recn.py needs at
build time - parse(), _pack_elem() and serialise() - ships here. No paths,
no other-file imports: this module only ever sees bytes its caller hands it.

Layout as stored (little endian):
  RNAN header      16 bytes: magic 'RNAN', BOM feff, ver 0100, u32 file size,
                             u16 header size (16), u16 section count (3)
  'KNBA' (ABNK)    u32 size; u16 nSeq; u16 nFrames; u32 seqOff; u32 frameOff;
                   u32 elemOff (all relative to the KNBA body start, i.e. the
                   byte after the 8-byte section header); 8 bytes zero pad.
    sequence       16 bytes each: u16 nFrames, u16 loopStart, u16 animType,
                   u16 elemType, u32 playMode, u32 frameOffset (into frame pool)
    frame          8 bytes each: u32 elemOffset (into element pool), u16
                   duration (in 60 fps ticks), u16 pad (0xBEEF in these files)
    element        elemType 1 (SRT): u16 cell, u16 rotation, s32 scaleX,
                   s32 scaleY, s16 px, s16 py   (16 bytes; scale is 20.12
                   fixed point, 0x1000 = 1.0, 0x0C00 = 0.75)
                   elemType 2 (T):   u16 cell, u16 pad, s16 px, s16 py (8 bytes)
                   elemType 0 (index): u16 cell (2 bytes)
  'LBAL' (LABL)    u32 size; u32 name offsets (one per sequence); NUL names
  'TXEU' (UEXT)    u32 size; u32 value

serialise()'s default (canonical=False) KEEPS the stored element pool byte
layout (orphaned records and stored offsets intact; referenced records are
re-packed in place at their existing offset) rather than rebuilding it -
this is what round trips the fan's own RNAN exactly, because the fan file's
pool is NOT canonical (it has orphaned records left over from editing, not
present in the JP or SET source files). An exact round trip in this mode
proves the parser reproduces the stored bytes faithfully; it does not by
itself mean the pool layout is canonical or minimal. canonical=True instead
rebuilds the pool in global first-use order, deduplicating by stored offset -
this is the layout the JP and SET files already use (so they round trip
either way); it is not the mode this module's own edits use, since an edit
must preserve the fan's non-canonical pool rather than replace it.

    import rnan25; rnan25.parse(rnan_bytes) / rnan25.serialise(d)
"""
import struct

ELEM_SIZE = {0: 2, 1: 16, 2: 8}


def _sections(d):
    n = struct.unpack_from('<H', d, 14)[0]
    p, out = 16, []
    for _ in range(n):
        magic = d[p:p + 4]
        size = struct.unpack_from('<I', d, p + 4)[0]
        out.append((magic, p, size))
        p += size
    return out


def parse(d):
    if d[:4] != b'RNAN':
        raise ValueError('rnan25.parse: not an RNAN container (got %r)' % (d[:4],))
    secs = dict((m, (p, s)) for m, p, s in _sections(d))
    p, s = secs[b'KNBA']
    body = d[p + 8:p + s]
    n_seq, n_frames, seq_off, frame_off, elem_off = struct.unpack_from('<HHIII', body, 0)
    pad = body[16:24]
    seqs = []
    for i in range(n_seq):
        nf, loop, atype, etype, mode, foff = struct.unpack_from('<HHHHII', body, seq_off + i * 16)
        frames = []
        for k in range(nf):
            eoff, dur, fpad = struct.unpack_from('<IHH', body, frame_off + foff + k * 8)
            q = elem_off + eoff
            if etype == 1:
                cell, rot, sx, sy, px, py = struct.unpack_from('<HHiihh', body, q)
                el = dict(cell=cell, rot=rot, sx=sx, sy=sy, px=px, py=py)
            elif etype == 2:
                cell, epad, px, py = struct.unpack_from('<HHhh', body, q)
                el = dict(cell=cell, pad=epad, px=px, py=py)
            else:
                cell, = struct.unpack_from('<H', body, q)
                el = dict(cell=cell)
            frames.append(dict(elem_off=eoff, dur=dur, pad=fpad, el=el))
        seqs.append(dict(nframes=nf, loop=loop, atype=atype, etype=etype, mode=mode,
                         frame_off=foff, frames=frames))
    # labels
    labels = []
    if b'LBAL' in secs:
        p, s = secs[b'LBAL']
        lb = d[p + 8:p + s]
        offs = [struct.unpack_from('<I', lb, i * 4)[0] for i in range(n_seq)]
        base = n_seq * 4
        for o in offs:
            e = lb.index(b'\0', base + o)
            labels.append(lb[base + o:e].decode('ascii'))
        label_raw = lb
    else:
        label_raw = None
    uext = d[secs[b'TXEU'][0] + 8:secs[b'TXEU'][0] + secs[b'TXEU'][1]] if b'TXEU' in secs else None
    return dict(n_frames=n_frames, seq_off=seq_off, frame_off=frame_off, elem_off=elem_off,
                pad=pad, seqs=seqs, labels=labels, label_raw=label_raw, uext=uext,
                abnk_len=len(body), version=d[4:8], pool_raw=body[elem_off:])


def _pack_elem(etype, el):
    if etype == 1:
        return struct.pack('<HHiihh', el['cell'], el['rot'], el['sx'], el['sy'], el['px'], el['py'])
    if etype == 2:
        return struct.pack('<HHhh', el['cell'], el['pad'], el['px'], el['py'])
    return struct.pack('<H', el['cell'])


def serialise(d, canonical=False):
    """canonical=False keeps the stored element pool (orphaned records and
    stored offsets intact, referenced records re-packed in place), which is
    what byte round trips the fan file. canonical=True rebuilds the pool in
    global first-use order with sharing by stored offset - the layout the
    fan file's pool is NOT already in (see this module's docstring)."""
    seqs = d['seqs']
    n_seq = len(seqs)
    seq_off = 24
    frame_off = seq_off + n_seq * 16
    # frame pool: in sequence order, offsets recomputed
    frame_pool = bytearray()
    keep = (not canonical) and d.get('pool_raw') is not None
    elem_pool = bytearray(d['pool_raw']) if keep else bytearray()
    elem_map = {}   # stored elem_off -> new offset (dedupe shared elements)
    seq_recs = []
    for sq in seqs:
        foff = len(frame_pool)
        for fr in sq['frames']:
            key = fr['elem_off']
            if keep:
                rec = _pack_elem(sq['etype'], fr['el'])
                elem_pool[key:key + len(rec)] = rec
                elem_map[key] = key
            elif key not in elem_map:
                elem_map[key] = len(elem_pool)
                elem_pool += _pack_elem(sq['etype'], fr['el'])
            frame_pool += struct.pack('<IHH', elem_map[key], fr['dur'], fr['pad'])
        seq_recs.append(struct.pack('<HHHHII', sq['nframes'], sq['loop'], sq['atype'],
                                    sq['etype'], sq['mode'], foff))
    elem_off = frame_off + len(frame_pool)
    n_frames = sum(sq['nframes'] for sq in seqs)
    body = struct.pack('<HHIII', n_seq, n_frames, seq_off, frame_off, elem_off) + d['pad']
    body += b''.join(seq_recs) + bytes(frame_pool) + bytes(elem_pool)
    while len(body) % 4:
        body += b'\0'
    out = b'KNBA' + struct.pack('<I', len(body) + 8) + body
    nsec = 1
    if d['label_raw'] is not None:
        out += b'LBAL' + struct.pack('<I', len(d['label_raw']) + 8) + d['label_raw']
        nsec += 1
    if d['uext'] is not None:
        out += b'TXEU' + struct.pack('<I', len(d['uext']) + 8) + d['uext']
        nsec += 1
    hdr = b'RNAN' + b'\xff\xfe' + d['version'][2:4] + struct.pack('<IHH', len(out) + 16, 16, nsec)
    return hdr + out
