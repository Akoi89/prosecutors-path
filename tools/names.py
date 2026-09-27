# -*- coding: utf-8 -*-
"""Harmonise fan character names to Capcom's in rows that KEEP fan text.

The official localization renamed most of the cast. 98.4% of this port's text
is Capcom's and uses the official names; the strings that keep fan text (whole
kept records, sparse-bank fan rows, hollow reverts, DS-only tutorials and the
over-long descriptions) still said the fan's. This pass rewrites exactly those
strings - a string is eligible only if it is byte-identical to the fan ROM's -
so official text is never touched, and a fan scene keeps its own phrasing with
only the names changed.

Pairs are ordered longest-first so full names win over surnames and surnames
over given names. PROTECT pairs map a phrase to itself to stop a later pair
from matching inside it ("John Doe" is official; "Grand Hall" is a place).
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dstext

PAIRS = [
    # protects (identity) - must come before the pairs they shield
    ('John Doe', 'John Doe'),
    ('Grand Hall', 'Grand Hall'),
    ('Main Hall', 'Main Hall'),
    ('Entrance Hall', 'Entrance Hall'),
    ('Penny Nichols', 'Penny Nichols'),
    # full names
    ('Simon Keyes', 'Simeon Saint'),
    ('Horace Knightley', 'Bronco Knight'),
    # The fan team redrew an e-grave into an unused slot of the main dialogue
    # font (dstext.ACCENT_SLOTS), so a row landing in ordinary dialogue can carry
    # the accent Capcom's own script uses for her name. _fwc below maps it to
    # that slot; rows in the smaller description/Logic face (DESC_BANKS) fall
    # back to a plain 'e' there, since that face's slots are unverified.
    ('Justine Courtney', 'Verity Gavèlle'),
    ('Sebastian Debeste', 'Eustace Winner'),
    ('Blaise Debeste', 'Excelsius Winner'),
    ('Patricia Roland', 'Fifi Laguarde'),
    ('Raymond Shields', 'Eddie Fender'),
    ('Sirhan Dogen', 'Bodhidharma Kanis'),
    ('Di-Jun Huang', 'Di-Jun Wang'),
    ('Nicole Swift', 'Tabby Lloyd'),
    ('Jay Elbird', 'Rocco Carcerato'),
    ('Ethan Rooke', 'Bastian Rook'),
    ('Jill Crane', 'Rosie Ringer'),
    ('Katherine Hall', 'Judy Bound'),
    ('Jeffrey Master', 'Samson Tangaroa'),   # fan long form, seen on the CG text screens
    ('Jeff Master', 'Samson Tangaroa'),
    ('Delicia Scones', 'Delicia Scone'),
    ('Dane Gustavia', 'Carmelo Gusto'),
    ('Isaac Dover', 'Artie Frost'),
    ('John Marsh', 'Shaun Fenn'),
    ('Karin Jenson', 'Florence Niedler'),
    ('Bonnie Young', 'Hilda Hertz'),
    ('Jack Cameron', 'Alf Aldown'),
    ('Pierre Hoquet', 'Paul Halique'),
    ('Amy Marsh', 'Amelie Fenn'),
    ('Dye-Young Hospital', 'Hertz Hospital'),
    ('Dai-Long Lang', 'Da-Long Lang'),   # official spelling per gk2_txtcut_en
    # non-person names the official localization also changed
    ('Moozilla', 'Taurusaurus'),   # the movie monster
    ('Astique', 'Azea'),           # the elephant
    ('Blaisie', 'Celsius'),        # the chairman's self-chosen nickname
    ('Conductor', 'Ringleader'),   # the masked auction figure
    # surnames
    ('Keyes', 'Saint'), ('Knightley', 'Knight'), ('Courtney', 'Gavèlle'),
    ('Debeste', 'Winner'), ('Roland', 'Laguarde'), ('Shields', 'Fender'),
    ('Dogen', 'Kanis'), ('Huang', 'Wang'), ('Swift', 'Lloyd'),
    ('Elbird', 'Carcerato'), ('Rooke', 'Rook'), ('Crane', 'Ringer'),
    ('Hall', 'Bound'), ('Master', 'Tangaroa'), ('Gustavia', 'Gusto'),
    ('Scones', 'Scone'), ('Dover', 'Frost'), ('Marsh', 'Fenn'),
    ('Jenson', 'Niedler'), ('Cameron', 'Aldown'), ('Hoquet', 'Halique'),
    ('Dye-Young', 'Hertz'), ('Dai-Long', 'Da-Long'),
    # NOTE: no bare ('Young','Hertz') - "Young girl..." is prose, and Bonnie
    # Young is always full-named or 'Dye-Young' in the fan text.
    # given names
    ('Simon', 'Simeon'), ('Horace', 'Bronco'), ('Justine', 'Verity'),
    ('Sebastian', 'Eustace'), ('Blaise', 'Excelsius'), ('Patricia', 'Fifi'),
    ('Raymond', 'Eddie'), ('Ray', 'Eddie'), ('Sirhan', 'Bodhidharma'),
    ('Nicole', 'Tabby'), ('Jay', 'Rocco'), ('Ethan', 'Bastian'),
    ('Jill', 'Rosie'), ('Katherine', 'Judy'), ('Kate', 'Judy'),
    ('Jeffrey', 'Samson'), ('Jeff', 'Samson'), ('Dane', 'Carmelo'), ('Isaac', 'Artie'),
    ('John', 'Shaun'), ('Karin', 'Florence'), ('Bonnie', 'Hilda'),
    ('Jack', 'Alf'), ('Pierre', 'Paul'), ('Amy', 'Amelie'),
]

CTRL = lambda v: 0xE000 <= v <= 0xF8FF
SPACE = 0xFF3F
APOS = 0x201D

def _ch(v):
    # The space glyph (U+FF3F) sits inside the fullwidth range and must be tested
    # first, or it projects to '_' and no pair containing a space can ever match:
    # that is how 'John Doe' lost its protection and became 'Shaun Doe' (1.8.1).
    if v == SPACE: return ' '
    if 0xFF01 <= v <= 0xFF5E: return chr(v - 0xFF01 + 0x21)
    return None

def _fwc(c):
    if c == ' ': return SPACE
    if ord(c) in dstext.ACCENT_SLOTS: return dstext.ACCENT_SLOTS[ord(c)]
    return ord(c) - 0x21 + 0xFF01

LETTER = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ')   # '-' is a boundary: 'Courtney-pie' must rename

def substitute(u):
    """Apply PAIRS to one unit list. Returns (new_units, n_changes) - word
    boundaries only, longest pair first at each position."""
    u = list(u)
    # ascii projection with index map (None for non-text units)
    proj = [(_ch(v) if not CTRL(v) else None) for v in u]
    out = []
    changes = 0
    i = 0
    N = len(u)
    def is_letter(k):
        c = proj[k] if 0 <= k < N else None
        return c is not None and c in LETTER
    while i < N:
        hit = None
        if is_letter(i) and not is_letter(i - 1):
            for src, dst in PAIRS:
                m = len(src)
                if i + m > N: continue
                ok = True
                for k in range(m):
                    c = proj[i + k]
                    want = src[k]
                    if c is None or c != want: ok = False; break
                if not ok: continue
                if is_letter(i + m): continue      # word boundary after
                hit = (src, dst)
                break
        if hit:
            src, dst = hit
            if src != dst:
                changes += 1
            out += [_fwc(c) for c in dst]
            i += len(src)
        else:
            out.append(u[i]); i += 1
    return out, changes

# line-width budget per bank (px) and its display line cap; everything else
# is dialogue (wraps at ~200 and paginates, and no dialogue line grew past
# its fan width in the audit)
LIMITS = {432: (180, 4), 438: (180, 4), 395: (176, 3), 391: (176, 3),
          453: (306, 1), 454: (306, 1), 455: (306, 1), 456: (306, 1), 457: (306, 1)}
DIALOG_LIMIT = 200
# 432/395 are the description/Logic banks (loc_patch.desc_font's smaller face,
# accent slots unverified there - see dstext.ACCENT_SLOTS_ON). 438 and 391 share
# those two banks' exact width/line budgets above, which is why they are grouped
# with them here rather than left as ordinary dialogue. The option-widget banks
# (WIDGET_BANKS below) render inline in a message box in the main dialogue font,
# so they are NOT in this set.
DESC_BANKS = {432, 438, 395, 391}
_ACCENT_VALS = set(dstext.ACCENT_SLOTS.values())        # {0x0415, 0x30A7}
_PLAIN_E = 0xFF01 + (ord('e') - 0x21)                    # fullwidth 'e'
# Acceptance bound for a RENAMED line (no re-wrapping involved). 200 is the wrap
# budget for reflowing official text; the fan patch itself shipped 1,224 dialogue
# lines wider than 216 px (max 238, p99 218), so a renamed line up to 216 is within
# what the fan already proved the box draws.
RENAME_LIMIT = 216
# Every budget above (LIMITS, DIALOG_LIMIT, RENAME_LIMIT) was cut in the units of
# dstext's ESTIMATE model, not real pixels. Since 2026-09-19 dstext._w returns the
# font's real advances once inject.py loads them, which run 12-14% wider, so
# measuring with it against these budgets would tighten every gate in this file
# by that much and quietly change which rows get their official names. Measure
# with the model the budgets were cut for; the numbers and the ruler stay together.
_w = dstext._estimate

# row-specific trims where a longer official name cannot fit a full box
# (drop a filler word - same discipline as tools/condense.py)
def _fwseq(s):
    return [0xFF3F if c == ' ' else (0x201D if c == "'" else ord(c) - 0x21 + 0xFF01) for c in s]

ROWFIX = {(432, 292): (_fwseq('Was Samson'), _fwseq('Samson')),
          # 'Mr. Master's' -> 'Mr. Tangaroa's' pushed this option-widget row past
          # the budget the fan proved; the honorific is the cheapest word to lose.
          # The period here is U+2025, which is how this script writes 'Mr.'
          (453, 299): ([0xFF2D, 0xFF52, 0x2025, 0xFF3F] + _fwseq('Tangaroa'),
                       _fwseq('Tangaroa'))}
          # 1.5.1 once carried five more rows here (DS[29] str14, DS[76] str7,
          # DS[94] str2, DS[99] str4, DS[117] str28): a literal find/replace pair
          # per row, each trimming a fan sentence that the official name had
          # pushed past its box. Removed 2026-09-23 (repo-text audit) rather than
          # converted: instrumenting the injector's real build path showed none of
          # the five rows' source strings are still byte-identical to the fan ROM
          # there (the surrounding rename/relayout work has moved past them since
          # 1.5.1), so harmonize_entry's own `tuple(u) == F[si]` guard already
          # skipped all five on every build - they never applied in the build path
          # that ships the ROM. (coverage.py calls harmonize_entry(fent, fent, i),
          # comparing the fan entry to itself for measurement only; that guard
          # trivially passes there, which is a different thing from the build
          # path and is not what "unreachable" refers to.) Confirmed by rebuilding
          # after the deletion: the output ROM is byte-identical without them.

# Option-widget banks: one line each. 456/457 keep the older budget - whatever
# the fan actually displayed in that bank, measured in dstext._estimate units,
# same as inject.py's own now-superseded fan-max budget for them. 453/454/455
# (WIDGET_SMALL_BANKS below) instead use the SMALL-font real advances against
# the 2026-09-27 sweep's proven field widths (fontwidths.small_widths, loaded
# by inject.py's use_small_widths() below) - the estimate model and a
# fan-row-derived budget both measure the wrong thing for these three, exactly
# as they did in inject.py's own widget path before that fix.
WIDGET_BANKS = {453, 454, 455, 456, 457}
WIDGET_SMALL_BANKS = {453, 454, 455}
WIDGET_PROVEN_PX = {453: 189, 454: 229, 455: 189}
_SMALL = {}


def use_small_widths(widths):
    """Load the SMALL1 real advances inject.py read from the ROM. Call once,
    before harmonize_entry() runs on any Mind Chess bank; a falsy `widths`
    (ROM did not match) leaves _SMALL empty, and row_px_small() below then
    prices every renamed row 9999 - the widget-budget check that uses it can
    then only fail toward keeping the fan's row, never ship an unmeasured
    one."""
    global _SMALL
    if not widths:
        return False
    _SMALL = widths
    return True
TYPO = {0x2018: "'", 0x2019: "'", 0x201C: '"', 0x201D: "'",
        0x2013: '-', 0x2014: '-', 0x2026: '.', 0x2025: '.'}
# Banks whose renamed rows must fall back to a plain 'e' rather than the
# redrawn MAIN-only accent slots (2026-09-27 text-box sweep): the description/
# Logic face already did this (DESC_BANKS); the Mind Chess banks (453-458, the
# option/question/banner widgets and their "_dl" copies alike - the spec calls
# for all six, not just WIDGET_BANKS' 453-457) draw a SMALL face that has no
# U+0415 record at all (fontwidths.SMALL_TABLE_OFF) and an unverified U+30A7
# one, so a kept-fan row renamed to "Gavelle" must not carry the accent into a
# face that may not draw it (found on-ROM: 453/451, 455/111 both spelled it
# with U+0415).
ACCENT_OFF_BANKS = DESC_BANKS | WIDGET_BANKS | {458}

def row_px(u):
    """Widest display line, measured the way inject.py measures these rows."""
    segs, k = [0], 0
    while k < len(u):
        v = u[k]
        if CTRL(v):
            k += 1 + dstext.ARGS.get(v, 0); continue
        if v == 0x0A:
            segs.append(0)
        else:
            ch = (chr(v - 0xFEE0) if 0xFF01 <= v <= 0xFF5E
                  else TYPO.get(v, chr(v) if v >= 0x20 else ''))
            if ch: segs[-1] += _w(ch)
        k += 1
    return max(segs)


def row_px_small(u):
    """Widest display line for a WIDGET_SMALL_BANKS row, measured with the
    ROM's own SMALL1 advances (_SMALL, loaded by use_small_widths()) instead
    of the estimate model row_px() uses - the same font Mind Chess actually
    draws these rows in (2026-09-27 text-box sweep). `u` is already fullwidth
    (substitute()'s _fwc() converts every replacement character before this
    ever runs), so most units are looked up as-is.

    The fan's redrawn accent slots (MAIN-only) map to a plain fullwidth 'e'
    first. Every OTHER unit is looked up DIRECTLY in _SMALL first, because the
    apostrophe (dstext.APOS, U+201D) and the open/close quote (U+201C) the
    fan's font actually draws are themselves real entries in SMALL1 (2px and
    7px) - only when that direct lookup misses does this fall back to TYPO's
    plain-ASCII spelling, re-fullwidthed (the em/en dash and the Collection's
    single-character ellipsis have no direct SMALL1 entry of their own, so
    they do need this). Getting this order backwards - re-fullwidthing the
    apostrophe/quote through TYPO before trying them directly - looks them up
    as U+FF07/U+FF02, which SMALL1 does not have either, so a renamed row
    with so much as one apostrophe priced at 9999 and always kept the fan
    name (found 2026-09-27 refuting this file's own first draft: 453/247 and
    453/536 wrongly kept fan names, and 453/299's "Tangaroa's" trim measured
    10,178px instead of its real ~181px). A glyph _SMALL has no record for at
    all - including every character while _SMALL is empty - still prices at
    9999, so an unmeasured row can only fail the budget check toward keeping
    the fan's line, never ship unmeasured."""
    segs, k = [0], 0
    while k < len(u):
        v = u[k]
        if CTRL(v):
            k += 1 + dstext.ARGS.get(v, 0); continue
        if v == 0x0A:
            segs.append(0)
        else:
            vv = _PLAIN_E if v in _ACCENT_VALS else v
            a = _SMALL.get(vv)
            if a is None and v in TYPO:
                c = TYPO[v]
                fv = 0xFF3F if c == ' ' else ord(c) - 0x21 + 0xFF01
                a = _SMALL.get(fv)
            segs[-1] += 9999 if a is None else a
        k += 1
    return max(segs)


