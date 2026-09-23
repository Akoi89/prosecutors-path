# -*- coding: utf-8 -*-
"""Trim 44 testimony/rebuttal statements and prompt questions so each fits the
DS engine's single message box (3 lines at the build's own width budget)
instead of wrapping to 4 and being split 2+2 over two boxes - of which the
engine only ever shows the first (rig, entry 92 statement 2, 2026-09-22; the
same defect for prompt questions ending in {E106}, entry 80 str 28).

This table contains NO game text beyond a handful of GENERIC substitute words
(the same convention as tools/condense.py: "was", "prime", "which", and the
like - never a reconstructed sentence). Each row is keyed by (DS entry, string
index) and holds a short hash of the SOURCE - the Collection string's visible
text exactly as inject.py sees it at the hook point, right after
buttons.substitute() and before dstext.convert() - plus word-index edit
operations (deletions and substitutions, condense.py's op shape) and a `want`
hash of the resulting visible text. A Collection dump whose wording differs
from what these rows were built against fails the source hash and the string
is left untrimmed (see `apply`, below); the build log counts that as a
fallback rather than silently shipping a mismatched edit.

VISIBLE TEXT AND HASHING. `visible()` walks the raw pre-convert units the way
dstext.convert()'s own tokenizer does - arity-aware, so a control code's
argument units are never mistaken for text - and applies the SAME two
normalisations convert() applies before anything is wrapped: apostrophes
(ASCII "'" and the Collection's U+2019) fold to the ROM's own curly form
(dstext.APOS, U+201D) and a run of three or more periods folds to that many
copies of the ROM's ellipsis glyph (dstext.ELLIPSIS_UNIT, U+2025 - convert()
does this same fold on its OUTPUT stream after layout, on the fullwidth form;
here it is done on the plain codepoints before layout, which is equivalent
for a run that never straddles a wrap). This is what the private review
file's "original" and "final" fields already look like (read back from the
build / approved by the maintainer; the file is kept outside this repo), so
a row's `hash` and `want` are computed against exactly that text. `visible()`
is used ONLY for hashing/word-matching - never for reconstruction (see next).

MESSAGE SEAMS - WHY RECONSTRUCTION CANNOT RE-DERIVE OUTPUT FROM 'chars'.
A prompt-question string (DELTA 4) packs several separate messages into one
raw unit stream, and Capcom's source runs one straight into the next with NO
whitespace at all - only control codes sit between them, e.g. a made-up but
representative shape, "...word?{E040}{E106}{E163}...Next..." (the real case
is entry 26 str 34; no row's actual wording appears in this file - see
STMT_TRIM's `hash`/`want` fields, not plaintext). Split on whitespace,
"word?" and "Next" are ONE slot: a control code BETWEEN two characters of
what _slots() treats as a single word. An earlier version of this module
bucketed a slot's codes into LEAD (before its first character) and TRAIL
(after its last) and rebuilt output as LEAD + all-characters-in-one-run +
TRAIL; for a seam slot that reorders the stream, since every character got
emitted together BEFORE the trailing codes, regardless of a code having sat
between them originally - "word?Next{E040}{E106}" instead of
"word?{E040}{E106}Next". The box-end code ({E106}) is a control code, so this
silently moved the NEXT message's first word into the PREVIOUS message's box
on every seam in every one of the 16 prompt strings (found 2026-09-23,
comparing check_idxargs_d4.nds box-by-box against the fan; the 28 DELTA 3
statement rows were unaffected because a lone statement has no message seams).

A second, narrower bug survived the first fix: the GAP between two words can
itself hold more than one unit - two or more whitespace units in a row, or a
control code sandwiched BETWEEN two whitespace units (e.g. a mid-string pause
code between a paragraph's trailing space and its newline) - and a version of
`_slots()` that kept only the LAST whitespace unit seen before each word lost
every earlier one: a run of spaces collapsed to one, a newline-after-space
lost the space, and leading or trailing whitespace on the whole string
vanished outright, while a code caught between two whitespace units was
re-emitted AFTER both instead of in its original position. Measured against
the strings the hook actually sees (counts below), 127 failed a
split-and-rejoin identity check (`_serialize(_slots(u)) == u` with no ops
applied) this way, 3 of them among the 44 approved rows (167|5, 235|6,
303|2 - all whitespace-only differences; nothing was dropped or reordered
badly enough to change what any of the 44 approved edits produced, since none
of the three differences fell inside an edited word's own gap, but the
underlying representation was still wrong and had to be fixed on principle).
(The hook sees 10,130 strings per build; 4,369 of them contain at least one
word and can be split at all - the rest are empty, whitespace-only or made
only of control codes, which `_slots()` refuses. The 127 failures were among
those 4,369.)

THE FIX (both bugs, one representation). `_slots()` now returns a single
ordered list of slots, where EVERY slot's 'atoms' list holds THREE kinds of
atom - ('sep', unit), ('code', unit-list) or ('char', codepoint) - in EXACTLY
the order they appeared in `units`. A slot's atoms are its OWN leading gap
(every whitespace and control-code unit since the end of the previous word,
or since the start of the string) followed by its own characters (with any
control code attached directly to them, no separator in between - the seam
case above). There is no separate "gap" or "separator" data structure and no
single-unit shortcut: the gap is however many atoms it actually took, stored
in full, in order. `_serialize()` simply concatenates every slot's atoms,
in order, with NOTHING synthesised for slots it does not touch - which is
what makes an untouched slot (seam or not, single space or a run of three)
reproduce the exact original units. Only a slot INSIDE an edited op's word
range is rebuilt: make_stmt_trim.py's guards (see its docstring) refuse to
build any row whose ops touch a seam slot or a box-end code, so `_apply_ops`
never has to decide how to re-order a code around characters, or around a
box boundary, within one of its own edits - it only ever has to move a
targeted range's WHOLE code set (in original relative order, gap codes and
word-attached codes alike) to a neighbouring kept slot, exactly as before.

WORD OPS. Ops are condense.py's shape - ['del', a, b] drops words [a, b) of
the ORIGINAL word list (split on whitespace); ['sub', a, b, [...]] replaces
that range with the given words. Deleting a range of slots concatenates every
CODE atom in that range - including any that sat in a slot's own leading gap,
not just ones directly touching a character - in original order, and prepends
them to the following kept slot's atoms (or appends them to the preceding
kept slot's atoms, if the deletion runs to the end of the string); the
range's own leading gap is otherwise discarded (its whitespace, not its
codes) since the following kept slot's own leading gap already supplies the
separator needed at the new join - EXCEPT when the deletion starts at word 0:
there the string's original leading gap is kept and the following kept word's
own separators are dropped (its codes kept), so the result never gains a
leading space. Substituting a range keeps the FIRST
replacement word's leading gap as the range's own original leading gap
(preserving whatever separator led into the edit unchanged) and prepends the
same moved-codes bundle to the first replacement word's own characters -
UNLESS the range runs to the end of the string, in which case the bundle can
be the string's own closing control sequence and must stay last, so it is
appended after the last replacement word's characters instead (found the
hard way: entry 265's sub() at the very last word first put the box
terminator in FRONT of "them."). Separators BETWEEN two freshly substituted
replacement words are synthesised, as plain 0x20; the gap AFTER the whole
edited range (the following kept slot's own leading gap) is never touched.
Apostrophes, quotes and ellipses are compared in normalised form via
`visible()`/`_slot_word()` for hashing and word matching only; a replacement
word's own characters are stored as typed (dstext.convert(), which runs
immediately after this hook, applies the same apostrophe/ellipsis
normalisation to the whole string regardless, so nothing here needs to
pre-empt it). For all 44 rows in this table the result was verified unit for
unit against the approved text after conversion, every message NOT holding
the edited words was verified byte-identical to the string before the edit,
and all 4,369 hook strings that contain a word (of 10,130 the hook sees)
pass the split-and-rejoin identity check with the fixed `_slots()`/
`_serialize()`, with 0 failures (see the DELTA 4 rework checks).
"""
import hashlib
import dstext

