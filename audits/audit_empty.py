# Find strings that are EMPTY (no printable text) in our ROM but had text in the
# fan ROM. An empty message can open a box with nothing in it and never advance -
# the failure the user just hit in Episode 1.
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

import sys, struct

import spt
from dstext import ARGS
from inject import file_id

# SCOPE - what this does NOT look at, so nobody has to guess:
#   * Only ' TPS' entries present in BOTH ROMs, and only strings present in both.
#   * "Empty" means no PRINTABLE characters. It counts message boxes but never
#     tests them - a string that keeps its text and loses its box passes here.
#     That is audit_boxes.py's job, and the split is why the v1.4.2 defect had no
#     standing audit until 2026-08-30.
#   * Nothing outside jpn/spt.bin: no graphics, no localisation tables.

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

def printable(u):
    """count of visible characters, walking control-code arguments correctly"""
    n = i = 0
    while i < len(u):
        v = u[i]
        if CTRL(v):
            i += 1 + ARGS.get(v, 0); continue
        if 0xFF01 <= v <= 0xFF5E or 0x21 <= v <= 0x7E or v in (0xFF3F,):
            n += 1
        i += 1
    return n

def boxes(u):
    BOXEND = {0xE102, 0xE104, 0xE106, 0xE185, 0xE081}
    n = i = 0
    while i < len(u):
        v = u[i]
        if CTRL(v):
            if v in BOXEND: n += 1
            i += 1 + ARGS.get(v, 0); continue
        i += 1
    return n

O = rs(OURS_ROM)
F = rs((sys.argv[2] if len(sys.argv) > 2 else _default_fan()))
n = struct.unpack_from('<I', O, 0)[0] // 8

def ent(c, i):
    o, s = struct.unpack_from('<II', c, i * 8)
    return c[o:o+s] if s else b''

hits = []
for i in range(n):
    eo, ef = ent(O, i), ent(F, i)
    if not eo or eo[:4] != b' TPS' or not ef or ef[:4] != b' TPS':
        continue
    try:
        SO = {si: list(u) for si, a, ln, u in spt.all_strings(eo, True)}
        SF = {si: list(u) for si, a, ln, u in spt.all_strings(ef, True)}
    except Exception:
        continue
    for si, u in SO.items():
        if si not in SF: continue
        po, pf = printable(u), printable(SF[si])
        if po == 0 and pf > 0:
            hits.append((i, si, pf, boxes(u), boxes(SF[si]), len(u)))

print('strings EMPTY in ours but non-empty in fan: %d' % len(hits))
print('%-7s %-6s %-9s %-8s %-8s %s' % ('entry', 'str', 'fanchars', 'ourboxes', 'fanboxes', 'ourunits'))
for h in hits:
    print('%-7d %-6d %-9d %-8d %-8d %d' % h)
