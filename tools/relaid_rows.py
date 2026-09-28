# -*- coding: utf-8 -*-
"""Lay Capcom's converted words into the FAN's box skeleton, for exactly three
rows the ordinary swap path cannot reach:

  entry 93  str 0  - Ep2 Simon Keyes elephant-stunt scene, fan boxes 0-7 pair
                      one to one with Capcom's; the fan's dead tail (box 8,
                      an {E081:6} jump) is kept verbatim.
  entry 236 str 0  - Ep4 hearing: fan moved the first 10 boxes of JP/Capcom
                      str 1 into str 0, and box 9 replaces a plain {E102} with
                      {E108:C}{E104} so an interrupted line auto-advances into
                      the next speaker's reply - which defeats a plain
                      box-end-multiset recut.
  entry 236 str 1  - the remaining Capcom str 1 boxes (10-55), offset 10
                      throughout.

Both the fan's box structure (leading/trailing codes per box, box-end variant,
staging/index/sound-cue ARGUMENTS, the box 9 auto-advance) and Capcom's own
words are load-bearing here, so this table is hash-guarded exactly like
tools/stmt_trim.py and tools/linefix.py: a row applies only when (a) the fan's
own raw units for that (entry, string) still hash to what this table was built
against, and (b) the Collection source string(s) it pulls words from still
hash to what it was built against. Either mismatch (a different fan ROM or a
different Collection dump) leaves the row completely untouched - the caller's
normal per-string path runs instead, exactly as if this module did not exist.
The result is also hashed and checked against a recorded 'want' before it is
allowed to ship, the same discipline linefix.py uses, so a change to
dstext.convert()'s wrapping or width tables cannot silently ship an unproven
merge; it falls back the same way.

PACING DECISION: Capcom's own {E107}/{E108} pause/pace pairs stay inside
Capcom's words (pacing='capcom'), the same as every other swapped string in
the port; every OTHER non-text command and its arguments - staging, speaker
codes, sound/shake cues, jumps, box structure including the fan's
{E108:C}{E104} auto-advance - equal the fan's exactly.

SOUND/SHAKE CUE PLACEMENT (E188/E1D1/E1D2/E1D5 and any other non-style,
non-pace inline code - the same set this module has always repositioned):
a fan cue is placed in Capcom's converted box by, in order:
  (a) if the fan's cue follows a STUTTER prefix (1-3 letters then a hyphen, at
      a word boundary) and Capcom's OWN words for that box also open with a
      stutter (their own letters, not the fan's), the cue goes right after
      Capcom's stutter hyphen - "I-<cue>Isn't", "Wh-<cue>Whaaat" - regardless
      of what letter either side's stutter uses;
  (b) if the fan's cue sits at the very start of its box (no fan text at all
      before it), it stays at the start;
  (c) if only closing punctuation (or nothing) follows the cue in the fan's
      own box, it goes after Capcom's own closing punctuation, before the box
      end;
  (d) otherwise, proportional placement at the nearest Capcom word boundary
      (the position this module always used, unchanged).
"""
import hashlib
import struct
import collections

import dstext
from dstext import ARGS, RESET, e106_clears

CTRL = lambda v: 0xE000 <= v <= 0xF8FF
STYLE = {0xE040, 0xE041, 0xE042, 0xE043}
PACE = {0xE107, 0xE108}
# The box-end code set, taken from dstext.RESET rather than re-typed, so it
# cannot drift from the set dstext.py's own box splitting uses. It holds the
# same five codes as tools/inject.py's own BOXEND literal; nothing checks the
# two against each other at run time.
BOXEND = set(RESET)
PACING = 'capcom'

# Terminal punctuation: marks that can legitimately close a box with nothing
# real after them (rule (c) below).
_PUNCT = {0xFF01, 0xFF1F, 0xFF0E, 0x2025, 0xFF0C, 0xFF1B, 0xFF1A,
          0x201C, 0x201D, 0xFF08, 0xFF09}


def _hash(units):
    return hashlib.sha1(struct.pack('<%dH' % len(units), *units)).hexdigest()[:16]


def toks(u):
    i, out = 0, []
    while i < len(u):
        v = u[i]
        if CTRL(v):
            n = ARGS.get(v, 0)
            out.append(('c', v, list(u[i + 1:i + 1 + n])))
            i += 1 + n
        else:
            out.append(('t', v))
            i += 1
    return out


def untok(ts):
    out = []
    for t in ts:
        if t[0] == 'c':
            out.append(t[1]); out.extend(t[2])
        else:
            out.append(t[1])
    return out


def split_boxes(u):
    bx = [[]]
    for t in toks(u):
        bx[-1].append(t)
        if t[0] == 'c' and t[1] in BOXEND:
            bx.append([])
    if not bx[-1]:
        bx.pop()
    return bx


