# -*- coding: utf-8 -*-
"""Does the built ROM ever ship a 0x0000 unit in TEXT position - the DS script
interpreter's own end-of-string marker - anywhere the fan didn't already ship
one there?

The DS engine walks a string with its own arity table (arm9 0x0200DD10-DDFA):
a control code's own argument units are skipped over, but the first plain
0x0000 unit it meets ends the string right there, and everything after it
never runs. tools/inject.py's `_has_zero_in_text` guard (added in DELTA 5,
fan_tone/E04X_FINDINGS.md section 4) checks a converted string for exactly
this BEFORE it is accepted, and keeps the fan's version if it finds one - but
that guard only runs on the main per-string conversion path. The DELTA 5
refuter found two paths that ship Capcom text without ever calling it:

  * the row-by-row sparse-bank path (tools/inject.py, the `conv[j2] = flat`
    assignment reached when a bank is rebuilt row by row rather than whole),
    which supplied 247 rows in entries 453/454;
  * the two localization-table patches, entries 432 (dump/jpn_trial/detailMsg.bin)
    and 395 (dump/jpn/logicKW.bin), patched in AFTER the main conversion loop.

Both were measured by hand at 0 zeros on the day of the fix. This audit makes
that permanent by checking the WHOLE built ROM's spt.bin directly, regardless
of which code path put a string there - it does not care how a string was
produced, only what is in it.

Method: for every ' TPS' entry present in the built ROM, for every string
(spt.all_strings, string 0 included), walk its units arity-aware (ARGS, so a
control code's own argument units - which may legitimately be 0 - are never
mistaken for the terminator) and record every literal 0x0000 unit that sits
BEFORE the string's declared length (the "declared end"; units the entry
keeps past that point are a tail/terminator slot, not text - see
tools/spt.py's `tails` docstring, and are out of scope here on purpose). A
flagged zero is ALLOWED only when the fan's string at the same (entry, string)
also has a text-position zero, walked the same way, whose immediately
preceding units are identical to ours - so a stray literal zero the fan
itself ships (entry 95 str 16, a {00} right after {E121} at the seam DELTA
2's seam-cue restoration copies verbatim from the fan) is accepted, and
nothing else is.

    python audits\\audit_zeros.py

SCOPE - what this does NOT look at:
  * "Immediately preceding units match" compares the last 4 units before the
    zero (fewer if the zero is closer than that to the string's start),
    clipped at each string's own start; it is a heuristic that identifies
    "the fan's own stray zero, copied forward," not a formal proof of
    provenance. A coincidental 4-unit match elsewhere would be misjudged; none
    is known to exist.
  * A string index present in ours but missing entirely from the fan's parse
    has no fan zeros to compare against, so any zero in it is always flagged -
    there is nothing to accept it against.
  * An entry present in the built ROM whose strings (or the fan's matching
    entry's strings) fail to parse (spt.all_strings raises) is skipped
    entirely for that entry - counted and printed, not swallowed.
  * This does not simulate the ARM9 interpreter or re-derive the DS arity
    table; it trusts dstext.ARGS, the same table tools/inject.py's own guard
    uses, so a code missing from that table would be misread here exactly as
    it would be by the guard it is checking.
  * It does not distinguish which code path produced a string - it reads the
    finished spt.bin, so it covers the main conversion path, the row-by-row
    path and the localization-table patches alike, and would catch a zero
    from a path nobody has written yet.
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


# The fan spt.bin is the ground truth (see the method above) and ships in
# dump/ - the same file tools/inject.py itself opens - so no raw fan ROM has
# to be found or hashed just to run this audit.
def _default_fan_spt():
    p = _os.path.join(_REPO, 'dump', 'ds_fan', 'jpn', 'spt.bin')
    if not _os.path.exists(p):
        raise SystemExit('no fan spt.bin at %s - run a build (or --skip-extract) once '
                         'first, or pass one as the second argument' % p)
    return p


import struct

import spt
import rowfold
from dstext import ARGS
from inject import file_id

# Optional overrides, so a deliberately broken fixture can be audited without
# touching out/ or dump/. See audits/audit_fixtures.py.
OURS_ROM = _sys.argv[1] if len(_sys.argv) > 1 else _default_built()
FAN_SPT_PATH = _sys.argv[2] if len(_sys.argv) > 2 else _default_fan_spt()

MATCH_WINDOW = 4  # units of preceding context that must match to allow a zero


def rs(rom, path):
    fat = struct.unpack_from('<I', rom, 0x48)[0]
    fid = file_id(rom, path)
    a, b = struct.unpack_from('<II', rom, fat + fid * 8)
    return rom[a:b]


def entry(c, i):
    o, s = struct.unpack_from('<II', c, i * 8)
    return c[o:o + s] if s else b''


def zero_positions(u, length):
    """Indices of every literal 0x0000 unit in TEXT position (never a control
    code's own argument, walked arity-aware exactly like the inject.py guard
    this checks) before `length`, the string's declared end."""
    out = []
    i, n = 0, len(u)
    while i < n:
        v = u[i]
        if 0xE000 <= v <= 0xF8FF:
            i += 1 + ARGS.get(v, 0)
        else:
            if v == 0 and i < length:
                out.append(i)
            i += 1
    return out


def preceding(u, k):
    return u[max(0, k - MATCH_WINDOW):k]


ROM = open(OURS_ROM, 'rb').read()
SPT = rowfold.fold_spt(rs(ROM, 'jpn/spt.bin'), OURS_ROM)
FAN_SPT = open(FAN_SPT_PATH, 'rb').read()

n = struct.unpack_from('<I', SPT, 0)[0] // 8
strings_walked = 0
zeros_found = 0
zeros_allowed = 0
hits = []
parse_failures = 0

for i in range(n):
    e = entry(SPT, i)
    if e[:4] != b' TPS':
        continue
    fe = entry(FAN_SPT, i)
    try:
        strs = [(j, length, u) for j, _, length, u in spt.all_strings(e, True)]
    except Exception:
        parse_failures += 1
        continue
    fan_strs = {}
    if fe[:4] == b' TPS':
        try:
            fan_strs = {j: (length, u) for j, _, length, u in spt.all_strings(fe, True)}
        except Exception:
            parse_failures += 1
            fan_strs = {}
    for j, length, u in strs:
        strings_walked += 1
        zeros = zero_positions(u, length)
        if not zeros:
            continue
        fan_length, fan_u = fan_strs.get(j, (0, ()))
        fan_zeros = zero_positions(fan_u, fan_length) if fan_u else []
        for k in zeros:
            zeros_found += 1
            ours_win = preceding(u, k)
            allowed = any(preceding(fan_u, fk) == ours_win for fk in fan_zeros)
            if allowed:
                zeros_allowed += 1
            else:
                hits.append((i, j, k, ours_win))

print('strings walked: %d' % strings_walked)
print('entries that failed to parse (skipped): %d' % parse_failures)
print('zero-in-text-position units found: %d' % zeros_found)
print('zeros allowed as the fan\'s own: %d' % zeros_allowed)
print('BAD - zeros not accounted for by the fan: %d' % len(hits))
for i, j, k, win in hits[:40]:
    # ascii() rather than the raw render: the preceding units can carry literal
    # Japanese text (an untranslated record), and a subprocess harness that
    # captures this script's stdout under a non-UTF-8 console encoding (the
    # default on Windows) crashes decoding it otherwise - see audit_fixtures.py.
    print('  entry %d str %d unit %d  preceding: %s' % (i, j, k, ascii(spt.render(win))))
if len(hits) > 40:
    print('... and %d more' % (len(hits) - 40))
if hits:
    _sys.exit(1)
