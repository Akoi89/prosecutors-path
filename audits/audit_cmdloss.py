# Final audit: is another DS-only engine command still being dropped?
# For every control code, compare how often the FAN string carries it against how
# often our swapped string drops it. A code the official script essentially never
# has (loss ratio near 1.0) is DS-only content - the class that hung Episode 1.
# A code dropped only sometimes is ordinary localisation variance.
import os as _os
import sys as _sys

# Portable paths: the audits live in <repo>/audits and the toolchain in
# <repo>/tools, so everything is found relative to this file rather than to any
# one machine. The ROMs are yours and are located the same way build.py does it.
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

import sys, struct, collections

import spt
from dstext import ARGS
from inject import file_id

# SCOPE - what this does NOT look at:
#   * ONLY strings that were SWAPPED. A string we kept as fan text is invisible
#     here, by design - it cannot have lost anything.
#   * Only codes appearing at least 10 times in the fan ROM; rarer codes are
#     excluded to keep the ratio meaningful, so a code used 9 times could vanish
#     unnoticed.
#   * A loss ratio is evidence, not proof. E107 is lost 17,000 times harmlessly.

# Optional ROM override, so a deliberately broken fixture can be audited
# without touching out/. See rig\audit_fixtures.py.
OURS_ROM = sys.argv[1] if len(sys.argv) > 1 else _default_built()


CTRL = lambda v: 0xE000 <= v <= 0xF8FF

def rs(p):
    rom = open(p, 'rb').read()
    fat = struct.unpack_from('<I', rom, 0x48)[0]
    fid = file_id(rom, 'jpn/spt.bin')
    a, b = struct.unpack_from('<II', rom, fat + fid * 8)
    return rom[a:b]

def ent(c, i):
    o, s = struct.unpack_from('<II', c, i * 8)
    return c[o:o+s] if s else b''

def codes(u):
    c = collections.Counter()
    i = 0
    while i < len(u):
        v = u[i]
        if CTRL(v):
            c[v] += 1; i += 1 + ARGS.get(v, 0); continue
        i += 1
    return c

O = rs(OURS_ROM)
F = rs((sys.argv[2] if len(sys.argv) > 2 else _default_fan()))
n = struct.unpack_from('<I', O, 0)[0] // 8

fan_total = collections.Counter()   # occurrences in fan strings that we swapped
lost = collections.Counter()        # of those, how many our version does not have
swapped = 0
for i in range(n):
    eo, ef = ent(O, i), ent(F, i)
    if not eo or eo[:4] != b' TPS' or not ef or ef[:4] != b' TPS':
        continue
    try:
        SO = {si: list(u) for si, a, l, u in spt.all_strings(eo, True)}
        SF = {si: list(u) for si, a, l, u in spt.all_strings(ef, True)}
    except Exception:
        continue
    for si, u in SO.items():
        if si not in SF or u == SF[si]:
            continue
        swapped += 1
        a, b = codes(SF[si]), codes(u)
        for k, v in a.items():
            fan_total[k] += v
            if v > b.get(k, 0):
                lost[k] += v - b.get(k, 0)

print('swapped strings compared: %d' % swapped)
print()
print('%-7s %9s %9s %7s  %s' % ('code', 'in fan', 'lost', 'ratio', 'reading'))
rows = []
for k, tot in fan_total.items():
    if tot < 10: continue
    l = lost.get(k, 0)
    if l == 0: continue
    rows.append((l / tot, k, tot, l))
rows.sort(reverse=True)
for ratio, k, tot, l in rows[:22]:
    if ratio >= 0.90:
        note = 'DS-ONLY?  official script essentially never has it'
    elif ratio >= 0.50:
        note = 'suspicious - check'
    else:
        note = 'ordinary variance'
    guard = ' [GUARDED]' if k in (0xE041, 0xE042) else ''
    print('%-7s %9d %9d %6.2f   %s%s' % ('%04X' % k, tot, l, ratio, note, guard))
