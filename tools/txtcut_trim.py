# -*- coding: utf-8 -*-
"""Apply txtcut_condensed.json's hash-guarded word-index edits to a close-up
text row read verbatim from the user's own Collection dump.

This module holds NO game text. A row in txtcut_condensed.json is either a
literal string (an unconverted row - rendered exactly as stored, unchanged
behaviour) or a dict `{'hash', 'ops', 'want'}`: `hash` guards the OFFICIAL row
exactly as tools/txtcut.py reads it before any edit, `ops` are word-index
edits (condense.py's op shape, plus one more this table needs: `['sep', i,
[units...]]`, which replaces word `i`'s own leading gap - its separator run,
never a character - with exactly the given run of space/newline units; pure
re-flow for the Organizer's Back button, never a wording change), and `want`
is a REQUIRED hash of the result (a row missing it falls back, the same as a
hash mismatch - there is no unguarded-result path). A Collection row whose
wording no longer matches `hash` is left exactly as read (verbatim) and
counted as a fallback by the caller, exactly like condense.py/stmt_trim.py.

WORD MODEL. A row is plain text (no DS control codes), so this reuses
tools/stmt_trim.py's `_slots`/`_apply_ops`/`_serialize` unmodified: they only
ever ask `dstext.CTRL(v)`, which is false for every ordinary text codepoint,
and split on runs of space/tab/newline/NUL - exactly the separators a close-up
row uses. `_apply_ops` already handles `del`/`sub`; `sep` ops are applied
SECOND, in their own pass over the RESULT of the `del`/`sub` pass (so their
word index `i` counts the row's words AFTER any deletion/substitution, not
before). This order matters: `del` drops the deleted range's own leading gap
and lets the following kept word's original gap supply the separator
(stmt_trim.py's documented behaviour, correct for the 44 dialogue rows it
already ships), but a close-up row can need the OPPOSITE - the newline (and
any indent spaces after it) that sat on a now-deleted word carried forward
onto the word that used to follow it. Running `sep` after `del`/`sub`,
against the word that actually ends up adjacent, expresses that directly
instead of teaching `del` a second, row-type-specific gap rule. `sep`
replaces the WHOLE gap, not just its first unit, because an indented
continuation line's gap is a newline followed by one unit per indent level -
collapsing that to a bare newline would drop the indent.

BULLET/INDENT SYMBOLS. Two characters, U+25A0 (bullet square) and U+3000
(the ideographic indent space some rows use), sit directly against the word
they mark with no ASCII space in between, so `_slots` would otherwise fuse
them onto that word's own characters - and a `del`/`sub` touching that word
would then have to decide by hand whether the symbol travels with it or
stays. Both are remapped, before `_slots` ever sees them, onto two private-use
codepoints (0xF700/0xF701) that `dstext.CTRL` reports as ordinary
zero-argument control codes; `_slots`/`_apply_ops` then carry them exactly the
way they already carry a real DS control code attached to a deleted or
substituted word - moved whole onto the neighbouring kept word - with no new
logic. The remap is reversed on the way back out, in `_serialize`'s output
only, never in a stored hash or word text.
"""
import hashlib
import dstext
import stmt_trim

_SYM_TO_CODE = {0x25A0: 0xF700, 0x3000: 0xF701}
_CODE_TO_SYM = {v: k for k, v in _SYM_TO_CODE.items()}
_ACCENT_TO_PLAIN = {chr(v): 'e' for v in dstext.ACCENT_SLOTS.values()}


def _key(text):
    # This module's rows are plain close-up text, hashed before any dstext
    # conversion, so the judge's redrawn accent slots (dstext.ACCENT_SLOTS)
    # are not expected here today - but the same guard as stmt_trim.py's
    # _norm_char is applied on principle, so a stored hash can never be made
    # to depend on whether dstext's accent switch happens to be on or off.
    for a, p in _ACCENT_TO_PLAIN.items():
        text = text.replace(a, p)
    return hashlib.sha1(text.encode('utf-8')).hexdigest()[:16]


def _to_units(text):
    return [_SYM_TO_CODE.get(ord(c), ord(c)) for c in text]


def _from_units(units):
    return ''.join(chr(_CODE_TO_SYM.get(v, v)) for v in units)


def _word_text(slot):
    return ''.join(chr(c) for t, c in slot['atoms'] if t == 'char')


def visible(units):
    """Plain text of a row, words joined by a single space - used only for
    hashing/diagnostics, never for reconstruction (see module docstring)."""
    return ' '.join(_word_text(s) for s in stmt_trim._slots(units))


def _set_gap(slot, units):
    """Replace slot's leading gap with exactly `units` (a list of separator
    codepoints), keeping its own characters untouched. Only rewrites a gap
    that already existed (the very first word of a row has none to move a
    line break into, and this table never needs to add one there). Refuses
    (raises ValueError) any requested unit that is not one of stmt_trim's own
    whitespace separators, and refuses a gap that holds a 'code' atom (a
    bullet/indent symbol per the module docstring) - `sep` only ever moves
    whitespace; a symbol's own carrying is stmt_trim._apply_ops's job, not
    this op's, and overwriting a gap that holds one would silently drop it."""
    gap, word = stmt_trim._split_gap_word(slot['atoms'])
    if any(t == 'code' for t, _ in gap):
        raise ValueError('txtcut_trim: refusing to overwrite a gap that holds a code atom')
    bad = [u for u in units if u not in stmt_trim._SEP]
    if bad:
        raise ValueError('txtcut_trim: refusing non-whitespace unit(s) in a sep op: %r' % bad)
    new_gap = [('sep', u) for u in units] if gap else []
    slot['atoms'] = new_gap + word


def apply(row_index, text, row):
    """Return (new_text, status). status is None when `row` is not a dict (a
    literal/unconverted row - `row` itself, the stored string, is rendered,
    exactly as txtcut.py always has); True when the row's source hash matched
    and the edit was applied to the verbatim `text`; False when the source
    hash did not match (a different Collection dump) - `text` is returned
    unchanged (rendered verbatim) and the caller counts a fallback."""
    if not isinstance(row, dict):
        return row, None
    # A row missing its hash or want, or carrying an op kind this engine does not
    # know, falls back and is counted like any other mismatch; it never crashes the
    # build and never ships a partly applied edit.
    if 'hash' not in row or 'want' not in row or _key(text) != row['hash']:
        return text, False
    if any(not op or op[0] not in ('sep', 'del', 'sub') for op in row.get('ops', ())):
        return text, False
    units = _to_units(text)
    try:
        slots = stmt_trim._slots(units)
    except ValueError:
        return text, False
    sep_ops = [op for op in row.get('ops', ()) if op[0] == 'sep']
    word_ops = [op for op in row.get('ops', ()) if op[0] in ('del', 'sub')]
    slots = [dict(atoms=list(s['atoms'])) for s in slots]
    try:
        slots = stmt_trim._apply_ops(slots, word_ops)
        for _, i, gap_units in sep_ops:
            _set_gap(slots[i], gap_units)
        out_units = stmt_trim._serialize(slots)
    except (ValueError, IndexError):
        return text, False
    out = _from_units(out_units)
    want = row.get('want')
    if not want or _key(out) != want:
        return text, False
    return out, True
