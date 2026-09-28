# -*- coding: utf-8 -*-
"""Guard 13 unguarded animated character entrances against a B-skip freeze.

An animated character entrance is issued with {E111 c,a2,slot,xpreset,mode,
speed} (c = the character id; non-zero mode/speed selects a fade-in or a
slide). Every one of this engine's actor-positioning commands for a character
(E111 itself, E112, E113, E122, E12F, E152) writes that character's SINGLE
task slot unconditionally - there is no queue, so whichever of these commands
is issued for a character LAST simply replaces whatever animation was already
running for them, even a slide or fade that has not finished playing. 4,188 of
the game's 4,221 animated entrances are followed by {E112 c} - a wait for that
character's task to finish - before the surrounding text box's next line, so
the next box's own actor commands never fire until the entrance has actually
completed. 33 are not, and it is the SAME 33 in the fan ROM and ours: this is
Capcom's own script, not something lost in translation. Of those 33, a held B
can flush the box in front of one fast enough that the NEXT box's own actor
command for that same character reaches the engine before the entrance's
animation frames have elapsed, overwriting the task slot and freezing the
sprite mid-move - the reported defect: entry 119 string 3 box 1 leaves
Edgeworth at x ~ -100, only his sleeve on screen.

This module guards:
  - the 9 unguarded entrances that are SLIDES (the visible failure is a
    character frozen off to one side of the screen), and
  - 4 of the unguarded fade-ins whose killer command (the next
    actor-positioning command issued for that same character) sits in the
    SAME box as the entrance, so reaching the failure does not need a skip
    fast enough to outrun a whole box of dialogue - only fast enough to beat
    the fade's own handful of frames:
      - 69/19, 74/19, 95/17: the killer fires before any text is shown in the
        box at all, so these three are reachable close to ordinary play, not
        only under a held B.
      - 114/8: the killer fires after the box's text, on a short (5-frame)
        fade; ordinary pacing usually lets the fade finish before a player
        advances past the text, but a held B can still flush the box inside
        those 5 frames.
A fifth same-box fade-in that Capcom's own script also leaves unguarded,
76/13, is NOT included here: in this build's own text layout (a side effect of
re-lineating the dialogue to fit English) its killer command ends up in a
LATER box than the entrance, so this build's copy of that string no longer
meets the same-box rule this module targets. The remaining 19 unguarded
fade-ins in the game are untouched entirely: a skipped fade-in there is only
ever briefly translucent, never frozen off-position, because their killer
command is not in the same box as the entrance at all.

Same hash-guard discipline as tools/linefix.py, simplified for an INSERTION
rather than a same-width edit: {E112 c} (2 units) is spliced in at a fixed
unit-index position, only when the target string's unit stream still hashes to
exactly what this table was built against. For every site but one, c is that
entrance's own first argument and the insertion point sits right after its
{E111}. The one exception is 69/19: Capcom already issues TWO entrances back
to back there (character 0's fade-in immediately followed by character 19's,
then {E112 19} waiting for character 19 alone) - inserting {E112 0} between
the two entrances would force them to fade in one after the other instead of
together, so its insertion point is placed right after the EXISTING
{E112 19}, preserving the paired-entrance shape and only adding the missing
second wait. A hash mismatch at any site leaves that string untouched and is
counted (and named) as a fallback, never a silent partial apply. No game text
is stored here, only unit-index positions and a hash of the unit stream.

INSERTION DOES NOT SHIFT ANY STRING-INDEX OR JUMP ARGUMENT: every control-code
argument in this engine that names another string, box or entry is a POSITION
IN A TABLE (a string index, a slot id, a graphic id), never a byte offset into
the unit stream being edited - splicing two units into one string's own stream
could only ever skew a byte-offset-valued argument, and this engine has none.
The splice changes only that ONE string's own length; spt's build_ds
recomputes only that string's own offset record, and every other string's
units, in this entry and every other entry, are left exactly as they were.
"""
import hashlib
import struct
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from spt import all_strings, parse, tails as _spt_tails
from build_spt import build_ds

