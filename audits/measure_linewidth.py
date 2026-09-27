# -*- coding: utf-8 -*-
"""THE canonical instrument for "dialogue-font lines wider than the 240px box".

    python audits/measure_linewidth.py [ROM ...]

With no argument it measures the built ROM in out/. Pass one or more ROMs to
compare them, oldest first. The per-glyph advances come from your own AAI2 Final
v2 ROM, found the same way build.py finds it, or passed with --fan-rom.

Four different walkers were written for this figure during the 2026-09-19 review
and they disagreed wildly on TOTALS while agreeing exactly on the OVER-240 COUNT.
The disagreement was always scope, never arithmetic. So the scope is pinned here,
and any figure taken from it must be quoted together with this command:

SCOPE, exactly:
  * jpn/spt.bin out of the ROM's own filesystem, every ' TPS' entry, EXCEPT
    WIDGET_BANKS below (banks proven to use a font other than MAIN - see the
    comment on that set; nothing is excluded on inference alone any more,
    2026-09-27 round 2 refuter correction).
  * EVERY line the MAIN dialogue font draws, dialogue AND narration alike -
    not only strings carrying {E101} (speaker_control). 2026-09-27 review: the
    E101-only filter was a leftover of the ORIGINAL walk (which needed E101 to
    find the dialogue banks at all) and silently dropped every string the
    engine prints in the same box without swapping the nameplate - narration,
    system lines and mid-conversation strings that continue a box already
    open (e.g. DS[18] str5, part of the same scene as str4's {E100}{E101},
    itself carrying none). MEASURE_SCOPE below controls this; set it to
    'dialogue' to reproduce the old E101-only figure for comparison.
  * A control code consumes its arguments (dump/ctrl_args.json) so argument units
    are never measured as text.
  * A line ends at 0x0A or at a box-terminating code: {E102}, {E104}, and an
    {E106} only when dstext.e106_clears says so (a prompt/popup code follows
    it before the next visible text unit, DELTA 7b) - most {E106}s are not a
    box end (their handler at overlay 7 0x020ACEB0 only does read-mark
    bookkeeping and returns), and treating every one as a line end measured
    boxes the DS never draws.
  * Width is the sum of the font's REAL advances, read from the decompressed arm9.
  * Empty lines are dropped.

The LINE TOTALS this prints are scope-specific and do not mean "lines in the
game". Do not quote them anywhere public; quote the over-budget count, which is
the figure three independent walkers agreed on.
"""
import os as _os
import sys as _sys

_REPO = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
_sys.path.insert(0, _os.path.join(_REPO, 'tools'))

import struct, json

from inject import file_id
from spt import all_strings
import fontwidths

BOX = 240
CTRL = lambda v: 0xE000 <= v <= 0xF8FF
# Import rather than restate: a second copy of this set drifts silently the day
# someone adds a box terminator to dstext and not here.
from dstext import RESET, e106_clears
SPEAKER = 0xE101

# 'both' measures every line the MAIN dialogue font draws (dialogue AND
# narration, the 2026-09-27 fix). 'dialogue' reproduces the pre-fix scope
# (string must carry {E101}) so an old figure can still be checked against a
# new build with the SAME ruler. Never change the default without saying so
# in the printed header - see the module docstring's SCOPE section.
MEASURE_SCOPE = 'both'

