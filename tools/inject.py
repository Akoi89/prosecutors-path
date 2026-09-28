# -*- coding: utf-8 -*-
"""Inject the Collection's official English script into the GK2 DS ROM.

Structure is taken from the DS side and only the string CONTENT is swapped:
the DS engine addresses strings by index, so record count, per-record A fields and
the trailer word are carried over from the DS entry. An entry is only touched when
its string count matches the Collection file's exactly.
"""
import sys, os, io, json, struct, collections, difflib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# The audit this prints contains Japanese, which the Windows console's default
# codepage cannot encode. reconfigure() rather than a fresh TextIOWrapper: wrapping
# sys.stdout.buffer again abandons whatever the old wrapper still had buffered, so
# anything printed before this module was imported would silently disappear.
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except AttributeError:                                    # pragma: no cover
    sys.stdout.flush()
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from spt import all_strings, parse, tails
from build_spt import build_ds, build_archive
import dstext
import fontwidths          # module level so PyInstaller's scan cannot miss it
import buttons             # same reason; see the note in buttons.py
from dstext import convert, ARGS
from episode_titles import retitle
from loc_patch import load_lookup, patch_entry
from map_ids import ds_entries
from paths import work, data
import stmt_trim
import linefix
import last_rows
import rewrite
import relaid_rows
import condense_rows
import skipguard

# Codes that end a message box (the box-count fingerprint used for alignment checks).
BOXEND = {0xE102, 0xE104, 0xE106, 0xE185, 0xE081}

# Capcom renamed every episode (Turnabout Target -> Turnabout Trigger, The Imprisoned
# Turnabout -> The Captive Turnabout, ...). Those names live in DS[460] strings 24-93,
# which is only the SAVE/LOAD slot list - the episode-select screen shows them as a
# BITMAP we have not located (it is somewhere in jpn/idlocal.bin, 676 entries).
# Switching only the save slots puts two different names for the same episode one menu
# apart, so leave the fan's names until the bitmap can be redrawn to match.
RETITLE = True

# Recover entries whose string COUNTS differ because the fan patch restructured
# them: joining long retail strings was split back, and regions re-cut into a
# different number of pieces are re-cut again at the fan's own boundaries
# (region_align below - it subsumed the earlier single-join `split_merged` and
# reproduces its 9 entries byte-identically, plus the shapes it could not reach:
# multiple joins in one entry, and p:q regions). Verification is strict per-string
# box-end code MULTISET equality against the fan layout - stronger than the JP
# profile's per-string counts, which is why realigned entries skip the relaid
# check. Every E081 argument (the index of the next string to play - all 2,650
# tail occurrences in the corpus are valid in-range indices; linear scenes use
# k+1, investigation hubs share a return target) is rewritten positionally from
# the fan counterpart, because official-layout indices are skewed after a re-cut
# and a stale index can make a string jump to itself.
SPLIT_MERGED = True

# Recover strings the fan patch RELAID by moving the cut point between neighbours.
# In 42 runs of adjacent strings (concentrated in Ep1 and Ep4-5) the fan shifted
# message boxes between two or three consecutive strings - always conserving the
# total (+8/-8, -38/+38) or adding exactly one E081 terminator when the retail
# layout's neighbour was empty. Joining the official strings for the run (absorbing
# each inner E081 tail where present - strings that end an entry carry none) and
# re-cutting at the fan's own boundaries reproduces the fan layout exactly. The
# only gate is strict per-string box-end code-multiset equality with the fan
# string: an official string that merged a box pair, or used a different box-end
# variant (DS[236] has E104 where the official holds E102), fails it and the whole
# run stays fan. No count tolerance applies here, unlike the ordinary swap path.
RECUT_SHIFTED = True

# Block (c) below (the DSONLY set, inside `if KEEP_DSONLY_GATE:` in main()) keeps the fan's string whenever
# the converted string carries fewer {E041}/{E042} than the fan's. Investigation
# 2026-09-21 (fan_tone/E04X_FINDINGS.md, independently refuted in
# fan_tone/E04X_REFUTATION.md: verdict ACCEPT) read the arm9 script interpreter
# (0x0200DCE0) and renderer (0x02078784, runs at 0x01FFCxxx from the ITCM autoload)
# and found E040-E043 are absolute colour setters with no state, no wait and no
# callback - not open/close pairs, so "fewer than the fan" is not "unbalanced". The
# v1.4.2 Episode 1 hang the gate's comment blames on a missing E041/E042 pair was
# really {E2B0}, Capcom's inline button-icon glyph, passing through unmapped (arity
# 0 in the engine's own arity table, so the following unit is misread as text);
# _has_foreign and tools/buttons.py now catch that. A throwaway ROM built with this
# gate off (port/out/EXPERIMENT_nodsonly.nds, not reproducible from any tree on
# disk) measured 98.8% coverage against the shipped 93.8%, ran Episode 1 past the
# Gourd Lake handoff twice from independent cold boots with no hang
# (fan_tone/RIG_NODSONLY.md), and survived a six-attack Fable adversarial pass
# (fan_tone/E04X_ATTACK.md) plus the refuter's ACCEPT. Set True to restore the old
# behaviour; the block itself is kept, not deleted, so the gate can be turned back
# on without reconstructing it.
KEEP_DSONLY_GATE = False

# Mind Chess option/question/banner rows (2026-09-27 text-box sweep). These
# three banks draw in the SMALL face (fontwidths.small_widths), not the MAIN
# dialogue face the sparse widget path used to measure every bank with - a
# capture of the option bar showed a row's final letter dropped where the
# MAIN measurement said it still fit. 456/457/458 share the same on-disk row
# shape and the same estimate-unit budget in names.py's WIDGET_BANKS, but the
# sweep found no engine handle for 456/457 in the arm9 or any overlay, and 458
# (Collection match score 1.0, the same 12 two-line rows as 455) sits at 2 of
# 160 rows non-empty in the fan ROM itself - so close to entirely unused that
# it is probably never read either - extending this fix to them would touch
# banks nothing displays, and forcing 456 (Collection match score 0.75)
# through this gate would newly trip the score<0.90 reject just below and
# drop official text an unread bank never shows anyway, so they are left out.
SMALL_WIDGET_BANKS = {453, 454, 455}
# Per-bank proven field width in SMALL px. 453 and 454's are the sweep's
# captured/measured limits (a capture of the option bar placed its field at
# 189<=L<193; a capture of the question bar showed a 192px row drawn whole,
# and the fan itself shipped this bank up to 229 with nothing narrower ever
# proven wrong). 455 is a single-line banner: the sweep found 12 of 32 rows
# silently losing their whole second line because the widget path never
# reached this bank at all (see the forced entry below), so it wrapped as
# ordinary MAIN dialogue at the 240px budget instead of drawing SMALL and
# staying on one line. Never inflate these from a fan placeholder row
# ("Temp." dev text, 453/54) - they are fixed numbers, not a max over fan
# rows, precisely so a placeholder cannot set the budget.
WIDGET_PROVEN_PX = {453: 189, 454: 229, 455: 189}
# 455 never reaches the sparse-widget gate on its own: its Collection/JP
# control-code profile overlap is high (never <0.35, unlike 453/454, whose
# rows are option-widget text foreign enough to the profile to trip it),
# even though it is display-identical in kind to 453/454 (a single option
# line, SMALL font, exam_ask_title in the trial bundle). Force it through so
# it gets the same unwrapped-widget treatment instead of ordinary paginated
# dialogue wrap. Checked empirically 2026-09-27 (build instrumented to print
# every bank that reaches the gate): only 453, 454 and unrelated banks
# 213/339-342/345/352/353/460 do on their own; 455/456/457/458 never do.
FORCE_WIDGET_GATE = {455}
# Accent-off scope for change 2 of the sweep fix: wider than SMALL_WIDGET_BANKS
# on purpose. 456-458 never reach the sparse widget path above (confirmed
# empirically, see FORCE_WIDGET_GATE's comment) and keep the ordinary
# convert(u) call a few lines down for whatever Capcom text lands there, but
# they are the same SMALL-font family as 453-455 (their "_dl" copies) and the
# spec calls for all six banks accent-clean, not only the three whose width
# this fix also corrects (456/451 and 458/111 both still carried U+0415
# before this set existed).
MIND_CHESS_BANKS = {453, 454, 455, 456, 457, 458}


def _boxend_counts(u):
    """Box-end code multiset, walking with arities so argument units are never
    mistaken for codes."""
    c = collections.Counter()
    i, n = 0, len(u)
    while i < n:
        v = u[i]
        if 0xE000 <= v <= 0xF8FF:
            if v in BOXEND:
                c[v] += 1
            i += 1 + ARGS.get(v, 0)
        else:
            i += 1
    return c


def _code_positions(u):
    """Indices of control-code units, walking arities so argument units are never
    mistaken for codes."""
    out = []
    i = 0
    while i < len(u):
        v = u[i]
        if 0xE000 <= v <= 0xF8FF:
            out.append(i)
            i += 1 + ARGS.get(v, 0)
        else:
            i += 1
    return out


INDEX_ARGS = {          # code: argument positions (0-based) that are string indices
    0xE187: (0, 1),     # existing behaviour: strip id AND target string, unchanged
    0xE11F: (1, 2, 3),  # rebuttal statement setup, arity 5
    0xE120: (1,),       # rebuttal setup close, arity 2
    0xE080: (0,),       # arity 1
    0xE0B0: (1, 3, 5, 7),  # arity 8, pairs (value, index) x4
    0xE1C1: (0,),       # arity 1
    0xE164: (1,),       # arity 2
    0xE161: (1,),       # arity 2
    0xE162: (0,),       # arity 1
    0xE1A6: (1, 2, 3),  # arity 5 (DELTA 1: entry 248 str 18)
    0xE1E9: (0,),       # arity 1 (DELTA 1: entry 248 str 18)
    0xE11B: (1,),       # arity 2 (DELTA 1: entry 248 str 22, points at itself)
    0xE160: (0,),       # arity 1 (DELTA 1: entry 247 str 4)
    # The six string-selecting codes VERIFY2 (Gap 2) found outside this table,
    # added 2026-09-27 as a GUARD: measured over the whole script on the
    # 1.10.0 release, the pre-fix 1.9.1 build and the merged next-release
    # tree, all 1,114 occurrences carry the fan's arguments already (0
    # differing, 0 count-mismatched strings), because none of the 48 entries
    # that hold them was ever re-cut - the 1.9.1 skew set was entries 92, 95,
    # 234, 245, 247, 248, 250, 253, 256, 267, 307, 314, 326 (and 411 for
    # {E131}), none of which carries any of the six. Listing them costs
    # nothing now (0 rewrites, measured by a dry run of this function) and stops a
    # future re-cut of a Mind Chess or talk-hub entry from skewing them
    # silently. Semantics (playtest/INDEXARGS6_FINDINGS.md): position 1 of
    # {E200} is a 1-based row of bank 453 (the Mind Chess option text) and
    # of {E1FD}/{E20A} a 1-based row of bank 454 (the question text);
    # position 2 of all three is the string in THIS entry the pick jumps to.
    # {E17E}/{E17F} position 1 and {E180} position 0 are the string in this
    # entry a talk topic / presented item / default response dispatches to.
    0xE200: (1, 2),     # arity 4: (?, bank-453 row 1-based, target string, ?)
    0xE1FD: (1, 2),     # arity 4: (?, bank-454 row 1-based, target string, ?)
    0xE20A: (1, 2),     # arity 4: (?, bank-454 row 1-based, target string, ?)
    0xE17E: (1,),       # arity 4: (topic id, target string, ?, ?)
    0xE17F: (1,),       # arity 2: (item id, target string)
    0xE180: (0,),       # arity 1: (target string)
}
for _code, _positions in INDEX_ARGS.items():
    if not all(p < ARGS[_code] for p in _positions):
        raise ValueError('INDEX_ARGS entry %s: position out of range' % (_code,))

# DS-specific values that are not string indices but must still come from the fan,
# same reason as {E187}/{E11F}/etc: the Collection's own value is wrong for our
# layout. {E131} (entry 411, map0c) is a list of map/area ids 0..19; ours holds
# [0,1,3,4..19], the fan AND the Japanese retail both hold [0,1,2,4..19] - one
# value differs (3 where the DS has 2); 0, 1 and 4..19 are identical. DS map ids are
# DS data the Collection must not override (same class as the 1.8.6 strip-id fix),
# not an index into this entry's own strings, so it gets its own table rather than
# INDEX_ARGS, but the same per-string positional copy and gate.
DS_VALUE_ARGS = {
    0xE131: (0,),       # arity 1
}
for _code, _positions in DS_VALUE_ARGS.items():
    if not all(p < ARGS[_code] for p in _positions):
        raise ValueError('DS_VALUE_ARGS entry %s: position out of range' % (_code,))