STMT_TRIM = {
    # Generated by a maintainer-side script (kept outside this repo) from a
    # private review file of approved wording; only the edit table lands here.
    # Row shape: (entry, string): {'hash': <source hash>, 'ops': [...], 'want': <result hash>}
    (8, 1): {'hash': 'e004facd6265bd11', 'ops': [['sub', 10, 15, ['contradicts']]], 'want': '4940267d4fb462cb'},  # p8|1
    (9, 6): {'hash': '8878ec7a0877cbd7', 'ops': [['del', 6, 9]], 'want': 'de1c0a4a2c0d23d4'},
    (9, 22): {'hash': 'baa07810b412bf24', 'ops': [['sub', 5, 7, ['shows']]], 'want': '1a25c3b4ef78d46f'},  # p9|22
    (11, 52): {'hash': 'f56e1e937af6cbed', 'ops': [['del', 2, 3]], 'want': '06a405572cd7da74'},  # p11|52
    (16, 15): {'hash': 'f25beb6fc55182cb', 'ops': [['del', 1, 2]], 'want': '98d4c8854064a5ef'},  # p16|15
    (26, 34): {'hash': '61062d94592c4b04', 'ops': [['sub', 11, 15, ['during']]], 'want': 'c8198340499bd928'},  # p26|34
    (62, 5): {'hash': '0484855425f1b875', 'ops': [['del', 7, 10]], 'want': 'ceddcf2d0a9a9a7b'},
    (74, 9): {'hash': '12ac1030d1cd2d0e', 'ops': [['del', 2, 3]], 'want': '71932d274abacddf'},
    (80, 28): {'hash': '36539738d18fe433', 'ops': [['del', 7, 8]], 'want': 'd41ca3b187ae058a'},  # p80|28
    (92, 5): {'hash': 'd6b210f9dcd57155', 'ops': [['sub', 1, 5, ['while']]], 'want': '5dd5d64c4723b2bd'},
    (94, 1): {'hash': 'e23cf5188a752e5c', 'ops': [['del', 1, 3]], 'want': '1d4826e3b8be9e64'},  # p94|1
    (94, 9): {'hash': '61e041eb22ca4a27', 'ops': [['sub', 8, 12, ['at', 'will,']]], 'want': '1d374b1570ae97ba'},  # p94|9
    (95, 5): {'hash': '1780b1e61d24e653', 'ops': [['del', 7, 10], ['del', 13, 14]], 'want': '4296d8cc9b7d5108'},
    (98, 4): {'hash': 'aefe392db95ccd54', 'ops': [['sub', 11, 14, ['plan.']]], 'want': 'f95bf6109d9c4671'},
    (112, 10): {'hash': '40da382ea546e498', 'ops': [['del', 147, 151]], 'want': 'd6f8c3464571d26d'},  # p112|10
    (117, 35): {'hash': '0deb56e83a1132e5', 'ops': [['del', 6, 8]], 'want': 'ad151bc5f7e40993'},  # p117|35
    (127, 5): {'hash': '4657611f21169899', 'ops': [['sub', 15, 16, ['prime']]], 'want': 'cc54e41010b53e0d'},
    (134, 9): {'hash': '86177b071672bb73', 'ops': [['del', 7, 9]], 'want': '3ab657df9b70d746'},
    (148, 5): {'hash': '296db8ff8680e779', 'ops': [['sub', 12, 16, ['which']]], 'want': '2162b7bec73d6cb3'},
    (160, 14): {'hash': '2534c8e822ec9c8f', 'ops': [['del', 1, 3]], 'want': '0c05f78b3b114559'},  # p160|14
    (167, 5): {'hash': '0ce91aee817504d8', 'ops': [['del', 3, 6]], 'want': 'be4266210bf1d377'},
    (168, 4): {'hash': 'ab7f38e92dd2751b', 'ops': [['del', 14, 15]], 'want': 'bc14c42cc3bd69a0'},
    (182, 4): {'hash': 'cc8388ba617a1255', 'ops': [['del', 10, 11]], 'want': '6d6f96963a5af899'},
    (182, 7): {'hash': '211b114baf03bca2', 'ops': [['del', 7, 9]], 'want': 'd531d0711ef228ee'},
    (183, 7): {'hash': '73551130e2fdc80f',
               'ops': [['sub', 8, 10, ['making']], ['sub', 12, 14, ['serving']],
                       ['sub', 16, 18, ['everybody.']]],
               'want': '2d48fe79a0684d10'},
    (189, 9): {'hash': 'ebf466a52e55a349', 'ops': [['del', 4, 5], ['del', 13, 14]], 'want': 'ad2cb31bcf9b5ee4'},
    (193, 4): {'hash': 'f4300fc0227f5871', 'ops': [['del', 6, 7]], 'want': 'a57fc0b403ee09c7'},
    (199, 15): {'hash': 'cf0d4725ccc69f0d', 'ops': [['del', 22, 23]], 'want': '9184d7137242cb1f'},  # p199|15
    (219, 4): {'hash': '042e5ab0dd9e1b4a', 'ops': [['sub', 10, 12, ['else!']]], 'want': 'e93018823a9f3817'},
    (233, 7): {'hash': 'a2189a3bffae331d', 'ops': [['sub', 3, 4, ['this']], ['del', 5, 8]], 'want': 'c03bcf83c06ee0cc'},
    (235, 3): {'hash': '71dbe6b93673f374', 'ops': [['del', 4, 5], ['sub', 12, 13, ['real']]], 'want': 'dcaa1b0951c80e55'},
    (235, 5): {'hash': '63b87587db7de220', 'ops': [['sub', 0, 2, ['If']], ['sub', 5, 8, ['right,']]], 'want': '49e2a21ed260a0a1'},
    (235, 6): {'hash': 'c00ffa8286d96da1', 'ops': [['del', 5, 8]], 'want': 'ca665e75df617526'},
    (242, 6): {'hash': 'b2df3f8ad9e922be', 'ops': [['del', 7, 9]], 'want': 'c94975c9f72f221d'},
    (246, 3): {'hash': 'e2ef9cdac8464181', 'ops': [['del', 11, 12], ['del', 15, 16]], 'want': '7a50f4a7ef36ec7c'},
    (247, 11): {'hash': 'deb2585157c245df', 'ops': [['del', 1, 4]], 'want': 'bd199a57aa6d1e33'},  # p247|11
    (265, 5): {'hash': '918e1ca22cb8d20e', 'ops': [['sub', 17, 20, ['them.']]], 'want': '89db319214b709e3'},
    (302, 3): {'hash': '72365777e31dce77', 'ops': [['sub', 11, 16, ['my', 'kit.']]], 'want': '3c884e26bd9c60be'},
    (303, 2): {'hash': 'b3a32b167f44bda3', 'ops': [['del', 5, 7]], 'want': '308eb2c538b59f4c'},  # p303|2
    (310, 21): {'hash': '3de47732310deeb5', 'ops': [['del', 6, 7]], 'want': '203d36d44e17e40f'},  # p310|21
    (312, 7): {'hash': '35c6b891384a618c',
               'ops': [['sub', 11, 12, ['stage']], ['sub', 16, 20, ['everyone', 'off.']]],
               'want': 'e2d7f9b9371f7eb3'},
    (324, 4): {'hash': '4cb297e479f13845', 'ops': [['sub', 0, 2, ['Think']]], 'want': 'dccdc834842364d6'},
    (327, 3): {'hash': '8331e618dfe79eda', 'ops': [['del', 15, 17]], 'want': '5bb63bb8ea8eebce'},
    (391, 1): {'hash': 'a57cb3a4b8cc7c98', 'ops': [['del', 1, 3]], 'want': '87f3d8329f56fe7c'},  # p391|1
}

