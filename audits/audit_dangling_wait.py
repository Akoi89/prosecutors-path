# -*- coding: utf-8 -*-
"""Does any {E14B} wait on a character the string never placed?

{E14A}(c, ...) starts an action on character c and {E14B}(c) blocks the script
until that action finishes. If c was never put into the scene (no {E114} walk,
{E16F} move, {E13A} place or {E13B} slide for c earlier in the same string),
the wait has nothing to wait for. Issue 3 (Case 3 freeze after Bound's second
rebuttal, 2026-10-01): the 1.10.0 staging restore removed the two walk-ins
{E114}(11,...) and {E114}(65,...) from spt entry 185 string 1 (the fan and the
retail Japanese have neither) but left their companions {E14A}(11,3,0)
{E14B}(11) {E14A}(65,3,0) {E14B}(65). Character 65 is never placed in
Episode 3, so the game hung at the start of Edgeworth's ice-block memory. The
cause is measured from the data (every version of the script, the fan and the
Japanese); the wait semantics are inferred, not disassembled. tools/inject.py's
STAGING_CODES now includes {E14A}/{E14B}, so the restore removes a companion
together with its walk-in, and this audit is the standing guard for the whole
class.

Method: for every string of every entry, for the built ROM and for the fan's
spt.bin, list each {E14B}(c) whose character c has no {E114}/{E16F}/{E13A}/
{E13B} earlier in the SAME string (first argument = the character; a
"same string" look-back). The fan's own list is the allowance: the fan has three, in entry 314
string 3 (characters 0, 2 and 44, right after a room load), and they are the
fan's, so they are allowed. BAD is any (entry, string, character) in ours that
is not in the fan's list.

{E14A} has no wait and the fan itself uses it all over without a prior move, so
it is not a BAD condition. Ours-only {E14A} without a prior placement are
printed as information, so a stray companion like entry 183 string 11's old
{E14A}(46) is visible.

    python audits\\audit_dangling_wait.py [built.nds [fan_spt.bin]]

SCOPE - what this does NOT look at:
  * Whether a character was placed in an EARLIER string of the same entry (the
    fan's 314/3 would pass that look-back, 185/1's 65 would not); the
    same-string rule is the one measured against the fan.
  * Any command other than {E14B} for the BAD verdict.
  * Entries or strings that fail to parse (spt.all_strings raises): counted
    and printed, not silently passed.
"""
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

OURS_ROM = _sys.argv[1] if len(_sys.argv) > 1 else _default_built()
FAN_SPT_PATH = _sys.argv[2] if len(_sys.argv) > 2 else _default_fan_spt()

PLACE = (0xE114, 0xE16F, 0xE13A, 0xE13B)   # dangling.py's MOVE set; first argument = character
WAIT = 0xE14B
ACT = 0xE14A


def rs(rom, path):
    fat = struct.unpack_from('<I', rom, 0x48)[0]
    fid = file_id(rom, path)
    a, b = struct.unpack_from('<II', rom, fat + fid * 8)
    return rom[a:b]


def entry(c, i):
    o, s = struct.unpack_from('<II', c, i * 8)
    return c[o:o + s] if s else b''


def scan(cont):
    """(waits, acts, total_waits, parse_failures): waits and acts are sets of
    (entry, string, character) for every {E14B} / {E14A} whose character has
    no placement command earlier in the same string."""
    waits, acts = set(), set()
    total = failures = 0
    n = struct.unpack_from('<I', cont, 0)[0] // 8
    for i in range(n):
        e = entry(cont, i)
        if e[:4] != b' TPS':
            continue
        try:
            strs = [u for _, _, _, u in spt.all_strings(e, True)]
        except Exception:
            failures += 1
            continue
        for j, u in enumerate(strs):
            placed = set()
            k, m = 0, len(u)
            while k < m:
                v = u[k]
                if 0xE000 <= v <= 0xF8FF:
                    a = list(u[k + 1:k + 1 + ARGS.get(v, 0)])
                    if a:
                        if v in PLACE:
                            placed.add(a[0])
                        elif v == WAIT:
                            total += 1
                            if a[0] not in placed:
                                waits.add((i, j, a[0]))
                        elif v == ACT and a[0] not in placed:
                            acts.add((i, j, a[0]))
                    k += 1 + ARGS.get(v, 0)
                else:
                    k += 1
    return waits, acts, total, failures


ROM = open(OURS_ROM, 'rb').read()
SPT = rowfold.fold_spt(rs(ROM, 'jpn/spt.bin'), OURS_ROM)
FAN_SPT = open(FAN_SPT_PATH, 'rb').read()

o_waits, o_acts, o_total, o_fail = scan(SPT)
f_waits, f_acts, f_total, f_fail = scan(FAN_SPT)

bad = sorted(o_waits - f_waits)
print('{E14B} waits: ours %d, fan %d' % (o_total, f_total))
print('{E14B} with no placement earlier in the string: ours %d, fan %d (the fan\'s are allowed)'
      % (len(o_waits), len(f_waits)))
print('fan list: %s' % sorted(f_waits))
print('{E14A} with no placement earlier in the string and not in the fan\'s own list '
      '(information only): %d' % len(o_acts - f_acts))
for x in sorted(o_acts - f_acts)[:20]:
    print('  info entry %d str %d char %d' % x)
print('entries that failed to parse (skipped): ours %d, fan %d' % (o_fail, f_fail))
print('BAD - {E14B} waits on a character never placed in the string, not in the fan: %d' % len(bad))
for i, j, c in bad[:40]:
    print('  entry %d str %d char %d' % (i, j, c))
if len(bad) > 40:
    print('... and %d more' % (len(bad) - 40))
if bad:
    _sys.exit(1)
