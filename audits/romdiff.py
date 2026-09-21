# -*- coding: utf-8 -*-
"""Which files differ between two built ROMs?

The release flow has always done this read-back by hand ("read back against
1.8.5, one file changes, the script") and there was no tool for it. This walks
both ROMs' filename tables and compares every file by content, so a change that
was meant to touch one file can be shown to touch exactly that one.

    python sweep/romdiff.py <old.nds> <new.nds>

Reports files that differ, that only one side has, and the count that match.
Reads only; writes nothing.
"""
import sys, struct, hashlib


def files(rom):
    """{path: (offset, end)} for every file in the ROM's filesystem."""
    fnt = struct.unpack_from('<I', rom, 0x40)[0]
    fat = struct.unpack_from('<I', rom, 0x48)[0]
    out = {}

    def walk(dirid, prefix=''):
        off = fnt + (dirid & 0xFFF) * 8
        suboff, firstid, _ = struct.unpack_from('<IHH', rom, off)
        p = fnt + suboff
        fid = firstid
        while True:
            t = rom[p]
            p += 1
            if t == 0:
                return
            ln = t & 0x7F
            name = rom[p:p + ln].decode('shift_jis', 'replace')
            p += ln
            if t & 0x80:
                sub = struct.unpack_from('<H', rom, p)[0]
                p += 2
                walk(sub, prefix + name + '/')
            else:
                a, b = struct.unpack_from('<II', rom, fat + fid * 8)
                out[prefix + name] = (a, b)
                fid += 1

    walk(0xF000)
    return out


def main(pa, pb):
    ra = open(pa, 'rb').read()
    rb = open(pb, 'rb').read()
    fa, fb = files(ra), files(rb)
    only_a = sorted(set(fa) - set(fb))
    only_b = sorted(set(fb) - set(fa))
    same = diff = 0
    changed = []
    for k in sorted(set(fa) & set(fb)):
        a0, a1 = fa[k]
        b0, b1 = fb[k]
        A, B = ra[a0:a1], rb[b0:b1]
        if A == B:
            same += 1
        else:
            diff += 1
            changed.append((k, len(A), len(B),
                            hashlib.sha256(A).hexdigest()[:12],
                            hashlib.sha256(B).hexdigest()[:12]))
    print('%s  ->  %s' % (pa, pb))
    print('files: %d both, %d identical, %d DIFFER' % (len(set(fa) & set(fb)), same, diff))
    if only_a:
        print('only in old (%d): %s' % (len(only_a), only_a[:10]))
    if only_b:
        print('only in new (%d): %s' % (len(only_b), only_b[:10]))
    for k, la, lb, ha, hb in changed:
        print('  DIFFER %-34s %8d -> %-8d  %s -> %s' % (k, la, lb, ha, hb))
    # the header and the arm9 live outside the filesystem; say if they moved
    for name, a, b in (('arm9', ra[0x4000:0x4000 + 0x10000], rb[0x4000:0x4000 + 0x10000]),
                       ('header', ra[:0x200], rb[:0x200])):
        print('  %-6s %s' % (name, 'identical' if a == b else 'DIFFERS'))


if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    main(sys.argv[1], sys.argv[2])
