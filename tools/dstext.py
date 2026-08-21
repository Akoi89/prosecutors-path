# -*- coding: utf-8 -*-
"""Convert Collection (official) text units into DS-renderable units.

The engine's control codes take a fixed number of argument units (portrait ids,
speaker ids, timings, 0xFFFF sentinels). Those must pass through untouched -
fullwidth-ing them corrupts the script. Argument counts were derived from the
official corpus as the minimum observed run length after each code
(see dump/ctrl_args.json); min == p01 == p05 for every code, which is what a
fixed arity looks like.

Dialogue becomes fullwidth with U+FF3F as the space - the same choice the AAI2 fan
patch made (its text is 80.8% fullwidth, with 259k uses of U+FF3F).

Lines are wrapped by PIXEL width, not character count: the fan patch installed a
variable-width font, so a fixed cell budget wastes most of the box. There is a hard
trade-off between clipping a line's right edge and spilling to an invisible 4th line;
the budget is set to avoid clipping, which is the uglier failure.

When a message needs more than one box, the lines are spread EVENLY across the boxes
rather than filled greedily. Greedy filling turns a 4-line thought into 3 lines plus a
one-word orphan ("...intend to draw logical)" / "(conclusions...)"); balancing gives
2 + 2, which is how the original script reads.
"""
import json, os, sys, unicodedata
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

SPACE = 0xFF3F
# Calibrated from an in-game screenshot: a line measuring 208px in this model was
# clipped at the right edge, and a 201px line fit, so the usable box is ~205px.
# 200 leaves a margin for error in the per-glyph estimates. Do NOT raise this - at
# 224px, 20,120 lines clip mid-word, which is far more destructive than the ~9% of
# messages that spill to a hidden 4th line.
LINE_PX = 200
NARROW = set("iljtfIJ.,!?:;'()[]|")
WIDE = set('mwMW@')
CTRL = lambda v: 0xE000 <= v <= 0xF8FF
# {E104} ends a box too - it auto-advances instead of waiting for input.
RESET = {0xE102, 0xE104, 0xE106, 0xE185, 0xE081}
LETTER = lambda v: 0x41 <= v <= 0x5A or 0x61 <= v <= 0x7A
BOX_LINES = 3
# Two kinds of page turn, and using the wrong one is very visible:
#   {E102} ends a box and WAITS for a button press  (830 JP precedents with {E107})
#   {E108}<delay>{E104} ends a box and AUTO-ADVANCES - what cutscene narration uses,
#   e.g. DS[206] str10 chains three pages this way, and the plane scene in DS[52].
# Whichever the surrounding message already uses is the one to emit.
WAIT_BREAK = 0xE102
AUTO_BREAK = 0xE104
AUTO_DELAY = 0x3C          # frames; JP uses 0x5A/0x3C/0x46 most in this position
# {E107}'s argument selects how the text starts: <03> opens a FRESH box, <02>
# continues inline. A break must use <03> - it is what the JP script uses after
# {E102} (512x vs 70x for <02>) and what opens the blue thought box in
# eng_trial/logic00_11. Reusing the last-seen arg emits <02> and the box loses its
# thought-text colour.
NEW_BOX_ARG = 0x0003
# Internal monologue renders blue, and the trigger is the PARENTHESIS, not a control
# code - 93% of thought boxes in both the JP and fan ROMs close their parens inside the
# same box. Splitting "(...)" across a page break leaves the new box without an opening
# paren, and it renders white. So a break inside parens closes and reopens them, which
# is exactly how the original script formats multi-box thoughts.
PAREN_OPEN = 0xFF08
PAREN_CLOSE = 0xFF09
# The source's newlines are almost all SOFT wrap for the Collection's own box, which is
# far wider than the DS box - honouring them produces ragged three-line messages
# ("The moment" / "the phone rang, I knew it was" / "serious."). Measured over the
# whole English corpus: 20,516 of 26,172 newlines end a line of 40-59 visible chars,
# capped hard at 59 - the signature of a fixed-width wrapper. Only the 79 newlines
# immediately followed by {E20D} are structural: that code opens a new laid-out row,
# as in {E043}March 25, 2:46 PM <newline> {E20D}Gourd Lake - Spectator Area{E040}.
LAYOUT_ROW = 0xE20D
# The DS font has no fullwidth apostrophe/quote (U+FF07 / U+FF02) - they render as a
# stray underline. The fan patch uses the curly forms instead: U+201D as the apostrophe
# (16,482 uses) and U+201C/U+201D as the double-quote pair.
APOS = 0x201D
DQ_OPEN = 0x201C
DQ_CLOSE = 0x201D

from paths import data as _data
ARGS = {int(k, 16): v for k, v in json.load(open(_data('ctrl_args.json'))).items()}
DEFAULT_ARGS = 0