# The camera/character position/pose family: six commands whose ARGUMENTS are
# DS screen coordinates or animation choices, not indices - {E13A} place
# character, {E13B} slide character over time, {E16F} move character, {E114}
# walk character, {E15B} camera, {E150} pose (<char><anim>). The Collection
# re-tuned every one of these for its own screen and cast; the fan ROM (AAI2
# Final v2) keeps the DS originals, which are the values right for the DS
# engine, same reasoning as DS_VALUE_ARGS above but for a whole command family
# rather than one argument slot. A tester playing the staged build reported a
# Case 2 scene where the camera never returns to its resting position and an
# officer is left out of frame; traced to spt entry 99 string 5, where our
# build carries the Collection's own staging in place of the fan's. A second
# tester reported (2026-09-26) a Case 3 scene where a character is drawn as
# in the Collection rather than as on the DS; traced to spt entry 125, where
# the fan carries about sixteen {E150} pose commands for three characters
# that ours lacked entirely. Measured whole-game with dedicated scanning
# tools (not part of this repo): 73 strings in 53 entries differ from the
# fan in the five position/camera codes, and {E150} differs from the
# fan in a further 8 strings in 5 entries; most differ only in argument
# values, some are STRUCTURAL (the Collection added or dropped a command in
# the sequence). See _restore_staging below, which restores the fan's
# subsequence of these codes (with all their arguments, and in the right
# message box) into every string this injector ships.
#
# {E12F} (the per-line talking animation, roughly 20,000 uses across the
# script) is deliberately NOT in this table: it is set by Capcom to match its
# OWN line's timing and delivery, not a DS position/pose value the fan
# preserves - restoring it here would fight the Collection's own voice
# direction rather than fix a staging fault. See _restore_index_args' own
# exclusions list above for the same reasoning stated for INDEX_ARGS.
STAGING_CODES = (0xE13A, 0xE13B, 0xE16F, 0xE114, 0xE15B, 0xE150)

# The character commands among STAGING_CODES carry the character id as their
# FIRST argument; {E15B} (camera) has no character. _restore_staging aligns
# occurrences on (code, character id) for the former and (code,) for the
# latter, so a run of "char 5 twice then char 32 twice" is never matched
# against "char 32 twice then char 5 twice" just because the codes agree.
_STAGING_CHAR_CODES = (0xE13A, 0xE13B, 0xE16F, 0xE114, 0xE150)


def _staging_key(code, args):
    return (code, args[0]) if code in _STAGING_CHAR_CODES else (code,)


def _restore_index_args(conv, ds, code, table=INDEX_ARGS):
    """Several engine commands carry arguments that are STRING INDICES within
    the same spt entry (a rebuttal's statement pointers, a choice button's
    target, ...). Both value spaces are DS-specific, and neither is remapped
    anywhere in the toolchain - dstext.py appends the Collection's own
    argument units unchanged, so any index a re-cut (region_align /
    RECUT_SHIFTED) skews comes through wrong. DS entry 92 (Case 2, Gavelle's
    rebuttal) proved this: its {E11F}x5/{E120} statement pointers were every
    one -1 against the fan, statement 0 pointed at an empty stub, no
    statement box was drawn, and the ARM9 data-aborted (rig, 2026-09-22;
    CRASH_ENTRY92_20260922.md). A ROM with only those indices set to the
    fan's values played the rebuttal correctly, five distinct statements in
    story order - the indices are not merely non-crashing, they are the
    RIGHT strings. DS entry 248 (Case 4) carries the identical fault.

    INDEX_ARGS lists, per code, which 0-based argument positions (of that
    code's ARGS arity) are string indices; every other argument position is
    left untouched. This absorbed the old {E187}-only `_restore_choice_args`
    (the 1.8.6 fix) - {E187}: (0, 1) reproduces that function's behaviour
    byte-for-byte, same two positions, same gate, same bounds check.

    Codes deliberately NOT in this table:
      * {E081} - the string-jump index is already rewritten by region_align
        (inject.py, the E081 rewrite below), which owns it.
      * {E254} - entry 333's ten values (332..341) differ from the fan by a
        ROTATION of the same ids (fan order 333..341, 332), not a shift; it
        is not an index fault and is not touched here.
      * {E100} (entry 70) - two box-position values swapped back and forth,
        speaker order, not an index.
      * {E12F} (entries 79, 234, 291) - the character-animation command;
        its small values are Capcom's animation choices, not indices.
      * {E131} (entry 411, map0c) - a list of DS map/area ids, not a string
        index into this entry; restored by the separate DS_VALUE_ARGS table
        (defined above) through this same function, not through INDEX_ARGS.

    `table` selects which of the two positional tables (INDEX_ARGS or
    DS_VALUE_ARGS) supplies the argument positions for `code`; everything
    else about the walk, the gate and the bounds check is shared.

    Gate is per STRING, not per entry (an entry is many strings) AND per
    CODE: where one string's count of this code does not match the fan's,
    that string's occurrences of this code alone are left unrewritten and
    counted as a mismatch; other codes in that string, and every other
    string, are still corrected.

    Bounds-checked the same way region_align's own {E081} rewrite loop is,
    a few dozen lines below in this file (the `for ku, ka in zip(pu, pa):`
    loop guarded by `ku + 1 < len(u) and ka + 1 < len(a)`): a string
    truncated at its declared length with the code's argument past the end
    would otherwise index past the list and kill the build. Skip that one
    occurrence, rather than raise, if it ever happens.

    Returns (rewritten, mismatched_strings)."""
    positions = table[code]
    hi = max(positions)
    rewritten = mismatched_strings = 0
    for j in range(len(conv)):
        u, a = conv[j], list(ds[j][3])
        pu = [k for k in _code_positions(u) if u[k] == code]
        pa = [k for k in _code_positions(a) if a[k] == code]
        if not pu and not pa:
            continue
        if len(pu) != len(pa):
            mismatched_strings += 1
            continue
        for ku, ka in zip(pu, pa):
            if ku + 1 + hi >= len(u) or ka + 1 + hi >= len(a):
                continue
            changed = False
            for p in positions:
                if u[ku + 1 + p] != a[ka + 1 + p]:
                    changed = True
                u[ku + 1 + p] = a[ka + 1 + p]
            if changed:
                rewritten += 1
    return rewritten, mismatched_strings


# Box-end codes for _restore_staging's insertion-anchor fallback AND its box-
# placement check - deliberately this specific list, not _SEAM_BOXEND a few
# lines down (narrower, for a different rule) and not BOXEND (the box-count
# fingerprint used elsewhere in this file).
_STAGING_BOXEND = (0xE102, 0xE104, 0xE185, 0xE081)


def _box_index(x, pos):
    """How many _STAGING_BOXEND codes occur in x strictly before raw index
    pos - which box (0-based) raw index pos falls in."""
    n = 0
    for k in _code_positions(x):
        if k >= pos:
            break
        if x[k] in _STAGING_BOXEND:
            n += 1
    return n


def _box_starts(x):
    """Raw start index of every box in x: box 0 begins at 0; box t+1 begins
    right after the t-th _STAGING_BOXEND code (in order) and its argument."""
    starts = [0]
    for k in _code_positions(x):
        if x[k] in _STAGING_BOXEND:
            starts.append(k + 1 + ARGS[x[k]])
    return starts


def _text_count(u, lo, hi):
    """Count of VISIBLE text units in u[lo:hi], walked arity-aware: anything
    that is not a control code or its arguments, and not a bare {0A} line
    break on its own - the one definition of "visible text" used everywhere
    this file or audits/audit_staging.py needs it: the proportional-point
    placement's F/O/f scaling and the coarse before/after-text property,
    _has_text below, are the same count; a line break alone was never "some
    text" for either purpose."""
    n = 0
    k = lo
    while k < hi:
        v = u[k]
        if 0xE000 <= v <= 0xF8FF:
            k += 1 + ARGS.get(v, 0)
        else:
            if v != 0x0A:
                n += 1
            k += 1
    return n


def _has_text(u, lo, hi):
    """The COARSE in-box property: is there any visible text unit in
    u[lo:hi] at all (_text_count > 0), without counting how many."""
    return _text_count(u, lo, hi) > 0


def _leading_codes(x, lo, hi):
    """Control-code IDs (not their arguments) that lead x[lo:hi], in order,
    stopping at the first visible text unit or at `hi` - a box's own OPENING
    codes, compared by id only when deciding where to insert at the very
    start of a box (see _place_like_fan)."""
    out, k = [], lo
    while k < hi:
        v = x[k]
        if 0xE000 <= v <= 0xF8FF:
            out.append(v)
            k += 1 + ARGS.get(v, 0)
        else:
            break
    return out


def _text_prefix_point(u, lo, hi, target):
    """Raw index in [lo, hi] after exactly `target` text units of u[lo:hi],
    walked one TOKEN at a time (a control code plus its own arguments is one
    token, contributing 0; anything else is one token, contributing 1) - so
    the result always sits on a token boundary, never between a code and its
    arguments or inside a run of arguments. target <= 0 returns lo
    unconditionally: the very start of the
    span, before any opening codes it might have ("at target 0, insert right
    after the previous box-end code... before its opening codes")."""
    if target <= 0:
        return lo
    seen, k = 0, lo
    while k < hi:
        v = u[k]
        if 0xE000 <= v <= 0xF8FF:
            k += 1 + ARGS.get(v, 0)
        else:
            k += 1
            seen += 1
            if seen >= target:
                return k
    return hi


def _box_span(x, box_idx):
    """(lo, hi) raw span of box `box_idx` in x, or None if x has fewer boxes."""
    starts = _box_starts(x)
    if box_idx >= len(starts):
        return None
    lo = starts[box_idx]
    hi = starts[box_idx + 1] if box_idx + 1 < len(starts) else len(x)
    return lo, hi


def _place_like_fan(u, a, box_idx, fan_pos):
    """Raw index in box `box_idx` of u at the SAME RELATIVE TEXT POINT as the
    fan's occurrence at raw index `fan_pos` in box `box_idx` of a - an
    earlier version of this placement always landed right after a box's
    OPENING codes regardless of where the fan actually put the command; this
    scales instead: f = text units before fan_pos in its own fan box, F =
    text units in that whole fan box, O = text units in our corresponding
    box; target = round(f * O / F) text units into our box (0 if F == 0, so
    an entirely textless fan box still lands at its own start), snapped to a
    token boundary. None if u has fewer than box_idx + 1 boxes.

    At target 0 specifically: landing at the raw box start (before EVERY
    opening code) can still put the command ahead of a code the fan itself
    has ahead of it in that box, if ours opens with the same one - DS[137]
    string 10's box 0 is `{E100}<0> pose {E101}...` in both the fan and an
    earlier build that landed the pose before {E100} instead of after it.
    Compare the fan's own leading code IDs ahead of its occurrence
    (_leading_codes) against ours' leading code IDs, by id only (not
    arguments), and skip forward past their
    common prefix before landing - the same {E100} at the front of both
    still means "insert right after it", not "at the very start"."""
    fspan = _box_span(a, box_idx)
    uspan = _box_span(u, box_idx)
    if uspan is None or fspan is None:
        return None
    flo, fhi = fspan
    f = _text_count(a, flo, fan_pos)
    F = _text_count(a, flo, fhi)
    ulo, uhi = uspan
    O = _text_count(u, ulo, uhi)
    target = round(f * O / F) if F else 0
    if target <= 0:
        fan_lead = _leading_codes(a, flo, fan_pos)
        our_lead = _leading_codes(u, ulo, uhi)
        k = 0
        while k < len(fan_lead) and k < len(our_lead) and fan_lead[k] == our_lead[k]:
            k += 1
        pos = ulo
        for code in our_lead[:k]:
            pos += 1 + ARGS.get(code, 0)
        return pos
    return _text_prefix_point(u, ulo, uhi, target)


def _adjacent_no_text(oa, a, prev_raw, next_raw):
    """True if fan occurrences at raw indices prev_raw and next_raw (into an
    occurrence list `oa` built over string `a`) sit in the SAME box with no
    TEXT between the end of prev_raw's own units and the start of next_raw -
    only then does "right after/before the neighbour" reproduce the fan's
    placement; a neighbour in a different box, or with text between, needs
    the proportional-point placement instead. False for an out-of-range
    index (no such neighbour exists)."""
    if prev_raw < 0 or next_raw < 0 or next_raw >= len(oa) or prev_raw >= len(oa):
        return False
    pk, pc, _ = oa[prev_raw]
    nk, _, _ = oa[next_raw]
    if _box_index(a, pk) != _box_index(a, nk):
        return False
    return _text_count(a, pk + 1 + ARGS[pc], nk) == 0


