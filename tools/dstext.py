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
#
# {E106} IS NOT A BOX END, and treating it as one is a live defect. Its handler,
# overlay 7 0x020ACEB0, clears interpreter flag bit 14, calls the read-mark
# bookkeeping at 0x020ACBCC and returns 1 so the interpreter carries straight on.
# It never touches the render buffer index, the render context or the canvas. Only
# {E102} (0x020ACE34) and {E104} (0x020ACE70) reach the path that zeroes the buffer
# index, re-inits the render context and wipes the canvas; {E185} and {E081} are
# string-final in every occurrence (61/61 and 2642/2642 in the JP script) so their
# behaviour does not arise. {E100} is what OPENS a box, argument 0, and {E101}
# re-opens one only when the box flag says it is closed, otherwise it just swaps
# the nameplate and continues in place.
#
# Consequence of getting this wrong: the wrapper fitted the text on each side of an
# {E106} into three lines INDEPENDENTLY, while the engine kept writing into the box
# already on screen, so the two ran together, the line went over the box width and
# the renderer chopped it mid-word with nothing on screen to say so. Seen in the
# SHIPPED release at entry 59 string 0 (Episode 2): the script holds a one-line
# question, then {E108 32} {E106} {E101} {E107 3}, then a two-line sentence, and the
# screen showed one box where the second sentence ran straight on from the question
# mark on the same line and was cut off mid-word at the box edge, losing two words.
# Proof rig/proof/e107/CUTOFF_fender_everythin_box.png. The fan's own line at that
# site is a single box too, which is the tell: the fan AUTHORED for this behaviour.
# {E106} STAYS IN THIS SET, and the reason is specific: tools/loc_patch.py:205
# preserves a string's trailing box-end with
#     tail = [v for v in u if CTRL(v) and v in dstext.RESET][-1:]
# so with {E106} out of RESET a string whose last box-end IS an {E106} loses it.
# That is what went wrong on the first attempt, measured: 322 occurrences
# disappeared, ALL of them string-final (322/322 within the last three units) and
# confined to the two loc_patch-handled banks, entry 432 (226) and entry 395 (96),
# and audit_boxes reported 322 strings with fewer boxes than the fan at exit 1.
# TWO THINGS THE FIRST VERSION OF THIS COMMENT GOT WRONG, corrected by a refuter
# pass: no string was reverted to the fan's text by inject's safety net (strings
# byte-identical to the fan number 6,001 in every build, before and after, and
# coverage is 94.6% either way), and the count was 322, not 285. Do not repeat
# either claim.
#
# So RESET keeps {E106} for every OTHER caller, and only convert()'s own
# box-splitting loop treats it differently: DELTA 7b (e106_clears(), defined
# below) narrowed the "never flushes" rule to the {E106}s the Japanese retail
# actually keeps a box open across. Where e106_clears() is False, {E106} is
# buffered like any ordinary control token so it stays at its exact stream
# position while the text on both sides is laid out as ONE box-run and
# paginated with real {E102} breaks - the Fender case this was written for.
# Where it is True (a prompt/popup code follows), {E106} flushes a box exactly
# as every other RESET code does. audits/audit_typography.py and
# audits/measure_linewidth.py import the same e106_clears() so all three agree
# on which {E106} ends a box.
#
# WHAT IT IS WORTH: figures are not repeated here because the instrument that
# measures them (audits/measure_linewidth.py) changed alongside this rule, so
# an old number quoted next to a new one would compare two different rulers.
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
# {E107}'s argument is TYPEWRITER PACING, not a box opener. Corrected 2026-09-21
# from the binary: the handler stores the argument into ctx+0x1E and the dispatcher
# copies it into the yield timer after every character (0x0200E114 -> 0x0200E13C),
# so it sets how fast the text prints. The older comment here claimed <03> opens a
# fresh box and <02> continues inline, and that reading is what sent a whole
# afternoon after the wrong cause: the Fender line that is chopped mid-word already
# carries <03> in the shipped build. 3 is still the right value to emit after a
# break because it is what the JP script uses there (512x against 70x for <02>) and
# it is what the blue thought box in eng_trial/logic00_11 opens with, so the name
# below is kept - but it is a PACE, and do not reason about box structure from it.
# (The countdown itself was not traced, so "strongly indicated" rather than proven.)
NEW_BOX_ARG = 0x0003

