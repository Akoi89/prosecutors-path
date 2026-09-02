# -*- coding: utf-8 -*-
"""Measure how much of the built ROM's text is official.

    python tools/coverage.py                     compare the default output ROM
    python tools/coverage.py path/to/rom.nds     compare any built ROM

The metric: for every string of every entry in the fan script archive, count the
character units - everything that is not a control code (0xE000-0xF8FF) or one of
its argument units (arities from dump/ctrl_args.json). A string counts as OFFICIAL
when its bytes in the built ROM differ from the fan ROM's - the injector only ever
replaces whole strings, so a byte difference means official content. The numerator
is the character units of those strings; the denominator is everyone's.

This counting exists so the README's coverage claim is something a user can
recompute. It is not comparable to the pre-v1.2.0 "85.7%" figure, whose script
never survived.
"""
import sys, os, json, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from spt import all_strings
from paths import work, data
from dstext import ARGS

CTRL = lambda v: 0xE000 <= v <= 0xF8FF


def charunits(u):
    n = 0
    i, ln = 0, len(u)
    while i < ln:
        v = u[i]
        if CTRL(v):
            i += 1 + ARGS.get(v, 0)
            continue
        n += 1
        i += 1
    return n


def entries(path):
    raw = open(path, 'rb').read()
    ntbl = struct.unpack_from('<I', raw, 0)[0] // 8
    out = {}
    for i in range(ntbl):
        o, s = struct.unpack_from('<II', raw, i * 8)
        if s:
            out[i] = raw[o:o+s]
    return out


def main(argv=None):
    os.chdir(work())
    rom = (argv or sys.argv[1:] or [os.path.join('out', 'GK2 (Official English, DS port).nds')])[0]
    import ndsx
    tmp = os.path.join(os.environ.get('TEMP', '.'), '_coverage_extract')
    import shutil
    if os.path.isdir(tmp):
        shutil.rmtree(tmp)
    ndsx.extract(rom, tmp)
    built = entries(os.path.join(tmp, 'jpn', 'spt.bin'))
    fan = entries('dump/ds_fan/jpn/spt.bin')
    m = json.load(open(data('ds_to_collection_final.json')))

    def bucket(i):
        info = m.get(str(i))
        name = info['name'] if info else ''
        if name.startswith('sce') and len(name) > 3 and name[3].isdigit():
            return 'Episode %d' % (int(name[3]) + 1)
        return 'Menus & UI'

    # A fan row that only had character names (or, in bank 460, episode names)
    # swapped in is still the fan's writing: count it as FAN, not official.
    # Otherwise the rename pass would inflate this figure for free.
    import names as _names, episode_titles as _titles
    tab = {}
    for i, fent in fan.items():
        b = built.get(i)
        if b is None or fent[:4] != b' TPS':
            continue          # a few entries are not script containers
        fs = list(all_strings(fent, True))
        bs = list(all_strings(b, True))
        if len(fs) != len(bs):
            continue          # never happens: the injector preserves string counts
        try:
            hf = _names.harmonize_entry(fent, fent, i)[0]
            hf = _titles.retitle(hf)[0] if i == 460 else hf
            hs = [tuple(u) for _, _, _, u in all_strings(hf, True)]
        except Exception:
            hs = [tuple(u) for _, _, _, u in fs]
        if len(hs) != len(fs):
            hs = [tuple(u) for _, _, _, u in fs]
        for (fa, fb, fc, fu), (_, _, _, bu), hu in zip(fs, bs, hs):
            n = charunits(fu)
            if not n:
                continue
            k = bucket(i)
            off, tot = tab.get(k, (0, 0))
            is_fan = list(fu) == list(bu) or tuple(bu) == hu
            tab[k] = (off + (0 if is_fan else n), tot + n)

    print('%-12s %9s %12s' % ('', 'official', 'char units'))
    to = tt = 0
    for k in sorted(tab, key=lambda x: (x == 'Menus & UI', x)):
        off, tot = tab[k]
        to += off; tt += tot
        print('%-12s %8.1f%%  %s / %s' % (k, 100.0 * off / tot, format(off, ','), format(tot, ',')))
    print('%-12s %8.1f%%  %s / %s' % ('TOTAL', 100.0 * to / tt, format(to, ','), format(tt, ',')))
    shutil.rmtree(tmp)
    return 0


if __name__ == '__main__':
    sys.exit(main())
