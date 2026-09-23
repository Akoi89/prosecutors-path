# -*- coding: utf-8 -*-
"""Does every string-index argument (other than {E187}/{E081}) still point at
the fan's string?

Several engine commands carry arguments that are STRING INDICES within the
same spt entry: a rebuttal's statement pointers ({E11F}/{E120}), a choice
menu's target ({E187}, covered by audit_choicearg.py instead), and several
narrower codes ({E080}, {E0B0}, {E1C1}, {E164}, {E161}, {E162}, {E1A6},
{E1E9}, {E11B}, {E160}). Both value
spaces are DS-specific and neither is remapped anywhere in the toolchain -
tools/dstext.py appends the Collection's own argument units unchanged, so any
re-cut (region_align / RECUT_SHIFTED) that skews an entry's string layout
skews these arguments with it. DS entry 92 (Case 2, Gavelle's rebuttal) proved
the effect: its {E11F}x5/{E120} statement pointers were every one -1 against
the fan, statement 0 pointed at an empty stub, no statement box was drawn, and
the ARM9 data-aborted (rig, 2026-09-22; CRASH_ENTRY92_20260922.md). DS entry
248 (Case 4) carries the identical fault. tools/inject.py's
`_restore_index_args` (the table is `INDEX_ARGS`, imported from there so this
audit and the fix can never drift apart) copies the listed argument positions
of each of these codes from the fan, per string; this audit checks the built
ROM actually carries the fan's values.

Also checked here, same method: `DS_VALUE_ARGS` ({E131}, entry 411/map0c) - not
a string index into this entry, but still a DS-specific value (a map/area id
list) the Collection must not override; before the fix one occurrence differed
from the fan across the whole game (compared/differ 431/1, measured on the pre-fix
build); a fixed build reads 431/0.

Method, for every code in INDEX_ARGS or DS_VALUE_ARGS, per string present in
BOTH ours and the fan: where the string's COUNT of that code is equal in
both, compare the listed argument positions of each occurrence, ours vs fan,
in order.

    python audits\\audit_indexargs.py

SCOPE - what this does NOT look at:
  * {E187} is intentionally excluded - audit_choicearg.py already checks it,
    with its own idlocal-specific classification (sprite vs palette) that
    does not apply to any other code here.
  * {E081} is not in INDEX_ARGS - region_align rewrites it directly
    (tools/inject.py's own {E081} loop) and it is not part of the fix this
    audit is proving.
  * {E254} is not in INDEX_ARGS - entry 333's ten values are a ROTATION of the
    same ids against the fan, not a shift; measured and excluded on purpose
    (CRASH_ENTRY92_20260922.md, "SCAN FOLLOW-UPS").
  * {E100}, {E12F} are not in INDEX_ARGS (DELTA 1) - a speaker swap and
    Capcom's animation choices, neither an index; see tools/inject.py's own
    exclusions list for the detail on each. {E131} is not an index either,
    but it IS checked here, through DS_VALUE_ARGS (DELTA 2), not INDEX_ARGS.
  * A string whose COUNT of a code differs from the fan's is not compared at
    all for that code (same policy as audit_choicearg's check 3) - reported
    as an informational count, does not fail the audit. An entry or string
    missing from either side entirely is skipped the same way.
  * An occurrence whose listed positions run past either argument list (a
    string truncated at its declared length, spt.tails) is skipped rather
    than compared - it cannot be judged right or wrong from truncated data,
    but the skip is counted and printed rather than swallowed.
  * An entry present in both ROMs whose strings fail to parse (spt.all_strings
    raises) is skipped entirely - also counted and printed, rather than
    silently passed over.
  * This only compares ours against the fan positionally; it does not
    independently verify the fan's own value is a valid in-range index (the
    fan ships with the DS engine already, so that is assumed correct).
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


import collections
import struct

import spt
from dstext import ARGS
from inject import file_id, INDEX_ARGS, DS_VALUE_ARGS

# Optional overrides, so a deliberately broken fixture can be audited without
# touching out/ or dump/. See audits/audit_fixtures.py.
OURS_ROM = _sys.argv[1] if len(_sys.argv) > 1 else _default_built()
FAN_SPT_PATH = _sys.argv[2] if len(_sys.argv) > 2 else _default_fan_spt()

CODES = [c for c in INDEX_ARGS if c != 0xE187] + list(DS_VALUE_ARGS)  # {E187} is audit_choicearg's
POSITIONS = dict(INDEX_ARGS)
POSITIONS.update(DS_VALUE_ARGS)


def rs(rom, path):
    fat = struct.unpack_from('<I', rom, 0x48)[0]
    fid = file_id(rom, path)
    a, b = struct.unpack_from('<II', rom, fat + fid * 8)
    return rom[a:b]


def entry(c, i):
    o, s = struct.unpack_from('<II', c, i * 8)
    return c[o:o + s] if s else b''


def occurrences(u, code):
    """[[argument units]] for every occurrence of `code` in unit list u, in
    order, walked with arities so argument units are never mistaken for
    codes. An occurrence whose declared arity runs past the end of u (a
    string truncated at its declared length) comes back short rather than
    raising; callers bounds-check the positions they need."""
    out = []
    i, n = 0, len(u)
    while i < n:
        v = u[i]
        if 0xE000 <= v <= 0xF8FF:
            if v == code:
                out.append(list(u[i + 1:i + 1 + ARGS.get(v, 0)]))
            i += 1 + ARGS.get(v, 0)
        else:
            i += 1
    return out


ROM = open(OURS_ROM, 'rb').read()
SPT = rs(ROM, 'jpn/spt.bin')
FAN_SPT = open(FAN_SPT_PATH, 'rb').read()

n = struct.unpack_from('<I', SPT, 0)[0] // 8
compared = collections.OrderedDict((c, 0) for c in CODES)
diffs = collections.OrderedDict((c, 0) for c in CODES)
mismatched_strings = collections.OrderedDict((c, 0) for c in CODES)
hits = []
parse_failures = 0
bounds_skipped = 0

for i in range(n):
    e = entry(SPT, i)
    if e[:4] != b' TPS':
        continue
    fe = entry(FAN_SPT, i)
    if fe[:4] != b' TPS':
        continue
    try:
        strs = [u for _, _, _, u in spt.all_strings(e, True)]
        fan_strs = [u for _, _, _, u in spt.all_strings(fe, True)]
    except Exception:
        parse_failures += 1
        continue
    for j, u in enumerate(strs):
        if j >= len(fan_strs):
            continue
        fu = fan_strs[j]
        for code in CODES:
            positions = POSITIONS[code]
            occ = occurrences(u, code)
            fan_occ = occurrences(fu, code)
            if not occ and not fan_occ:
                continue
            if len(occ) != len(fan_occ):
                mismatched_strings[code] += 1
                continue
            for k, (args_o, args_f) in enumerate(zip(occ, fan_occ)):
                if any(p >= len(args_o) or p >= len(args_f) for p in positions):
                    bounds_skipped += 1
                    continue
                compared[code] += 1
                vo = [args_o[p] for p in positions]
                vf = [args_f[p] for p in positions]
                if vo != vf:
                    diffs[code] += 1
                    hits.append((i, j, code, k, vo, vf))

for code in CODES:
    print('{%s} occurrences compared: %d  (differences: %d, mismatched-count strings: %d)'
          % (format(code, 'X'), compared[code], diffs[code], mismatched_strings[code]))

print('entries that failed to parse (skipped): %d' % parse_failures)
print('occurrences skipped by the bounds check: %d' % bounds_skipped)
print('BAD - string-index arguments that differ from the fan: %d' % len(hits))
for i, j, code, k, vo, vf in hits[:40]:
    print('  entry %d str %d code {%s} #%d ours %s fan %s'
          % (i, j, format(code, 'X'), k, vo, vf))
if len(hits) > 40:
    print('... and %d more' % (len(hits) - 40))
if hits:
    _sys.exit(1)