# Rewrite Capcom's {E107} argument from 2 to 3 where it OPENS a box. See the long
# note at the call site in convert(). Set False to build the old behaviour for a
# side-by-side comparison; the counter is how many sites were rewritten.
BOX_OPEN_FIX = False
_STATS = {'boxopen': 0}
# Internal monologue renders blue, and the trigger is the PARENTHESIS, not a control
# code - 93% of thought boxes in both the JP and fan ROMs close their parens inside the
# same box. Splitting "(...)" across a page break leaves the new box without an opening
# paren, and it renders white. So a break inside parens closes and reopens them, which
# is exactly how the original script formats multi-box thoughts.
# A box-terminating code RESETS the engine's inline style register, exactly as it drops the
# blue thought colour when a "(" is stranded. Proved on hardware 2026-09-03: flip one byte so
# a term opens with {E043} instead of {E041} and box 1 turns green while box 2 stays WHITE
# either way - yet a span OPENED inside box 2 still renders. Box 2 can draw style; it just
# cannot inherit it. So a break inside a styled span must close and re-open it, exactly as
# parens are, and it must re-emit the CACHED opener, never a hard-coded {E041}: most of the
# affected spans in the script are {E043}.
# {E041} (orange keyword) and {E043} (green) OPEN a styled span; {E040} and {E042} both
# CLOSE one - e.g. "(The {E041}rolls of blue cloth{E042} and the {E041}rock crystals{E042}
# inside the castle...)". Do NOT read {E042} as an opener because it is frequent and often
# follows {E041}: that inference is wrong, and caching it as a style makes the emitter
# re-open a CLOSER after a break. Emit {E040} as the closer (the dominant one, 1276 uses,
# and it pairs with both openers).
STYLE_OFF = 0xE040
STYLE_CLOSERS = (0xE040, 0xE042)
STYLE_ON = (0xE041, 0xE043)
PAREN_OPEN = 0xFF08
PAREN_CLOSE = 0xFF09
# The source's newlines are almost all SOFT wrap for the Collection's own box, which is
# far wider than the DS box - honouring them produces ragged three-line messages
# (a two-word line, a long line, a one-word line). Measured over the
# whole English corpus: 20,516 of 26,172 newlines end a line of 40-59 visible chars,
# capped hard at 59 - the signature of a fixed-width wrapper. Only the 79 newlines
# immediately followed by {E20D} are structural: that code opens a new laid-out row,
# as in {E043}<date row> <newline> {E20D}<place row>{E040} on a location card.
LAYOUT_ROW = 0xE20D
# {E20D} also CENTRES its row, and only its row. The Collection's cards put the whole place
# on one row ("Detention Center - Visitor's Room"); on the DS that row is too wide, the
# wrapper broke it with a bare newline, and the tail ("Room") printed flush left under the
# centred text on 22 of 82 cards in 1.8.2 (seen in the rig, Ep2 ch3; Reddit report). The
# fan ROM gives the building and the room a row each, so a place row splits at its " - "
# into two {E20D} rows when both halves fit and the card stays within one box; a row that
# still has to wrap re-opens {E20D} on the wrapped line so it is centred too.
CARD_SEP = 0xFF0D           # the fullwidth hyphen of " - "
# The DS font has no fullwidth apostrophe/quote (U+FF07 / U+FF02) - they render as a
# stray underline. The fan patch uses the curly forms instead: U+201D as the apostrophe
# (16,482 uses) and U+201C as the double quote - at BOTH ends (925 of its quotations
# open and close on U+201C). The font has no separate closing-quote glyph: U+201D IS
# the apostrophe, so closing with it drew "Gourdy'. for "Gourdy". in every release
# through 1.6.1 (~1,070 sites; found by the 2026-09-03 rig playtest).
APOS = 0x201D
DQ_OPEN = 0x201C
DQ_CLOSE = 0x201C

from paths import data as _data
ARGS = {int(k, 16): v for k, v in json.load(open(_data('ctrl_args.json'))).items()}
DEFAULT_ARGS = 0

# Which {E106}s the box really stays open across. Measured on the Japanese
# retail script, counting the text lines on both sides of each {E106} together
# inside one box-run: where one of these codes comes after the {E106} and
# before the next visible text, 210 of the 283 cases with text after carry more
# than 3 lines across it, which a 3-line box cannot hold, so the screen clears
# there. Every other {E106} with text after: 0 of 27 go over 3 lines, and the
# rig photographed the box staying open at one of them (entry 59 str 0).
# E113 and E19C are in the set because they sit beside E163/E198/E1CF in the
# over-3 cases; on their own the retail has only 5 cases of them, none over 3.
E106_CLEARS = {0xE163, 0xE1CF, 0xE198, 0xE160, 0xE113, 0xE234, 0xE19C}


