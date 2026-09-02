# -*- coding: utf-8 -*-
"""Enumerate the evidence/profile descriptions and Logic cards whose OFFICIAL text
overflows the DS box, exactly the way loc_patch.patch_entry decides it.

    python tools/desc_overflow.py OUT.txt [OUT.json]

For each such row: bank, string, Japanese source, Capcom's English, the fan text
that ships instead, lines needed vs allowed, and pixel width of each wrapped line.
"""
import sys, os, json, io
PORT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(PORT)
import dstext, condense
from spt import all_strings
from loc_patch import (load_lookup, _ds_plain, _norm, _to_units, _fan_age_line,
                       SUFFIX_JA, SUFFIX_EN, BOXES, CTRL)

SOURCES = {432: ('dump/jpn_trial/detailMsg.bin', 'detailMsg'),
           395: ('dump/jpn/logicKW.bin', 'logicKW')}


def plain(u):
    out = []
    for v in u:
        if v in (0xFF3F, 0x3000): out.append(' ')
        elif 0xFF01 <= v <= 0xFF5E: out.append(chr(v - 0xFF01 + 0x21))
        elif v == 0x0A: out.append('\n')
        elif v == 0x2025: out.append('.')
        elif v in (0x201D, 0x2019): out.append("'")
        elif CTRL(v): pass
        elif v >= 0x20: out.append(chr(v))
    return ''.join(out)


def wrapped(eng, suffix, age, px):
    old = dstext.LINE_PX; dstext.LINE_PX = px
    try:
        conv, _ = dstext.convert(_to_units(eng), page=False, hard_nl=False)
        if suffix:
            sc, _ = dstext.convert(_to_units(suffix), page=False, hard_nl=False)
            conv = conv + [0x0A] + sc
    finally:
        dstext.LINE_PX = old
    if age:
        conv = age + [0x0A] + conv
    lines, cur = [], []
    for v in conv:
        if v == 0x0A: lines.append(cur); cur = []
        else: cur.append(v)
    lines.append(cur)
    widths = [sum(dstext._w(chr(v)) for v in l if not CTRL(v)) for l in lines]
    return lines, widths


def main(out_txt, out_json=None):
    lookup = load_lookup()
    fan_spt = open('dump/ds_fan/jpn/spt.bin', 'rb').read()
    import struct
    def fan_entry(i):
        o, s = struct.unpack_from('<II', fan_spt, i * 8); return fan_spt[o:o + s]
    rows = []
    for bank, (src, box) in SOURCES.items():
        D = list(all_strings(fan_entry(bank), True))
        J = list(all_strings(open(src, 'rb').read(), False))
        if len(D) != len(J):
            print('bank %d: string count mismatch, skipped' % bank); continue
        px, maxln = BOXES[box]
        for k, (_, _, _, u) in enumerate(D):
            t = _ds_plain(J[k][3])
            eng = suffix = None
            if t and t in lookup:
                eng = lookup[t]
            elif t.endswith(_norm(SUFFIX_JA)) and t[:-len(_norm(SUFFIX_JA))] in lookup:
                eng = lookup[t[:-len(_norm(SUFFIX_JA))]]; suffix = SUFFIX_EN
            if eng is None:
                continue
            c = condense.apply(t, eng)
            if c is not None:
                eng = c
            head = []
            for v in u:
                if CTRL(v) or v < 0x20: head.append(v)
                else: break
            age = _fan_age_line(u[len(head):])
            lines, widths = wrapped(eng, suffix, age, px)
            if len(lines) <= maxln:
                continue
            ja = ''.join(chr(v) for v in J[k][3] if not CTRL(v) and v >= 0x20)
            rows.append(dict(bank=bank, str=k, box=box, allowed=maxln, needed=len(lines), px=px,
                             widths=widths, ja=ja, official=eng.replace('\n', ' '),
                             suffix=suffix or '', age=plain(age) if age else '',
                             fan=plain(u[len(head):]).replace('\n', ' | ')))
    rows.sort(key=lambda r: (r['bank'], r['str']))
    with io.open(out_txt, 'w', encoding='utf-8', newline='\n') as f:
        f.write('OFFICIAL DESCRIPTIONS THAT OVERFLOW THE DS BOX (kept fan in the build)\n')
        f.write('=' * 78 + '\n\n')
        from collections import Counter
        by = Counter((r['bank'], r['needed']) for r in rows)
        f.write('count by bank and lines needed: %s\n\n' % dict(by))
        for r in rows:
            f.write('[bank %d str %d]  %s box: %d lines at %dpx; official needs %d%s%s\n' % (
                r['bank'], r['str'], r['box'], r['allowed'], r['px'], r['needed'],
                '  (+Age line)' if r['age'] else '', '  (+suffix line)' if r['suffix'] else ''))
            f.write('  JAPANESE : %s\n' % r['ja'])
            f.write('  CAPCOM   : %s\n' % r['official'])
            f.write('  FAN      : %s\n' % r['fan'])
            f.write('  wrapped widths: %s\n\n' % r['widths'])
    if out_json:
        json.dump(rows, io.open(out_json, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    print('overflow rows: %d  ->  %s' % (len(rows), out_txt))
    print('by (bank, lines needed):', dict(sorted(by.items())))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
