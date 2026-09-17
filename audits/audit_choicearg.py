# -*- coding: utf-8 -*-
"""Does every {E187} choice-menu argument resolve on the DS?

{E187} builds one button of an answer menu: {E187} <strip id> <target string>.
Our spt.bin copies both arguments verbatim from the official Collection script
(tools/dstext.py:454-457 appends argument units unchanged - there is no remap
anywhere in the toolchain). Two different faults share that one root cause
(ROOTCAUSE.md, G:\\Claude\\GK2\\sweep\\e187_rootcause_20260917):

  * the strip id is sometimes a Collection-only value past the DS's own block -
    argument 170 lands on idlocal 533, a 192-byte RLCN palette, not a sprite,
    and rig-proven freezes the game with the prompt up and no buttons
    (DS[58] str 2);
  * the target string index is shifted by one wherever region_align re-lays an
    entry, because inject.py's {E081}-index rewrite (inject.py:217-232) does
    not do the same for {E187}'s second argument.

Three checks per {E187} occurrence in the BUILT ROM, cheapest first:
  1. 363 + strip_arg must be inside jpn/idlocal.bin and be a sprite bundle -
     not one of the two palette entries (363, 533 - choice_strips.PALETTE_ENTRY)
     and not out of range.
  2. target_string must be less than the entry's own string count.
  3. wherever the fan string carries the same number of {E187}s, BOTH
     arguments must equal the fan's - this is the one that actually catches
     every one of the 12 known sites; 1-2 only catch the 7 whose bad id lands
     outside the DS block or on the palette.

    python audits\\audit_choicearg.py
"""
import os as _os
import sys as _sys

# Portable paths: the audits live in <repo>/audits and the toolchain in
# <repo>/tools, so everything is found relative to this file rather than to any
# one machine. The ROM is yours and is located the same way build.py does it.
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


# The fan spt.bin is the ground truth for both arguments (see check 3) and ships
# in dump/ - the same file tools/inject.py itself opens at inject.py:312 - so no
# raw fan ROM has to be found or hashed just to run this audit.
def _default_fan_spt():
    p = _os.path.join(_REPO, 'dump', 'ds_fan', 'jpn', 'spt.bin')
    if not _os.path.exists(p):
        raise SystemExit('no fan spt.bin at %s - run a build (or --skip-extract) once '
                         'first, or pass one as the second argument' % p)
    return p


import struct

import spt
from dstext import ARGS
from inject import file_id
from choice_strips import Idlocal, PALETTE_ENTRY

# SCOPE - what this does NOT look at:
#   * Only {E187}. Other codes whose arguments are DS-specific indices are not
#     checked here - the generalised table was left for a future audit
#     (ROOTCAUSE.md section 4).
#   * Check 3 only fires where the fan string carries the SAME number of
#     {E187}s as ours; a string whose count differs is left to checks 1-2 only.
#   * The idlocal classifier tells a sprite bundle from a palette by its first
#     u32 (12, measured) and the RLCN tag - it does not verify the bundle
#     actually draws a real strip.
#   * Measured on the shipped 1.8.5 ROM's 25 bad {E187} occurrences (the 12
#     known sites): check 3 (the fan diff) catches all 25; check 1 (sprite vs
#     palette) catches exactly 1 (DS[200], arg 170 -> idlocal 533); check 2
#     (target range) catches 0 - every bad target is still a valid index into
#     its own entry, just the WRONG one. Run without a fan spt (FAN_SPT_PATH
#     missing), this audit would have caught almost none of them.

CODE = 0xE187

# Optional overrides, so a deliberately broken fixture can be audited without
# touching out/ or dump/. See audits/audit_fixtures.py.
OURS_ROM = _sys.argv[1] if len(_sys.argv) > 1 else _default_built()
FAN_SPT_PATH = _sys.argv[2] if len(_sys.argv) > 2 else _default_fan_spt()