def e106_clears(units, k):
    """True if the {E106} whose code+args end at index k is followed, before the
    next visible text unit or a box-ending RESET code other than E106, by a code
    in E106_CLEARS.

    Walks forward from k using each control code's ARGS arity, skipping
    whitespace/newlines/the null separator on the way. Stops - and returns
    False - at the first visible text unit or at a RESET code other than E106
    (a real box end); returns True as soon as a code in E106_CLEARS is met.
    Shared by convert() below and, via import, by audits/audit_typography.py
    and audits/measure_linewidth.py, so all three agree on which {E106} ends a
    box.
    """
    n = len(units)
    while k < n:
        v = units[k]
        if CTRL(v):
            if v in E106_CLEARS:
                return True
            if v in RESET and v != 0xE106:
                return False
            k += 1 + ARGS.get(v, DEFAULT_ARGS)
            continue
        if v in (0x0A, 0x20, 0x09, 0, 0x3000, SPACE):
            k += 1
            continue
        return False
    return False


# Control codes that exist only in the Collection's script and have a direct DS
# equivalent. The DS engine skips a code it does not know and then reads the
# code's argument units as text; an argument of 0 ends the string early, and the
# closing {E10E} of the pair is left orphaned - the scene stops and the game hangs
# (Ep1 Audience Area, right after Knight's introduction: {E2A0 2,1,0} where the
# fan ROM has {E10D 2,1,0}; 15 such sites in every release through v1.5.0).
# Codes with no DS equivalent (E2B0 = inline button icon) are left in place here
# and the injector keeps the fan's string for that message instead.
OFFICIAL_TO_DS = {0xE2A0: 0xE10D}

# Ellipses print as U+2025, the glyph the fan ROM uses for every one of its own, and not
# as fullwidth periods, which draw the same dot but are LETTERS to the engine: it flaps
# the speaker's mouth while printing them. A silent '............' box (a Logic Chess
# wait, a stunned pause) therefore had Edgeworth talking through it in 1.4.0 through
# 1.8.0 (Reddit report, reproduced in the rig 2026-09-06 from one save state: fullwidth
# periods flap with print-mode argument 7 and 8 alike; U+2025 is still on every printing
# frame, and normal speech keeps animating). Same count of units, same advance, so
# nothing re-wraps and nothing moves. Runs of three or more only; a lone period is a
# period.
ELLIPSIS_UNIT = 0x2025

# The fan patch's own per-glyph advances, read from the player's ROM at build
# time by fontwidths.py. Empty until use_real_widths() is called, and then the
# estimate below is bypassed. A glyph the table does not list gets a full cell,
# so an unmeasured character can only wrap EARLY, never clip.
_REAL = {}

def use_real_widths(widths, line_px):
    """Swap the dialogue width model from the estimate to the font's own metrics.

    Call once, before converting anything. The widgets that wrap with their own
    face (the description card, Logic cards) save and restore LINE_PX and
    WIDTH_FN around their own call, so they are unaffected either way - but that
    save/restore is why this must not happen lazily in the middle of one.
    """
    global _REAL, LINE_PX
    if not widths:
        return False
    _REAL = widths
    LINE_PX = line_px
    return True

def _estimate(ch):
    """The original character-class model.

    Its units are arbitrary and run about 12% compressed against real pixels, so it
    only means anything against a budget cut in the SAME units (LINE_PX 200, and the
    widget budgets in loc_patch.BOXES). Never mix it with a real-pixel budget, or the
    other way round: doing so once cost 2,163 char units of Menus & UI coverage.
    """
    o = ord(ch)
    if o == SPACE: return 5                       # the game's space glyph
    if 0xFF01 <= o <= 0xFF5E:                     # fullwidth Latin -> its ASCII form
        ch = chr(o - 0xFF01 + 0x21); o = ord(ch)
    if o >= 0x2E80: return 12                     # real CJK keeps a full cell
    if o == 0x2025: return 4                      # ellipsis dot, same advance as '.'
    if ch in NARROW: return 4
    if ch in WIDE: return 9
    return 7