def _w(ch):
    o = ord(ch)
    if o == SPACE: return 5                       # the game's space glyph
    if 0xFF01 <= o <= 0xFF5E:                     # fullwidth Latin -> its ASCII form
        ch = chr(o - 0xFF01 + 0x21); o = ord(ch)
    if o >= 0x2E80: return 12                     # real CJK keeps a full cell
    if ch in NARROW: return 4
    if ch in WIDE: return 9
    return 7

def _fw(ch):
    o = ord(ch)
    if o == 0x20: return chr(SPACE)
    if 0x21 <= o <= 0x7E: return chr(o - 0x21 + 0xFF01)
    if (0xFF01 <= o <= 0xFF60 or 0x3000 <= o <= 0x30FF
            or 0x4E00 <= o <= 0x9FFF or 0x2010 <= o <= 0x203B): return ch
    d = unicodedata.normalize('NFD', ch)
    base = ''.join(c for c in d if not unicodedata.combining(c))
    if base and base != ch: return ''.join(_fw(c) for c in base)
    return ch

def _layout(tokens):
    """Assign each token a line number, wrapping at LINE_PX. Control tokens have no
    width but must keep their position. Returns (tokens_with_lines, line_count)."""
    line, cells, pending = 0, 0, False
    placed = []
    for kind, val in tokens:
        if kind == 'w':
            ww = sum(_w(chr(u)) for u in val)
            gap = _w(chr(SPACE)) if pending else 0
            if cells and cells + gap + ww > LINE_PX:
                line += 1; cells = ww; pending = False
                placed.append((kind, val, line, False))
            else:
                placed.append((kind, val, line, pending))
                cells += gap + ww; pending = False
        elif kind == 's':
            if cells: pending = True
            placed.append((kind, val, line, False))
        elif kind == 'br':
            placed.append((kind, val, line, False))
            line += 1; cells = 0; pending = False
        else:
            placed.append((kind, val, line, False))
    return placed, line + 1

PUNCT = set('.,!?;:')
# A box break reads best just after punctuation, or just before a word that opens a
# new clause. Without this the split lands mid-phrase ("well-reasoned" / "connections").
CLAUSE = {'if','and','but','so','then','when','while','because','though','although',
          'since','unless','or','yet','that','which','who','after','before','until',
          'as','however','therefore','still','instead','plus','also'}