def rs(rom, path):
    fat = struct.unpack_from('<I', rom, 0x48)[0]
    fid = file_id(rom, path)
    a, b = struct.unpack_from('<II', rom, fat + fid * 8)
    return rom[a:b]


def entry(c, i):
    o, s = struct.unpack_from('<II', c, i * 8)
    return c[o:o + s] if s else b''


def occurrences(u):
    """[(strip_arg, target)] for every {E187} in unit list u, in order, walked
    with arities so argument units are never mistaken for codes."""
    out = []
    i, n = 0, len(u)
    while i < n:
        v = u[i]
        if 0xE000 <= v <= 0xF8FF:
            if v == CODE and i + 2 < n:
                out.append((u[i + 1], u[i + 2]))
            i += 1 + ARGS.get(v, 0)
        else:
            i += 1
    return out


def strip_kind(idl, idx):
    """'sprite' / 'palette' / 'out of range' / 'unrecognized', from the idlocal
    container itself - not from tools/select_strips.json (a lettering map that
    omits its own 'empty' rows and is not authoritative for what the engine
    accepts) and not from the outside-the-repo inventory map."""
    if idx < 0 or idx >= idl.n:
        return 'out of range'
    if idx in (PALETTE_ENTRY['long'], PALETTE_ENTRY['short']):
        return 'palette'
    b = idl.blob(idx)
    if b[:4] == b'RLCN':
        return 'palette'
    if len(b) >= 4 and struct.unpack_from('<I', b, 0)[0] == 12:
        return 'sprite'
    return 'unrecognized'


ROM = open(OURS_ROM, 'rb').read()
SPT = rs(ROM, 'jpn/spt.bin')
IDL = Idlocal(rs(ROM, 'jpn/idlocal.bin'))
FAN_SPT = open(FAN_SPT_PATH, 'rb').read()

n = struct.unpack_from('<I', SPT, 0)[0] // 8
checked = bad_strip = bad_range = bad_vs_fan = 0
hits = []
for i in range(n):
    e = entry(SPT, i)
    if e[:4] != b' TPS':
        continue
    try:
        strs = [u for _, _, _, u in spt.all_strings(e, True)]
    except Exception:
        continue
    fe = entry(FAN_SPT, i)
    fan_strs = None
    if fe[:4] == b' TPS':
        try:
            fan_strs = [u for _, _, _, u in spt.all_strings(fe, True)]
        except Exception:
            fan_strs = None
    for j, u in enumerate(strs):
        occ = occurrences(u)
        if not occ:
            continue
        fan_occ = (occurrences(fan_strs[j]) if fan_strs is not None and j < len(fan_strs)
                   else None)
        for k, (strip, target) in enumerate(occ):
            checked += 1
            problems = []
            kind = strip_kind(IDL, 363 + strip)
            if kind != 'sprite':
                bad_strip += 1
                problems.append('strip 363+%d = idlocal %d (%s)' % (strip, 363 + strip, kind))
            if target >= len(strs):
                bad_range += 1
                problems.append('target %d >= %d strings in entry' % (target, len(strs)))
            if fan_occ is not None and len(fan_occ) == len(occ):
                fstrip, ftarget = fan_occ[k]
                if (strip, target) != (fstrip, ftarget):
                    bad_vs_fan += 1
                    problems.append('!= fan (strip=%d target=%d)' % (fstrip, ftarget))
            if problems:
                hits.append((i, j, strip, target, problems))

print('{E187} occurrences checked: %d' % checked)
print('  strip id not a real sprite bundle: %d' % bad_strip)
print('  target string index out of range: %d' % bad_range)
print('  differs from the fan (same {E187} count in the string): %d' % bad_vs_fan)
print('BAD - {E187} sites that cannot resolve on the DS as built: %d' % len(hits))
for i, j, strip, target, problems in hits[:40]:
    print('  DS[%d] str %d  strip=%d target=%d  %s' % (i, j, strip, target, '; '.join(problems)))
if len(hits) > 40:
    print('... and %d more' % (len(hits) - 40))
if hits:
    _sys.exit(1)
