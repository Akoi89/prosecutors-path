# Audit 3: the option-widget banks (confrontation / Logic Chess lines, Logic
# keywords). 453/454/455 (Mind Chess) must be one line each, no wider than the
# real SMALL-font field the 2026-09-27 text-box sweep proved (SMALL_BANKS
# below) - not a fan-relative comparison. Every other bank here (456/457,
# description/Logic) keeps the older rule: no wider than the widest line the
# fan translation ever put in that same widget, in the MAIN dialogue font.
import os as _os
import sys as _sys

# Portable paths: the audits live in <repo>/audits and the toolchain in
# <repo>/tools, so everything is found relative to this file rather than to any
# one machine. The ROMs are yours and are located the same way build.py does it.
_REPO = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
_sys.path.insert(0, _os.path.join(_REPO, 'tools'))


def _default_built():
    p = _os.path.join(_REPO, 'out', 'GK2 (Official English, DS port).nds')
    if _os.path.exists(p):
        return p
    cand = [f for f in _os.listdir(_os.path.join(_REPO, 'out'))
            if f.lower().endswith('.nds')] if _os.path.isdir(_os.path.join(_REPO, 'out')) else []
    if len(cand) == 1:
        return _os.path.join(_REPO, 'out', cand[0])
    raise SystemExit('no built ROM in %s - run a build first, or pass one as the '
                     'first argument' % _os.path.join(_REPO, 'out'))


def _default_fan():
    import locate
    rom, _ = locate.find_fan_rom([_REPO, _os.path.dirname(_REPO), _os.getcwd()])
    if not rom:
        raise SystemExit('could not find your AAI2 Final v2 ROM - pass it as the '
                         'second argument')
    return rom

import sys, struct

import spt, dstext
from inject import file_id

# SCOPE - what this does NOT look at:
#   * ONLY the option-widget banks (453-457). Every other bank's line widths are
#     unchecked here; the dialogue box is checked at build time instead.
#   * 453/454/455 (Mind Chess option/question/banner rows) are measured in the
#     SMALL face they actually draw in, against the fixed field widths the
#     2026-09-27 text-box sweep proved (SMALL_BANKS below) - NOT the widest
#     line the fan itself drew, which is a MAIN-font measurement and means
#     nothing for a SMALL-font widget (a capture of the option bar showed a
#     row drawn clipped where a MAIN measurement said it still fit).
#     456/457 and the description/Logic banks
#     keep the older fan-relative MAIN comparison; nobody has proven their
#     real per-bank field width the way 453/454/455 are now proven.
#   * Measures rendered width only - says nothing about whether the text is right.

# Optional ROM override, so a deliberately broken fixture can be audited
# without touching out/. See rig\audit_fixtures.py.
OURS_ROM = sys.argv[1] if len(sys.argv) > 1 else _default_built()


CTRL = lambda v: 0xE000 <= v <= 0xF8FF
BOXEND = {0xE102, 0xE104, 0xE106, 0xE185, 0xE081}

def rom_spt(path):
    rom = open(path, 'rb').read()
    fat = struct.unpack_from('<I', rom, 0x48)[0]
    fid = file_id(rom, 'jpn/spt.bin')
    a, b = struct.unpack_from('<II', rom, fat + fid * 8)
    return rom[a:b]

def entry(cont, i):
    o, s = struct.unpack_from('<II', cont, i * 8)
    return cont[o:o+s] if s else b''

def lines_of(u):
    """widths of each display line, and the line count.

    Every one of these rows ends on a box-end code (usually {E106}, used here
    as a terminator, never actually flushing a box mid-widget), which this
    walk also treats as a line end - so a plain trailing 0.0 for "the empty
    line after the last real one" always showed up here, and `len(w) > 1`
    below could never be False. Fixed 2026-09-27: drop trailing empty lines
    (but always keep at least one, so an empty row still reports [0.0]).
    """
    out, cur = [], 0.0
    for v in u:
        if v == 0x0A or v in BOXEND:
            out.append(cur); cur = 0.0
        elif not CTRL(v) and v >= 0x20:
            cur += dstext._w(chr(v))
    out.append(cur)
    while len(out) > 1 and out[-1] == 0.0:
        out.pop()
    return out


def small_lines_of(u, small_adv):
    """Same shape as lines_of(), measured with the SMALL1 table (the face
    banks 453-455 actually draw) instead of dstext._w's MAIN table. Of the
    fan's two redrawn accent slots, SMALL1 has no U+0415 record at all, and
    its U+30A7 record (6px) is unverified as the actual redrawn glyph rather
    than a coincidentally valid entry - so both map to a plain fullwidth 'e'
    here, the same fallback inject.py's widget path and names.py's
    WIDGET_BANKS use."""
    out, cur = [], 0.0
    for v in u:
        if v == 0x0A or v in BOXEND:
            out.append(cur); cur = 0.0
        elif not CTRL(v) and v >= 0x20:
            vv = 0xFF45 if v in (0x0415, 0x30A7) else v
            a = small_adv.get(vv) if small_adv else None
            if a is None and 0x20 <= vv <= 0x7E:
                a = small_adv.get(vv - 0x21 + 0xFF01) if small_adv else None
            cur += 9999 if a is None else a
    out.append(cur)
    while len(out) > 1 and out[-1] == 0.0:
        out.pop()
    return out

OURS = rom_spt(OURS_ROM)
_FAN_ROM = sys.argv[2] if len(sys.argv) > 2 else _default_fan()
FAN  = rom_spt(_FAN_ROM)

