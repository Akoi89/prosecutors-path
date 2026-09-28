# -*- coding: utf-8 -*-
"""One row Capcom's own matcher mapped to the wrong Collection file entirely.

DS[213] str3 (Ep4): Kay, her memory gone, turning down a gift Edgeworth offers
her. The build's own name-similarity matcher points bank 213 at
'sce3_c0_m20_npc' (score 0.9439); the real match, found by pivoting through the
JP retail text, is a different file: dump/eng/sce3_c0_01.bin#4 (JP `…申しわけあ
りません。そのようなものを頂けるほど、あなたのこと、覚えていないのです。` -> EN
"...I'm sorry." / "I don't remember you well enough to accept a gift like that
just yet."). The fan's own string was left as an untranslated stub ("Test" +
leftover Japanese). Only the first two message boxes of that Collection string
are used - the Collection string continues into a THIRD box for a different
speaker's reply that this entry has no room for (str4 onward are all empty;
porting further would invent content this entry never had).

A DROPPED ROW (2026-09-28 rework): DS[36] str37 was ported in the first round
and is REMOVED here - refuted as unreachable. JP retail entry 36 str33 is the
room's own examine/hotspot table ({E165} header, four {E168} <hotspot, target
string> pairs, one {E169} default): hotspot 1 points at string 36 only.
Nothing else in the script - no {E12E} jump, no other command, in either the
fan or the JP retail copy - targets string 37. Capcom's own Collection file
leaves the matching slot (str37) hollow too, consistent with a slot neither
side's engine ever reads.

THE FAN TAIL (2026-09-28 rework, refuter catch): this entry's str3 carries a
fan tail - 0xE102 sitting in the terminator slot, past the string's declared
length, the 1.8.3 Bound/Larry class (see spt.tails()/build_ds(tails=...) in
patch_entry below). The fan's own body NEVER puts a closing {E102} at the very
end of a string whose tail already supplies one - checked against the OTHER
8 strings in the whole script whose tail is exactly [0xE102] (entries 14, 339,
341, 342, 345, 351, 352, 353): not one of their bodies ends in {E102} either.
The first round's port broke that convention (Capcom's own two-box translation
naturally closes its second box with {E102}), shipping a body that ended
...{E102} immediately followed by the tail's own {E102} - a redundant
double-close. Fixed by dropping just that one trailing unit: the ported body
keeps the INTERNAL {E102} that separates box 1 from box 2 (structurally
required - two real boxes are shown), but ends on the second box's own last
text unit, exactly like the fan's original single-box string did, and lets the
tail alone close it.

CONSTRUCTION (not re-derived at build time, only the hash and the final unit
list are baked in here, same discipline as tools/linefix.py): the Capcom source
was run through dstext.convert() with the SAME real per-glyph advances
inject.py itself loads from the fan ROM before anything is converted, then
spliced onto the FAN'S OWN leading non-text codes (the portrait/animation
arguments before the first {E107} - DS platform values, not text, the class
tools/inject.py's INDEX_ARGS/DS_VALUE_ARGS tables exist to protect). No
camera/pose-family code ({E13A}/{E13B}/{E16F}/{E114}/{E15B}/{E150}) is present,
so no staging restoration was needed.

A row applies only when the fan's existing unit stream for that (entry,
string) still hashes to what this table was built against, and the
constructed replacement is verified against its own hash before shipping.
Either mismatch leaves the row exactly as it already was.
"""
import hashlib
import os
import struct
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from spt import all_strings, parse, tails as spt_tails
from build_spt import build_ds

LAST_ROWS = {
    (213, 3): {
        'hash': 'b351c058153f34f1',
        'units': [57646, 4, 3105, 1, 4, 57600, 0, 57647, 35, 3, 57601, 35, 62, 57607, 2, 8229, 8229, 8229, 65321, 8221, 65357, 65343, 65363, 65359, 65362, 65362, 65369, 65294, 57602, 57601, 35, 62, 57607, 2, 65321, 65343, 65348, 65359, 65358, 8221, 65364, 65343, 65362, 65349, 65357, 65349, 65357, 65346, 65349, 65362, 65343, 65369, 65359, 65365, 65343, 65367, 65349, 65356, 65356, 65343, 65349, 65358, 65359, 65365, 65351, 65352, 10, 65364, 65359, 65343, 65345, 65347, 65347, 65349, 65360, 65364, 65343, 65345, 65343, 65351, 65353, 65350, 65364, 65343, 65356, 65353, 65355, 65349, 65343, 65364, 65352, 65345, 65364, 65343, 65354, 65365, 65363, 65364, 65343, 65369, 65349, 65364, 65294],
        'want': '0ad0365aff8c1c3f',
    },
}


def _key(units):
    return hashlib.sha1(struct.pack('<%dH' % len(units), *units)).hexdigest()[:16]


def apply(entry, string_index, units):
    """Return (new_units, status). status is None when this (entry, string) has
    no row (units unchanged, not counted); True when the fan source hash matched
    and the port was applied; False when the source hash did not match (a
    different build of this row) - units are left untouched and the caller
    counts a fallback."""
    row = LAST_ROWS.get((entry, string_index))
    if row is None:
        return units, None
    u = list(units)
    if _key(u) != row['hash']:
        return units, False
    new = list(row['units'])
    if _key(new) != row['want']:
        return units, False
    return new, True


def patch_entry(entry_id, entry_bytes):
    """Apply every LAST_ROWS row that belongs to this entry. Returns
    (new_bytes, applied, fallback); every existing string's tail (spt.tails) is
    carried over unchanged, including strings this module does not touch -
    see the module docstring on DS[213] str3's fan tail."""
    rows = [si for (ei, si) in LAST_ROWS if ei == entry_id]
    if not rows or not entry_bytes or entry_bytes[:4] != b' TPS':
        return entry_bytes, 0, 0
    h = parse(entry_bytes, True)[0]
    ftails = spt_tails(entry_bytes, True)
    S = list(all_strings(entry_bytes, True))
    changed = fallback = 0
    new = []
    for si, a, _ln, u in S:
        nu, status = apply(entry_id, si, u) if si in rows else (u, None)
        new.append((a, list(nu)))
        if status is True:
            changed += 1
        elif status is False:
            fallback += 1
    if not changed:
        return entry_bytes, 0, fallback
    keep = [t if any(t) else None for t in ftails]
    return build_ds(new[0][1], new[1:], h['term'], h['scale'], h['last'], keep), changed, fallback