def is_text(t):
    return t[0] == 't' and t[1] != 0x0A


def regions(b):
    ti = [k for k, t in enumerate(b) if t[0] == 't']
    if not ti:
        return b, [], []
    return b[:ti[0]], b[ti[0]:ti[-1] + 1], b[ti[-1] + 1:]


def _is_letter(v):
    # A-Z and a-z only, fullwidth or ASCII: the punctuation between the two
    # cases (brackets, backslash, caret, underscore, backtick) is not a letter,
    # and the fullwidth underscore is this script's space (see _is_space).
    return (0xFF21 <= v <= 0xFF3A or 0xFF41 <= v <= 0xFF5A
            or 0x41 <= v <= 0x5A or 0x61 <= v <= 0x7A)


def _is_hyphen(v):
    return v in (0xFF0D, 0x2D)


def _is_space(v):
    return v in (0xFF3F, 0x0A)


def _fan_stutter_positions(fan_chars):
    """Text ordinals (count of preceding is_text units) that sit right after
    a fan stutter prefix - 1-3 letters then a hyphen, starting at the box's
    own start or right after a space/newline. Rule (a)."""
    out = set()
    start = 0
    for i in range(len(fan_chars) + 1):
        if i == len(fan_chars) or _is_space(fan_chars[i]):
            word = fan_chars[start:i]
            for L in (1, 2, 3):
                if len(word) > L and _is_hyphen(word[L]) and all(_is_letter(c) for c in word[:L]):
                    out.add(start + L + 1)
                    break
            start = i + 1
    return out


def _cap_stutter_target(keep):
    """keep-list index right after Capcom's OWN first stutter hyphen (1-3
    letters then a hyphen, at a word boundary), or None if Capcom's box has
    no stutter. Rule (a)'s other half."""
    word, idxs = [], []
    for c, t in enumerate(keep):
        if not is_text(t):
            continue
        v = t[1]
        if _is_space(v):
            word, idxs = [], []
            continue
        word.append(v); idxs.append(c)
        n = len(word)
        if 2 <= n <= 4 and _is_hyphen(word[-1]) and all(_is_letter(x) for x in word[:-1]):
            return idxs[-1] + 1
    return None


def merge_box(A, B, pacing, rep, cue_log=None):
    """Merge one fan box A with one Capcom-converted box B. cue_log, if given,
    is a list this appends (code, rule, keep_index) to for every repositioned
    inline code - used only to build the RESULTS report, never by apply()."""
    la, ia, ta = regions(A)
    lb, ib, tb = regions(B)
    if not ia and not ib:
        return list(A)
    if bool(ia) != bool(ib):
        rep.append('TEXTLESS MISMATCH')
        return None
    lida = [t[1] for t in la if t[0] == 'c']
    lidb = [t[1] for t in lb if t[0] == 'c']
    if lida != lidb:
        rep.append('lead ids differ: fan %s capcom %s' % (
            ' '.join('%04X' % c for c in lida), ' '.join('%04X' % c for c in lidb)))
    ea = A[-1][1] if A and A[-1][0] == 'c' else None
    eb = B[-1][1] if B and B[-1][0] == 'c' else None
    if ea != eb:
        rep.append('box-end variant: fan %04X capcom %s (fan kept)' % (ea, '%04X' % eb if eb else None))
    sa = [t[1] for t in ia if t[0] == 'c' and t[1] in STYLE]
    sb = [t[1] for t in ib if t[0] == 'c' and t[1] in STYLE]
    if sa != sb:
        rep.append('STYLE MISMATCH fan %s capcom %s' % (sa, sb))
    fan_chars = [t[1] for t in ia if is_text(t)]
    fan_stutter_f = _fan_stutter_positions(fan_chars)
    F = len(fan_chars)
    place = []
    f = 0
    for t in ia:
        if is_text(t):
            f += 1
        elif t[0] == 'c':
            if t[1] in STYLE:
                continue
            if t[1] in PACE and pacing == 'capcom':
                continue
            place.append((f, t))
    keep = []
    for t in ib:
        if (t[0] == 'c' and t[1] not in STYLE and len(t) == 3
                and not (t[1] in PACE and pacing == 'capcom')):
            continue
        keep.append(t)
    fan_ms = collections.Counter(t[1] for t in A if t[0] == 'c' and t[1] not in PACE and t[1] not in STYLE)
    cap_ms = collections.Counter(t[1] for t in B if t[0] == 'c' and len(t) == 3 and t[1] not in PACE and t[1] not in STYLE)
    if fan_ms != cap_ms:
        rep.append('whole-box cue multiset differs (fan wins): fan-only %s capcom-only %s' % (
            {'%04X' % c: n for c, n in (fan_ms - cap_ms).items()}, {'%04X' % c: n for c, n in (cap_ms - fan_ms).items()}))
    text_idx = [k for k, t in enumerate(keep) if is_text(t)]
    O = len(text_idx)
    starts = [0]
    for p in range(1, O):
        prev = keep[text_idx[p - 1]][1]
        if prev in (0xFF3F, 0x0A):
            starts.append(p)
    for k, t in enumerate(keep):
        if t[0] == 't' and t[1] == 0x0A:
            nxt = next((p for p, ti in enumerate(text_idx) if ti > k), O)
            if nxt not in starts:
                starts.append(nxt)
    starts.append(O)
    starts = sorted(set(starts))
    cap_stutter_k = _cap_stutter_target(keep)
    ins = collections.defaultdict(list)
    for f, t in place:
        if f in fan_stutter_f and cap_stutter_k is not None:
            k, rule = cap_stutter_k, 'a'
        elif f == 0:
            k, rule = 0, 'b'
        elif all(v in _PUNCT for v in fan_chars[f:]):
            k, rule = len(keep), 'c'
        else:
            tgt = round(f * O / F) if F else 0
            p = min(starts, key=lambda s: (abs(s - tgt), s))
            k, rule = (text_idx[p] if p < O else len(keep)), 'd'
        # a cue goes BEFORE a style opener that opens on the same word - the
        # fan's (and the JP's) order is {E1D5}{E041}word{E040}, never the
        # reverse (the converter emits a word's leading space AFTER any codes
        # that precede the word, so the opener may sit one space back).
        while k > 0:
            prev = keep[k - 1]
            if prev[0] == 'c' and prev[1] in dstext.STYLE_ON:
                k -= 1
            elif (prev[0] == 't' and prev[1] == 0xFF3F and k > 1
                  and keep[k - 2][0] == 'c' and keep[k - 2][1] in dstext.STYLE_ON):
                k -= 1
            else:
                break
        ins[k].append(t)
        if cue_log is not None:
            cue_log.append((t, rule, k))
    out = list(la)
    for k, t in enumerate(keep):
        out.extend(ins.get(k, []))
        out.append(t)
    out.extend(ins.get(len(keep), []))
    out.extend(ta)
    return out


