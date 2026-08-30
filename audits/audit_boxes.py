# -*- coding: utf-8 -*-
"""Does any string have FEWER message boxes than the fan ROM's?

This is the v1.4.2 defect class and it had no standing audit. `audit_empty.py`
looks for strings empty of TEXT; it computes box counts but only to print them,
never to decide anything. The distinction matters: v1.4.2 hung because seven rows
lost their box-end, and a box that opens with nothing in it never closes.

Found by building a fixture that stripped box-ends and watching audit_empty give
byte-identical output on the broken ROM. An audit that has never failed has not
been tested.

SCOPE, stated so nobody has to guess:
  * Only ' TPS' entries present in BOTH our ROM and the fan ROM.
  * Only strings present in both, compared by index.
  * "Ours has fewer boxes than the fan's" is the alarm. Ours having MORE is
    normal and very common - Capcom's prose is longer, so it paginates further.
  * Nothing here looks at wording, width, or anything outside jpn/spt.bin.

    python rig\audit_boxes.py [rom.nds]
"""
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

import struct
import sys


import spt                                    # noqa: E402
from dstext import ARGS                       # noqa: E402
from inject import file_id                    # noqa: E402

OURS_ROM = sys.argv[1] if len(sys.argv) > 1 else _default_built()
FAN_ROM = (sys.argv[2] if len(sys.argv) > 2 else _default_fan())

BOXEND = {0xE102, 0xE104, 0xE106, 0xE185, 0xE081}


def rs(path):
    rom = open(path, 'rb').read()
    fat = struct.unpack_from('<I', rom, 0x48)[0]
    fid = file_id(rom, 'jpn/spt.bin')
    a, b = struct.unpack_from('<II', rom, fat + fid * 8)
    return rom[a:b]


def ent(c, i):
    o, s = struct.unpack_from('<II', c, i * 8)
    return c[o:o + s] if s else b''


def boxes(u):
    """Count box-ends, stepping over control-code arguments so an argument that
    happens to equal a box-end value is not counted as one."""
    n = i = 0
    while i < len(u):
        v = u[i]
        if 0xE000 <= v <= 0xF8FF:
            if v in BOXEND:
                n += 1
            i += 1 + ARGS.get(v, 0)
            continue
        i += 1
    return n


O, F = rs(OURS_ROM), rs(FAN_ROM)
n = struct.unpack_from('<I', O, 0)[0] // 8

compared = 0
lost = []
gained = 0
for i in range(n):
    eo, ef = ent(O, i), ent(F, i)
    if not eo or eo[:4] != b' TPS' or not ef or ef[:4] != b' TPS':
        continue
    try:
        SO = {si: list(u) for si, a, ln, u in spt.all_strings(eo, True)}
        SF = {si: list(u) for si, a, ln, u in spt.all_strings(ef, True)}
    except Exception:                                        # noqa: BLE001
        continue
    for si, u in SO.items():
        if si not in SF:
            continue
        compared += 1
        bo, bf = boxes(u), boxes(SF[si])
        if bo < bf:
            lost.append((i, si, bo, bf))
        elif bo > bf:
            gained += 1

# Report the denominator. An audit that silently compares nothing reports success.
print('strings compared: %d' % compared)
if not compared:
    print('NOTHING WAS COMPARED - this is not a pass, the inputs did not line up')
    sys.exit(1)
print('strings with MORE boxes than the fan (normal, longer prose): %d' % gained)
print('strings with FEWER boxes than the fan: %d' % len(lost))
if lost:
    print()
    print('%-7s %-6s %-9s %s' % ('entry', 'str', 'ourboxes', 'fanboxes'))
    for i, si, bo, bf in lost[:40]:
        print('%-7d %-6d %-9d %d' % (i, si, bo, bf))
    if len(lost) > 40:
        print('... and %d more' % (len(lost) - 40))
    sys.exit(1)
print('no string lost a message box')