# Banks PROVEN to use a font other than MAIN - excluded so this stays "the
# dialogue box, real MAIN advances, 240px" and never mismeasures a different
# widget with the wrong table (a narrow SMALL-font row can measure OVER 240
# in the wider MAIN table while fitting its own much smaller field). Round 1
# of this fix also excluded 456/457/458 and DS[460] on an INFERENCE (a
# names.py comment, and a control-code-profile guess for 460) - a refuter
# round 2 pass found the repo does not support that for 456-458: inject.py's
# own comment at the SMALL_WIDGET_BANKS definition says the 2026-09-27 sweep
# "found no engine handle for 456/457 in the arm9 or any overlay" and that
# 456-458 "keep the ordinary convert(u) call ... for whatever Capcom text
# lands there" - i.e. the plain MAIN-font dialogue wrap, same as every DS[n]
# bank. Direct proof they render in MAIN: inject.py's DSONLY-gate comment
# records a v1.4.1 player bug where emptied DS[456] rows (bank "exam_dl") were
# shown "in a message box" ON EDGEWORTH'S NAMEPLATE - the ordinary dialogue
# widget, not a SMALL-font option row. names.py's ACCENT_OFF_BANKS comment
# ("453-458 draw a SMALL face") is about accent-glyph safety only and is
# contradicted by this evidence, so it is not relied on any more. 456/457/458
# and DS[460] are therefore IN scope below; excluding a bank now requires
# code that says what font it uses, not an inference.
#   453/454/455  Mind Chess option/question/banner rows: the SMALL1 font
#                (fontwidths.SMALL_TABLE_OFF), fixed proven fields 189/229/189
#                px, audited by audits/audit_widgets.py (SMALL_BANKS). This is
#                the only exclusion with real code proof (inject.py's
#                SMALL_WIDGET_BANKS/use_small_widths() actually swap the font
#                table for these three at build time).
#   395, 432     "logicKW" / "detailMsg" (tools/names.py's DESC_BANKS =
#                {432, 438, 395, 391}). Both are patched through
#                tools/loc_patch.patch_entry(box=...), which swaps in
#                loc_patch.desc_font()'s own smaller face and its own line_px
#                (132, or the description card's own field) instead of the
#                MAIN table - confirmed at the one call site that does this,
#                tools/inject.py:1917-1920, a loop over the two banks
#                ((432, ..., 'detailMsg'), (395, ..., 'logicKW')). Audited
#                (fan-relative, MAIN-font model) by audit_widgets.py.
# 391 ("logic04_08") and 438 ("itm01_002") are the other two names of
# DESC_BANKS but are NOT excluded, on purpose: most of their strings carry
# real {E101} (checked empirically: 3/8 and 7/7), neither ever reaches
# loc_patch.patch_entry, and both go through the ordinary
# harmonize_entry -> dstext.convert() build path exactly like every other
# DS[n] dialogue bank - same MAIN font, same 240px budget - so their few
# non-{E101} strings belong in THIS scope, not audit_widgets.py's.
#
# 456/457/458 numbers on the shipped 1.10.0 ROM (MAIN font, this scope):
# 456 has 222 visible rows / 309 lines, widest 240px; 457 has 63 rows / 93
# lines, widest 239px; 458 has 32 non-empty rows / 44 lines, widest 239px -
# all at or under budget, so keeping them in scope adds 0 hits today (checked
# below). 458 is near-unused in the FAN ROM specifically (2 of 160 rows
# non-empty there - the port fills in far more of it than the fan ever did,
# which is why the shipped and fan row counts differ so much) and is not in
# audit_widgets.py's own BANKS list either - a real coverage gap in that
# audit (audit_widgets.py was not touched by this task).
#
# DS[460] (episode titles AND player-facing system prompts, e.g. str1 "Erase
# all data and restore default settings?" - not only titles): no code found
# that says it uses a font other than MAIN, and no other audit measures its
# text width (audit_titles.py only checks the title-STRIP IMAGES). Its widest
# line on the shipped ROM is 181px, so including it costs nothing and closes
# a real coverage gap. Kept in scope; the control-code-profile-based exclusion
# from round 1 (no {E100} in its non-{E101} strings) was inference, not proof,
# and is dropped.
WIDGET_BANKS = {395, 432, 453, 454, 455}
EXCLUDE_BANKS = WIDGET_BANKS


def _default_built():
    p = _os.path.join(_REPO, 'out', 'GK2 (Official English, DS port).nds')
    if _os.path.exists(p):
        return p
    raise SystemExit('no built ROM in %s - run a build first, or pass one as an '
                     'argument' % _os.path.join(_REPO, 'out'))


def _default_fan():
    import locate
    rom, _ = locate.find_fan_rom([_REPO, _os.path.dirname(_REPO), _os.getcwd()])
    if not rom:
        raise SystemExit('could not find your AAI2 Final v2 ROM - pass it with '
                         '--fan-rom')
    return rom


def spt_of(rom_path):
    rom = open(rom_path, 'rb').read()
    fid = file_id(rom, 'jpn/spt.bin')
    fat = struct.unpack_from('<I', rom, 0x48)[0]
    s, e = struct.unpack_from('<II', rom, fat + fid * 8)
    return rom[s:e]


def entries(blob, exclude=EXCLUDE_BANKS):
    n = struct.unpack_from('<I', blob, 0)[0] // 8
    for i in range(n):
        if i in exclude:
            continue
        o, s = struct.unpack_from('<II', blob, i * 8)
        if s and blob[o:o + 4] == b' TPS':
            yield i, blob[o:o + s]


def _render_short(units, limit=60):
    """A short, readable preview of a line's visible units: fullwidth Latin
    back to ASCII, the game's own space/apostrophe/ellipsis units to their
    plain form, everything else (real CJK, unmapped) as-is. For reporting
    only - never used for measurement."""
    out = []
    for v in units:
        # 0xFF3F (the game's space unit) sits INSIDE the 0xFF01-0xFF5E
        # fullwidth-Latin range, so it must be tested first or it decodes as
        # the fullwidth-Latin char at that offset ('_') instead of a space -
        # the same ordering trap tools/names.py:92-94 documents. Found by the
        # 2026-09-27 round-2 refuter: every FAIL listing printed spaces as
        # underscores before this fix.
        if v == 0xFF3F:
            out.append(' ')
        elif 0xFF01 <= v <= 0xFF5E:
            out.append(chr(v - 0xFF01 + 0x21))
        elif v in (0x201C, 0x201D):
            out.append("'" if v == 0x201D else '"')
        elif v == 0x2025:
            out.append('.')
        elif 0x20 <= v < 0x7F:
            out.append(chr(v))
        else:
            out.append(chr(v))
    s = ''.join(out)
    return (s[:limit] + '...') if len(s) > limit else s