def _w(ch):
    if not _REAL:
        return _estimate(ch)
    o = ord(ch)
    a = _REAL.get(o)
    if a is None:
        # The table is keyed by what the engine is actually fed, which is the
        # FULLWIDTH form; it holds no plain ASCII at all. Callers that measure in
        # ASCII (inject's row-budget test, names.py) would otherwise price every
        # letter at a fallback and flatten the model to monospace.
        if 0x21 <= o <= 0x7E:
            a = _REAL.get(o - 0x21 + 0xFF01)
        elif o == 0x20:
            a = _REAL.get(SPACE)
    if a is not None:
        return a
    # Eight printable ASCII have no glyph in this font at all (" ' \ ^ ` { | }).
    # Pricing them at a full cell inflated inject's row budget, which is a max over
    # the fan's own rows, and let 39 extra over-wide rows through. The estimate is
    # much closer than a flat cell, and corpus-wide only one codepoint ever misses.
    return _estimate(ch)

# The width model above is the DIALOGUE box's. Other widgets draw other fonts: the
# evidence/profile description card uses a smaller face whose advances were measured
# in game on 2026-09-02 (see loc_patch.DESC_FONT). Callers that wrap for such a widget
# set WIDTH_FN for the duration of their convert() call; everything below measures
# through W() so the swap is complete.
WIDTH_FN = _w
def W(ch):
    return WIDTH_FN(ch)

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

def _chunk(val):
    """Break one token that is wider than a whole line into line-sized pieces.

    Only ever called on a token that cannot fit however it is placed, so there is
    no good break point to look for; fill each line and cut. A single unit wider
    than LINE_PX still goes out whole, because a glyph cannot be split.
    """
    out, cur, px = [], [], 0
    for u in val:
        uw = W(chr(u))
        if cur and px + uw > LINE_PX:
            out.append(cur); cur, px = [], 0
        cur.append(u); px += uw
    if cur:
        out.append(cur)
    return out

def _layout(tokens, cells0=0):
    """Assign each token a line number, wrapping at LINE_PX. Control tokens have no
    width but must keep their position. Returns (tokens_with_lines, line_count).

    cells0 is width already spent on the first line before any token here: a box
    break inside a parenthesised thought re-opens the paren, and that glyph is
    emitted by the caller, so without this the first line is budgeted short by
    its width and overruns the box.
    """
    line, cells, pending = 0, cells0, False
    # Whether a WORD has been placed on the current line. `cells` used to serve as
    # that test, but cells0 is width the CALLER already emitted (the re-opened
    # paren), and that must count toward the wrap budget without making a leading
    # space pending: a separator belongs between two words, and there is no word on
    # the line yet. Conflating the two put a space after every re-opened paren:
    # 157 of them across 144 strings, counted with control arguments consumed,
    # since the emitter writes PAREN_OPEN, then the re-opened style code, then the
    # space. Counting raw adjacency instead sees only the 95 with no style code.
    started = False
    placed = []
    for kind, val in tokens:
        if kind == 'w':
            ww = sum(W(chr(u)) for u in val)
            gap = W(chr(SPACE)) if pending else 0
            if ww > LINE_PX:
                # A single token wider than the entire line. The `cells and` guard
                # below placed it anyway when it landed at the start of a line, so
                # it ran off the right edge of the box. Capcom's long screams
                # ("MMMMMAAAAAAAAAAAAAAAA") carry no space to wrap at, and 59 of
                # them shipped clipped. Break by force instead.
                if cells:
                    line += 1; cells = 0
                pending = False
                for k, piece in enumerate(_chunk(val)):
                    if k:
                        line += 1
                    placed.append((kind, piece, line, False))
                    cells = sum(W(chr(u)) for u in piece)
                started = True
            elif cells and cells + gap + ww > LINE_PX:
                line += 1; cells = ww; pending = False
                placed.append((kind, val, line, False))
                started = True
            else:
                placed.append((kind, val, line, pending))
                cells += gap + ww; pending = False
                started = True
        elif kind == 's':
            if started: pending = True
            placed.append((kind, val, line, False))
        elif kind == 'br':
            placed.append((kind, val, line, False))
            line += 1; cells = 0; pending = False; started = False
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

def _opens_with_close(chunk):
    """True when the first style code in a chunk is the CLOSER, so re-opening the span
    across the break would wrap {E040} in an opener around nothing - two wasted units and
    no visual change. Only leading control tokens count: a word means the term really does
    continue into this box and must keep its colour."""
    for kind, val in chunk:
        if kind == 'w':
            return False
        if kind == 'c':
            for c in val:
                if c in STYLE_CLOSERS: return True
                if c in STYLE_ON: return False
    return False