_SEP = (0x20, 0x09, 0x0A, 0x00)


def _key(text):
    return hashlib.sha1(text.encode('utf-8')).hexdigest()[:16]


def _fold_ellipsis(chars):
    """Runs of 3+ ASCII/fullwidth periods fold to that many
    dstext.ELLIPSIS_UNIT - the same rule dstext.convert() applies to its
    output stream after layout, applied here to plain codepoints before
    layout (equivalent for a run that never straddles a wrap)."""
    out, i, n = [], 0, len(chars)
    while i < n:
        v = chars[i]
        if v in (0x2E, 0xFF0E):
            j = i
            while j < n and chars[j] in (0x2E, 0xFF0E):
                j += 1
            if j - i >= 3:
                out.extend([dstext.ELLIPSIS_UNIT] * (j - i))
            else:
                out.extend(chars[i:j])
            i = j
        else:
            out.append(v); i += 1
    return out


def _norm_char(v):
    """One character unit's normalised codepoint (apostrophe/quote only - the
    ellipsis fold is applied separately, in _slot_chars). Used ONLY to build
    the word text _slot_word()/visible() compare and hash - never to alter
    what _serialize() writes out for an untouched slot (see module
    docstring). Every straight quote maps to dstext.DQ_OPEN, which is only
    right because dstext uses the same glyph for opening and closing quotes
    (DQ_OPEN == DQ_CLOSE)."""
    if v == 0x22:
        return dstext.DQ_OPEN
    if v in (0x27, 0x2019):
        return dstext.APOS
    return v


