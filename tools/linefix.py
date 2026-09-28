# -*- coding: utf-8 -*-
"""Move one wrapped line break by a single word, for a fan-inherited dialogue
line the 2026-09-27 text-box sweep measured over the proven 240px budget
(spt 19/26, 253px).

Same hash-guard discipline as tools/stmt_trim.py, simplified for what this
needs: no word deletion or substitution, only swapping which whitespace unit
in an ALREADY-BUILT row is the line break. A row applies only when its exact
final unit stream still hashes to what this table was built against; the
result is verified against its own hash before shipping. Either mismatch
leaves the row exactly as it already was - a stale table can only fall back
to the pre-fix text, never ship an unverified edit. No game text is stored,
only unit-index positions into a hashed stream.

19/26 is fan-inherited dialogue text (kept because the Collection has nothing
usable there) whose line 1 is a fan-authored line already over the real-pixel
budget; the existing kept-fan mechanisms (names.py's ROWFIX/rebreak) do not
reach it, because both are gated behind a NAME substitution actually
happening in that row (harmonize_entry only calls them when `c`, the rename
count, is truthy) and this line renames no character, and rebreak() in any
case measures with dstext._estimate, the WRONG ruler for a budget cut in real
MAIN-table pixels (the model mismatch names.py's own module docstring warns
against). Hence the smallest guarded mechanism the spec calls for, applied
directly to the finished row: swap the space before line 1's final word for
the {0x0A} that currently sits right after that word, and swap that old
{0x0A} back to a space - the break moves one word later, joining the pushed
word onto line 2 instead. No wording is reproduced here; the text this table
was built against is Capcom/fan dialogue already on record elsewhere in the
project's own working notes, not repeated in this file.

A second row (spt 100/32, Capcom's own text, 241px) went through this exact
mechanism until 2026-09-27's rework: traced to a general dstext.convert() gap
(a synthetic closing parenthesis emitted at a box break with no width check)
and fixed at the source in dstext.py instead, so it no longer needs an entry
here - see dstext.py's emit(), the paren-close reservation next to
`PAREN_CLOSE`.
"""
import hashlib
import os
import struct
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from spt import all_strings, parse, tails as _spt_tails
from build_spt import build_ds

LINEFIX = {
    # (entry, string): {'hash': <source unit-stream hash>,
    #                    'edits': [(unit_index, from_value, to_value), ...],
    #                    'want': <result unit-stream hash>}
    (19, 26): {'hash': '66757bff2fcdc7d1',
               'edits': [(299, 0x0A, 0xFF3F), (295, 0xFF3F, 0x0A)],
               'want': '63d807f881ce069a'},
}


def _key(units):
    return hashlib.sha1(struct.pack('<%dH' % len(units), *units)).hexdigest()[:16]


def apply(entry, string_index, units):
    """Return (new_units, status). status is None when this (entry, string)
    has no row (units passed through unchanged, not counted); True when the
    row's source hash matched and the break was moved; False when the source
    hash did not match, or an edit's `from_value` was not what the table
    expects at that index (a different build of this row) - units are left
    untouched and the caller counts a fallback."""
    row = LINEFIX.get((entry, string_index))
    if row is None:
        return units, None
    u = list(units)
    if _key(u) != row['hash']:
        return units, False
    for idx, frm, to in row['edits']:
        if not (0 <= idx < len(u)) or u[idx] != frm:
            return units, False
    for idx, frm, to in row['edits']:
        u[idx] = to
    if _key(u) != row['want']:
        return units, False
    return u, True


def patch_entry(entry_id, entry_bytes):
    """Apply every LINEFIX row that belongs to this entry. Returns
    (new_bytes, applied, fallback) - `new_bytes` is entry_bytes unchanged and
    both counts 0 when nothing in this entry has a row; `fallback` counts a
    row whose hash did not match (stmt_trim.py's own convention: a mismatch
    is reported, not silently absorbed into "0 changed")."""
    rows = [si for (ei, si) in LINEFIX if ei == entry_id]
    if not rows or not entry_bytes or entry_bytes[:4] != b' TPS':
        return entry_bytes, 0, 0
    h = parse(entry_bytes, True)[0]
    keep = _spt_tails(entry_bytes, True)
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
    return (build_ds(new[0][1], new[1:], h['term'], h['scale'], h['last'], keep),
            changed, fallback)