BOXEND = {0xE102, 0xE104, 0xE106, 0xE185, 0xE081}

def line_widths(u):
    """Width in px of each display line: lines break on 0x0A AND at box ends."""
    lines, cur = [], 0.0
    for v in u:
        if v == 0x0A or v in BOXEND:
            lines.append(cur); cur = 0.0
        elif not CTRL(v) and v >= 0x20:
            cur += _w(chr(v))
    lines.append(cur)
    return lines

def rebreak(u, limit, orig=None):
    """Move trailing words of over-wide lines onto the following SOFT line.

    A push moves a line break, never adds one, so line indices are stable -
    which lets each line's ORIGINAL width act as its own floor: a line the fan
    already drew wider than `limit` (the padded Age headers, wide dialogue
    lines) is left exactly as wide as it was, and only lines our substitutions
    GREW past both bounds are re-broken. Returns (units, still_over:list)."""
    u = list(u)
    floors = line_widths(orig) if orig is not None else []
    def lim_for(k):
        f = floors[k] if k < len(floors) else 0.0
        return max(limit, f)
    def width(seq):
        return sum(_w(chr(v)) for v in seq if not CTRL(v) and v >= 0x20)
    # index lines: list of (start, end, sep_index_or_None soft)
    changed = True
    guard = 0
    while changed and guard < 64:
        changed = False; guard += 1
        # find first over-wide line with a soft break after it
        pos = 0; start = 0
        breaks = []          # (start, end, sep_pos, soft)
        for k, v in enumerate(u):
            if v == 0x0A or v in BOXEND:
                breaks.append((start, k, k, v == 0x0A))
                start = k + 1
        breaks.append((start, len(u), None, False))
        for ln, (a, b, sep, soft) in enumerate(breaks):
            seg = u[a:b]
            if width(seg) <= lim_for(ln) or not soft:
                continue
            # last space in the segment
            sp = None
            for k in range(b - 1, a, -1):
                if u[k] == SPACE: sp = k; break
            if sp is None: continue
            # push the last word down: the space becomes the line break and
            # the old break becomes a space joining it to the next line
            u[sp] = 0x0A; u[b] = SPACE
            changed = True
            break
    bad = [(k, w) for k, w in enumerate(line_widths(u)) if w > lim_for(k)]
    return u, bad