def _slots(units):
    """Split raw pre-convert units into a list of slots, one per
    whitespace-delimited word: {'atoms': [...]}. An atom is ('sep', unit),
    ('code', unit-list) or ('char', codepoint), IN THE EXACT ORDER they
    appeared in `units`. A slot's atoms are its OWN LEADING GAP - every
    whitespace unit and every control code seen since the end of the
    previous word (or since the very start of the string), IN FULL, not just
    the last one - followed by its own characters, with any control code
    attached directly to a character (no separator in between - the
    message-seam case in the module docstring) interleaved in place. Trailing
    whitespace/codes after the very LAST word, with no further word to carry
    a leading gap, land as trailing atoms of the LAST slot instead (same walk,
    no special-casing). `_serialize()` can replay the full slot list and
    reproduce `units` exactly, because nothing about a gap - how many
    separators it had, which kind, or a code's exact position inside it - is
    ever discarded or replaced by a single stand-in unit."""
    slots, cur, gap = [], None, []
    i, n = 0, len(units)
    while i < n:
        v = units[i]
        if dstext.CTRL(v):
            code = list(units[i:i + 1 + dstext.ARGS.get(v, dstext.DEFAULT_ARGS)])
            i += len(code)
            if cur is None:
                gap.append(('code', code))
            else:
                cur['atoms'].append(('code', code))
            continue
        if v in _SEP:
            if cur is not None:
                slots.append(cur); cur = None
            gap.append(('sep', v))
            i += 1
            continue
        if cur is None:
            cur = {'atoms': gap}
            gap = []
        cur['atoms'].append(('char', v))
        i += 1
    if cur is not None:
        slots.append(cur)
    if gap:
        if slots:
            slots[-1]['atoms'] = slots[-1]['atoms'] + gap
        else:
            # no word at all in this string - not reachable by any of the
            # 44 rows; nothing sensible to attach the codes to.
            raise ValueError('stmt_trim: no words to attach control codes to')
    if not slots:
        raise ValueError('stmt_trim: no words in this string')
    return slots


