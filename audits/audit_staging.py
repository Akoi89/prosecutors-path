# -*- coding: utf-8 -*-
"""Does every string's camera/character-position/pose command sequence still
match the fan's, in the same message box?

Six DS engine commands set camera, character position and pose: {E13A} place
character, {E13B} slide character over time, {E16F} move character, {E114}
walk character, {E15B} camera, {E150} pose (STAGING_CODES, imported from
tools/inject.py so this audit and the fix can never drift apart). Their
arguments are DS screen coordinates or animation choices, not translated
content, and the Collection re-tuned every one of them for its own screen and
cast; the fan ROM (AAI2 Final v2) carries the DS originals, which are the
values right for the DS engine. A tester playing the staged build reported a
Case 2 scene where the camera never returns to its resting position and an
officer is left out of frame; traced to spt entry 99 string 5, where the
built ROM carried the Collection's own staging instead of the fan's. A second
tester reported a Case 3 scene where a character is drawn as in the
Collection rather than as on the DS; traced to spt entry 125, where the fan
carries about sixteen {E150} pose commands ours lacked entirely (both
described here, not quoted - see tools/inject.py's STAGING_CODES comment for
the full measurement and the {E12F} exclusion). tools/inject.py's
`_restore_staging` copies or resequences the fan's subsequence into every
string the injector ships, box-correct; this audit checks the built ROM
actually carries it.

Method, per entry and string present in BOTH ours and the fan, where the
entry's COUNT of strings is equal between the two (spt.all_strings, index by
index): walk both strings' unit lists arity-aware (ARGS) and pull out every
occurrence of a STAGING_CODES command, in order, as (code, argument tuple,
box index - the count of box-end codes {E102}/{E104}/{E185}/{E081} before
it, raw unit position). Three checks, independent:
  1. the (code, argument tuple) list as a whole - not per code - since a
     structural difference (a command added or dropped) shows up as the
     SUBSEQUENCE no longer lining up, not as one code's count changing;
  2. where the string's TOTAL count of box-end codes agrees between ours and
     the fan (a translation-driven box-count difference makes a box-for-box
     comparison meaningless, not a placement fault) and check 1 already
     passed for that string: the box index of every occurrence against the
     fan's occurrence at the same position;
  3. where check 2 also passed for that string: the COARSE in-box property -
     is there any VISIBLE text before this occurrence in its own box, or
     none (any plain unit that is not a control code AND not a bare {0A}
     line break; a line break alone does not count as "some text"). That
     before/after-text status must equal the fan's for every occurrence;
     ORDER within the box is already implied by checks 1 and 2 (an equal
     subsequence in an equal box cannot cross itself), so this only checks
     the coarse side, not a scaled distance - an earlier, stricter version
     scaled a precise target point from the fan's OWN (different) wording,
     which moved 28 strings the Collection had already placed correctly
     against its own text.

    python audits\\audit_staging.py [rom.nds] [fan_spt.bin]

SCOPE - what this does NOT look at:
  * Only STAGING_CODES is compared; every other command (colour codes, box
    codes, pacing codes, and {E12F} - the per-line talking animation - is
    deliberately never added to the rule) is out of scope for this audit the
    same way it is out of scope for the fix; see tools/inject.py's
    STAGING_CODES comment for the codes deliberately excluded and why.
  * check 2 (box placement) only runs for a string whose check-1 subsequence
    already matches AND whose box-end COUNT already matches; check 3
    (coarse in-box property) only runs where check 2 ALSO passed for that
    string; a string that fails an earlier check is not double-counted into
    a later one's numbers.
  * An entry present in only one ROM, or whose string COUNT differs between
    the two, is skipped entirely for that entry, counted separately as
    "entries skipped" rather than silently passed over - on the build this
    audit was written against, that count is 0 (every entry in the built ROM
    has a same-count counterpart in the fan spt.bin); this is NOT the same
    skip audit_indexargs.py performs (that audit skips per CODE per STRING
    when one code's own count disagrees, not per entry).
  * An entry whose strings fail to parse (spt.all_strings raises) is skipped
    entirely - also counted and printed; also 0 today.
  * This only compares the built ROM against the fan positionally; it does
    not independently verify the fan's own coordinates or box layout are
    correct for the DS engine (the fan ships with the DS engine already, so
    that is assumed correct, same assumption audit_indexargs.py makes).
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
from dstext import ARGS
from inject import file_id, STAGING_CODES

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


# Box-end codes for the box-index count (check 2) - the same set
# tools/inject.py's _STAGING_BOXEND names, kept independent here rather than
# imported from inject.py's private helpers (STAGING_CODES is imported because it
# is the shared list the audit and the fix must agree on).
BOXEND = (0xE102, 0xE104, 0xE185, 0xE081)


def staging_seq(u):
    """([(code, argument tuple, box index, raw position)], total box-end
    count) for unit list u: every STAGING_CODES occurrence, in order, walked
    with arities so argument units are never mistaken for codes; box index
    is the count of BOXEND codes seen strictly before that occurrence."""
    out = []
    box = 0
    i, n = 0, len(u)
    while i < n:
        v = u[i]
        if 0xE000 <= v <= 0xF8FF:
            if v in STAGING_CODES:
                out.append((v, tuple(u[i + 1:i + 1 + ARGS.get(v, 0)]), box, i))
            if v in BOXEND:
                box += 1
            i += 1 + ARGS.get(v, 0)
        else:
            i += 1
    return out, box


def has_text(u, lo, hi):
    """The COARSE in-box property: is there any VISIBLE text unit in
    u[lo:hi] - a plain unit that is not a control code and not a bare {0A}
    line break (tools/inject.py's own _has_text, kept independent here like
    every other constant, matched exactly to the coarse before/after-text
    measurement this fix's scope was sized against)."""
    k = lo
    while k < hi:
        v = u[k]
        if 0xE000 <= v <= 0xF8FF:
            k += 1 + ARGS.get(v, 0)
        else:
            if v != 0x0A:
                return True
            k += 1
    return False


def box_spans(u):
    """[(lo, hi), ...] raw span of every box in u, box 0 first."""
    starts = [0]
    i, n = 0, len(u)
    while i < n:
        v = u[i]
        if 0xE000 <= v <= 0xF8FF:
            if v in BOXEND:
                starts.append(i + 1 + ARGS.get(v, 0))
            i += 1 + ARGS.get(v, 0)
        else:
            i += 1
    return [(s, starts[k + 1] if k + 1 < len(starts) else len(u)) for k, s in enumerate(starts)]


ROM = open(OURS_ROM, 'rb').read()
SPT = rs(ROM, 'jpn/spt.bin')
FAN_SPT = open(FAN_SPT_PATH, 'rb').read()

n = struct.unpack_from('<I', SPT, 0)[0] // 8
compared = differ = 0
box_compared = box_differ = 0
coarse_compared = coarse_differ = 0
parse_failures = 0
mismatched_entries = 0
hits = []
box_hits = []
coarse_hits = []

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
    if len(strs) != len(fan_strs):
        mismatched_entries += 1
        continue
    for j, (u, fu) in enumerate(zip(strs, fan_strs)):
        occ_o, box_o = staging_seq(u)
        occ_f, box_f = staging_seq(fu)
        seq_o = [(c, args) for c, args, _, _ in occ_o]
        seq_f = [(c, args) for c, args, _, _ in occ_f]
        if not seq_o and not seq_f:
            continue
        compared += 1
        if seq_o != seq_f:
            differ += 1
            hits.append((i, j))
            continue
        if box_o != box_f:
            continue
        box_compared += 1
        if any(bo != bf for (_, _, bf, _), (_, _, bo, _) in zip(occ_f, occ_o)):
            box_differ += 1
            box_hits.append((i, j))
            continue

        # Check 3: the COARSE in-box property per occurrence -
        # some visible text before it in its own box, or none.
        fspans, ospans = box_spans(fu), box_spans(u)
        bad_string = False
        for t in range(len(occ_f)):
            b = occ_f[t][2]
            flo, _ = fspans[b]
            olo, _ = ospans[b]
            coarse_compared += 1
            if has_text(fu, flo, occ_f[t][3]) != has_text(u, olo, occ_o[t][3]):
                bad_string = True
        if bad_string:
            coarse_differ += 1
            coarse_hits.append((i, j))

print('strings with a staging-code subsequence compared: %d' % compared)
print('entries skipped (string count mismatch): %d' % mismatched_entries)
print('entries that failed to parse (skipped): %d' % parse_failures)
print('BAD - strings whose staging (camera/character position/pose) sequence differs from the fan: %d'
      % differ)
for i, j in hits[:20]:
    print('  entry %d str %d' % (i, j))
if len(hits) > 20:
    print('... and %d more' % (len(hits) - 20))
print('strings with box placement compared (subsequence and box-end count both match): %d'
      % box_compared)
print('BAD - strings whose staging box placement differs from the fan: %d' % box_differ)
for i, j in box_hits[:20]:
    print('  entry %d str %d' % (i, j))
if len(box_hits) > 20:
    print('... and %d more' % (len(box_hits) - 20))
print('staging occurrences with a coarse in-box property compared (box placement also matched): %d'
      % coarse_compared)
print('BAD - strings whose coarse in-box property (before/after text) differs from the fan: %d'
      % coarse_differ)
for i, j in coarse_hits[:20]:
    print('  entry %d str %d' % (i, j))
if len(coarse_hits) > 20:
    print('... and %d more' % (len(coarse_hits) - 20))
if hits or box_hits or coarse_hits:
    _sys.exit(1)
