# Audit: are there MORE mis-classified control codes like E1E2?
#  A) Corruption signature: any code whose declared arguments contain fullwidth
#     Latin in our ROM - i.e. an argument that got converted to text.
#  B) Suspicion signature: any code we declare arity 0 for, which in the FAN ROM
#     is almost always followed by the SAME constant value. That is exactly how
#     E1E2 (always followed by 68 = 'D') hid from the letter heuristic.
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

import sys, struct, collections, json

import spt
from dstext import ARGS
from inject import file_id

# SCOPE - what this does NOT look at:
#   * Only jpn/spt.bin, and only codes present in dump/ctrl_args.json.
#   * Part A finds arguments turned into TEXT. A wrong-but-still-numeric argument
#     looks fine to it.
#   * Part B only flags a zero-arity code always followed by the same constant.
#     A code whose declared arity is too LARGE is not detected here - E1BE is a
#     standing known false positive for exactly that reason.

# Optional ROM override, so a deliberately broken fixture can be audited
# without touching out/. See rig\audit_fixtures.py.
OURS_ROM = sys.argv[1] if len(sys.argv) > 1 else _default_built()


CTRL = lambda v: 0xE000 <= v <= 0xF8FF
FW = lambda v: 0xFF01 <= v <= 0xFF5E

def rs(p):
    rom = open(p, 'rb').read()
    fat = struct.unpack_from('<I', rom, 0x48)[0]
    fid = file_id(rom, 'jpn/spt.bin')
    a, b = struct.unpack_from('<II', rom, fat + fid * 8)
    return rom[a:b]

def strings(cont):
    n = struct.unpack_from('<I', cont, 0)[0] // 8
    for i in range(n):
        o, s = struct.unpack_from('<II', cont, i * 8)
        if not s or cont[o:o+4] != b' TPS': continue
        try:
            for si, a, ln, u in spt.all_strings(cont[o:o+s], True):
                yield i, si, list(u)
        except Exception:
            continue

OUR = rs(OURS_ROM)
FAN = rs((sys.argv[2] if len(sys.argv) > 2 else _default_fan()))

# ---- A: corrupted arguments in our ROM -------------------------------------
bad = collections.Counter()
examples = {}
for i, si, u in strings(OUR):
    k = 0
    while k < len(u):
        v = u[k]
        if CTRL(v):
            ar = ARGS.get(v, 0)
            args = u[k+1:k+1+ar]
            if ar and any(FW(x) for x in args):
                bad['%04X' % v] += 1
                examples.setdefault('%04X' % v, (i, si))
            k += 1 + ar
            continue
        k += 1
print('=== A. arguments corrupted into text (the E1E2 signature) ===')
print('codes affected: %d' % len(bad))
for c, n in bad.most_common():
    print('   %s x%d  first at DS[%d] str%d' % (c, n, *examples[c]))
if not bad:
    print('   none - every declared argument in the ROM is still raw')

# ---- B: zero-arity codes that look like they take a constant argument ------
follow = collections.defaultdict(collections.Counter)
for i, si, u in strings(FAN):
    for k, v in enumerate(u):
        if CTRL(v) and k + 1 < len(u):
            follow[v][u[k+1]] += 1
print()
print('=== B. codes we treat as arity 0 but that always carry the same value ===')
sus = []
for v, cnt in follow.items():
    if ARGS.get(v, 0) != 0: continue
    tot = sum(cnt.values())
    if tot < 8: continue
    val, n = cnt.most_common(1)[0]
    if n / tot >= 0.98 and not FW(val) and val < 0x3000:
        sus.append(('%04X' % v, tot, val, round(n / tot, 3)))
sus.sort(key=lambda t: -t[1])
if not sus:
    print('   none - no zero-arity code is followed by a constant')
for c, tot, val, r in sus:
    print('   %s occurs %d times, followed by %d (0x%X) in %.0f%% of them' % (c, tot, val, val, r * 100))