def _restore_staging(conv, ds):
    """Per string, restore the fan's SUBSEQUENCE of STAGING_CODES (with every
    argument, in the same message box, and at the same RELATIVE TEXT POINT
    inside that box) - nothing else in the string changes.

    Most of the strings the whole-game scan found (see STAGING_CODES above)
    carry the same staging occurrences in the same order as the fan, only the
    argument VALUES differ (the Collection's re-tuned coordinates/poses);
    those are copied in place, occurrence by occurrence. A smaller set is
    STRUCTURAL - the Collection added, dropped or reordered a staging command
    - so the two occurrence lists (ours vs the fan's) are aligned first, not
    on the CODE alone (entry 125 string 0 has the fan placing char 5
    twice then char 32 twice, all four {E13A} in the SAME box, where ours had
    one of each; aligning on code alone matched (5, 32) to the fan's (5, 5)
    and put char 32's pair in the wrong box). The alignment KEY is (code,
    character id) for the five character commands and (code,) alone for
    {E15B} (camera, no character) - _staging_key above.

    Before alignment, both occurrence lists are DEDUPED (_dedupe): the fan
    sometimes issues the exact same staging command twice with NOTHING
    between the two but {E107}/{E108} pacing codes, and (code, character id)
    alone cannot tell two DIFFERENT poses of the same character apart, so a
    run of "the same character, several different poses" would otherwise
    look like one ambiguous block of identical keys to difflib. Collapsing
    every occurrence that merely shares a VALUE, not just a back-to-back
    repeat, was tried first and proved too broad: entry 128 string 1 reuses
    the SAME pose value at two points in the SAME
    box with nine text units and an {E101} between them - not a back-to-back
    repeat - and collapsing it anyway put both copies together at one end of
    the box, losing the one meant for the other end. Only a TRUE repeat
    (nothing textual or structural between the two) collapses to one
    representative plus a multiplicity; anything else stays two occurrences,
    each placed on its own merits below.

    A key that only names the code and character cannot tell two DIFFERENT
    occurrences of the same character's command apart when OUR side repeats
    it more than the fan does (real content between the repeats, so _dedupe
    left them separate) - _disambiguate relabels every excess occurrence of
    ours EXCEPT the one that best corresponds to the fan's, so the excess
    falls to removal on its own merits instead of stealing an 'equal' match
    that belongs to a closer occurrence (entry 137 string 10: our side had
    five copies of a pose the fan uses once; a plain match kept the wrong
    one, in the wrong box, and deleted the copy that was already right).

    Placement for a command this function INSERTS or MOVES: the same
    relative TEXT POINT inside the fan's box as the fan's own occurrence -
    `f` text units before it in the fan's box, `F` text units in that whole
    box, `O` text units in our corresponding box; target = round(f * O / F)
    text units into our box (0 if F == 0), snapped to a token boundary
    (_place_like_fan/_text_prefix_point) - never after every opening code by
    default, which could print a pose before any of its box's own text when
    the fan meant it mid-line or at the very end; and at target 0, never
    before an opening code the fan itself has ahead of the command AND our
    box also opens with (compared by code id, not arguments; a plain "always
    the very start" placed a pose ahead of a speaker-set code both the fan
    and ours already had there). Two shortcuts skip this maths for the
    common case of a duplicate riding the neighbour it is inserted next to:
    the very FIRST fan occurrence of an our-side-empty run goes right after
    our nearest preceding surviving occurrence, and the very LAST goes right
    before our next surviving occurrence, but ONLY when that neighbour is
    the SAME occurrence in the fan too - same box, no text between
    (_adjacent_no_text). Every other occurrence, including one whose
    "neighbour" shortcut fails this check, is placed by the proportional
    point instead, each on its own text point independently (not as one
    shared block) - multiple such placements queue against the ORIGINAL
    string and are spliced in together, in fan order, when the string is
    rebuilt. A block where our side is NOT empty (both sides have
    occurrences to align) keeps the fan's run where our first removed
    occurrence stood.

    Bounds-checked the same way _restore_index_args is: a string truncated at
    its declared length (spt.tails) could put an argument past either
    string's end. Whatever is built is verified afterwards - the recomputed
    staging list must equal the fan's exactly - and if it does not, or a
    bounds check ever fails, the string is left exactly as it stood before
    this function touched it. Never raises.

    Separately, and regardless of whether a string needed restoring: if our
    string and the fan's carry the same COUNT of _STAGING_BOXEND codes, every
    staging occurrence's box index is compared against the fan's occurrence
    at the same position. A string whose subsequence ALREADY matched the
    fan's (so the alignment above never touched it) can still land a staging
    occurrence in the wrong box - an unrelated code shifted the box-end count
    around without changing the total. Rather than leave that unrepaired,
    _relocate_boxes moves ONLY that occurrence's own raw units (code plus its
    arguments, nothing else in the string) to the fan's box, at the fan's
    relative text point inside it (an earlier version of this move used the
    same after-every-opening-code rule mentioned above and put entry 277
    string 1's pose ahead of text the fan prints it after), and re-verifies
    the subsequence still matches before keeping the move. Only a mismatch
    that CANNOT be fixed this way (the target box does not exist, or the
    move would break the subsequence) is LOGGED and shipped as-is -
    reverting would put back whatever the Collection shipped, which is not
    known to be right either.

    Once box placement is right, ONE more thing is checked - an earlier
    version of this pass also scaled every occurrence's exact in-box text
    POINT to a proportional target and moved anything more than 2 units off,
    even in a string whose subsequence and box already equalled the fan's;
    that used the fan's own (different) wording to guess where a pose
    belongs in ours, and touched 28 strings that needed no fix at all. That
    is removed: a string already matching the fan on subsequence and box
    comes out
    byte-identical to the build before this pass, except that each
    occurrence's COARSE property - _has_text, some visible text before it in
    its own box, or none - is compared to the fan's, and only a mismatch is
    moved (still by the proportional-point placement/_relocate_boxes) to the
    fan's side of the text. A coarse before/after-text comparison run over
    the whole game found 634 of 637 already-matching strings already
    agreeing with the fan here; only 124/3, 147/0 and 214/1 (each a pose
    Capcom sets before the text where the fan sets it after some) do not.
    The build log's count is higher because it also includes strings that
    were resequenced first and then needed this move.

    Returns (values, resequenced, skipped, box_mismatches, moved_box,
    moved_coarse): strings fixed by a straight argument copy, strings whose
    staging sequence had to be resequenced (NOT counting a string that was
    only moved by one of the two passes below - those are counted only in
    moved_box/moved_coarse, so a resequenced string always needed a real
    realignment), strings left untouched because the result could not be
    proven right, the string indices (within this entry) whose box placement
    disagreed with the fan's, and two separate STRING counts for
    _relocate_boxes's two passes - box placement and coarse text side - so a
    string that needed both is visible in each count
    rather than being double-counted into one combined total."""
    values = resequenced = skipped = moved_box = moved_coarse = 0
    box_mismatches = []
    for j in range(len(conv)):
        u = conv[j]
        a = list(ds[j][3])

        def occs(x):
            out = []
            for k in _code_positions(x):
                v = x[k]
                if v in STAGING_CODES:
                    n = ARGS[v]
                    out.append((k, v, tuple(x[k + 1:k + 1 + n])))
            return out

        ou, oa = occs(u), occs(a)

        def _relocate_boxes(x, targets, expect_seq):
            """Move ONLY the raw units of mismatched staging occurrences
            (their own code unit plus arguments - nothing else) to the box
            each should sit in per `targets` ((occurrence index, fan box
            index) pairs), at the fan's own relative text point inside that
            box (proportional-point placement: _place_like_fan, using this same string's `oa` for
            the fan occurrence's position), leaving every other unit exactly
            where it was. Every target's insertion point is computed against
            the ORIGINAL x, all moving occurrences are removed together, and
            occurrences that land at the SAME point are reinserted together
            in FAN order (occurrences the fan placed before or after each
            other keep that relative order) - moving several at once one at
            a time, recomputing
            positions as it goes, could otherwise reorder a whole cluster
            relative to itself. None if a target box does not exist in x, or
            the result would stop matching `expect_seq` (the fan's
            subsequence) - the caller logs the mismatch instead of shipping a
            broken move."""
            occ = occs(x)
            if any(t >= len(occ) for t, _ in targets):
                return None
            plans = []
            for t, box_idx in targets:
                k, code, _ = occ[t]
                n = ARGS[code]
                ins = _place_like_fan(x, a, box_idx, oa[t][0])
                if ins is None:
                    return None
                plans.append((t, k, n, ins))
            spans = sorted((k, k + 1 + n, t) for t, k, n, _ in plans)
            rest, keep_ranges = [], []
            prev = 0
            for k, end, _t in spans:
                keep_ranges.append((prev, k, len(rest)))
                rest.extend(x[prev:k])
                prev = end
            keep_ranges.append((prev, len(x), len(rest)))
            rest.extend(x[prev:len(x)])

            def to_new(idx):
                for lo, hi, base in keep_ranges:
                    if lo <= idx <= hi:
                        return base + (idx - lo)
                return len(rest)

            blocks = {t: x[k:k + 1 + n] for t, k, n, _ in plans}
            groups = {}
            for t, k, n, ins in plans:
                groups.setdefault(to_new(ins), []).append(t)
            cur = list(rest)
            for ins in sorted(groups, reverse=True):
                block = []
                for t in sorted(groups[ins]):
                    block += blocks[t]
                cur = cur[:ins] + block + cur[ins:]
            if [(c, ag) for _, c, ag in occs(cur)] != expect_seq:
                return None
            return cur

        fan_seq = [(c, args) for _, c, args in oa]
        final_u = u
        if [(c, args) for _, c, args in ou] != fan_seq:
            try:
                keys_u = [_staging_key(c, args) for _, c, args in ou]
                keys_a = [_staging_key(c, args) for _, c, args in oa]
                if keys_u == keys_a:
                    nu = list(u)
                    for (ku, cu, _), (ka, _, aargs) in zip(ou, oa):
                        n = ARGS[cu]
                        if ku + 1 + n > len(nu) or ka + 1 + n > len(a):
                            raise ValueError('truncated string')
                        nu[ku + 1:ku + 1 + n] = list(aargs)
                    kind = 'values'
                else:
                    m = len(ou)
                    bp = [0] * (m + 1)
                    for t in range(m):
                        bp[t + 1] = ou[t][0] + 1 + ARGS[ou[t][1]]
                    gaps = [list(u[bp[t]:ou[t][0]]) for t in range(m)]
                    gaps.append(list(u[bp[m]:len(u)]))
                    slots = [list(u[ou[t][0]:ou[t][0] + 1 + ARGS[ou[t][1]]]) for t in range(m)]
                    removed = [False] * m

                    def _true_repeat(raw, end_prev, start_next):
                        """True if raw[end_prev:start_next] holds nothing but
                        {E107}/{E108} pacing codes - a genuine
                        back-to-back repeat, not the same value reused at two
                        different points in the box (entry 128 string 1)."""
                        k = end_prev
                        while k < start_next:
                            v = raw[k]
                            if v in (0xE107, 0xE108):
                                k += 1 + ARGS.get(v, 0)
                            else:
                                return False
                        return True

                    def _dedupe(occ_list, raw):
                        """Maximal runs of TRUE-repeat occurrences (same code
                        and args, _true_repeat between each consecutive
                        pair). Returns [(raw_index_of_representative,
                        multiplicity), ...]."""
                        out = []
                        i, n = 0, len(occ_list)
                        while i < n:
                            k = i + 1
                            while (k < n and occ_list[k][1] == occ_list[i][1]
                                   and occ_list[k][2] == occ_list[i][2]
                                   and _true_repeat(raw, occ_list[k - 1][0] + 1 + ARGS[occ_list[k - 1][1]],
                                                     occ_list[k][0])):
                                k += 1
                            out.append((i, k - i))
                            i = k
                        return out

                    def _rep_units(rep_i, mult):
                        ka, ca, aargs = oa[rep_i]
                        n = ARGS[ca]
                        if ka + 1 + n > len(a):
                            raise ValueError('truncated string')
                        return ([ca] + list(aargs)) * mult

                    dedup_u = _dedupe(ou, u)
                    dedup_a = _dedupe(oa, a)
                    du = len(dedup_u)

                    def _frac(x, pos):
                        """0..1: how far through its own box raw index pos
                        sits, by TEXT units - None if x has no box there."""
                        b = _box_index(x, pos)
                        span = _box_span(x, b)
                        if span is None:
                            return None
                        lo, hi = span
                        total = _text_count(x, lo, hi)
                        return _text_count(x, lo, pos) / total if total else 0.0

                    def _disambiguate():
                        """A reduced (code, char) key does not distinguish
                        two occurrences of the SAME character's command with
                        DIFFERENT values - fine when there is at most one on
                        each side, but if OUR side repeats a key at points
                        _dedupe did not merge (real content between them, not
                        a true repeat) more times than the fan does, plain
                        key-based alignment has no way to tell which of ours
                        already corresponds to the fan's occurrence and
                        matches whichever difflib meets first: entry 137
                        string 10 has five occurrences of a pose the fan only
                        uses once; a plain match paired the fan's copy with
                        whichever of ours came first (in the wrong box),
                        deleted the copy that was ALREADY RIGHT, and placed
                        the survivor into the fan's box from the wrong side.
                        Relabel every occurrence of our excess EXCEPT
                        whichever sits in the SAME BOX as the fan's
                        occurrence (ties broken by text fraction) so it gets
                        a unique key and can never claim an 'equal' match -
                        it falls to removal instead, on its own merits. (The
                        opposite direction - the fan repeating a key more
                        than we do - was tried the same way and confirmed, by
                        comparing a build with and without it over the whole
                        game, to change nothing: removed.)"""
                        keys_a_d = [_staging_key(oa[s][1], oa[s][2]) for s, _ in dedup_a]
                        keys_u_d = [_staging_key(ou[s][1], ou[s][2]) for s, _ in dedup_u]
                        ra, ru = {}, {}
                        for idx, k in enumerate(keys_a_d):
                            ra.setdefault(k, []).append(idx)
                        for idx, k in enumerate(keys_u_d):
                            ru.setdefault(k, []).append(idx)
                        for key in set(ra) | set(ru):
                            a_idxs, u_idxs = ra.get(key, []), ru.get(key, [])
                            if len(u_idxs) > len(a_idxs):
                                a_box = {ai: _box_index(a, oa[dedup_a[ai][0]][0]) for ai in a_idxs}
                                u_box = {ui: _box_index(u, ou[dedup_u[ui][0]][0]) for ui in u_idxs}
                                af = {ai: _frac(a, oa[dedup_a[ai][0]][0]) for ai in a_idxs}
                                uf = {ui: _frac(u, ou[dedup_u[ui][0]][0]) for ui in u_idxs}
                                pairs = sorted(
                                    (0 if u_box[ui] == a_box[ai] else 1,
                                     abs(af[ai] - uf[ui]) if af[ai] is not None and uf[ui] is not None else 1.0,
                                     ai, ui)
                                    for ai in a_idxs for ui in u_idxs)
                                chosen, used_a = set(), set()
                                for _, _, ai, ui in pairs:
                                    if ui in chosen or ai in used_a:
                                        continue
                                    chosen.add(ui)
                                    used_a.add(ai)
                                for ui in u_idxs:
                                    if ui not in chosen:
                                        keys_u_d[ui] = ('EXCESS', ui)
                        return keys_a_d, keys_u_d

                    keys_a_d, keys_u_d = _disambiguate()

                    # Positions chosen by proportional-point placement queue here against the
                    # ORIGINAL string (never against a gap already grown by
                    # an earlier insertion), sorted into place per gap once
                    # every opcode has been read - order_seq is the tiebreak
                    # so same-point insertions still land in fan order.
                    lead_prefix = {}
                    trail_suffix = {}
                    pending = {t: [] for t in range(m + 1)}
                    order_seq = [0]

                    def _gap_of(idx):
                        for t in range(m + 1):
                            end = ou[t][0] if t < m else len(u)
                            if bp[t] <= idx <= end:
                                return t
                        return m

                    def _queue(idx, units):
                        t = _gap_of(idx)
                        pending[t].append((idx - bp[t], order_seq[0], units))
                        order_seq[0] += 1

                    def _place(fan_pos, units):
                        box_idx = _box_index(a, fan_pos)
                        ins = _place_like_fan(u, a, box_idx, fan_pos)
                        if ins is None:
                            ins = len(u)
                        _queue(ins, units)

                    sm = difflib.SequenceMatcher(None, keys_a_d, keys_u_d, autojunk=False)
                    for op, i1, i2, j1, j2 in sm.get_opcodes():
                        if op == 'equal':
                            for di, dj in zip(range(i1, i2), range(j1, j2)):
                                rs, rc = dedup_u[dj]
                                fi, fmult = dedup_a[di]
                                _, ca, aargs = oa[fi]
                                n = ARGS[ca]
                                if oa[fi][0] + 1 + n > len(a):
                                    raise ValueError('truncated string')
                                take = min(rc, fmult)
                                for t in range(take):
                                    ku, cu, _ = ou[rs + t]
                                    if ku + 1 + n > len(u):
                                        raise ValueError('truncated string')
                                    slots[rs + t] = [ca] + list(aargs)
                                for t in range(rs + take, rs + rc):
                                    removed[t] = True
                                if fmult > rc:
                                    # A TRUE repeat (see _dedupe) our side only has
                                    # once: the extra copy is a genuine
                                    # back-to-back duplicate, so it rides
                                    # right after the copy already there.
                                    extra = ([ca] + list(aargs)) * (fmult - rc)
                                    lead_prefix[rs + rc] = lead_prefix.get(rs + rc, []) + extra
                            continue

                        if j1 < j2:
                            # Both sides have deduped groups here (replace, or
                            # an our-only run to drop): the fan's run goes
                            # where our first removed group stood.
                            raw_start = dedup_u[j1][0]
                            raw_end = dedup_u[j2 - 1][0] + dedup_u[j2 - 1][1]
                            units = []
                            for di in range(i1, i2):
                                fi, fmult = dedup_a[di]
                                units += _rep_units(fi, fmult)
                            slots[raw_start] = units
                            for t in range(raw_start + 1, raw_end):
                                removed[t] = True
                            continue

                        # Our side is EMPTY here (deduped j1 == j2): the fan
                        # has one or more deduped groups ours entirely lacks.
                        # First, chain consecutive fan groups that have NO
                        # TEXT between them - this is about ADJACENCY, not
                        # value identity, so it ignores KEY entirely (a
                        # key-based run split was tried first and proved too
                        # narrow). Only the chain touching the block's own
                        # start can ride the real preceding surviving
                        # occurrence, and only the chain touching its own end
                        # can ride the real following one, and only when that
                        # neighbour really is adjacent with no text either;
                        # every other chain (including a boundary chain that
                        # fails its neighbour check) is placed by the
                        # proportional-point placement as one unit, using its
                        # first member's fan position. (Removing the "ride
                        # the following occurrence" shortcut for the chain
                        # touching the block's own end was tried, expecting
                        # it to be redundant once a chain can be placed on
                        # its own; comparing a build with and without it,
                        # byte for byte, over the whole game showed exactly
                        # one difference, entry 99 string 5: without the
                        # shortcut, the proportional placement moved an
                        # {E16F} move-character command to land after the
                        # engine command {E15A}<0> instead of before it,
                        # where the shortcut (and the fan) keep it. Kept.)
                        chains = []
                        for di in range(i1, i2):
                            if chains and _adjacent_no_text(
                                    oa, a, dedup_a[di - 1][0] + dedup_a[di - 1][1] - 1, dedup_a[di][0]):
                                chains[-1].append(di)
                            else:
                                chains.append([di])
                        lead_claim = (j1 > 0 and i1 > 0 and _adjacent_no_text(
                            oa, a, dedup_a[i1 - 1][0] + dedup_a[i1 - 1][1] - 1, dedup_a[i1][0]))
                        trail_claim = (j2 < du and i2 < len(dedup_a) and _adjacent_no_text(
                            oa, a, dedup_a[i2 - 1][0] + dedup_a[i2 - 1][1] - 1, dedup_a[i2][0]))

                        for ci, chain in enumerate(chains):
                            units = []
                            for di in chain:
                                fi, fmult = dedup_a[di]
                                units += _rep_units(fi, fmult)
                            if ci == 0 and lead_claim:
                                raw_gap = dedup_u[j1][0] if j1 < du else m
                                lead_prefix[raw_gap] = lead_prefix.get(raw_gap, []) + units
                            elif ci == len(chains) - 1 and trail_claim:
                                raw_gap = dedup_u[j2][0] if j2 < du else m
                                trail_suffix[raw_gap] = trail_suffix.get(raw_gap, []) + units
                            else:
                                _place(oa[dedup_a[chain[0]][0]][0], units)

                    for t in range(m + 1):
                        content = gaps[t]
                        if pending[t]:
                            items = sorted(pending[t], key=lambda p: (p[0], p[1]))
                            rebuilt, prev = [], 0
                            for off, _, punits in items:
                                off = max(0, min(off, len(content)))
                                rebuilt.extend(content[prev:off])
                                rebuilt.extend(punits)
                                prev = off
                            rebuilt.extend(content[prev:])
                            content = rebuilt
                        gaps[t] = lead_prefix.get(t, []) + content + trail_suffix.get(t, [])

                    nu = []
                    for t in range(m):
                        nu.extend(gaps[t])
                        if not removed[t]:
                            nu.extend(slots[t])
                    nu.extend(gaps[m])
                    kind = 'resequenced'
            except (ValueError, IndexError):
                skipped += 1
                continue

            if [(c, args) for _, c, args in occs(nu)] != fan_seq:
                skipped += 1
                continue
            conv[j] = nu
            final_u = nu
            if kind == 'values':
                values += 1
            else:
                resequenced += 1

        # Box placement check: only where box-end COUNTS agree (a
        # translation-driven box count difference makes a box-for-box
        # comparison meaningless, not a placement fault) and only once the
        # subsequence itself is known to match the fan's (true here either
        # because the string always matched, or because it was just proven
        # above) - so occurrence counts are always equal when this runs.
        occ_o = occs(final_u) if final_u is not u else ou
        box_ok = False
        if len(_box_starts(final_u)) == len(_box_starts(a)) and len(oa) == len(occ_o):
            bad = [(t, _box_index(a, oa[t][0])) for t in range(len(oa))
                   if _box_index(a, oa[t][0]) != _box_index(final_u, occ_o[t][0])]
            if bad:
                fixed = _relocate_boxes(final_u, bad, fan_seq)
                if fixed is not None:
                    conv[j] = fixed
                    final_u = fixed
                    occ_o = occs(final_u)
                    moved_box += 1
                    box_ok = True
                else:
                    box_mismatches.append(j)
            else:
                box_ok = True

        # COARSE in-box property, checked separately from box placement and
        # only once it is right: an earlier version of this pass also scaled
        # every occurrence's exact in-box text point to a proportional target
        # and moved anything more than 2 units off, even in a string whose
        # subsequence AND box already equalled the fan's - a string the
        # Collection placed against ITS OWN wording, where a point derived
        # from the fan's different wording is a guess. A coarse
        # before/after-text comparison run over the whole game found that of
        # 637 strings whose subsequence and box already matched, 634 already
        # agree with the fan on this coarser property; only 3 (124/3, 147/0,
        # 214/1) do not, so only those need moving (the log's count also
        # includes resequenced strings that land on the wrong side). Once every occurrence
        # sits in the right box, each occurrence's COARSE property - is
        # there any visible text before it in its own box, _has_text, not a
        # scaled text-unit count - is compared to the fan's; only a mismatch
        # is moved, still by the proportional-point placement
        # (_relocate_boxes/_place_like_fan), to the fan's side of the text.
        # Everything else in a box-correct string is left exactly as it was
        # - byte-identical to the build before this pass unless this is the
        # reason it changed.
        if box_ok:
            coarse_bad = []
            for t in range(len(oa)):
                b = _box_index(a, oa[t][0])
                fspan, ospan = _box_span(a, b), _box_span(final_u, b)
                if fspan is None or ospan is None:
                    continue
                fan_after = _has_text(a, fspan[0], oa[t][0])
                our_after = _has_text(final_u, ospan[0], occ_o[t][0])
                if fan_after != our_after:
                    coarse_bad.append((t, b))
            if coarse_bad:
                fixed = _relocate_boxes(final_u, coarse_bad, fan_seq)
                if fixed is not None:
                    conv[j] = fixed
                    final_u = fixed
                    moved_coarse += 1
    return values, resequenced, skipped, box_mismatches, moved_box, moved_coarse