# Official surnames, for the one line where the full official name will not fit.
# Capcom's own script refers to most characters by surname anyway.
def _short_pairs():
    # From every full-name pair, learn the official SURNAME for the fan full name,
    # the fan first name and the fan surname alike ('Sirhan' -> 'Kanis', not
    # 'Bodhidharma'), keeping PAIRS' longest-first order. Pairs with no full-name
    # parent stay as they are.
    surname = {}
    for src, dst in PAIRS:
        if src != dst and ' ' in src and ' ' in dst:
            last = dst.split()[-1]
            surname.setdefault(src, last)
            for part in src.split():
                surname.setdefault(part, last)
    out = []
    for src, dst in PAIRS:
        if src == dst:
            out.append((src, dst))
        else:
            out.append((src, surname.get(src, dst.split()[-1] if ' ' in dst else dst)))
    return out


SHORT_PAIRS = _short_pairs()


def _substitute_with(u, pairs):
    global PAIRS
    saved = PAIRS
    PAIRS = pairs
    try:
        return substitute(u)
    finally:
        PAIRS = saved


def _split_lines(u):
    """Split a unit list into (segment, separator) pieces at soft newlines and
    box ends, keeping every unit. Segments carry the text, separators the break."""
    out, cur = [], []
    for v in u:
        if v == 0x0A or v in BOXEND:
            out.append((cur, [v])); cur = []
        else:
            cur.append(v)
    out.append((cur, []))
    return out