def _rows(tokens):
    """Split a token list at its 'br' tokens, and also wherever a {E20D} row
    starts mid-buffer after real dialogue.

    A place/date card used to always be its OWN buf - {E106} flushed a box
    right before the leading run of scene-setup codes that leads into
    {E20D}, so that run was always the first thing _split_card_rows ever
    saw. Now that {E106} no longer flushes, a card can arrive stuck onto the
    end of the dialogue that precedes it, with no 'br' between them - and
    _is_layout_row(row) looks at a row's FIRST token, so a row starting with
    dialogue WORDS never even reaches the {E20D} later in it; the card
    never gets split. Hold a run of trailing control/index tokens in
    `pending` rather than committing it to the current row - if it turns out
    to lead into a {E20D}, close the row before it and start the new one
    from `pending`, exactly as if a 'br' had been there."""
    rows, cur, pending = [], [], []
    for t in tokens:
        kind, val = t
        if kind == 'br':
            rows.append(cur + pending); cur, pending = [], []
        elif kind == 'c' and LAYOUT_ROW in val and cur:
            rows.append(cur); cur, pending = pending + [t], []
        elif kind in ('c', 'n'):
            pending.append(t)
        else:                                   # 'w' or 's': not a boundary
            cur += pending + [t]; pending = []
    rows.append(cur + pending)
    return rows

def _is_layout_row(row):
    """True when an {E20D} comes before the row's first word."""
    for kind, val in row:
        if kind == 'w': return False
        if kind == 'c' and LAYOUT_ROW in val: return True
    return False

def _split_at_sep(row):
    """(head, tail) at the row's first ' - ', both halves one line wide, else None."""
    for k in range(1, len(row) - 1):
        if (row[k] == ('w', [CARD_SEP]) and row[k - 1][0] == 's'
                and row[k + 1][0] == 's'):
            head = row[:k - 1]
            tail = [('c', [LAYOUT_ROW])] + row[k + 2:]
            if _layout(head)[1] == 1 and _layout(tail)[1] == 1:
                return head, tail
            return None
    return None

TITLE_DASHES = [CARD_SEP, CARD_SEP]      # '-- Testimony --' rows are titles, not places

def _bind_title_closer(tokens):
    """A centred '-- title --' row that wraps must not leave the closing '--' alone on the
    second line (7 testimony titles did, e.g. '-- President Wang's Testimony' / '--').
    Glue the closer to the word before it so the break moves back one word
    ('-- President Wang's' / 'Testimony --'). Same units, same width; only the wrap
    point can change, and only when the row wraps at all."""
    words = [k for k, (kind, _) in enumerate(tokens) if kind == 'w']
    if len(words) < 3 or tokens[words[0]][1][:2] != TITLE_DASHES:
        return tokens
    if tokens[words[-1]][1] != TITLE_DASHES or not _is_layout_row(tokens):
        return tokens
    if 'br' in (kind for kind, _ in tokens):
        return tokens
    a, b = words[-2], words[-1]
    if [kind for kind, _ in tokens[a + 1:b]] != ['s']:
        return tokens
    glued = ('w', tokens[a][1] + [SPACE] + tokens[b][1])
    return tokens[:a] + [glued] + tokens[b + 1:]

