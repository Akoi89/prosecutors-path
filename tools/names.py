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
    # the DS text font has no accented glyphs (the converter strips them), so
    # dialogue uses 'Gavelle' - matching how the official swapped text already
    # renders her name. Only the nameplate graphic carries the accent.
    ('Justine Courtney', 'Verity Gavelle'),
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
    # non-person names the official localization also changed
    ('Moozilla', 'Taurusaurus'),   # the movie monster
    ('Astique', 'Azea'),           # the elephant
    ('Blaisie', 'Celsius'),        # the chairman's self-chosen nickname
    ('Conductor', 'Ringleader'),   # the masked auction figure
    # surnames
    ('Keyes', 'Saint'), ('Knightley', 'Knight'), ('Courtney', 'Gavelle'),
    ('Debeste', 'Winner'), ('Roland', 'Laguarde'), ('Shields', 'Fender'),
    ('Dogen', 'Kanis'), ('Huang', 'Wang'), ('Swift', 'Lloyd'),
    ('Elbird', 'Carcerato'), ('Rooke', 'Rook'), ('Crane', 'Ringer'),
    ('Hall', 'Bound'), ('Master', 'Tangaroa'), ('Gustavia', 'Gusto'),
    ('Scones', 'Scone'), ('Dover', 'Frost'), ('Marsh', 'Fenn'),
    ('Jenson', 'Niedler'), ('Cameron', 'Aldown'), ('Hoquet', 'Halique'),
    ('Dye-Young', 'Hertz'),
    # NOTE: no bare ('Young','Hertz') - "Young girl..." is prose, and Bonnie
    # Young is always full-named or 'Dye-Young' in the fan text.
    # given names
    ('Simon', 'Simeon'), ('Horace', 'Bronco'), ('Justine', 'Verity'),
    ('Sebastian', 'Eustace'), ('Blaise', 'Excelsius'), ('Patricia', 'Fifi'),
    ('Raymond', 'Eddie'), ('Ray', 'Eddie'), ('Sirhan', 'Bodhidharma'),
    ('Nicole', 'Tabby'), ('Jay', 'Rocco'), ('Ethan', 'Bastian'),
    ('Jill', 'Rosie'), ('Katherine', 'Judy'), ('Kate', 'Judy'),
    ('Jeff', 'Samson'), ('Dane', 'Carmelo'), ('Isaac', 'Artie'),
    ('John', 'Shaun'), ('Karin', 'Florence'), ('Bonnie', 'Hilda'),
    ('Jack', 'Alf'), ('Pierre', 'Paul'), ('Amy', 'Amelie'),
]

CTRL = lambda v: 0xE000 <= v <= 0xF8FF
SPACE = 0xFF3F
APOS = 0x201D

def _ch(v):
    if 0xFF01 <= v <= 0xFF5E: return chr(v - 0xFF01 + 0x21)
    if v == SPACE: return ' '
    return None

def _fwc(c):
    if c == ' ': return SPACE
    return ord(c) - 0x21 + 0xFF01

LETTER = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ-')

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

# Option-widget banks: one line each, and the widget's proven width is whatever
# the fan actually displayed in it - the same budget inject.py uses when it
# swaps these rows. A renamed row wider than that keeps the fan line rather than
# risking a clip, exactly as the injector does.
WIDGET_BANKS = {453, 454, 455, 456, 457}
TYPO = {0x2018: "'", 0x2019: "'", 0x201C: '"', 0x201D: "'",
        0x2013: '-', 0x2014: '-', 0x2026: '.', 0x2025: '.'}

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
            if ch: segs[-1] += dstext._w(ch)
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
            cur += dstext._w(chr(v))
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
        return sum(dstext._w(chr(v)) for v in seq if not CTRL(v) and v >= 0x20)
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
SHORT_PAIRS = [(src, dst.split()[-1]) if (' ' in dst and src != dst) else (src, dst)
               for src, dst in PAIRS]


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


def per_line_harmonize(uu, lim):
    """Rename line by line. Returns (units, changed_lines, fan_lines_kept)."""
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
            w = row_px(nu)
            if w <= lim or w <= orig_w:      # fits, or no wider than the fan drew it
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
    if idx in WIDGET_BANKS and F:
        budget = max(row_px(list(u)) for u in F.values())
    changed = 0
    over = []
    recs = []
    for si, a, ln, u in S:
        uu = list(u)
        if si in F and tuple(u) == F[si]:
            nu, c = substitute(uu)
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
                if budget is not None and row_px(nu) > budget:
                    # wider than the fan ever proved this widget can draw -
                    # keep the fan row rather than risk a clipped line
                    over.append((si, [('widget', row_px(nu), budget)]))
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
                    nu2, c2, kept_lines = per_line_harmonize(uu, lim)
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