def _apply_fix(nu, fix):
    """Replace the first occurrence of fix[0] in nu with fix[1] (a ROWFIX pair)."""
    if not fix:
        return nu
    f, r = fix
    for k in range(len(nu) - len(f) + 1):
        if nu[k:k + len(f)] == f:
            return nu[:k] + list(r) + nu[k + len(f):]
    return nu


def per_line_harmonize(uu, lim, fix=None):
    """Rename line by line. Returns (units, changed_lines, fan_lines_kept).
    `fix` is the row's ROWFIX pair, applied to a line after the full-name
    substitution so a hand-shortened line is measured, not the raw rename."""
    out, changed, kept = [], 0, 0
    for seg, sep in _split_lines(uu):
        if not seg:
            out += sep; continue
        orig_w = row_px(seg)
        best = None
        for pairs in (PAIRS, SHORT_PAIRS):
            nu, c = _substitute_with(seg, pairs)
            if not c:
                best = seg; break
            nu = _apply_fix(nu, fix)
            w = row_px(nu)
            if w <= max(lim, RENAME_LIMIT) or w <= orig_w:   # fits the proven box, or no wider than the fan drew it
                best = nu; changed += 1; break
        if best is None:
            best = seg; kept += 1
        out += best + sep
    return out, changed, kept