def convert_box(src_tokens):
    """Convert one Capcom source box on its own. Returns (tokens, synthetic,
    unmapped): synthetic is the set of token indices the converter ADDED when
    the words needed more than 3 lines (a page break + pace pair per extra
    box), tagged as 4-tuples in the returned token list."""
    cu, unmapped = dstext.convert(untok(src_tokens))
    ts = toks(cu)
    ends = [k for k, t in enumerate(ts) if t[0] == 'c' and t[1] in BOXEND]
    last = ends[-1] if ends and ts[-1][0] == 'c' and ts[-1][1] in BOXEND else None
    syn = set()
    for k in ends:
        if k == last:
            continue
        syn.add(k)
        if k + 1 < len(ts) and ts[k + 1] == ('c', 0xE107, [dstext.NEW_BOX_ARG]):
            syn.add(k + 1)
        if k >= 1 and ts[k][1] == dstext.AUTO_BREAK and ts[k - 1] == ('c', 0xE108, [dstext.AUTO_DELAY]):
            syn.add(k - 1)
    ts = [(t[0], t[1], t[2], 'syn') if k in syn else t for k, t in enumerate(ts)]
    return ts, syn, unmapped


def relay(fan_units, pieces, en_strings, pacing='capcom', cue_log=None):
    """(out_units, ok, notes, out_tokens). ok is False on any structural
    failure (out of range, textless mismatch, more Capcom boxes than fan
    boxes, an unmapped glyph) - the caller must not ship out_units in that
    case. out_tokens is the pre-flatten token list (4-tuples mark a
    converter-added page break, matching convert_box's own 'syn' tag) - used
    only for the build's own proof checks; apply() below does not expose it
    further. cue_log, if given, collects (code, rule, keep_index) for every
    repositioned inline code, for the RESULTS report only."""
    rep = []
    fb = split_boxes(fan_units)
    conv_boxes = []
    for si, lo, hi in pieces:
        sb = split_boxes(list(en_strings[si]))
        if hi > len(sb):
            rep.append('PIECE OUT OF RANGE: en %d has %d boxes, wanted %d..%d' % (si, len(sb), lo, hi))
            return None, False, rep, None
        for k in range(lo, hi):
            ts, syn, unmapped = convert_box(sb[k])
            if unmapped:
                rep.append('unmapped glyphs in en %d box %d: %s' % (si, k, sorted(unmapped)))
                return None, False, rep, None
            conv_boxes.append((ts, syn))
    if len(conv_boxes) > len(fb):
        rep.append('MORE CAPCOM BOXES (%d) THAN FAN BOXES (%d)' % (len(conv_boxes), len(fb)))
        return None, False, rep, None
    out = []
    for k, A in enumerate(fb):
        if k < len(conv_boxes):
            B, syn = conv_boxes[k]
            if syn:
                nb = 1 + sum(1 for s in syn if B[s][0] == 'c' and B[s][1] in BOXEND)
                rep.append('box %02d: PAGINATED (Capcom words need %d boxes here)' % (k, nb))
            ob = merge_box(A, B, pacing, rep, cue_log)
            if ob is None:
                return None, False, rep, None
        else:
            ob = list(A)
        out += ob
    return untok(out), True, rep, out