def _split_gap_word(atoms):
    """Split one slot's atoms into (leading gap, word-own atoms): everything
    before the first 'char' atom, and the first 'char' atom onward. Every
    real slot has at least one 'char' atom (that is what starts it)."""
    for i, (t, _) in enumerate(atoms):
        if t == 'char':
            return atoms[:i], atoms[i:]
    return atoms, []  # unreachable for a real slot; kept defensive


def _has_seam(slot):
    """True if a control code sits BETWEEN two characters of this slot - a
    message seam (module docstring). make_stmt_trim.py refuses to build any
    row whose ops touch such a slot; _apply_ops therefore never has to decide
    how to re-order codes around characters within one of its own edits."""
    char_idx = [i for i, (t, _) in enumerate(slot['atoms']) if t == 'char']
    if not char_idx:
        return False
    first, last = char_idx[0], char_idx[-1]
    return any(slot['atoms'][i][0] == 'code' for i in range(first, last + 1))


def _slot_chars(slot):
    """Normalised word text for this slot (character atoms only, apostrophe
    and ellipsis folded) - used for word matching and visible()/hashing.
    NEVER used for reconstruction; see _serialize."""
    raw = [_norm_char(v) for (t, v) in slot['atoms'] if t == 'char']
    return _fold_ellipsis(raw)


def _slot_word(s):
    return ''.join(chr(c) for c in _slot_chars(s))


def visible(units):
    """Plain visible text of a raw (pre-convert) unit list, normalised the way
    dstext.convert() would present it once built: control codes are skipped,
    apostrophes fold to dstext.APOS, runs of 3+ periods fold to that many
    dstext.ELLIPSIS_UNIT, and any run of whitespace/NUL between words
    collapses to one space - the same soft-space treatment dstext.convert()
    gives a source newline not followed by {E20D} (dstext.py's `hard_nl`).
    Built from the SAME word split _slots()/apply() use, so a row's ops line
    up with visible(...).split() by construction. Matches
    private review file's "original"/"final" text exactly."""
    return ' '.join(_slot_word(s) for s in _slots(units))