def harmonize_entry(entry, fan_entry, idx):
    """Apply the name pairs to every string of `entry` that is byte-identical
    to its counterpart in `fan_entry` (i.e. kept fan text). Returns
    (new_entry_bytes_or_original, strings_changed, still_overflowing)."""
    import spt as _spt
    from build_spt import build_ds as _build_ds
    try:
        h, _ = _spt.parse(entry, True)
        S = list(_spt.all_strings(entry, True))
        F = {si: tuple(u) for si, a, ln, u in _spt.all_strings(fan_entry, True)} if fan_entry else {}
    except Exception:
        return entry, 0, []
    lim, cap = LIMITS.get(idx, (DIALOG_LIMIT, None))
    budget = None
    rowpx_fn = row_px
    if idx in WIDGET_SMALL_BANKS:
        rowpx_fn = row_px_small
        budget = WIDGET_PROVEN_PX[idx]
    elif idx in WIDGET_BANKS and F:
        budget = max(row_px(list(u)) for u in F.values())
    changed = 0
    over = []
    recs = []
    for si, a, ln, u in S:
        uu = list(u)
        if si in F and tuple(u) == F[si]:
            nu, c = substitute(uu)
            if c and idx in ACCENT_OFF_BANKS:
                # This row's font is the smaller description/Logic face, or one
                # of the Mind Chess widget banks, whose slots have not been
                # checked for the redrawn accents (SMALL1 has no U+0415 record
                # at all - see fontwidths.py); fall back to the plain letter
                # rather than assume they carry it too.
                nu = [_PLAIN_E if v in _ACCENT_VALS else v for v in nu]
            if c:
                fx = ROWFIX.get((idx, si))
                if fx:
                    f, r = fx
                    for k in range(len(nu) - len(f) + 1):
                        if nu[k:k+len(f)] == f:
                            nu[k:k+len(f)] = r; break
                nu, bad = rebreak(nu, lim, orig=uu)
                if bad and cap:
                    cur = 1 + sum(1 for v in nu if v == 0x0A)
                    if cur < cap:
                        target = bad[0][0]
                        line_no = 0; start = 0
                        for k2, v in enumerate(nu + [0x0A]):
                            if v == 0x0A or v in BOXEND:
                                if line_no == target:
                                    sp = None
                                    for q in range(k2 - 1, start, -1):
                                        if nu[q] == SPACE: sp = q; break
                                    if sp is not None: nu[sp] = 0x0A
                                    break
                                line_no += 1; start = k2 + 1
                        bad = [(k3, w) for k3, w in enumerate(line_widths(nu)) if w > lim]
                if budget is not None and rowpx_fn(nu) > budget:
                    # wider than the fan ever proved this widget can draw -
                    # keep the fan row rather than risk a clipped line
                    over.append((si, [('widget', rowpx_fn(nu), budget)]))
                    recs.append((a, uu))
                    continue
                if bad:
                    # A longer official name pushed a line past its box and
                    # neither re-breaking nor the spare-line split could bring
                    # it back - usually because the over-wide line ends a box,
                    # so there is nowhere to push the word to. Until v1.5 the
                    # whole row then kept the fan's names, dozens of boxes for
                    # the sake of one line. Now: rename line by line, official
                    # name where it fits, official surname where it does not,
                    # and the fan line only if even that is too wide.
                    nu2, c2, kept_lines = per_line_harmonize(uu, lim, fix=ROWFIX.get((idx, si)))
                    if c2 and idx in ACCENT_OFF_BANKS:
                        # same plain-letter fallback as above for the smaller/widget face
                        nu2 = [_PLAIN_E if v in _ACCENT_VALS else v for v in nu2]
                    if kept_lines:
                        over.append((si, [('line-kept-fan', kept_lines)]))
                    if c2:
                        recs.append((a, nu2)); changed += 1
                    else:
                        recs.append((a, uu))
                    continue
                uu = nu
                changed += 1
        recs.append((a, uu))
    if not changed:
        return entry, 0, over
    return _build_ds(recs[0][1], recs[1:], h['term'], h['scale'], h['last']), changed, over