# Measure in the SAME units the build gates rows in. Standalone, dstext starts on
# the estimate model, so before 2026-09-19 this audit reported estimate units for a
# ROM wrapped in real pixels, and the two disagreed about which rows were over.
# In real pixels bank 454's apparent overrun turns out to be well inside what the
# fan itself drew, and bank 453 improves rather than regressing.
try:
    import fontwidths
    _adv, _px = fontwidths.widths(_FAN_ROM)
    if not dstext.use_real_widths(_adv, _px):
        print('note: ROM advances unavailable; measuring with the estimate model')
    _small_adv = fontwidths.small_widths(_FAN_ROM)
except Exception:
    print('note: ROM advances unavailable; measuring with the estimate model')
    _small_adv = None
if not _small_adv:
    # 453/454/455 cannot be measured at all without this table - exit
    # non-zero rather than silently pass them (they would in fact still fail,
    # since small_lines_of() prices every glyph 9999 with no table, but that
    # is an accident of that fallback, not a documented guarantee).
    print('FAIL: SMALL-font advances unavailable; cannot measure 453/454/455')
    sys.exit(1)

# Fixed field widths the 2026-09-27 text-box sweep proved for the Mind Chess
# SMALL-font banks (a capture of the option bar placed 453's field at 189; a
# capture of the question bar plus the fan's own shipped rows placed 454's at
# 229; 455 is a single-line banner whose field is the same 189 as 453's option
# bar). Never derived from a row in the bank itself, so a fan placeholder
# ("Temp." dev text, 453/54) cannot inflate the limit the way the old
# fan-widest-row budget could.
SMALL_BANKS = {453: 189, 454: 229, 455: 189}

BANKS = [453, 454, 455, 456, 457, 395, 391, 432, 438]
print('%-6s %8s %8s %8s %8s   %s' % ('entry', 'rows', 'fanmax', 'ourmax', 'over', 'multiline rows (ours)'))
problems = []
hard_over = []          # (entry, str, px, limit) - 453/454/455 past their proven field
hard_multi = []         # (entry, str) - 453-457 rows that lost a second line
for i in BANKS:
    eo, ef = entry(OURS, i), entry(FAN, i)
    if not eo or eo[:4] != b' TPS' or not ef or ef[:4] != b' TPS':
        continue
    try:
        SO = {si: list(u) for si, a, ln, u in spt.all_strings(eo, True)}
        SF = {si: list(u) for si, a, ln, u in spt.all_strings(ef, True)}
    except Exception as e:
        print(i, 'parse fail', e); continue
    small_limit = SMALL_BANKS.get(i)
    measure = (lambda u: small_lines_of(u, _small_adv)) if small_limit is not None else lines_of
    fanmax = 0.0
    for u in SF.values():
        w = measure(u)
        if w: fanmax = max(fanmax, max(w))
    ourmax = 0.0
    over = 0
    multi = []
    for si, u in SO.items():
        w = measure(u)
        if not w: continue
        ourmax = max(ourmax, max(w))
        if small_limit is not None:
            # Absolute proven field width, not a fan-relative comparison: a
            # SMALL-font budget was never set by "whatever the fan drew". Still
            # floored by the row's OWN fan width (same principle as the other
            # branch's per-row floor, and the general fix rule this project
            # uses: never re-flag a line already inside the proven limit) -
            # a handful of fan rows in 453
            # (untranslated Japanese placeholders, and the "Temp." dev row
            # itself, 453/54) sit over 189 unchanged by every build this
            # pipeline can produce; only a row THIS build made wider than the
            # fan's own is a build defect.
            fw = measure(SF[si]) if si in SF else [0]
            if max(w) > small_limit + 0.5 and max(w) > max(fw) + 0.5:
                over += 1
                problems.append((i, si, max(w), float(small_limit), max(fw)))
                hard_over.append((i, si, max(w), small_limit))
        else:
            # compare against this row's own fan width too (per-row floor)
            fw = measure(SF[si]) if si in SF else [0]
            if max(w) > fanmax + 0.5 and max(w) > max(fw) + 0.5:
                over += 1
                problems.append((i, si, max(w), fanmax, max(fw)))
        if i in (453, 454, 455, 456, 457) and len(w) > 1 and si in SF and len(measure(SF[si])) == 1:
            multi.append(si)
            if i in (453, 454, 455):
                hard_multi.append((i, si))
    print('%-6d %8d %8.0f %8.0f %8d   %s' % (i, len(SO), fanmax, ourmax, over,
                                             (multi[:6] if multi else 'none')))

print()
print('rows wider than BOTH the widget max and their own fan row: %d' % len(problems))
for p in problems[:20]:
    print('   DS[%d] str%d  %.0fpx  (widget fan max %.0f, this row fan %.0f)' % p)

print()
if hard_over:
    print('rows over their proven SMALL field width: %d' % len(hard_over))
    for i, si, px, lim in hard_over[:20]:
        print('   DS[%d] str%d  %.0fpx  (field %d)' % (i, si, px, lim))
if hard_multi:
    print('rows that lost a second line (453-455, must stay one line): %d' % len(hard_multi))
    for i, si in hard_multi[:20]:
        print('   DS[%d] str%d' % (i, si))
if hard_over or hard_multi:
    print('\nFAIL: %d row(s) over field, %d row(s) lost a line'
          % (len(hard_over), len(hard_multi)))
    sys.exit(1)
print('\nPASS: every 453/454/455 row fits its proven SMALL field and one line')
sys.exit(0)
