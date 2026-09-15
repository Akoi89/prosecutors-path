# Does every string keep what the fan ROM stores AFTER its declared length?
#
# Found by a player on 1.8.2 (Reddit, 2026-09-15): in Episode 3, talking to Ms. Bound
# at the Zodiac Art Gallery fountain opened Larry's scene instead. DS[178] string 23 is
# nothing but {E12E} 3,0x857,1 with a declared length of 4 units; the command's fourth
# argument, 0x18 (string 24, her talk), sits in the slot where a terminator normally
# goes. The injector rebuilt the entry with a plain 0 there, so the jump went to
# string 0. Every other audit gave byte-identical output on the broken and fixed ROMs:
# they all read strings up to their declared length and never look past it.
#
# Compares each built string's terminator slot against the fan ROM's wherever the
# string's content is unchanged from the fan's. A slot the fan fills and we zero is
# LOST; that is the defect.
import os as _os
import sys as _sys

_REPO = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
_sys.path.insert(0, _os.path.join(_REPO, 'tools'))


def _default_built():
    p = _os.path.join(_REPO, 'out', 'GK2 (Official English, DS port).nds')
    if _os.path.exists(p):
        return p
    cand = [f for f in _os.listdir(_os.path.join(_REPO, 'out'))
            if f.lower().endswith('.nds')] if _os.path.isdir(_os.path.join(_REPO, 'out')) else []
    if len(cand) == 1:
        return _os.path.join(_REPO, 'out', cand[0])
    raise SystemExit('no built ROM in %s - run a build first, or pass one as the '
                     'first argument' % _os.path.join(_REPO, 'out'))


def _default_fan():
    import locate
    rom, _ = locate.find_fan_rom([_REPO, _os.path.dirname(_REPO), _os.getcwd()])
    if not rom:
        raise SystemExit('could not find your AAI2 Final v2 ROM - pass it as the '
                         'second argument')
    return rom

import sys, struct

import spt
from inject import file_id

# SCOPE - what this does NOT look at:
#   * Only strings whose content is identical to the fan's. Where our text differs,
#     the fan's slot belonged to the fan's last command and cannot be carried over
#     blindly; those are counted, not compared (DS[395] str 26 is one: a stray
#     newline after the text, which the engine does not read).
#   * Only ' TPS' entries that parse; strings that do not parse are counted.
#   * It says nothing about what the unit in the slot MEANS - only that we kept it.

OURS_ROM = sys.argv[1] if len(sys.argv) > 1 else _default_built()


def rs(path):
    rom = open(path, 'rb').read()
    fat = struct.unpack_from('<I', rom, 0x48)[0]
    fid = file_id(rom, 'jpn/spt.bin')
    a, b = struct.unpack_from('<II', rom, fat + fid * 8)
    return rom[a:b]


def entry(c, i):
    o, s = struct.unpack_from('<II', c, i * 8)
    return c[o:o + s] if s else b''


OURS = rs(OURS_ROM)
FAN = rs((sys.argv[2] if len(sys.argv) > 2 else _default_fan()))

n = struct.unpack_from('<I', FAN, 0)[0] // 8
filled = kept = changed = bad = 0
lost = []
for i in range(n):
    f, o = entry(FAN, i), entry(OURS, i)
    if f[:4] != b' TPS' or o[:4] != b' TPS':
        continue
    try:
        ft, ot = spt.tails(f, True), spt.tails(o, True)
        fs = [u for _, _, _, u in spt.all_strings(f, True)]
        os_ = [u for _, _, _, u in spt.all_strings(o, True)]
    except Exception:
        bad += 1
        continue
    for k, t in enumerate(ft):
        if not any(t):
            continue
        filled += 1
        if k >= len(os_) or list(os_[k]) != list(fs[k]):
            changed += 1
            continue
        if list(ot[k]) == list(t):
            kept += 1
        else:
            lost.append((i, k, t, ot[k]))

print('fan strings with something after their declared length: %d' % filled)
print('  unchanged in our build and kept: %d' % kept)
print('  our text differs, so not compared: %d' % changed)
print('entries that did not parse: %d' % bad)
print('LOST - unchanged string, fan slot zeroed or altered: %d' % len(lost))
for i, k, t, got in lost[:30]:
    print('  DS[%d] str %d  fan %s  ours %s' % (i, k, ' '.join('%04X' % u for u in t),
                                              ' '.join('%04X' % u for u in got)))