# Box-end codes for the seam-cue rule below - deliberately NOT inject.py's own
# BOXEND (which also holds {E185}/{E081}, used for the box-count fingerprint):
# this is rig/seam_cues.py's narrower set, the definition the DELTA 2 spec names
# ("after the last E102/E104/E106 or text unit").
_SEAM_BOXEND = {0xE102, 0xE104, 0xE106}


def _seam_cmds(u):
    """(start_index, code_or_None, args_tuple) per unit, arity-aware exactly like
    _code_positions/rig/seam_cues.py's cmds() - a plain text or data unit (outside
    0xE000-0xF8FF, which includes a stray non-argument {00}) comes back as
    (k, None, None), never mistaken for a code."""
    out, k = [], 0
    while k < len(u):
        v = u[k]
        if 0xE000 <= v <= 0xF8FF:
            n = ARGS.get(v, 0)
            out.append((k, v, tuple(u[k + 1:k + 1 + n])))
            k += 1 + n
        else:
            out.append((k, None, None))
            k += 1
    return out


def _trailing_start(u):
    """Raw index where u's trailing control block begins: right after the last
    box-end/text/{E107} reset. Matches rig/seam_cues.py's trailing(); slicing
    u[_trailing_start(u):] gives that block's raw units."""
    start = 0
    for k, v, a in _seam_cmds(u):
        if v is None or v in _SEAM_BOXEND or v == 0xE107:
            start = k + 1 + (ARGS.get(v, 0) if v is not None else 0)
    return start


def _leading_end(u):
    """Raw index where u's leading control block ends: at the first text unit
    or {E107}. Matches rig/seam_cues.py's leading(); u[:_leading_end(u)] is that
    block's raw units."""
    for k, v, a in _seam_cmds(u):
        if v is None or v == 0xE107:
            return k
    return len(u)


def _after_last_boxend(u):
    """Raw index right after u's LAST {E102}/{E104}/{E106}, or 0 if it has none.
    Deliberately narrower than _trailing_start: it does NOT reset on a plain
    text/data unit. _trailing_start exists to DETECT the seam-cue trigger
    (matching rig/seam_cues.py, where a stray unit correctly breaks the block
    so the trigger is not confused by noise elsewhere in the string); this is
    for the verbatim COPY the fix actually makes, which must not lose units
    that a stray unit happens to sit next to. Bug this replaced: entry 95's
    fan string 16 is {E102}{E100}<01>{E121}{00}{E11B}<55,18>{E081}<08> - the
    {00} between {E121} and {E11B} is a plain unit, not a command, and
    _trailing_start correctly treats it as a reset for detection, but copying
    only from THAT reset point (as the first cut of this fix did) dropped
    {E100}<01>{E121}{00} on the floor instead of carrying them into ours."""
    last = 0
    for k, v, a in _seam_cmds(u):
        if v in _SEAM_BOXEND:
            last = k + 1 + ARGS.get(v, 0)
    return last