def _apply_ops(slots, ops):
    """Apply condense.py-shaped ops to the slot list. Returns a new list.
    Only slots inside an edited op's [a, b) range are rebuilt; every other
    slot keeps its own 'atoms' object untouched (copied, not mutated, so a
    caller holding the pre-edit list is unaffected)."""
    slots = list(slots)
    off = 0
    for op in ops:
        if op[0] == 'del':
            a, b = op[1] + off, op[2] + off
            gap_a, word_a = _split_gap_word(slots[a]['atoms'])
            moved = [atom for atom in gap_a if atom[0] == 'code']
            moved += [atom for atom in word_a if atom[0] == 'code']
            for s in slots[a + 1:b]:
                moved += [atom for atom in s['atoms'] if atom[0] == 'code']
            if b < len(slots) and a == 0:
                # Deleting from the very first word: the following kept word now
                # starts the string, so its own leading whitespace must not become
                # a leading space. Keep the string's ORIGINAL leading gap (gap_a,
                # whitespace and codes as they were), then every code from the
                # deleted words, then the kept word's own gap CODES (its separators
                # are dropped), then its characters. No code is lost or reordered
                # relative to the others it travelled with.
                nxt = dict(slots[b])
                ngap, nword = _split_gap_word(nxt['atoms'])
                deleted_codes = [atom for atom in word_a if atom[0] == 'code']
                for s in slots[a + 1:b]:
                    deleted_codes += [atom for atom in s['atoms'] if atom[0] == 'code']
                nxt['atoms'] = (list(gap_a) + deleted_codes
                                + [atom for atom in ngap if atom[0] == 'code'] + nword)
                slots[b] = nxt
            elif b < len(slots):
                nxt = dict(slots[b])
                nxt['atoms'] = moved + nxt['atoms']
                slots[b] = nxt
            elif a > 0:
                prev = dict(slots[a - 1])
                prev['atoms'] = prev['atoms'] + moved
                slots[a - 1] = prev
            else:
                raise ValueError('stmt_trim: del would empty the string')
            del slots[a:b]
            off -= (b - a)
        elif op[0] == 'sub':
            a, b, words = op[1] + off, op[2] + off, op[3]
            gap_a, word_a = _split_gap_word(slots[a]['atoms'])
            moved = [atom for atom in word_a if atom[0] == 'code']
            for s in slots[a + 1:b]:
                moved += [atom for atom in s['atoms'] if atom[0] == 'code']
            new_slots = []
            for wi, w in enumerate(words):
                chars = [('char', c) for c in _fold_ellipsis([ord(ch) for ch in w])]
                # The range's OWN leading gap (whatever separator led into the
                # edit) stays on the first replacement word, unchanged;
                # between multiple replacement words a plain space is
                # synthesised, since no original separator exists there.
                lead = list(gap_a) if wi == 0 else [('sep', 0x20)]
                new_slots.append({'atoms': lead + chars})
            # The moved bundle's last piece can be the STRING'S OWN closing
            # sequence (when b == len(slots), the last deleted slot's trailing
            # atoms are whatever follows the very last character of the
            # string). That must stay at the very end, not jump in front of
            # the replacement words - append to the LAST new slot's atoms
            # there; otherwise (a kept word still follows) prepend to the
            # FIRST new slot's own characters (after its preserved gap).
            if b < len(slots):
                first_gap, first_word = _split_gap_word(new_slots[0]['atoms'])
                new_slots[0]['atoms'] = first_gap + moved + first_word
            else:
                new_slots[-1]['atoms'] = new_slots[-1]['atoms'] + moved
            slots[a:b] = new_slots
            off += len(words) - (b - a)
        else:
            raise ValueError('stmt_trim: unknown op %r' % (op,))
    return slots


def _serialize(slots):
    """Concatenate every slot's atoms, in order. Nothing is synthesised for a
    slot outside an edited range: it still holds its ORIGINAL atoms (see
    _slots/_apply_ops) - every whitespace unit, in the order it appeared,
    plus any control code that sat between two characters or between two
    whitespace units - so this reproduces the source bytes for it exactly."""
    out = []
    for s in slots:
        for (t, v) in s['atoms']:
            if t == 'code':
                out += v
            else:
                out.append(v)
    return out


def apply(entry, string_index, units):
    """Return (new_units, status). status is None when this (entry, string)
    has no row (units passed through unchanged, not counted); True when the
    row's source hash matched and the trim was applied; False when the source
    hash did not match (a different Collection dump) - units are left
    untouched and the caller counts a fallback."""
    row = STMT_TRIM.get((entry, string_index))
    if row is None:
        return units, None
    try:
        src = visible(units)
    except ValueError:
        return units, False
    if _key(src) != row['hash']:
        return units, False
    try:
        slots = _slots(units)
        slots = _apply_ops(slots, row['ops'])
        out = _serialize(slots)
    except ValueError:
        return units, False
    want = row['want']
    if want and _key(visible(out)) != want:
        return units, False
    return out, True