# ---------------------------------------------------------------------------
# Hash-guarded row table. fan_hash: sha1[:16] of the fan ROM's raw units for
# (entry, string), packed little-endian u16 (linefix.py's _key convention).
# src_hash: sha1[:16] of the Collection source units this row pulls from,
# each string's raw units packed the same way and concatenated in `pieces`
# order, joined with a single 0xFFFF separator unit (never a valid code or
# text unit) so two different splits cannot collide. want: sha1[:16] of the
# final merged output units, pacing='capcom'. All three were computed from
# the same fan ROM and Collection dump this build's other hash-guarded
# tables (stmt_trim.py, linefix.py) were built against.
# ---------------------------------------------------------------------------
RELAID = {
    (93, 0): {
        'fan_hash': 'eda849cd2f43f5db',
        'src_hash': '192cc4d06d02e72b',
        'pieces': [(0, 0, 8)],
        'want': 'e0320303fa426778',
    },
    (236, 0): {
        'fan_hash': '144053b6afca421c',
        'src_hash': 'aad0343665ca2d27',
        'pieces': [(0, 0, 31), (1, 0, 10)],
        'want': '2f20ba1b8b8d0296',
    },
    (236, 1): {
        'fan_hash': '2f4cb419d0adaf9b',
        'src_hash': '5798628ef3d049c8',
        'pieces': [(1, 10, 56)],
        'want': '0b450181a059997d',
    },
}

# Entry 340 string 0 only: not relaid at all - box-for-box identical to JP and
# Capcom. It wrongly hits inject.py's overlap_low widget gate because the
# WHOLE-entry JP-profile overlap (strings 3/4 are fan-empty, Capcom
# "DEMO TEXT") is far below the gate's threshold. This table exempts exactly
# (340, 0), hash-guarded on the fan's own string 0 bytes for that entry - a
# fan ROM whose entry 340 differs leaves the ordinary widget gate in place
# instead of trusting the entry number alone. Every sibling row on the same
# gate is untouched.
SKIP_WIDGET_GATE = {
    (340, 0): {'fan_hash': 'c86c2d4d8d7f4959'},
}


def skip_widget_gate(entry, string_index, fan_units):
    row = SKIP_WIDGET_GATE.get((entry, string_index))
    if row is None or row['fan_hash'] is None:
        return False
    return _hash(list(fan_units)) == row['fan_hash']


def _src_hash(en_strings, pieces):
    parts = []
    for si, _lo, _hi in pieces:
        u = list(en_strings[si])
        parts.append(struct.pack('<%dH' % len(u), *u))
        parts.append(struct.pack('<H', 0xFFFF))
    return hashlib.sha1(b''.join(parts)).hexdigest()[:16]


def apply(entry, string_index, fan_units, en_strings, _has_foreign=None, _has_zero_in_text=None):
    """(out_units, status, notes). status is None when this (entry, string)
    has no row (units NOT returned as a usable value - caller must ignore
    out_units and run its normal path); True when both hashes matched, the
    merge succeeded, the result hashes to 'want', and (if the caller passed
    them) it also clears the ordinary foreign-code/zero-in-text gates; False
    on any mismatch or failure - the caller's normal per-string path runs
    instead."""
    row = RELAID.get((entry, string_index))
    if row is None:
        return None, None, []
    if _hash(list(fan_units)) != row['fan_hash']:
        return None, False, ['fan hash mismatch - different fan ROM, row not applied']
    try:
        if _src_hash(en_strings, row['pieces']) != row['src_hash']:
            return None, False, ['source hash mismatch - different Collection dump, row not applied']
    except KeyError as e:
        return None, False, ['missing Collection source string %s, row not applied' % e]
    out, ok, notes, _toks = relay(list(fan_units), row['pieces'], en_strings, PACING)
    if not ok:
        return None, False, notes + ['relay() failed, row not applied']
    if row['want'] is not None and _hash(out) != row['want']:
        return None, False, notes + ['result hash mismatch after relay(), row not applied']
    if _has_foreign is not None and _has_foreign(out):
        return None, False, notes + ['relayed result carries a non-DS code, row not applied']
    if _has_zero_in_text is not None and _has_zero_in_text(out):
        return None, False, notes + ['relayed result has a zero unit in text position, row not applied']
    return out, True, notes