def _restore_seam_cues(conv, ds):
    """At a recut seam the fan keeps certain cue commands between a string's LAST
    box-end and its {E081} tail; the converter instead moves the Collection's
    equivalents to the head of the NEXT string. Flagged by the 2026-08-23 review
    ("PLAYTEST THESE FIVE: DS[27], [70], [80], [95], [221]") and never playtested;
    measured whole-game on check_idxargs_d1.nds (rig/seam_cues.py, then filtered to
    true relocations by rig/seam_reloc.py): exactly three seams -
      entry  95 seam 16|17  moved {E11B}<55,18> (with {E100}<01>{E121} in front of
              it: the fan's dispatcher, a conditional jump on flag 55, ends up
              stranded mid-string in ours, after {E121} - the last unit of its
              string in 113 of 114 other uses in the corpus)
      entry 221 seam  1|2   moved {E100}<01>
      entry 259 seam 51|52  moved {E158}<186>
    Entry 95 is the one with a gameplay effect: after our string 16 the flag check
    never runs (Case 2, Dogen - possible endless testimony loop).

    For each adjacent pair of emitted strings (j, j+1): compare ours' and the fan's
    TRAILING block of j (control codes after the last box-end/text/{E107} -
    _trailing_start) and LEADING block of j+1 (control codes before the first
    text unit/{E107} - _leading_end). The trigger is a criss-cross: some command
    the fan has in trailing(j) that ours lacks there, which ours ALSO has in
    leading(j+1) where the fan lacks it - compared as sets of (code, args), since
    a command "travelling" is what matters, not how many times it recurs
    elsewhere in the same block. That trigger only has to name ONE command; once
    it fires, the actual move can carry other units with it (entry 95's
    {E100}<01>{E121} ride along in front of the triggering {E11B}), so the fix
    itself is structural, not limited to the triggering command:
      * ours' string j has every unit after ITS OWN last box-end replaced,
        verbatim, with every unit after the FAN's last box-end (_after_last_boxend,
        not _trailing_start - the copy must keep a stray non-argument unit like
        the {00} after {E121} in entry 95's fan string 16, which _trailing_start
        would otherwise reset on and drop along with the units before it).
      * the leading commands that travel are removed from the head of ours'
        string j+1: the exact prefix length p = len(leading(j+1) ours) -
        len(leading(j+1) fan) commands are cut from the front. Gate: only
        applied when the trigger is non-empty AND cutting p commands leaves a
        remainder that is EXACTLY the fan's leading(j+1) command list, position
        for position - otherwise this seam is left untouched (region_align's own
        E081 rewrite runs separately and is not affected either way).
      * a second gate, conservation: the commands removed (ours' run after j's
        last box-end plus the prefix cut from j+1) must equal the commands
        copied in (the fan's run), as a multiset of (code, args); otherwise the
        seam is left untouched, so the rule can never drop a command.
    Only these commands move; the tail's terminator slot (already restored from
    the fan elsewhere) is not specially handled here - the fan's trailing block
    already ends in whatever terminator it has, copied verbatim along with it.

    Returns (count, [j, ...]) - j is the FIRST string of each fixed seam (so the
    seam is j|j+1); the caller has the entry index."""
    fixed = []
    for j in range(len(conv) - 1):
        u, un = conv[j], list(ds[j][3])
        v, vn = conv[j + 1], list(ds[j + 1][3])
        to = _trailing_start(u)
        tf = _trailing_start(un)
        to_cmds = [(c, a) for _, c, a in _seam_cmds(u[to:])]
        tf_cmds = [(c, a) for _, c, a in _seam_cmds(un[tf:])]
        lo_e = _leading_end(v)
        lf_e = _leading_end(vn)
        lo_cmds = [(c, a) for _, c, a in _seam_cmds(v[:lo_e])]
        lf_cmds = [(c, a) for _, c, a in _seam_cmds(vn[:lf_e])]
        missing_trailing = set(tf_cmds) - set(to_cmds)
        extra_leading = set(lo_cmds) - set(lf_cmds)
        if not (missing_trailing & extra_leading):
            continue
        p = len(lo_cmds) - len(lf_cmds)
        if p <= 0 or lo_cmds[p:] != lf_cmds:
            continue
        # p can equal len(lo_cmds) (the fan's leading block is empty - entry 259):
        # the whole leading run is the cut point, past the last parsed command.
        v_cmds = _seam_cmds(v[:lo_e])
        cut = v_cmds[p][0] if p < len(v_cmds) else lo_e
        tc, tfc = _after_last_boxend(u), _after_last_boxend(un)
        # Conservation gate: every command this removes (ours after j's last
        # box-end, plus the prefix cut from j+1's head) must reappear in what it
        # copies in (the fan's run after its last box-end), and nothing else may
        # arrive - as a multiset of (code, args). Plain units such as the fan's
        # {00} after {E121} are not commands and may differ. Without this the
        # rule could drop commands without a trace (the first cut of this fix lost
        # entry 95's {E100}<01>{E121}); all three real seams conserve.
        removed = [(c, a) for _, c, a in _seam_cmds(u[tc:]) + _seam_cmds(v[:cut])
                   if c is not None]
        added = [(c, a) for _, c, a in _seam_cmds(un[tfc:]) if c is not None]
        if collections.Counter(removed) != collections.Counter(added):
            continue
        # ...and the only plain (non-command) units the move may remove or copy
        # in are {00}s, like the fan's after {E121}: real text on either side
        # means this is not a pure cue relocation, so leave the seam alone. (Not
        # "require a box-end on both sides": entry 259's strings have none.)
        segs = (u[tc:], v[:cut], un[tfc:])
        if any(seg[k] != 0 for seg in segs for k, c, _ in _seam_cmds(seg) if c is None):
            continue
        conv[j] = u[:tc] + un[tfc:]
        conv[j + 1] = v[cut:]
        fixed.append(j)
    return len(fixed), fixed


def rebuild_region(fan_strs, en_strs):
    """Join en_strs (absorbing inner E081 tails where present - strings that end
    an entry carry none), then re-cut into len(fan_strs) pieces at the fan's own
    boundaries, restoring the fan's E081 tails verbatim. The E081 argument is the
    index of the next string to jump to, so the fan's value is correct by
    construction here - the rebuild reproduces the fan's string indices. Strict
    per-string box-end multiset equality or None."""
    joined = []
    for t, u in enumerate(en_strs):
        u = list(u)
        if t < len(en_strs) - 1 and len(u) >= 2 and u[-2] == 0xE081:
            u = u[:-2]
        joined += u
    out, pos = [], 0
    for t, a in enumerate(fan_strs):
        if t == len(fan_strs) - 1:
            h = joined[pos:]
            # the official region can end without a terminator (empty retail
            # neighbour) - restore the fan's tail exactly like an inner one
            if _boxend_counts(h) != _boxend_counts(a) and len(a) >= 2 and a[-2] == 0xE081:
                w = _boxend_counts(a)
                w[0xE081] -= 1
                if _boxend_counts(h) == +w:
                    h = h + list(a[-2:])
        else:
            if len(a) < 2 or a[-2] != 0xE081:
                return None
            k = sum(1 for v in a if v in BOXEND) - 1
            if k <= 0:
                return None
            cut = _cut_after(joined[pos:], k)
            if cut is None:
                return None
            h = joined[pos:pos + cut] + list(a[-2:])
            pos += cut
        if _boxend_counts(h) != _boxend_counts(a):
            return None
        out.append(h)
    return out


def region_align(ds, en, maxspan=4):
    """Align official strings to the FAN layout when the string counts differ.

    Greedy: strings whose box-end multisets match pair 1:1; at a mismatch, the
    smallest (p fan : q en) region whose rebuild verifies is taken. Trailing
    empty/fragment official strings with no fan counterpart are consumed. This
    subsumes the fan's two restructurings - joining retail strings (with an added
    E081 terminator) and re-cutting a region into a different number of pieces -
    including several of them in one entry. Returns an en-shaped list or None;
    every returned string is multiset-verified against the fan, which is stronger
    than the count-level JP-profile check, so the relaid guard is skipped for
    entries rebuilt here.
    """
    du = [list(t[3]) for t in ds]
    eu = [list(t[3]) for t in en]
    P, Q = len(du), len(eu)
    i = j = 0
    out = []
    while i < P or j < Q:
        if i >= P and j < Q and len(eu[j]) <= 4 and not _boxend_counts(eu[j]):
            j += 1
            continue
        if i < P and j < Q and _boxend_counts(du[i]) == _boxend_counts(eu[j]):
            out.append(eu[j])
            i += 1; j += 1
            continue
        done = False
        for span in range(2, 2 * maxspan + 1):
            for p in range(1, min(maxspan, P - i) + 1):
                q = span - p
                if q < 1 or q > min(maxspan, Q - j) or (p == 1 and q == 1):
                    continue
                got = rebuild_region(du[i:i + p], eu[j:j + q])
                if got is not None:
                    out += got
                    i += p; j += q
                    done = True
                    break
            if done:
                break
        if not done:
            return None
    if len(out) != P:
        return None
    # Every E081 argument is a STRING INDEX in this entry - and after a p:q
    # region with p != q, indices carried from the official layout are skewed
    # against the fan layout this entry now uses (a copied arg can even point a
    # string at itself, which is a text loop). Rewrite every argument from the
    # fan counterpart positionally; the multiset gate guarantees the counts
    # match, so the copy is total.
    for t in range(P):
        u, a = out[t], du[t]
        pu = [k for k in _code_positions(u) if u[k] == 0xE081]
        pa = [k for k in _code_positions(a) if a[k] == 0xE081]
        if len(pu) != len(pa):
            return None
        for ku, ka in zip(pu, pa):
            if ku + 1 < len(u) and ka + 1 < len(a):
                u[ku + 1] = a[ka + 1]
    return [(0, 0, 0, u) for u in out]


def _cut_after(u, k):
    """Index just past the k-th box-end code, argument units included, or None."""
    i, n, seen = 0, len(u), 0
    while i < n:
        v = u[i]
        i += 1 + (ARGS.get(v, 0) if 0xE000 <= v <= 0xF8FF else 0)
        if v in BOXEND:
            seen += 1
            if seen == k:
                return i
    return None


def recut_run(ds, en, js):
    """Rebuild official strings js (consecutive indices) in the FAN's layout.

    Joins the official strings, then cuts at each fan boundary. Returns one unit
    list per index, or None the moment anything fails strict verification.
    """
    joined = []
    for t, j in enumerate(js):
        u = list(en[j][3])
        if t < len(js) - 1 and len(u) >= 2 and u[-2] == 0xE081:
            u = u[:-2]                # inner terminator absorbed by the fan's move
        joined += u
    out, pos = [], 0
    for t, j in enumerate(js):
        a = ds[j][3]
        if t == len(js) - 1:
            h = joined[pos:]
            # the official run can end on an EMPTY retail string - then the joined
            # stream has no final terminator and the fan's E081 tail is restored
            # exactly like an inner one
            if _boxend_counts(h) != _boxend_counts(a) and len(a) >= 2 and a[-2] == 0xE081:
                w = _boxend_counts(a)
                w[0xE081] -= 1
                if _boxend_counts(h) == +w:
                    h = h + list(a[-2:])
        else:
            if len(a) < 2 or a[-2] != 0xE081:
                return None
            k = sum(1 for v in a if v in BOXEND) - 1
            if k <= 0:
                return None
            cut = _cut_after(joined[pos:], k)
            if cut is None:
                return None
            h = joined[pos:pos + cut] + list(a[-2:])
            pos += cut
        if _boxend_counts(h) != _boxend_counts(a):
            return None
        out.append(h)
    return out


def file_id(rom, want):
    fnt = struct.unpack_from('<I', rom, 0x40)[0]
    def walk(dirid, prefix=''):
        off = fnt + (dirid & 0xFFF) * 8
        suboff, firstid, _ = struct.unpack_from('<IHH', rom, off)
        p = fnt + suboff; fid = firstid
        while True:
            t = rom[p]; p += 1
            if t == 0: return None
            ln = t & 0x7F; name = rom[p:p+ln].decode('shift_jis', 'replace'); p += ln
            if t & 0x80:
                sub = struct.unpack_from('<H', rom, p)[0]; p += 2
                r = walk(sub, prefix + name + '/')
                if r is not None: return r
            else:
                if prefix + name == want: return fid
                fid += 1
    return walk(0xF000)

def crc16(data):
    c = 0xFFFF
    for b in data:
        c ^= b
        for _ in range(8):
            c = (c >> 1) ^ 0xA001 if c & 1 else c >> 1
    return c

def eng_path(name, src):
    fs = ('dump/eng', 'dump/eng_trial') if src == 'main' else ('dump/eng_trial', 'dump/eng')
    for c in [name] + [name[:-len(x)] for x in ('_tridl', '_dl') if name.endswith(x)]:
        for f in fs:
            p = os.path.join(f, c + '.bin')
            if os.path.exists(p): return p

DEFAULT_OUT = os.path.join('out', 'GK2 (Official English, DS port).nds')