def lines_of(blob, W, args, scope=None):
    """[(px, entry, str, text_preview), ...] for every display line in scope.

    scope: 'dialogue' reproduces the pre-2026-09-27 rule (string must carry
    {E101}); 'both' (default, MEASURE_SCOPE) measures every line, dialogue and
    narration alike, in every entry not in EXCLUDE_BANKS.
    """
    scope = scope or MEASURE_SCOPE
    out = []
    for ei, ent in entries(blob):
        for idx, _a, _ln, u in all_strings(ent, ds=True):
            if scope == 'dialogue' and SPEAKER not in u:
                continue
            cur, cur_units, i, n = 0, [], 0, len(u)
            while i < n:
                v = u[i]
                if CTRL(v):
                    i += 1
                    for _ in range(args.get(v, 0)):
                        if i < n and not CTRL(u[i]):
                            i += 1
                    # {E106} is in dstext.RESET but only ends a box when a
                    # prompt/popup code follows it before the next visible text
                    # unit (dstext.e106_clears, DELTA 7b) - its handler (overlay 7
                    # 0x020ACEB0) otherwise only does the engine's read-mark
                    # bookkeeping and returns, so the engine keeps writing into
                    # the box already on screen. Treating every {E106} as a line
                    # end measures a box the DS never draws, and it hid the very
                    # defect class this instrument exists to find: under the old
                    # model the build showed 2 lines over budget, under the
                    # 7b model it shows the real figure. {E185} and {E081} are
                    # string-final in every occurrence. RESET itself is left
                    # alone, because other callers use it to mean "codes that can
                    # end a message".
                    if v in RESET and (v != 0xE106 or e106_clears(u, i)):
                        if cur:
                            out.append((cur, ei, idx, _render_short(cur_units)))
                        cur, cur_units = 0, []
                    continue
                if v == 0x0A:
                    if cur:
                        out.append((cur, ei, idx, _render_short(cur_units)))
                    cur, cur_units = 0, []; i += 1; continue
                if v == 0:
                    i += 1; continue
                cur += W.get(v, 14); cur_units.append(v); i += 1
            if cur:
                out.append((cur, ei, idx, _render_short(cur_units)))
    return out


def main(argv):
    fan = None
    roms = []
    it = iter(argv)
    for a in it:
        if a == '--fan-rom':
            fan = next(it)
        else:
            roms.append(a)
    roms = roms or [_default_built()]
    fan = fan or _default_fan()

    args = {int(k, 16): v for k, v in
            json.load(open(_os.path.join(_REPO, 'dump', 'ctrl_args.json'))).items()}
    W, _px = fontwidths.widths(fan)
    if not W:
        raise SystemExit('could not read the font advances out of %s' % fan)

    print('box budget: %d real px      scope: %s (excludes banks %s)'
          % (BOX, MEASURE_SCOPE, sorted(EXCLUDE_BANKS)))
    print('advances from: %s' % _os.path.basename(fan))
    print()
    print('%-44s %8s %9s %7s  %s' % ('rom', 'lines', 'over %d' % BOX, 'max', 'widest at'))
    worst_over = 0
    all_over = []
    for r in roms:
        L = lines_of(spt_of(r), W, args)
        over = [x for x in L if x[0] > BOX]
        mx = max(L)
        worst_over = max(worst_over, len(over))
        all_over.append((_os.path.basename(r), sorted(over, reverse=True)))
        print('%-44s %8d %9d %7d  entry %d str %d'
              % (_os.path.basename(r)[:44], len(L), len(over), mx[0], mx[1], mx[2]))
    # Real audit exit code (added 2026-09-27, alongside audit_widgets.py's own):
    # any dialogue-font line over the 240px box on any ROM passed fails the
    # run, so this can be wired into run_audits.sh instead of only read by eye.
    if worst_over:
        print('\nFAIL: %d line(s) over %dpx' % (worst_over, BOX))
        for name, over in all_over:
            if not over:
                continue
            print('\n  %s:' % name)
            for px, ei, si, text in over[:200]:
                print('    entry %-4d str %-4d  %5dpx  %s' % (ei, si, px, text))
        return 1
    print('\nPASS: no dialogue-font line over %dpx' % BOX)
    return 0


if __name__ == '__main__':
    _sys.exit(main(_sys.argv[1:]))