# (entry, string index): {'hash': <source unit-stream hash>, 'char': <actor id
#  the spliced {E112} waits for>, 'insert_at': <unit index to splice at>,
#  'want': <result unit-stream hash>}.
# The 9 slide-ins:
SKIPGUARD = {
    (9, 29):    {'hash': 'f9c1abc677f2d2a1', 'char': 1,  'insert_at': 1017, 'want': 'f0ad4b325288884a'},
    (119, 3):   {'hash': '74cf9e2179181b80', 'char': 0,  'insert_at': 87,   'want': '68919c1ac02f71d2'},
    (130, 15):  {'hash': '410bc5d1bb96662d', 'char': 33, 'insert_at': 13,   'want': 'f43d6dfc260d51dc'},
    (164, 17):  {'hash': '0e7497dfd385d7b0', 'char': 29, 'insert_at': 84,   'want': '56d2a0341ae526c9'},
    (210, 2):   {'hash': 'a37f1ae58e8e6121', 'char': 35, 'insert_at': 10,   'want': '1efe81a27d3572e7'},
    (213, 1):   {'hash': '0596b2ea0461572e', 'char': 35, 'insert_at': 10,   'want': '67840bf4aa663668'},
    (227, 0):   {'hash': '94f79da4c42d787b', 'char': 10, 'insert_at': 1254, 'want': '941af040c9c99df8'},
    (255, 0):   {'hash': '4cb17278e09d6cfd', 'char': 0,  'insert_at': 1038, 'want': 'c4a99d403ee2fe20'},
    (356, 2):   {'hash': '25f1a68d84c266eb', 'char': 2,  'insert_at': 461,  'want': 'd5c0bee54fe5356e'},
    # the 4 fade-ins whose killer command shares the entrance's own box:
    # 69/19 splices AFTER the partner's existing {E112 19} - see the module
    # docstring's paired-entrance note.
    (69, 19):   {'hash': '0666161280d1a41b', 'char': 0,  'insert_at': 1049, 'want': '1975398f77cff678'},
    (74, 19):   {'hash': 'fcc4274fb187d4b9', 'char': 0,  'insert_at': 1192, 'want': 'b660cc5ba0e537ab'},
    (95, 17):   {'hash': 'c5491a624d7ed157', 'char': 0,  'insert_at': 2611, 'want': '8a8347200347e364'},
    (114, 8):   {'hash': '854940af340c8bd3', 'char': 9,  'insert_at': 2099, 'want': 'e48fbf3a2b5c36bb'},
}


def _key(units):
    return hashlib.sha1(struct.pack('<%dH' % len(units), *units)).hexdigest()[:16]


def apply(entry, string_index, units):
    """Return (new_units, status). status is None when this (entry, string)
    has no row (units passed through unchanged, not counted); True when the
    row's source hash matched and {E112 char} was spliced in; False when the
    source hash did not match, or the units at `insert_at` are not the shape
    this table expects (a different build of this string) - units are left
    untouched and the caller counts and names a fallback."""
    row = SKIPGUARD.get((entry, string_index))
    if row is None:
        return units, None
    u = list(units)
    if _key(u) != row['hash']:
        return units, False
    pos = row['insert_at']
    if not (0 <= pos <= len(u)):
        return units, False
    nu = u[:pos] + [0xE112, row['char']] + u[pos:]
    if _key(nu) != row['want']:
        return units, False
    return nu, True


def patch_entry(entry_id, entry_bytes):
    """Apply every SKIPGUARD row that belongs to this entry. Returns
    (new_bytes, applied, fallback_sites) - `new_bytes` is entry_bytes
    unchanged and both `applied`/`fallback_sites` are 0/[] when nothing in
    this entry has a row; `fallback_sites` is a list of (entry, string) pairs
    whose hash did not match (tools/linefix.py's own convention: a mismatch is
    reported, not silently absorbed into "0 changed" - named here, not just
    counted, so a stale row can be found without re-deriving it). The
    string-terminator tail units (spt.tails - a live command argument can sit
    there, not just a 0) are read from the SOURCE entry and carried through
    unchanged into the rebuilt entry, exactly like every other string in it
    that this module does not touch."""
    rows = [si for (ei, si) in SKIPGUARD if ei == entry_id]
    if not rows or not entry_bytes or entry_bytes[:4] != b' TPS':
        return entry_bytes, 0, []
    h = parse(entry_bytes, True)[0]
    keep = _spt_tails(entry_bytes, True)
    S = list(all_strings(entry_bytes, True))
    changed = 0
    fallback_sites = []
    new = []
    for si, a, _ln, u in S:
        nu, status = apply(entry_id, si, u) if si in rows else (u, None)
        new.append((a, list(nu)))
        if status is True:
            changed += 1
        elif status is False:
            fallback_sites.append((entry_id, si))
    if not changed:
        return entry_bytes, 0, fallback_sites
    return (build_ds(new[0][1], new[1:], h['term'], h['scale'], h['last'], keep),
            changed, fallback_sites)