def _split_card_rows(tokens):
    """Place rows split at their ' - ' onto a second {E20D} row, when both halves fit on
    one line and the result still fits one box. Two shapes carry places:
      date/time cards: the first row is the date, every later {E20D} row is the place;
      place labels ({E226}...{E229}): the whole message is one {E20D} row.
    A '-- title --' row and anything else is returned unchanged."""
    rows = _rows(tokens)
    if len(rows) == 1:
        row = rows[0]
        first = next((v for k, v in row if k == 'w'), None)
        if not _is_layout_row(row) or first is None or first[:2] == TITLE_DASHES:
            return tokens
        cut = _split_at_sep(row)
        return tokens if cut is None else cut[0] + [('br', None)] + cut[1]
    if not all(_is_layout_row(r) for r in rows[1:]):
        return tokens
    out_rows = [rows[0]]
    budget = BOX_LINES - len(rows)
    for row in rows[1:]:
        cut = _split_at_sep(row) if budget > 0 else None
        if cut:
            out_rows += list(cut); budget -= 1
        else:
            out_rows.append(row)
    out = []
    for i, r in enumerate(out_rows):
        if i: out.append(('br', None))
        out.extend(r)
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
                total += sum(W(chr(u)) for u in val) + W(chr(SPACE))
                idx.append(k); cum.append(total)
        if len(idx) < nb: return [tokens]
        cuts = []
        for b in range(1, nb):
            target = total * b / nb
            window = total / nb * 0.35

            def _word_at(k):
                last = tokens[k][1][-1]
                ch = chr(last - 0xFF01 + 0x21) if 0xFF01 <= last <= 0xFF5E else chr(last)
                nxt = next((tokens[q][1] for q in range(k + 1, len(tokens))
                            if tokens[q][0] == 'w'), None)
                clause = False
                if nxt:
                    w = ''.join(chr(u - 0xFF01 + 0x21) if 0xFF01 <= u <= 0xFF5E else chr(u)
                                for u in nxt).strip('.,!?;:“”()').lower()
                    clause = w in CLAUSE
                return ch in PUNCT, clause

            best, best_score = None, None
            for j, k in enumerate(idx):
                d = abs(cum[j] - target)
                if d > window: continue
                is_punct, is_clause = _word_at(k)
                bonus = window * 0.8 if is_punct else (window * 0.7 if is_clause else 0)
                score = d - bonus
                if best_score is None or score < best_score:
                    best, best_score = k, score
            # RESCUE PASS. The window above is a fixed fraction of the segment
            # width, so a punctuation break sitting just past it can lose to a
            # bare word sitting inside it, even though the file's own stated
            # rule is to prefer punctuation - "widest fits" beats "best reads".
            # Only fires when the windowed search above found NOTHING with a
            # bonus (best has none), so it can only IMPROVE a currently
            # bonus-free pick; it never overrides a punctuation/clause break
            # already chosen inside the normal window, so already-verified
            # good breaks do not move.
            #
            # THE CAP IS WEAKER THAN IT LOOKS. Reach is capped at half this cut's
            # own segment width, which stops the rescue CROSSING a neighbouring
            # cut but not COINCIDING with one: cut b at target+0.5*seg and cut
            # b+1 at target-0.5*seg can be the same word index, and the
            # sorted(set(cuts)) below then yields one chunk FEWER than nb.
            # Measured by a refuter over 2,553 real dialogue messages at nb 2 to
            # 5: the rescue changed 1,664 splits, lost a punctuation break in 0 of
            # them, produced out-of-order cuts in 0, and COLLAPSED THE CHUNK
            # COUNT IN 9. It never reached the built ROM as a defect only because
            # the retry loop further down escalates nb and tries again - that is
            # luck, not a guarantee, so reject any rescue whose index is already
            # a cut b' < b chose (b runs in order, so a later cut is the one that
            # would collide and the one skipped).
            #
            # THAT GUARD DOES NOT MAKE sorted(set(cuts)) SAFE IN GENERAL, and do
            # not read it as if it does. Forcing nb 2 to 5 over the corpus still
            # collapses 1,219 times: 967 of those come from the `best is None`
            # min() fallback just below and 256 from the plain windowed pick.
            # What the guard achieves is that NONE of them originates in the
            # rescue any more. On the build's own nb values the collapse count is
            # 0 either way - a refuter confirmed the shipped jpn/spt.bin is
            # BYTE-IDENTICAL with this guard removed - so it is a no-op today
            # and kept only so the rescue cannot become the cause later.
            if best is not None and _word_at(best) == (False, False):
                reach = total / nb * 0.5
                taken = set(cuts)
                rescue, rescue_d = None, None
                for j, k in enumerate(idx):
                    d = abs(cum[j] - target)
                    if d > reach or d <= window: continue
                    if k + 1 in taken: continue
                    if _word_at(k)[0] and (rescue_d is None or d < rescue_d):
                        rescue, rescue_d = k, d
                if rescue is not None:
                    best = rescue
            if best is None:
                best = min(idx, key=lambda k: abs(cum[idx.index(k)] - target))
            c = best + 1
            # A source {E040}/{E042} sitting right at this cut belongs to the
            # text BEFORE the break, not after: box-end already resets the
            # style register (see the note above STYLE_OFF), so leaving a
            # closer as the first thing in the new box only ever matches
            # nothing there - possible now that a merged {E106} run can put
            # a real page break anywhere, including right before a closer
            # the source already carries. Fold it back.
            while c < len(tokens) and tokens[c][0] == 'c' and any(
                    v in STYLE_CLOSERS for v in tokens[c][1]):
                c += 1
            # Test the FOLDED cut against the ones already taken, not the
            # pre-fold candidate: the fold above can walk c forward onto a cut
            # an earlier b already claimed, and then sorted(set(cuts)) below
            # yields one chunk fewer than nb. Never happens in this corpus
            # (0 of 1,223 duplicate cuts were folded) so it is theoretical, but
            # checking before the fold instead of after is simply the wrong
            # place to check.
            if c in cuts and best is not None:
                c = best + 1
            cuts.append(c)
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
        tokens = _bind_title_closer(_split_card_rows(tokens))
        _, nlines = _layout(tokens)
        nb = max(1, -(-nlines // BOX_LINES)) if page else 1
        chunks = [tokens]
        if nb > 1:
            for extra in range(0, 4):
                chunks = split_tokens(tokens, nb + extra)
                # KNOWN, measured, deliberately not fixed: this counts at cells0=0
                # while the emission below passes prefix_px for a re-opened paren,
                # so for a chunk after a break inside a thought the count can be one
                # line short of what is emitted. Passing the prefix here would change
                # box splitting for every parenthesised message, which needs its own
                # verification; the discrepancy does not currently bite (4-line boxes
                # number 217 in both the estimate and real-width builds).
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
        style = None            # the {E04x} opener currently in effect, or None
        for ci, chunk in enumerate(chunks):
            prefix_px = 0       # width this chunk's first line has already spent
            if ci:
                # Close the open span before the break and re-open it after, innermost
                # first. `style` is None whenever the span closed on its own earlier in
                # this chunk, so a term that ends just before the break re-opens nothing.
                # `already_closes` is also true when the chunk's OWN leading tokens are
                # going to print a real {E040}/{E042} first: merging {E106} runs can now
                # put a real page break just before a closer the source already carries,
                # and emitting our own synthetic closer there doubles it up (a {E040}
                # with nothing between it and the source's own, in a box that never had
                # anything coloured in it - box N+1 cannot inherit style either way, so
                # skipping our closer here changes nothing rendered).
                already_closes = _opens_with_close(chunk)
                reopen = style if style is not None and not already_closes else None
                if style is not None and not already_closes: out.append(STYLE_OFF)
                if depth > 0: out.append(PAREN_CLOSE)
                if term == AUTO_BREAK:
                    out.extend((0xE108, AUTO_DELAY, AUTO_BREAK, 0xE107, NEW_BOX_ARG))
                else:
                    out.extend((WAIT_BREAK, 0xE107, NEW_BOX_ARG))
                if depth > 0:
                    out.append(PAREN_OPEN)
                    prefix_px = W(chr(PAREN_OPEN))
                if reopen is not None: out.append(reopen)
                style = reopen
            placed, _ = _layout(chunk, prefix_px)
            cur = 0
            centred = False     # this row opened with {E20D}
            after_br = False
            for kind, val, ln, sp in placed:
                while ln > cur:
                    cur += 1; out.append(0x0A)
                    if centred and not after_br:
                        out.append(LAYOUT_ROW)      # a wrap inside a centred row
                    else:
                        centred = False
                after_br = kind == 'br'
                if kind == 'c' and val[0] == LAYOUT_ROW:
                    centred = True
                if kind == 'c':
                    out.extend(val)
                    for c in val:
                        if c in STYLE_ON: style = c
                        elif c in STYLE_CLOSERS: style = None
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
            tok = [OFFICIAL_TO_DS.get(v, v)]; i += 1
            for _ in range(ARGS.get(v, DEFAULT_ARGS)):
                if i < n and not CTRL(units[i]):
                    tok.append(units[i]); i += 1
            # BOX-OPEN PASSTHROUGH. Capcom's own {E107} argument is emitted
            # unchanged, and where that argument is 2 it means "continue inline in
            # the box already on screen" while Capcom means it to OPEN A FRESH
            # box. The DS then writes a whole new message into a box that was
            # never cleared, the line overflows, and the renderer chops it at the
            # box's right edge IN THE MIDDLE OF A WORD, losing everything after
            # the cut with nothing on screen to say so.
            #
            # Seen on the rig 2026-09-21 in the shipped release, entry 59 str0,
            # Episode 2: the second sentence ran on from the first one's question
            # mark on the same line and was cut off mid-word at the box edge, two
            # words simply gone. A tester independently
            # reported the same fault class in entry 80. Proof in
            # rig/proof/e107/CUTOFF_fender_everythin_box.png.
            #
            # The rule is narrow on purpose. It fires only where this {E107} is
            # OPENING a box, meaning no text has been laid into the current box
            # yet - the first one in a string, or one straight after a
            # box-terminating code. Only the value 2 is rewritten, and only to 3.
            # The values 1, 4, 7 and 9 that the fan script also uses are left
            # alone because nobody has established what they mean. Boxes this
            # converter creates itself already emit NEW_BOX_ARG, so they are
            # unaffected.
            if (BOX_OPEN_FIX and v == 0xE107 and len(tok) > 1 and tok[1] == 2
                    and not any(k == 'w' for k, _ in buf)):
                tok[1] = NEW_BOX_ARG
                _STATS['boxopen'] += 1
            if v in RESET and (v != 0xE106 or e106_clears(units, i)):
                # look ahead: is this a waiting or an auto-advancing terminator?
                # {E106} only takes this branch (a real box end) when
                # e106_clears() finds a prompt/popup code before the next
                # visible text unit - i is already just past {E106}'s args, so
                # this is exactly the position the helper expects. Every other
                # {E106} falls through to the buffering `else` below.
                emit(buf, v if v in (WAIT_BREAK, AUTO_BREAK) else WAIT_BREAK)
                out.extend(tok); buf = []; dq_open = False
            elif (v == LAYOUT_ROW and hard_nl == 'e20d'
                    and any(k == 'w' for k, _ in buf)
                    and buf[-1][0] != 'br'):
                # A {E20D} card row starting a NEW box-run, mid-buffer, after
                # real dialogue - only possible now that {E106} no longer
                # flushes, so a location/date card can arrive glued onto the
                # end of the prose that precedes it. A card has always
                # shipped in its own box and is photographed rendering
                # correctly that way (rig/proof); nothing establishes the
                # engine draws one correctly glued to preceding text, so give
                # it its own box on purpose rather than let it fall wherever
                # pagination happens to land.
                #
                # TWO GUARDS, not one, because a date/place card can hold
                # SEVERAL {E20D} rows of its own (a date row and two place
                # rows) and only the first may
                # open a box - `any(w in buf)` alone fires on every later row
                # too, since the earlier rows' own words are still sitting in
                # buf, and that splits a card that must stay in one box. A
                # source row-to-row separator is a REAL newline immediately
                # followed by {E20D} (hard_nl='e20d' above turns exactly that
                # into a 'br' token, never anything else does), so `buf[-1]`
                # being 'br' means this {E20D} is a later row of a card
                # already under way, not a fresh dialogue-to-card boundary -
                # leave it with what came before.
                #
                # AND THE WHOLE BRANCH IS GATED ON hard_nl == 'e20d', because
                # that is the ONLY mode that produces a 'br' token at all. The
                # four callers that pass hard_nl=False (inject.py:625,
                # loc_patch.py:192, desc_fit.py:34, desc_overflow.py:46) turn a
                # source newline into an 's' token instead, so the card-row
                # guard above would be permanently OFF for them and every later
                # card row would open a box - exactly the card-splitting fault
                # this guard exists to prevent. It fires 0 times from those
                # callers today, so the gate costs no byte, but a latent trap
                # that is already known to have been tripped once does not get
                # left armed.
                #
                # Measured across the corpus: of the 297 {E20D} that reach this
                # tokenizer, 217 are first-in-run with no word content yet
                # (unaffected), 79 are later card rows and EVERY ONE has 'br'
                # as its predecessor, and exactly 1 fires - the Gourd Lake card
                # this branch exists for. Cards split: 0.
                emit(buf, WAIT_BREAK)
                out.extend((WAIT_BREAK, 0xE107, NEW_BOX_ARG))
                buf = [('c', tok)]; dq_open = False
            else:
                # {E106} stays in RESET (other tools - audit_typography,
                # measure_linewidth, loc_patch - still need it as a box-end
                # code for their own purposes) but only e106_clears() decides
                # whether THIS occurrence flushes. An {E106} that does not
                # clear (no prompt/popup code before the next visible text
                # unit - the Fender case) lands here and must NOT flush a box:
                # it does not end one (see the comment on RESET above). Buffer
                # it like an ordinary control token, in its exact stream
                # position, so the text on both sides is laid out and
                # paginated as ONE box-run.
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
    # Glyph swap after layout, so wrapping and page breaks are decided on the periods
    # exactly as before and only the code points change.
    i = 0
    while i < len(out):
        if out[i] == 0xFF0E:
            j = i
            while j < len(out) and out[j] == 0xFF0E: j += 1
            if j - i >= 3:
                for k in range(i, j): out[k] = ELLIPSIS_UNIT
            i = j
        else:
            i += 1
    return out, unmapped
