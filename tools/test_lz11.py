# -*- coding: utf-8 -*-
"""Round-trip test for lz11.compress. Run from the port folder:
    python tools/test_lz11.py

Every input is decoded by lz11.decompress AND by a second, independently
written decoder (below, a byte-cursor generator; it also reports the smallest
displacement the stream uses and the match classes). Corpus: edge sizes, runs,
overlapping matches, random and text-like data, and every LZ11 entry of the
fan's jpn/idlocal.bin (decoded, recompressed, decoded again). Raises on any
mismatch; prints the numbers.
"""
import os
import random
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lz11


def decode2(s):
    """Independent LZ11 decoder. -> (bytes, minimum displacement or None,
    {class: matches}, bytes of the stream consumed)."""
    if s[0] != 0x11:
        raise ValueError('tag')
    size = s[1] | s[2] << 8 | s[3] << 16
    cur = 4
    if size == 0 and len(s) >= 8:
        size = struct.unpack_from('<I', s, 4)[0]
        cur = 8
    out = bytearray()
    mind = None
    classes = {1: 0, 2: 0, 3: 0}
    while len(out) < size:
        flag = s[cur]
        cur += 1
        for mask in (0x80, 0x40, 0x20, 0x10, 8, 4, 2, 1):
            if len(out) >= size:
                break
            if not flag & mask:
                out.append(s[cur])
                cur += 1
                continue
            hi = s[cur] >> 4
            if hi > 1:
                length = hi + 1
                disp = ((s[cur] & 15) << 8 | s[cur + 1]) + 1
                cur += 2
                classes[1] += 1
            elif hi == 0:
                length = (s[cur] << 4 | s[cur + 1] >> 4) + 0x11
                disp = ((s[cur + 1] & 15) << 8 | s[cur + 2]) + 1
                cur += 3
                classes[2] += 1
            else:
                length = ((s[cur] & 15) << 12 | s[cur + 1] << 4 | s[cur + 2] >> 4) + 0x111
                disp = ((s[cur + 2] & 15) << 8 | s[cur + 3]) + 1
                cur += 4
                classes[3] += 1
            if disp > len(out):
                raise ValueError('displacement %d before the start of the output' % disp)
            mind = disp if mind is None else min(mind, disp)
            start = len(out) - disp
            for k in range(length):
                out.append(out[start + k])
    if len(out) != size:
        raise ValueError('decoded %d bytes, header says %d' % (len(out), size))
    return bytes(out), mind, classes, cur


def roundtrip(data, tag):
    c = lz11.compress(data)
    if c != lz11.compress(data):
        raise ValueError('%s: compress is not deterministic' % tag)
    a = lz11.decompress(c)
    b, mind, classes, used = decode2(c)
    if a != data:
        raise ValueError('%s: lz11.decompress does not return the input' % tag)
    if b != data:
        raise ValueError('%s: the independent decoder does not return the input' % tag)
    if mind is not None and mind < 2:
        raise ValueError('%s: displacement %d used' % (tag, mind))
    if used > len(c):
        raise ValueError('%s: decoder read past the stream' % tag)
    return len(c), used, classes


def main(fan_idlocal='dump/ds_fan/jpn/idlocal.bin'):
    rnd = random.Random(20260928)
    corpus = [('empty', b''), ('1', b'a'), ('2', b'ab'), ('3', b'abc'), ('abab', b'ab' * 40),
              ('zeros 100000', bytes(100000)), ('zeros 70000+', bytes(0x10110 + 300)),
              ('zeros 0x111', bytes(0x111)), ('zeros 0x110', bytes(0x110)), ('zeros 0x10', bytes(0x10)),
              ('zeros 0x11', bytes(0x11)), ('abc*3000', b'abc' * 3000),
              ('random 5000', bytes(rnd.getrandbits(8) for _ in range(5000))),
              ('two symbols 20000', bytes(rnd.choice(b'ab') for _ in range(20000))),
              ('window edge', bytes(rnd.getrandbits(8) for _ in range(0x1000)) * 3),
              ('past window', bytes(rnd.getrandbits(8) for _ in range(0x1001)) * 2)]
    text = (b'The quick brown fox jumps over the lazy dog. ' * 40 + bytes(rnd.getrandbits(8) for _ in range(300))) * 5
    corpus.append(('text', text))
    for _ in range(40):
        n = rnd.randrange(0, 3000)
        base = bytes(rnd.getrandbits(3) for _ in range(rnd.randrange(1, 60)))
        corpus.append(('mix%d' % n, (base * (n // len(base) + 1))[:n] + bytes(rnd.getrandbits(8) for _ in range(rnd.randrange(0, 50)))))
    for tag, data in corpus:
        roundtrip(data, tag)
    try:
        lz11.compress(bytes(1 << 24))
    except ValueError as e:
        print('16 MB input raises: %s' % e)
    else:
        raise ValueError('compress accepted a 16 MB input')
    print('synthetic corpus: %d inputs round-trip through both decoders, minimum displacement >= 2' % len(corpus))
    if not os.path.exists(fan_idlocal):
        print('fan idlocal not found at %s, skipping the real-data half' % fan_idlocal)
        return 0
    d = open(fan_idlocal, 'rb').read()
    n = struct.unpack_from('<I', d, 0)[0] // 8
    ents = [struct.unpack_from('<II', d, i * 8) for i in range(n)]
    done = 0
    raw_total = fan_used = mine = 0
    cls = {1: 0, 2: 0, 3: 0}
    for i, (o, s) in enumerate(ents):
        if not s & 0x80000000 or not s & 0x7FFFFFFF:
            continue
        nxt = min([e[0] for e in ents if e[0] > o] + [len(d)])
        stream = d[o:nxt]
        fan_dec, _m, _c, used = decode2(stream)
        if fan_dec != lz11.decompress(stream):
            raise ValueError('idlocal entry %d: the two decoders disagree on the fan stream' % i)
        c, _u, k = roundtrip(fan_dec, 'idlocal %d' % i)
        raw_total += len(fan_dec)
        fan_used += used
        mine += c
        for q in cls:
            cls[q] += k[q]
        done += 1
    print('fan idlocal: %d LZ11 entries recompressed and round-tripped; decoded %d bytes; fan streams %d bytes, '
          'lz11.compress %d bytes (%.1f%%); match classes %s' % (done, raw_total, fan_used, mine, 100.0 * mine / fan_used, cls))
    return 0


if __name__ == '__main__':
    sys.exit(main(*sys.argv[1:2]))