def _boxes(nlines, ends=None):
    """Split nlines across as few boxes as possible, as evenly as possible. When a
    line adjacent to the balanced split point ends on punctuation, prefer that - it
    reads far better than cutting a phrase in half."""
    n = max(1, -(-nlines // BOX_LINES))
    base, extra = divmod(nlines, n)
    sizes = [base + (1 if k < extra else 0) for k in range(n)]
    if not ends or n < 2:
        return sizes
    stops, acc = [], 0
    for sz in sizes[:-1]:
        acc += sz; stops.append(acc)
    for idx, st in enumerate(stops):
        if ends.get(st - 1): continue                 # already a clean break
        lo = stops[idx-1] + 1 if idx else 1
        hi = (stops[idx+1] if idx + 1 < len(stops) else nlines) - 1
        best = None
        for cand in range(max(lo, st - 1), min(hi, st + 1) + 1):
            if cand - lo + 1 > BOX_LINES or (hi - cand) + 1 > BOX_LINES: continue
            if ends.get(cand - 1) and (best is None or abs(cand - st) < abs(best - st)):
                best = cand
        if best: stops[idx] = best
    out, prev = [], 0
    for st in stops + [nlines]:
        out.append(st - prev); prev = st
    return out

def convert(units, wrap=True, page=True, hard_nl='e20d'):
    """hard_nl: 'e20d' keeps a source newline as a line break only when {E20D} follows
    (location/date cards); True keeps every newline; False folds them all to spaces."""
    out, unmapped = [], set()
    dq_open = False

    def word_units(val):
        nonlocal dq_open
        parts = []
        for u in val:
            if u == 0x22:
                parts.append(chr(DQ_OPEN if not dq_open else DQ_CLOSE)); dq_open = not dq_open
            elif u in (0x27, 0x2019):
                parts.append(chr(APOS))
            else:
                parts.append(_fw(chr(u)))
        s = ''.join(parts)
        for ch in s:
            o = ord(ch)
            if not (0xFF01 <= o <= 0xFF60 or 0x3000 <= o <= 0x30FF
                    or 0x4E00 <= o <= 0x9FFF or 0x2010 <= o <= 0x203B or o < 0x80):
                unmapped.add(o)
        return [ord(c) for c in s]

    def split_tokens(tokens, nb):
        """Partition tokens into nb chunks at WORD boundaries, balanced by width and
        preferring a break just after punctuation. Splitting the LINE list instead
        strands phrases ('...connections if I)' / '(intend to draw...')."""
        idx, cum, total = [], [], 0
        for k, (kind, val) in enumerate(tokens):
            if kind == 'w':
                total += sum(_w(chr(u)) for u in val) + _w(chr(SPACE))
                idx.append(k); cum.append(total)
        if len(idx) < nb: return [tokens]
        cuts = []
        for b in range(1, nb):
            target = total * b / nb
            window = total / nb * 0.35
            best, best_score = None, None
            for j, k in enumerate(idx):
                d = abs(cum[j] - target)
                if d > window: continue
                last = tokens[k][1][-1]
                ch = chr(last - 0xFF01 + 0x21) if 0xFF01 <= last <= 0xFF5E else chr(last)
                bonus = window * 0.8 if ch in PUNCT else 0
                nxt = next((tokens[q][1] for q in range(k + 1, len(tokens))
                            if tokens[q][0] == 'w'), None)
                if nxt:
                    w = ''.join(chr(u - 0xFF01 + 0x21) if 0xFF01 <= u <= 0xFF5E else chr(u)
                                for u in nxt).strip('.,!?;:“”()').lower()
                    if w in CLAUSE: bonus = max(bonus, window * 0.7)
                score = d - bonus
                if best_score is None or score < best_score:
                    best, best_score = k, score
            if best is None:
                best = min(idx, key=lambda k: abs(cum[idx.index(k)] - target))
            cuts.append(best + 1)
        chunks, prev = [], 0
        for c in sorted(set(cuts)):
            chunks.append(tokens[prev:c]); prev = c
        chunks.append(tokens[prev:])
        return [c for c in chunks if c]

    def emit(tokens, term):
        if not tokens:
            return
        if not wrap:
            for kind, val in tokens:
                if kind in ('c', 'w'): out.extend(val)
                elif kind == 'n': out.append(0)
                elif kind == 'br': out.append(0x0A)
                elif kind == 's': out.append(SPACE)
            return
        _, nlines = _layout(tokens)
        nb = max(1, -(-nlines // BOX_LINES)) if page else 1
        chunks = [tokens]
        if nb > 1:
            for extra in range(0, 4):
                chunks = split_tokens(tokens, nb + extra)
                if all(_layout(c)[1] <= BOX_LINES for c in chunks): break
            # A trailing chunk of pure control codes would open a box, reopen the
            # parenthesis and close it again with nothing inside - a blank '()'
            # box the player has to click through. Fold any wordless chunk back.
            merged = []
            for c in chunks:
                if merged and not any(k == 'w' for k, _ in c): merged[-1] = merged[-1] + c
                else: merged.append(c)
            chunks = merged
        depth = 0
        for ci, chunk in enumerate(chunks):
            if ci:
                if depth > 0: out.append(PAREN_CLOSE)
                if term == AUTO_BREAK:
                    out.extend((0xE108, AUTO_DELAY, AUTO_BREAK, 0xE107, NEW_BOX_ARG))
                else:
                    out.extend((WAIT_BREAK, 0xE107, NEW_BOX_ARG))
                if depth > 0: out.append(PAREN_OPEN)
            placed, _ = _layout(chunk)
            cur = 0
            for kind, val, ln, sp in placed:
                while ln > cur:
                    cur += 1; out.append(0x0A)
                if kind == 'c':
                    out.extend(val)
                elif kind == 'n':
                    out.append(0)
                elif kind == 'w':
                    if sp: out.append(SPACE)
                    out.extend(val)
                    for c in val:
                        if c == PAREN_OPEN: depth += 1
                        elif c == PAREN_CLOSE: depth = max(0, depth - 1)

    # Split the stream into messages; a message ends at a box-terminating code.
    i, n = 0, len(units)
    buf = []
    while i < n:
        v = units[i]
        if CTRL(v):
            tok = [v]; i += 1
            for _ in range(ARGS.get(v, DEFAULT_ARGS)):
                if i < n and not CTRL(units[i]):
                    tok.append(units[i]); i += 1
            if v in RESET:
                # look ahead: is this a waiting or an auto-advancing terminator?
                emit(buf, v if v in (WAIT_BREAK, AUTO_BREAK) else WAIT_BREAK)
                out.extend(tok); buf = []; dq_open = False
            else:
                buf.append(('c', tok))
            continue
        j = i
        while j < n and not CTRL(units[j]): j += 1
        run = units[i:j]; base = i; i = j
        cur = []
        for k, u in enumerate(run):
            if u == 0x0A:
                if cur: buf.append(('w', word_units(cur))); cur = []
                nxt = units[base + k + 1] if base + k + 1 < n else None
                if hard_nl is True or (hard_nl == 'e20d' and nxt == LAYOUT_ROW):
                    buf.append(('br', None))
                elif not buf or buf[-1][0] != 's':
                    buf.append(('s', None))
            elif u in (0x20, 0x09):
                if cur: buf.append(('w', word_units(cur))); cur = []
                if not buf or buf[-1][0] != 's': buf.append(('s', None))
            elif u == 0:
                if cur: buf.append(('w', word_units(cur))); cur = []
                buf.append(('n', None))
            else:
                cur.append(u)
        if cur: buf.append(('w', word_units(cur)))
    emit(buf, WAIT_BREAK)
    return out, unmapped