def main(base=None, out=None):
    os.chdir(work())
    BASE = base or os.environ.get('GK2_ROM',
                                  'Gyakuten Kenji 2 (AAI2 Final v2).nds')
    OUT = out or DEFAULT_OUT
    # Injecting a ROM onto itself destroys the input halfway through and yields a
    # doubly-patched file. Easy to do by accident once a previous output is lying
    # around next to the fan ROM.
    if os.path.abspath(BASE) == os.path.abspath(OUT):
        raise SystemExit('the output would overwrite the input ROM: %s' % OUT)
    # The dialogue font's real advances, out of the arm9 in the player's own ROM.
    # Done here, once, before anything is converted: the widgets that wrap with
    # their own face save and restore dstext.LINE_PX around their call, so this
    # must not land in the middle of one. A ROM we do not recognise returns
    # nothing and the old estimate stands, which wraps early rather than wrong.
    _adv, _px = fontwidths.widths(BASE)
    if dstext.use_real_widths(_adv, _px):
        print('font metrics: %d real advances from the ROM, line budget %d px' % (len(_adv), _px))
    else:
        print('font metrics: ROM advances unavailable, estimating (line budget %d)'
              % dstext.LINE_PX)
    # The SMALLER face Mind Chess draws banks 453-455 in (2026-09-27 text-box
    # sweep: a capture of the option bar showed a row clipped where the widget
    # path's old MAIN-font measurement said it still fit - Mind Chess never
    # draws MAIN). None when the ROM does not match; the widget path below
    # then keeps the fan's row for every one of these banks rather than
    # measure with the wrong font again.
    _small_adv = fontwidths.small_widths(BASE)
    if _small_adv:
        print('small-font metrics: %d real advances from the ROM' % len(_small_adv))
    else:
        print('small-font metrics: ROM advances unavailable - Mind Chess widgets keep fan text')
    # ships with the tool (inside the bundle when frozen), unlike everything
    # else under dump/, which the user extracts from their own copies
    m = json.load(open(data('ds_to_collection_final.json')))
    # The two guards below compare against the retail JAPANESE script, but need
    # only COUNTS from it, never text - so the counts ship with the tool and the
    # user does not have to supply a second ROM. See tools/jp_profile.py.
    jp = json.load(open(data('jp_structure.json')))
    raw = open('dump/ds_fan/jpn/spt.bin', 'rb').read()
    ntbl = struct.unpack_from('<I', raw, 0)[0] // 8
    entries = {}
    for i in range(ntbl):
        o, s = struct.unpack_from('<II', raw, i * 8)
        entries[i] = raw[o:o+s] if s else None
    fan = dict(ds_entries('dump/ds_fan/jpn/spt.bin'))

    swapped = overflow = mismatch = skipped = demo = untranslated = tiny = shape = dropped = boxkeep = 0
    restructured = relaidn = unmerged = recut = hollowed = boxless = dsonly = 0
    kept_tails = 0
    choicearg = choicearg_mismatched_strings = 0
    indexarg_counts = collections.OrderedDict((c, 0) for c in INDEX_ARGS if c != 0xE187)
    indexarg_mismatch = collections.OrderedDict((c, 0) for c in INDEX_ARGS if c != 0xE187)
    dsvalue_counts = collections.OrderedDict((c, 0) for c in DS_VALUE_ARGS)
    dsvalue_mismatch = collections.OrderedDict((c, 0) for c in DS_VALUE_ARGS)
    seamcues = 0
    seamcue_seams = []
    staging_values = staging_resequenced = staging_skipped = 0
    staging_moved_box = staging_moved_coarse = 0
    staging_box_mismatches = []
    stmttrim = stmttrim_fallback = 0
    relaidrows = relaidrows_fallback = 0
    relaidrows_notes = []
    condensed_rows_applied = condensed_rows_fallback = 0
    foreign = 0
    zerounit = 0
    zerounit_rows = []
    iconsub = iconrows = 0
    # Every control code the DS engine is known to accept: the set used by the fan
    # script. A converted string that still carries any other code would make the
    # engine skip it and read its arguments as text (see dstext.OFFICIAL_TO_DS).
    ds_codes = set()
    for _e in fan.values():
        for _, _, _, _u in all_strings(_e, True):
            _k = 0
            while _k < len(_u):
                _v = _u[_k]
                if 0xE000 <= _v <= 0xF8FF:
                    ds_codes.add(_v); _k += 1 + ARGS.get(_v, 0)
                else:
                    _k += 1
    def _has_foreign(u):
        k = 0
        while k < len(u):
            v = u[k]
            if 0xE000 <= v <= 0xF8FF:
                if v not in ds_codes: return True
                k += 1 + ARGS.get(v, 0)
            else:
                k += 1
        return False
    def _has_zero_in_text(u):
        """The zero-unit guard (fan_tone/E04X_FINDINGS.md section 4, condition 1,
        added alongside lifting the DSONLY gate above): a 0x0000 unit in TEXT
        position - never inside a code's own arguments, which this walk skips over
        ARGS-aware, exactly like _has_foreign - is the DS script interpreter's own
        end-of-string marker (arm9 0x0200DD10-DDFA), so the engine would stop
        reading right there and drop everything after it. Catches a stray literal
        zero from a mapping bug even in a string _has_foreign finds nothing foreign
        to reject in."""
        k = 0
        while k < len(u):
            v = u[k]
            if 0xE000 <= v <= 0xF8FF:
                k += 1 + ARGS.get(v, 0)
            else:
                if v == 0: return True
                k += 1
        return False
    dsonly_banks = set()
    sparse_kept = sparse_entries = 0
    unmapped = {}
    for k in sorted(m, key=int):
        i = int(k); info = m[k]
        if info['score'] < 0.40 or i not in fan:
            skipped += 1; continue
        # A DS entry with almost no text produces a 1-2 character signature, which
        # fuzzy-matches anything and scores a meaningless 1.00 (DS[319] -> map0b).
        # There is nothing to gain translating these, so leave them alone.
        if info['ds_chars'] < 12:
            tiny += 1; continue
        p = eng_path(info['name'], info['src'])
        if not p:
            skipped += 1; continue
        ds = list(all_strings(fan[i], True))
        en = list(all_strings(open(p, 'rb').read(), False))
        # Capcom's English bundle is imperfect in two ways, and BOTH are per-RECORD,
        # not per-file: a few records are literal "DEMO TEXT" placeholders, and some
        # files were never localised and still hold Japanese. Skipping whole files
        # threw away 16,780 letters of perfectly good official English that sat
        # alongside ~1,000 letters of stub. Fall back only on the offending records.
        realigned = False
        if len(ds) != len(en):
            r = region_align(ds, en) if SPLIT_MERGED else None
            if r is None:
                mismatch += 1; continue      # index layout must not shift
            en = r; unmerged += 1; realigned = True
        # STRUCTURAL PREREQUISITE - the fan patch's own layout must still match the
        # JAPANESE original. The Collection matches the JP script box-for-box, but
        # the fan REDISTRIBUTED message boxes between strings in 54 entries
        # (DS[4]: +8 boxes into str3, -8 out of str4; DS[27]: -38/+38). Swapping
        # per string into a restructured entry replays the moved boxes in official
        # wording after the fan has already shown them, and overwrites whatever the
        # DS keeps at those indices - for DS[4] that is the Logic tutorial and the
        # 'Gourd Lake Park / Stage' location card, and the game hangs there.
        # Box counts are the tell: 375 entries match the JP exactly and are safe.
        # The relayout is confined to the STRINGS whose box count moved, so revert
        # just those and keep the rest of the entry official (DS[4]: only str3/4/6
        # moved, so str0/1/2/5/7 - including the Newspaper Clipping scene - are
        # still safe to swap).
        relaid = set()
        jpb = None
        # Entries rebuilt by region_align skip the JP-profile relaid check: every
        # one of their strings was verified against the fan by box-end code
        # MULTISET, which is strictly stronger than the profile's per-string
        # counts (and the profile's string indices no longer line up anyway).
        prof = None if realigned else jp.get(str(i))
        if prof:
            jpb = prof['boxes']
            if len(jpb) != len(ds):
                restructured += 1; continue      # cannot compare; leave it alone
            relaid = {j2 for j2 in range(len(ds))
                      if sum(1 for v in ds[j2][3] if v in BOXEND) != jpb[j2]}
        if relaid and RECUT_SHIFTED:
            en = list(en)
            block = []
            for j2 in sorted(relaid) + [None]:
                if block and j2 != block[-1] + 1:
                    if len(block) >= 2:
                        got = recut_run(ds, en, block)
                        if got is not None:
                            for t, jj in enumerate(block):
                                en[jj] = (0, 0, 0, got[t])
                            relaid -= set(block)
                            recut += len(block)
                    block = []
                block.append(j2)
        conv = []
        # relaid_rows.py: exactly three (entry, string) rows the ordinary swap
        # path cannot reach - the fan moved boxes across a string boundary or
        # dropped a dead tail, which trips the `relaid`/JP-profile check below
        # and would otherwise keep the fan's own text verbatim. Checked BEFORE
        # that ordinary `relaid` gate so it can override it; every other
        # entry's `relaid` handling is untouched. The relayed result still has
        # to clear the same foreign-code / zero-in-text gates any other
        # converted string does (_has_foreign/_has_zero_in_text, defined
        # above) - a hash match only proves the INPUT is what this table
        # expects, not that dstext.convert() produced a shippable output.
        en_by_idx = {n2: eu for n2, (_, _, _, eu) in enumerate(en)}
        for n_, (_, _, _, u) in enumerate(en):
            if (i, n_) in relaid_rows.RELAID:
                rowu, rowstat, rownotes = relaid_rows.apply(
                    i, n_, ds[n_][3], en_by_idx, _has_foreign, _has_zero_in_text)
                if rowstat is True:
                    conv.append(rowu); relaidrows += 1
                    relaidrows_notes += ['entry %d str %d: %s' % (i, n_, nt) for nt in rownotes]
                    continue
                relaidrows_fallback += 1
                relaidrows_notes.append('entry %d str %d: FALLBACK - %s'
                                         % (i, n_, '; '.join(rownotes) or 'hash mismatch'))
            if n_ in relaid:
                conv.append(list(ds[n_][3])); relaidn += 1; continue
            asc = ''.join(chr(v) for v in u if v < 0x80)
            cj = sum(1 for v in u if 0x3040 <= v <= 0x30FF or 0x4E00 <= v <= 0x9FFF)
            la = sum(1 for v in u if 0x41 <= v <= 0x5A or 0x61 <= v <= 0x7A)
            if 'DEMO TEXT' in asc:
                conv.append(list(ds[n_][3])); demo += 1; continue
            if cj > max(4, la * 0.25):
                conv.append(list(ds[n_][3])); untranslated += 1; continue
            # Capcom's inline controller-button glyph {E2B0} is a code the DS
            # engine does not know, so without this the foreign-code gate below
            # discards the whole string and the fan's version of the line
            # survives - which is why the how-to-play text was still fan
            # writing in every release up to 1.9.1. Put the DS button name in
            # the glyph's place FIRST, so what the gate then sees is ordinary
            # text. buttons.py raises rather than guess.
            u, nb = buttons.substitute(i, n_, u, ARGS)
            if nb:
                iconsub += nb; iconrows += 1
            # DELTA 3: 28 testimony/rebuttal statements Capcom wrote a line too
            # long for the DS engine's single statement box, wrapping to 4 lines
            # and getting split 2+2 over two boxes - of which the engine only
            # ever shows the first (rig, entry 92 statement 2, 2026-09-22). Must
            # run on the RAW Collection units, before convert() wraps them, and
            # before the foreign-code/box checks below so a trimmed string is
            # judged on what it will actually ship as. See tools/stmt_trim.py.
            u, trimstat = stmt_trim.apply(i, n_, u)
            if trimstat is True:
                stmttrim += 1
            elif trimstat is False:
                stmttrim_fallback += 1
            if i in MIND_CHESS_BANKS:
                # Every Mind Chess bank draws SMALL, which has no U+0415
                # record and an unverified U+30A7 one (see MIND_CHESS_BANKS
                # above) - off for the ordinary conversion path too, not just
                # the sparse widget one, since 456-458 never reach that path.
                _accent_saved = dstext.ACCENT_SLOTS_ON
                dstext.ACCENT_SLOTS_ON = False
                try:
                    d, un = convert(u)
                finally:
                    dstext.ACCENT_SLOTS_ON = _accent_saved
            else:
                d, un = convert(u)
            for v in un: unmapped[v] = unmapped.get(v, 0) + 1
            if _has_foreign(d):
                conv.append(list(ds[n_][3])); foreign += 1; continue
            if _has_zero_in_text(d):
                conv.append(list(ds[n_][3])); zerounit += 1
                zerounit_rows.append((i, n_)); continue
            conv.append(d)
        hfan = parse(fan[i], True)[0]
        # STRUCTURAL ALIGNMENT CHECK. Matching string COUNTS is not enough: the
        # Collection sometimes distributes the same scene across strings differently
        # (DS[115] str5 = 3,582 units on the DS, 0 in the Collection), and it omits
        # DS-only content such as the touch/A-Button tutorials (DS[4] str3: 16 message
        # boxes on the DS, 10 in the Collection). Substituting index-by-index then
        # scrambles the scene or drops a message the engine waits on - which HANGS the
        # game. Reject the whole entry if any string would lose message boxes.
        END = {0xE102, 0xE104, 0xE106, 0xE185, 0xE081}
        PRINT = lambda u: sum(1 for v in u if 0xFF01 <= v <= 0xFF5E or 0x21 <= v <= 0x7E)
        # (b) scene SHIFT / hollow strings: a DS string with real dialogue whose
        # official counterpart is nearly empty. Two very different causes share the
        # symptom. When the JP profile confirms the string's box count is unchanged,
        # the scene is NOT redistributed - the Collection simply has a hole at that
        # slot (trial-build cuts, all in Ep1 free roam), and the string reverts to
        # fan individually, exactly like a DEMO TEXT record. Only when the profile
        # cannot vouch for the alignment is the whole entry rejected, because then
        # index-by-index substitution could scramble the scene (the original case,
        # DS[115] str5 = 3,582 units on the DS and 0 in the Collection, is now
        # normally repaired upstream by recut_run).
        hollow = [j2 for j2 in range(len(ds))
                  if PRINT(ds[j2][3]) > 200 and PRINT(conv[j2]) < 0.2 * PRINT(ds[j2][3])]
        if hollow:
            jpb_ok = jpb is not None and len(jpb) == len(ds)
            if jpb_ok and all(sum(1 for v in ds[j2][3] if v in BOXEND) == jpb[j2]
                              for j2 in hollow):
                for j2 in hollow:
                    conv[j2] = list(ds[j2][3]); hollowed += 1
            else:
                dropped += 1; continue
        # (a) per-string: the Collection omits DS-only content such as the touch /
        # A-Button tutorials (DS[4] str3: 16 message boxes on the DS, 10 here). Losing
        # a box the engine waits on HANGS the game, so keep the fan's string for it.
        # Losing ONE box is benign and common (868 of 913 cases) - the official
        # localization simply merges a pair. Losing two or more means DS-only content
        # is missing, e.g. DS[4] str3 drops 6 boxes including the A-Button tutorial,
        # and the engine hangs waiting for it.
        for j2 in range(len(ds)):
            a2 = sum(1 for v in ds[j2][3] if v in END)
            b2 = sum(1 for v in conv[j2] if v in END)
            if a2 - b2 >= 2:
                conv[j2] = list(ds[j2][3]); boxkeep += 1
        # (c) DS-ONLY ENGINE COMMANDS. Counting message boxes does not catch the
        # case that matters most: Capcom's prose is LONGER, so a converted string
        # can carry MORE boxes than the fan's while still having silently dropped
        # a command the engine waits on. DS[4] str3/str4 - the Gourd Lake stage,
        # where Episode 1 hands control to the player - ends up with 18 boxes
        # against the fan's 16 and still hangs, because the E041/E042 pair around
        # the DS-only touch/A-Button/Logic tutorials is gone. Reproduced from a
        # cold boot on v1.4.2 and fixed by restoring the fan's strings; the fan
        # ROM reaches free roam at the same point. So compare the commands, not
        # the boxes, and keep the fan's string whenever one goes missing.
        # DELTA 5 (2026-09-23): gated behind KEEP_DSONLY_GATE (see the flag's
        # comment above _boxend_counts) - E040-E043 are absolute colour setters
        # with no engine state, not the hang this block was written for. Kept, not
        # deleted, so the gate can be restored without reconstructing it.
        if KEEP_DSONLY_GATE:
            DSONLY = {0xE041, 0xE042}
            def _cmds(u):
                c = collections.Counter()
                k = 0
                while k < len(u):
                    v = u[k]
                    if 0xE000 <= v <= 0xF8FF:
                        if v in DSONLY: c[v] += 1
                        k += 1 + ARGS.get(v, 0); continue
                    k += 1
                return c
            for j2 in range(len(ds)):
                fa, fb = _cmds(ds[j2][3]), _cmds(conv[j2])
                if any(fa[k] > fb.get(k, 0) for k in fa):
                    if list(conv[j2]) != list(ds[j2][3]):
                        conv[j2] = list(ds[j2][3]); dsonly += 1
                        dsonly_banks.add(i)
        trailer, scale, longest = hfan['term'], hfan['scale'], hfan['last']
        # Structural sanity check: the Collection file should drive roughly the same
        # engine commands as the DS original. A wrong match shows up as near-zero
        # overlap in the control-code profile.
        if prof:
            a = collections.Counter({int(k, 16): v for k, v in prof['ctrl'].items()})
            b = collections.Counter(v for c2 in conv for v in c2 if 0xE000 <= v <= 0xF8FF)
            overlap_low = bool(a) and sum((a & b).values()) / sum(a.values()) < 0.35
            if ((overlap_low or i in FORCE_WIDGET_GATE)
                    and not relaid_rows.skip_widget_gate(i, 0, ds[0][3])):
                # A near-zero profile overlap usually means a WRONG file match -
                # reject. But the exam/exam_ask confrontation banks fail this test
                # for a different reason: only the trial bundle carries them, and
                # it populates just the demo's rows (215 of 848), so the converted
                # file can never cover the full JP profile. For matches this
                # confident, fall back to swapping the populated rows one by one -
                # official English text in a string whose box-end multiset equals
                # the fan's exactly - and keep fan for everything else.
                if info['score'] < 0.90:
                    shape += 1; continue
                # These rows are OPTION-WIDGET lines, not dialogue: every fan row
                # is a single line, up to ~306px - far wider than the dialogue box
                # the default conversion wraps for. Re-convert unwrapped, and
                # measure against the widget's proven budget: anything wider
                # keeps the fan line rather than risking a clip.
                small = i in SMALL_WIDGET_BANKS
                TYPO = {0x2018: "'", 0x2019: "'", 0x201C: '"', 0x201D: '"',
                        0x2013: '-', 0x2014: '-', 0x2026: '.', 0x2025: '.'}
                def _rowpx(u):
                    segs = [0]
                    k2 = 0
                    while k2 < len(u):
                        v = u[k2]
                        if 0xE000 <= v <= 0xF8FF:
                            k2 += 1 + ARGS.get(v, 0); continue
                        if v == 0x0A:
                            segs.append(0)
                        else:
                            ch = ('e' if v in (0x0415, 0x30A7) else  # fan font's e-grave/e-acute slots
                                  chr(v - 0xFEE0) if 0xFF01 <= v <= 0xFF5E else
                                  ' ' if v == 0xFF3F else
                                  TYPO.get(v) or (chr(v) if 0x20 <= v < 0x7F else None))
                            # an unpriceable glyph poisons the row: force it wide so
                            # the budget test can only fail toward keeping fan
                            segs[-1] += 9999 if ch is None else dstext._w(ch)
                        k2 += 1
                    return max(segs), len(segs)
                # Mind Chess (banks 453-455) draws SMALL, not MAIN - measure with
                # the ROM's own SMALL1 table instead of dstext._w (2026-09-27 text-
                # box sweep). SMALL1 has no U+0415 record at all; it does have one
                # for U+30A7 (6px), but whether that slot is really the fan's
                # redrawn e-acute in this face, and not just a coincidentally valid
                # entry, is unverified - so both map to plain fullwidth 'e' here
                # too rather than measure a glyph this face may not actually draw.
                def _rowpx_small(u):
                    segs = [0]
                    k2 = 0
                    while k2 < len(u):
                        v = u[k2]
                        if 0xE000 <= v <= 0xF8FF:
                            k2 += 1 + ARGS.get(v, 0); continue
                        if v == 0x0A:
                            segs.append(0)
                        else:
                            vv = 0xFF45 if v in (0x0415, 0x30A7) else v  # plain fullwidth 'e'
                            av = _small_adv.get(vv) if _small_adv else None
                            if av is None and 0x20 <= vv <= 0x7E:
                                av = _small_adv.get(vv - 0x21 + 0xFF01) if _small_adv else None
                            # an unpriceable glyph, or no SMALL table at all, poisons
                            # the row: force it wide so the budget test can only fail
                            # toward keeping fan, same discipline as _rowpx above
                            segs[-1] += 9999 if av is None else av
                        k2 += 1
                    return max(segs), len(segs)
                if small:
                    rowpx = _rowpx_small
                    budget = WIDGET_PROVEN_PX[i]
                else:
                    rowpx = _rowpx
                    # the budget comes from the fan's ENGLISH rows only - the bank's
                    # untranslated Japanese placeholder rows are not display-proven
                    # and their glyphs are unpriceable anyway
                    lat = [t[3] for t in ds
                           if t[3] and sum(1 for v in t[3]
                                           if 0xFF21 <= v <= 0xFF5A or 0x41 <= v <= 0x7A) > 4]
                    if not lat:
                        shape += 1; continue
                    budget = max(rowpx(u)[0] for u in lat)
                kept = gained = 0
                condensed_applied = condensed_fallback = 0
                old_accent = dstext.ACCENT_SLOTS_ON
                if small:
                    # SMALL1 has no U+0415 record, and its U+30A7 record is
                    # unverified as the actual redrawn glyph (see _rowpx_small
                    # above); keep the plain letter here rather than assume
                    # this face carries the fan's MAIN-only accent glyphs.
                    dstext.ACCENT_SLOTS_ON = False
                try:
                    for j2 in range(len(ds)):
                        def _try_row(u):
                            fl, _ = convert(u, wrap=False, page=False, hard_nl=False)
                            la = sum(1 for v in fl if 0xFF21 <= v <= 0xFF5A or 0x41 <= v <= 0x7A)
                            px, nl = rowpx(fl)
                            ok = not (la == 0 or j2 in relaid or nl > 1 or px > budget
                                      or _boxend_counts(fl) != _boxend_counts(ds[j2][3]))
                            return fl, ok
                        u2 = en[j2][3]
                        # Try Capcom's own row through the gate first, unchanged.
                        # tools/condense_rows.py only substitutes its approved
                        # wording - same control codes, fewer words - when
                        # Capcom's row fails THIS gate, and only when its own
                        # source hash still matches what the row was built
                        # against; the substitute is then run through the SAME
                        # gate again. This way a future budget increase that
                        # lets Capcom's own line fit ships that line, not a
                        # condensed one still sitting in the table unused.
                        flat, fits = _try_row(u2)
                        if not fits and small and (i, j2) in condense_rows.CONDENSE_ROWS:
                            if condense_rows.mc_source_ok(i, j2, u2):
                                cflat, cfits = _try_row(condense_rows.mc_units(i, j2, u2))
                                if cfits:
                                    flat, fits = cflat, True
                                    condensed_applied += 1
                                else:
                                    condensed_fallback += 1
                            else:
                                condensed_fallback += 1
                        if not fits:
                            if list(conv[j2]) != list(ds[j2][3]):
                                conv[j2] = list(ds[j2][3]); kept += 1
                        else:
                            conv[j2] = flat
                            if list(flat) != list(ds[j2][3]):
                                gained += 1
                finally:
                    dstext.ACCENT_SLOTS_ON = old_accent
                condensed_rows_applied += condensed_applied
                condensed_rows_fallback += condensed_fallback
                if not gained:
                    # nothing official survived the per-row gate - keep the fan
                    # entry byte-for-byte rather than rebuilding its container
                    shape += 1; continue
                sparse_kept += kept; sparse_entries += 1
        # Last net: a SHORT fan string emptied outright by the Collection (DS[13]
        # str1, an Ep1 NPC line the trial build cut - 53 chars, one box, invisible
        # to both the 200-char hollow floor and the lose-two-boxes guard). Runs
        # AFTER every entry-level guard so it can never change an entry's verdict,
        # and demands English fan text with a box (walked with arities, so argument
        # bytes never count as text) - the demo entries' Japanese placeholder stubs
        # stay gone.
        def _wprint(u):
            n2 = i2 = 0
            while i2 < len(u):
                v2 = u[i2]
                if 0xE000 <= v2 <= 0xF8FF:
                    i2 += 1 + ARGS.get(v2, 0); continue
                if 0xFF01 <= v2 <= 0xFF5E or 0x21 <= v2 <= 0x7E:
                    n2 += 1
                i2 += 1
            return n2
        for j2 in range(len(ds)):
            fu = ds[j2][3]
            cj2 = sum(1 for v in fu if 0x3040 <= v <= 0x30FF or 0x4E00 <= v <= 0x9FFF)
            la2 = sum(1 for v in fu if 0xFF21 <= v <= 0xFF5A or 0x41 <= v <= 0x7A)
            if (_wprint(fu) > 0 and _wprint(conv[j2]) == 0
                    and la2 > max(4, cj2)
                    and sum(1 for v in fu if v in BOXEND) > 0):
                conv[j2] = list(fu); hollowed += 1
        # Harder net, and the one that actually protects the player: a row that
        # loses its MESSAGE BOX hangs the game wherever it is displayed - the box
        # opens on a speaker with nothing in it and never closes, so there is no
        # input that advances. That is strictly worse than any wording, including
        # untranslated Japanese, so a row whose official replacement has no
        # box-end at all keeps the fan's row whatever language it is in.
        # Found by a player on v1.4.1: DS[456] (exam_dl - examine responses)
        # rows 54-60 had been emptied outright, and examining the wrong thing
        # early in Episode 1 locked the game on Edgeworth's nameplate over an
        # empty box. The English-only net above skipped them precisely because
        # the fan's rows there are Japanese.
        def _nbox(u):
            n2 = i2 = 0
            while i2 < len(u):
                v2 = u[i2]
                if 0xE000 <= v2 <= 0xF8FF:
                    if v2 in BOXEND: n2 += 1
                    i2 += 1 + ARGS.get(v2, 0); continue
                i2 += 1
            return n2
        for j2 in range(len(ds)):
            fu = ds[j2][3]
            if _nbox(fu) > 0 and _nbox(conv[j2]) == 0:
                conv[j2] = list(fu); boxless += 1
        # Run last, after every structural reject (dropped/shape continue above)
        # and every net that can still replace or re-convert a string (the
        # sparse row-by-row swap, hollow/boxkeep/dsonly/boxless) - otherwise the
        # count includes entries this loop never ships, and a string re-converted
        # by the sparse path after an earlier call would keep the Collection's
        # raw argument values instead of the fan's.
        n_restored, n_mismatch = _restore_index_args(conv, ds, 0xE187)
        choicearg += n_restored
        choicearg_mismatched_strings += n_mismatch
        for _code in indexarg_counts:
            n_r, n_m = _restore_index_args(conv, ds, _code)
            indexarg_counts[_code] += n_r
            indexarg_mismatch[_code] += n_m
        n_seam, seam_js = _restore_seam_cues(conv, ds)
        seamcues += n_seam
        seamcue_seams += [(i, j, j + 1) for j in seam_js]
        for _code in dsvalue_counts:
            n_r, n_m = _restore_index_args(conv, ds, _code, DS_VALUE_ARGS)
            dsvalue_counts[_code] += n_r
            dsvalue_mismatch[_code] += n_m
        (n_stage_v, n_stage_r, n_stage_s, stage_box_js,
         n_stage_moved_box, n_stage_moved_coarse) = _restore_staging(conv, ds)
        staging_values += n_stage_v
        staging_resequenced += n_stage_r
        staging_skipped += n_stage_s
        staging_box_mismatches += [(i, j) for j in stage_box_js]
        staging_moved_box += n_stage_moved_box
        staging_moved_coarse += n_stage_moved_coarse
        recs = [(ds[j][1], conv[j]) for j in range(1, len(ds))]
        # A string the injector left as the fan wrote it keeps whatever the fan put in
        # its terminator slot: that slot can be the last argument of a command cut off
        # by the declared length (spt.tails; the Ep3 Bound/Larry talk mix-up).
        ftails = tails(fan[i], True)
        keep = [t if any(t) and list(conv[j]) == list(ds[j][3]) else None
                for j, t in enumerate(ftails)]
        kept_tails += sum(1 for t in keep if t)
        try:
            entries[i] = build_ds(conv[0], recs, trailer, scale, longest, keep)
            swapped += 1
        except OverflowError:
            overflow += 1

    # Evidence/profile descriptions, Logic cards and topics are not in the Collection's
    # script files at all - they live in the localization string tables. Patch those in.
    loc = load_lookup()
    locn = 0
    for idx, src, box in ((432, 'dump/jpn_trial/detailMsg.bin', 'detailMsg'),
                          (395, 'dump/jpn/logicKW.bin', 'logicKW')):
        if entries.get(idx) and entries[idx][:4] == b' TPS':
            nd, c, (cr_a, cr_f) = patch_entry(entries[idx], src, loc, box, bank=idx)
            if c: entries[idx] = nd; locn += c
            condensed_rows_applied += cr_a
            condensed_rows_fallback += cr_f
    print('strings patched from localization tables:  %d' % locn)

    # The episode titles live in DS[460], which is kept as fan text (its Collection
    # counterpart is untranslated). Patch the official names in on top.
    titles = 0
    if RETITLE:
        for i, d in entries.items():
            if d and d[:4] == b' TPS':
                nd, c = retitle(d)
                if c: entries[i] = nd; titles += c
    print('episode titles switched to official names:   %d%s'
          % (titles, '' if RETITLE else '  (RETITLE off - keeping fan names)'))

    # Character names: strings that keep fan text still used the fan's names
    # (Simon Keyes, Ray Shields, ...). Rewrite them to Capcom's, verified
    # string-identical-to-fan first so official text is never touched.
    import names as _names
    # Mind Chess's SMALL-font real advances, so a kept-fan row renamed here
    # (e.g. 453/391, "Swift" -> "Lloyd") is measured against the same proven
    # field width and font the widget path above uses, not names.py's older
    # estimate-unit budget. A ROM that does not match leaves _names._SMALL
    # empty, and every renamed WIDGET_SMALL_BANKS row then prices 9999 and
    # keeps its fan wording rather than ship unmeasured.
    _names.use_small_widths(_small_adv)
    renamed = 0
    over_rows = []
    for i, d in entries.items():
        if not d or d[:4] != b' TPS':
            continue
        nd, c, over = _names.harmonize_entry(d, fan.get(i), i)
        if c:
            entries[i] = nd; renamed += c
        for si, bad in over:
            over_rows.append((i, si, bad))
    print('kept-fan strings renamed to official names:  %d' % renamed)
    if over_rows:
        # These were NOT renamed - the official name would not fit the line, so
        # the fan's row shipped instead. Reported, not warned about.
        print('rows left fan-named (official name would not fit): %d'
              % len(over_rows))

    # A fan-inherited dialogue line over the proven 240px budget (2026-09-27
    # text-box sweep, spt 19/26): move one wrapped line break by a word,
    # hash-guarded against the exact row this table was built from - see
    # tools/linefix.py for why neither existing mechanism (ROWFIX, the dstext
    # wrap itself) reaches it. spt 100/32 (Capcom's own text) used this same
    # mechanism until 2026-09-27's rework fixed its cause in dstext.py instead.
    linefixed = linefix_fallback = 0
    for _ent_i in {ei for ei, _si in linefix.LINEFIX}:
        d = entries.get(_ent_i)
        if d:
            nd, c, fb = linefix.patch_entry(_ent_i, d)
            if c: entries[_ent_i] = nd; linefixed += c
            linefix_fallback += fb
    print('dialogue lines re-broken to fit the proven budget: %d  (fallback: %d)'
          % (linefixed, linefix_fallback))

    # One row Capcom's own matcher mapped to the wrong Collection file entirely
    # - hand-ported and hash-guarded, same discipline as linefix.py above. Runs
    # before skipguard (which wants to see the final built bytes last). See
    # tools/last_rows.py.
    lastrows = lastrows_fallback = 0
    for _ent_i in {ei for ei, _si in last_rows.LAST_ROWS}:
        d = entries.get(_ent_i)
        if d:
            nd, c, fb = last_rows.patch_entry(_ent_i, d)
            if c: entries[_ent_i] = nd; lastrows += c
            lastrows_fallback += fb
    print('last-rows hand ports applied: %d  (fallback: %d)' % (lastrows, lastrows_fallback))

    # Rows Capcom never wrote (their Collection slot is empty/hollow), so the
    # fan's old wording still shows there: replace just the words with new
    # text in Capcom's style - hand-drafted, reviewed and hash-guarded, same
    # discipline as linefix.py/last_rows.py above. See tools/rewrite.py.
    rewritten = rewrite_fallback = 0
    for _ent_i in {ei for ei, _si in rewrite.REWRITE}:
        d = entries.get(_ent_i)
        if d:
            nd, c, fb = rewrite.patch_entry(_ent_i, d)
            if c: entries[_ent_i] = nd; rewritten += c
            rewrite_fallback += fb
    print('rows rewritten in Capcom\'s style: %d  (fallback: %d)' % (rewritten, rewrite_fallback))

    # 33 animated {E111} entrances in the game (identical set in the fan ROM
    # and ours - Capcom's own script) ship with no {E112 <char>} wait before
    # the next box. Every actor-positioning command writes that character's
    # single task slot unconditionally, so a held B can flush the box before
    # the entrance animation finishes, and the next command for that actor
    # overwrites its task slot mid-move, freezing it (entry 119 string 3 box
    # 1: Edgeworth left at x ~ -100). This runs last, after every other text
    # and staging step, so it sees the final built bytes - see
    # tools/skipguard.py for the 13 guarded sites (9 slide-ins, 4 fade-ins
    # whose killer command shares the entrance's own box) and why the other
    # 20 unguarded fade-ins are left alone.
    guarded = 0
    guard_fallback_sites = []
    for _ent_i in {ei for ei, _si in skipguard.SKIPGUARD}:
        d = entries.get(_ent_i)
        if d:
            nd, c, fb_sites = skipguard.patch_entry(_ent_i, d)
            if c: entries[_ent_i] = nd; guarded += c
            guard_fallback_sites += fb_sites
    print('animated entrances guarded against a B-skip freeze: %d  (fallback: %d%s)'
          % (guarded, len(guard_fallback_sites),
             ': ' + ', '.join('DS[%d] str %d' % s for s in guard_fallback_sites)
             if guard_fallback_sites else ''))

    newspt = build_archive(entries)
    print('entries replaced with official English: %d' % swapped)
    print('kept fan text - string count mismatch:  %d' % mismatch)
    print('entries where a joined string was split back: %d' % unmerged)
    print('relaid strings rebuilt in the fan layout:   %d' % recut)
    print('hollow official strings kept as fan:       %d' % hollowed)
    print('rows kept as fan to keep their message box: %d' % boxless)
    print('terminator slots kept from the fan (a command argument lives there): %d' % kept_tails)
    print('{E187} choice-menu arguments restored from the fan (strip id, target string): %d'
          % choicearg)
    if choicearg_mismatched_strings:
        print('strings whose {E187} count did not match the fan - left unrewritten: %d'
              % choicearg_mismatched_strings)
    for _code, _n in indexarg_counts.items():
        print('string-index arguments restored from the fan, {%s}: %d  (mismatched strings, '
              'counted before the seam-cue step: %d)'
              % (format(_code, 'X'), _n, indexarg_mismatch[_code]))
    print("seam cues restored to the fan's string: %d" % seamcues)
    if seamcue_seams:
        print('  ' + ', '.join('entry %d seam %d|%d' % t for t in seamcue_seams))
    for _code, _n in dsvalue_counts.items():
        print('DS map/list value restored from the fan, {%s}: %d  (mismatched strings: %d)'
              % (format(_code, 'X'), _n, dsvalue_mismatch[_code]))
    print('staging (camera and character positions) restored from the fan: '
          '%d strings by value, %d resequenced, %d skipped, %d placed in a '
          'different box than the fan, %d %s moved to fix box placement, '
          '%d %s moved to the fan\'s side of the text in the box'
          % (staging_values, staging_resequenced, staging_skipped, len(staging_box_mismatches),
             staging_moved_box, 'string' if staging_moved_box == 1 else 'strings',
             staging_moved_coarse, 'string' if staging_moved_coarse == 1 else 'strings'))
    if staging_box_mismatches:
        print('  ' + ', '.join('entry %d str %d' % t for t in staging_box_mismatches))
    if KEEP_DSONLY_GATE:
        print('rows kept as fan to keep a DS-only command:  %d  (in %d script banks)'
              % (dsonly, len(dsonly_banks)))
    else:
        print('rows kept as fan to keep a DS-only command:  0  (gate off)')
    print('kept fan text - over 64 KB u16 cap:     %d' % overflow)
    print('records kept as fan - DEMO TEXT stub:      %d' % demo)
    print('records kept as fan - still Japanese:       %d' % untranslated)
    print('kept fan text - too little text to map: %d' % tiny)
    print('kept fan text - control-code shape off:  %d' % shape)
    print('sparse official banks swapped row-by-row: %d (%d rows kept fan)'
          % (sparse_entries, sparse_kept))
    print('kept fan text - scene shifted between strings: %d' % dropped)
    print('kept fan text - cannot align to JP original: %d' % restructured)
    print('records kept as fan - fan relaid it vs JP:    %d' % relaidn)
    print('records kept as fan - would lose a message box: %d' % boxkeep)
    print('records kept as fan - official-only control code: %d' % foreign)
    # Counted where the guard runs, BEFORE the entry-level rejects: a row counted
    # here can still end up fan anyway if its whole entry is rejected later.
    print('converted strings refused for a zero in text position (before entry-level '
          'checks): %d' % zerounit)
    if zerounit_rows:
        print('  ' + ', '.join('entry %d str %d' % t for t in zerounit_rows))
    print('button glyphs replaced with DS button names: %d in %d records' % (iconsub, iconrows))
    print('statements and prompt questions trimmed to one box: %d  (fallback: %d)'
          % (stmttrim, stmttrim_fallback))
    print("Capcom's words relaid into the fan's box skeleton: %d  (fallback: %d)"
          % (relaidrows, relaidrows_fallback))
    for _nt in relaidrows_notes:
        print('  ' + _nt)
    print('condensed rows shipped at approved wording: %d  (fallback: %d)'
          % (condensed_rows_applied, condensed_rows_fallback))
    print('box-open arguments corrected 2 -> 3 (see dstext.BOX_OPEN_FIX): %d' % dstext._STATS['boxopen'])
    print('kept fan text - no/weak mapping:        %d' % skipped)
    print('spt.bin: fan %.2f MB -> new %.2f MB' % (len(raw)/1e6, len(newspt)/1e6))
    if unmapped:
        print('unmapped code points: %d distinct, %d occurrences'
              % (len(unmapped), sum(unmapped.values())))

    # The dialogue nameplates are graphics; redraw them with the official
    # names using the fan patch's own font, harvested from the user's files.
    import plates as _plates
    newid, plate_n = _plates.rebuild_idlocal('dump/ds_fan/jpn/idlocal.bin')
    print('nameplates redrawn with official names:      %d' % plate_n)

    rom = bytearray(open(BASE, 'rb').read())
    fid = file_id(rom, 'jpn/spt.bin')
    fat = struct.unpack_from('<I', rom, 0x48)[0]
    while len(rom) % 512: rom += b'\xFF'
    start = len(rom)
    rom += newspt
    while len(rom) % 512: rom += b'\xFF'
    struct.pack_into('<II', rom, fat + fid * 8, start, start + len(newspt))
    idfid = file_id(rom, 'jpn/idlocal.bin')
    start = len(rom)
    rom += newid
    while len(rom) % 512: rom += b'\xFF'
    struct.pack_into('<II', rom, fat + idfid * 8, start, start + len(newid))
    struct.pack_into('<I', rom, 0x80, len(rom))
    cap = 0
    while (128 * 1024) << cap < len(rom): cap += 1
    rom[0x14] = cap
    struct.pack_into('<H', rom, 0x15E, crc16(bytes(rom[:0x15E])))
    os.makedirs('out', exist_ok=True)
    open(OUT, 'wb').write(bytes(rom))
    print('wrote %s  (%.2f MB)' % (OUT, len(rom)/1e6))

if __name__ == '__main__':
    _a = [a for a in sys.argv[1:] if not a.startswith('-')]
    _o = sys.argv[sys.argv.index('-o') + 1] if '-o' in sys.argv[:-1] else None
    main(_a[0] if _a else None, _o)
