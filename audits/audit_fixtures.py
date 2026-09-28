# -*- coding: utf-8 -*-
"""Prove each audit can FAIL.

An audit that has never failed has not been tested, it has only been run. This
project learned that twice in one night: my chapter-sweep hang detector reported
"zero frozen" across 25 chapters while measuring something that could never
happen, and claude-2f's structural audit passed a build they had already proven
broken because it silently compared nothing.

This breaks a COPY of the ROM in exactly the way each audit claims to detect and
checks the audit notices. out/ is never touched.

WHAT IT HAS ALREADY CAUGHT: audit_empty gave byte-identical output on a ROM with
400 box-ends stripped out - because it looks for strings empty of TEXT and only
PRINTS box counts, never tests them. The v1.4.2 defect class had no standing audit
at all. audit_boxes.py exists because this harness was written.

Method: patch units IN PLACE. Every substitution is the same width, so no offset
moves and the file stays structurally valid - a fixture that were merely corrupt
would be detected for the wrong reason. Text is stored XOR 0x55AA, so unit u sits
on disk as (u ^ 0x55AA) little-endian.

    python audits\audit_fixtures.py [clean_rom.nds]

The optional argument is the clean ROM every fixture is built on top of and
compared against (default: the ROM out/ points at, see _default_built above).
"""
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

import os
import struct
import subprocess
import sys
import tempfile


import spt                                    # noqa: E402
from dstext import ARGS                       # noqa: E402
from inject import file_id, STAGING_CODES     # noqa: E402
import txtcut                                 # noqa: E402
import title_logo                             # noqa: E402

_BOXEND = (0xE102, 0xE104, 0xE185, 0xE081)

REAL = _default_built()
RIG = _os.path.dirname(_os.path.abspath(__file__))
WORK = os.path.join(tempfile.gettempdir(), 'claude', 'fixtures')
XOR = 0x55AA


def enc(u):
    return struct.pack('<H', u ^ XOR)


def spt_span(rom):
    fat = struct.unpack_from('<I', rom, 0x48)[0]
    fid = file_id(rom, 'jpn/spt.bin')
    return struct.unpack_from('<II', rom, fat + fid * 8)


def swap_code(rom, frm, to, limit):
    """Replace up to `limit` encoded occurrences of unit `frm` with `to`."""
    a, b = spt_span(rom)
    src, dst = enc(frm), enc(to)
    out = bytearray(rom)
    n, i = 0, a
    while n < limit:
        j = out.find(src, i, b)
        if j < 0:
            break
        if (j - a) % 2 == 0:
            out[j:j + 2] = dst
            n += 1
            i = j + 2
        else:
            i = j + 1
    return bytes(out), n


def break_boxes(rom):
    """Strip box-ends: the v1.4.2 defect. E102 -> E040, same width, arity 0."""
    return swap_code(rom, 0xE102, 0xE040, 400)


def break_dsonly(rom):
    """Delete the DS-only tutorial pair: the v1.4.3 hang."""
    return swap_code(rom, 0xE041, 0xE040, 200)


def break_arity(rom):
    """Fullwidth a control-code argument: the v1.3.3 Little Thief signature.

    E108 takes one argument and carries an ASCII letter at ~398 sites, which is
    precisely the shape that defeated the arity heuristic.
    """
    a, b = spt_span(rom)
    out = bytearray(rom)
    code = enc(0xE108)
    n, i = 0, a
    while n < 120:
        j = out.find(code, i, b)
        if j < 0:
            break
        if (j - a) % 2 == 0 and j + 4 <= b:
            arg = struct.unpack_from('<H', out, j + 2)[0] ^ XOR
            if 0x41 <= arg <= 0x7A:
                out[j + 2:j + 4] = enc(0xFF00 + (arg - 0x20))
                n += 1
        i = j + 2
    return bytes(out), n


def break_empty(rom):
    """Blank a whole string's visible text, leaving its structure intact.

    audit_empty looks for strings with no printable characters where the fan ROM
    had some. Replacing each visible unit with 0x0A keeps every offset and the
    box structure while emptying the text - the v1.2.1 / Episode 1 NPC shape.
    """
    a, b = spt_span(rom)
    out = bytearray(rom)
    cont = bytes(rom[a:b])
    n = struct.unpack_from('<I', cont, 0)[0] // 8
    done = 0
    for i in range(n):
        if done >= 6:
            break
        o, s = struct.unpack_from('<II', cont, i * 8)
        e = cont[o:o + s] if s else b''
        if not e or e[:4] != b' TPS':
            continue
        try:
            rows = list(spt.all_strings(e, True))
        except Exception:                                    # noqa: BLE001
            continue
        cnt = struct.unpack_from('<H', e, 0x06)[0]
        for j in range(1, min(cnt, len(rows))):
            off, clen = struct.unpack_from('<HH', e, 0x10 + (j - 1) * 8 + 4)
            base = a + o + off * 2
            if clen < 12 or base + clen * 2 > b:
                continue
            vis = 0
            for k in range(clen):
                v = struct.unpack_from('<H', out, base + k * 2)[0] ^ XOR
                if 0xFF01 <= v <= 0xFF5E or 0x21 <= v <= 0x7E:
                    out[base + k * 2:base + k * 2 + 2] = enc(0x0A)
                    vis += 1
            if vis >= 10:
                done += 1
                break
    return bytes(out), done


def _tps_entries(rom):
    """(entry index, absolute offset, bytes) for every ' TPS' entry of spt.bin."""
    a, b = spt_span(rom)
    cont = bytes(rom[a:b])
    n = struct.unpack_from('<I', cont, 0)[0] // 8
    for i in range(n):
        o, s = struct.unpack_from('<II', cont, i * 8)
        e = cont[o:o + s] if s else b''
        if e[:4] == b' TPS':
            yield i, a + o, e


def break_hint(rom):
    """Shrink the 0x08 buffer-size hint below the longest string it must hold.

    audit_hint compares the hint against the DATA, so a hint two units short of
    the longest string is exactly the defect it claims to catch. Same width (u16
    in place), nothing else moves.
    """
    out = bytearray(rom)
    done = 0
    for i, base, e in _tps_entries(rom):
        if done >= 8:
            break
        try:
            longest = max(len(u) for _, _, _, u in spt.all_strings(e, True))
        except Exception:                                    # noqa: BLE001
            continue
        hint = struct.unpack_from('<H', e, 0x08)[0]
        if longest < 4 or hint < longest:
            continue
        struct.pack_into('<H', out, base + 0x08, longest - 2)
        done += 1
    return bytes(out), done


def break_tails(rom):
    """Zero every non-zero unit a string stores after its declared length.

    That slot can hold the last argument of a command the declared length cuts off
    (DS[178] str 23, the Episode 3 Bound/Larry talk). audit_tails compares it with
    the fan ROM's; zeroing it in place is exactly the 1.8.3 defect, repeated at
    every site. Same size, nothing else moves.
    """
    out = bytearray(rom)
    done = 0
    for i, base, e in _tps_entries(rom):
        try:
            h, recs = spt.parse(e, True)
            tl = spt.tails(e, True)
        except Exception:                                    # noqa: BLE001
            continue
        starts = [h['dstart']] + [r[1] for r in recs]
        lens = [h['lead']] + [r[2] for r in recs]
        for s, n, t in zip(starts, lens, tl):
            if any(t):
                for k in range(len(t)):
                    out[base + s + 2 * (n + k):base + s + 2 * (n + k) + 2] = enc(0)
                done += 1
    return bytes(out), done


# fullwidth 'W'. Real advances (checked against the ROM, not the old estimate
# model): 10px in SMALL1, 13px in MAIN - see break_widgets_narrow's docstring
# below, which found the same glyph is NOT 9px in either table. Used at
# 13px/MAIN by break_narration_width (measure_linewidth.py's fixture).
WIDE_UNIT = 0xFF37


def break_widgets(rom):
    """Widen option rows past the widget's proven field.

    Bank 453 (confrontation lines) has a proven SMALL-font field of 189px
    (2026-09-27 text-box sweep; audit_widgets.py's SMALL_BANKS). Every visible
    unit and every line break in a row becomes 'W' (10px in SMALL1), so a row
    of 32+ units renders at 320px or more on one line - wider than the field
    and wider than its own fan row either way the row is measured. Control
    codes and their arguments are left alone so the row is wide for the right
    reason, not corrupt.
    """
    a, b = spt_span(rom)
    out = bytearray(rom)
    done = 0
    for i, base, e in _tps_entries(rom):
        if i != 453:
            continue
        cnt = struct.unpack_from('<H', e, 0x06)[0]
        for j in range(1, cnt):
            if done >= 8:
                break
            off, clen = struct.unpack_from('<HH', e, 0x10 + (j - 1) * 8 + 4)
            sbase = base + off * 2
            if sbase + clen * 2 > b:
                continue
            units = [struct.unpack_from('<H', out, sbase + k * 2)[0] ^ XOR for k in range(clen)]
            targets, skip = [], 0
            for k, v in enumerate(units):
                if skip:
                    skip -= 1
                    continue
                if 0xE000 <= v <= 0xF8FF:
                    skip = ARGS.get(v, 0)
                    continue
                if v == 0x0A or 0x21 <= v <= 0x7E or 0xFF01 <= v <= 0xFF5E:
                    targets.append(k)
            if len(targets) < 32:
                continue
            for k in targets:
                out[sbase + k * 2:sbase + k * 2 + 2] = enc(WIDE_UNIT)
            done += 1
        break
    return bytes(out), done


def break_widgets_narrow(rom):
    """Push one bank-453 row to 190-200px in the SMALL font - just past the
    189px field - while staying at 247-260px in the MAIN dialogue font (real
    advances, not the estimate model: 'W' is 10px in SMALL1 but 13px in MAIN,
    not 9px - checked against the ROM, not assumed), under the ~285px budget
    a fan-max MAIN measurement of this bank would have used. Proves the
    SMALL-font measurement specifically: break_widgets above (320px+ in
    either font) is wide enough that an older, MAIN-font-and-fan-max version
    of audit_widgets.py would also have caught it, so it does not on its own
    prove THIS fix added anything - this one measures 0 over on the OLD
    fan-max-in-MAIN rule and over on the new SMALL/189 rule. Every visible
    unit becomes 'W'; picks the first row with 19 or 20 of them (this ROM:
    DS[453] str103, 20 units, 200px SMALL / 260px MAIN), so the replaced row
    lands in the target window exactly from its own unit count, not by
    chance.
    """
    a, b = spt_span(rom)
    out = bytearray(rom)
    for i, base, e in _tps_entries(rom):
        if i != 453:
            continue
        cnt = struct.unpack_from('<H', e, 0x06)[0]
        for j in range(1, cnt):
            off, clen = struct.unpack_from('<HH', e, 0x10 + (j - 1) * 8 + 4)
            sbase = base + off * 2
            if sbase + clen * 2 > b:
                continue
            units = [struct.unpack_from('<H', out, sbase + k * 2)[0] ^ XOR for k in range(clen)]
            targets, skip = [], 0
            for k, v in enumerate(units):
                if skip:
                    skip -= 1
                    continue
                if 0xE000 <= v <= 0xF8FF:
                    skip = ARGS.get(v, 0)
                    continue
                if v == 0x0A or 0x21 <= v <= 0x7E or 0xFF01 <= v <= 0xFF5E:
                    targets.append(k)
            if len(targets) not in (19, 20):
                continue
            for k in targets:
                out[sbase + k * 2:sbase + k * 2 + 2] = enc(WIDE_UNIT)
            return bytes(out), 1
        break
    return bytes(rom), 0


def break_narration_width(rom):
    """Widen a NARRATION line (no {E101}) past the 240px dialogue budget -
    proves the 2026-09-27 measure_linewidth.py fix (narration scope) can
    fail. DS[18] str5 is part of the same scene as str4 (which carries
    {E100}{E101}) but never reopens the box itself, so the PRE-fix
    E101-only scope of measure_linewidth.py never looked at this string at
    all - exactly the blind spot the fix exists to close. Every visible unit
    becomes 'W' (0xFF37, 13px in the MAIN real-advance table measure_linewidth.py
    builds against), so the string's widest line - same box-end codes at the
    same positions, same line breaks, nothing added or removed - grows from
    209px to well over 400px. Control codes, their arguments, 0x0A and the
    null separator are left untouched, so only the defect this fixture exists
    to prove is introduced.
    """
    a, b = spt_span(rom)
    cont = bytes(rom[a:b])
    o, s = struct.unpack_from('<II', cont, 18 * 8)
    if not s or cont[o:o + 4] != b' TPS':
        return bytes(rom), 0
    e = cont[o:o + s]
    h, recs = spt.parse(e, True)
    starts = [h['dstart']] + [r[1] for r in recs]
    lens = [h['lead']] + [r[2] for r in recs]
    j = 5
    if j >= len(starts):
        return bytes(rom), 0
    sbase = a + o + starts[j]
    ln = lens[j]
    if sbase + ln * 2 > b:
        return bytes(rom), 0
    units = [struct.unpack_from('<H', rom, sbase + k * 2)[0] ^ XOR for k in range(ln)]
    out = bytearray(rom)
    done, skip = 0, 0
    for k, v in enumerate(units):
        if skip:
            skip -= 1
            continue
        if 0xE000 <= v <= 0xF8FF:
            skip = ARGS.get(v, 0)
            continue
        if v in (0, 0x0A):
            continue
        out[sbase + k * 2:sbase + k * 2 + 2] = enc(WIDE_UNIT)
        done += 1
    return bytes(out), done


def _find_e187_offset(e, base, j, arg_index):
    """Absolute file offset of the (arg_index)'th argument (0=strip id,
    1=target string) of the FIRST {E187} in string j of entry bytes `e`,
    which itself starts at file offset `base`. None if string j has none."""
    h, recs = spt.parse(e, True)
    starts = [h['dstart']] + [r[1] for r in recs]
    lens = [h['lead']] + [r[2] for r in recs]
    if j >= len(starts):
        return None
    s, ln = starts[j], lens[j]
    u = spt.units(e[s:], ln)
    k, n = 0, len(u)
    while k < n:
        v = u[k]
        if 0xE000 <= v <= 0xF8FF:
            if v == 0xE187:
                return base + s + 2 * (k + 1 + arg_index)
            k += 1 + ARGS.get(v, 0)
        else:
            k += 1
    return None


def break_choicearg_strip(rom):
    """Point DS[58] str 2's {E187} strip-arg at 170 so 363+170 = idlocal 533,
    the short-strip PALETTE entry, not a sprite (the real Ep3 DS[200] hazard -
    ROOTCAUSE.md; rig-proven elsewhere to freeze the game with the prompt up
    and no buttons). Chosen specifically so audit_choicearg's check 1 (idlocal
    sprite-vs-palette) is what catches this, not check 3 (the fan diff): 363 +
    163, the id the real DS[58] bug actually carries, lands on idlocal 526, a
    real 3872-byte sprite bundle, so a 163 fixture here would only be caught by
    the fan comparison and would prove nothing about check 1. No-ops (returns
    0) if the site already holds 170, so the harness never reports a
    byte-identical write as a patch."""
    a, b = spt_span(rom)
    cont = bytes(rom[a:b])
    o, s = struct.unpack_from('<II', cont, 58 * 8)
    off = _find_e187_offset(cont[o:o + s], a + o, 2, 0) if s else None
    if off is None:
        return bytes(rom), 0
    cur = struct.unpack_from('<H', rom, off)[0] ^ XOR
    if cur == 170:
        return bytes(rom), 0
    out = bytearray(rom)
    out[off:off + 2] = enc(170)
    return bytes(out), 1


def break_choicearg_target(rom):
    """Drop DS[92] str 18's {E187} target-string index by one - the Group-B
    defect: region_align re-lays this entry onto the fan's one-shorter string
    layout but only rewrites {E081} indices, so {E187}'s second argument goes
    stale. Same shape as the real fault, applied fresh so the fixture proves
    the audit rather than reproducing the fix."""
    a, b = spt_span(rom)
    cont = bytes(rom[a:b])
    o, s = struct.unpack_from('<II', cont, 92 * 8)
    off = _find_e187_offset(cont[o:o + s], a + o, 18, 1) if s else None
    if off is None:
        return bytes(rom), 0
    cur = struct.unpack_from('<H', rom, off)[0] ^ XOR
    out = bytearray(rom)
    out[off:off + 2] = enc(cur - 1)
    return bytes(out), 1


def _find_code_offset(e, base, j, code, arg_index):
    """Absolute file offset of the (arg_index)'th argument of the FIRST
    occurrence of `code` in string j of entry bytes `e`, which itself starts
    at file offset `base`. None if string j has none. Same shape as
    _find_e187_offset above, generalised to any code/position."""
    h, recs = spt.parse(e, True)
    starts = [h['dstart']] + [r[1] for r in recs]
    lens = [h['lead']] + [r[2] for r in recs]
    if j >= len(starts):
        return None
    s, ln = starts[j], lens[j]
    u = spt.units(e[s:], ln)
    k, n = 0, len(u)
    while k < n:
        v = u[k]
        if 0xE000 <= v <= 0xF8FF:
            if v == code:
                return base + s + 2 * (k + 1 + arg_index)
            k += 1 + ARGS.get(v, 0)
        else:
            k += 1
    return None


def _find_code_offset_by_value(e, base, j, code, arg_index, value):
    """Absolute file offset of the (arg_index)'th argument of the occurrence
    of `code` in string j of entry bytes `e` (base = absolute offset `e`
    starts at) whose CURRENT value at that position equals `value`. None if
    string j has no such occurrence. Same shape as _find_code_offset above,
    but picks the occurrence by its value rather than always the first -
    DS[99] str 5 carries three {E15B} occurrences and only one of them is the
    reported fault (see break_staging below)."""
    h, recs = spt.parse(e, True)
    starts = [h['dstart']] + [r[1] for r in recs]
    lens = [h['lead']] + [r[2] for r in recs]
    if j >= len(starts):
        return None
    s, ln = starts[j], lens[j]
    u = spt.units(e[s:], ln)
    k, n = 0, len(u)
    while k < n:
        v = u[k]
        if 0xE000 <= v <= 0xF8FF:
            if v == code and u[k + 1 + arg_index] == value:
                return base + s + 2 * (k + 1 + arg_index)
            k += 1 + ARGS.get(v, 0)
        else:
            k += 1
    return None


def break_indexarg_e11f(rom):
    """Decrement DS[92] str 1's first {E11F}'s argument position 1 by one -
    the real Case 2 rebuttal fault (CRASH_ENTRY92_20260922.md): every
    {E11F}/{E120} statement pointer in this string was one less than the
    fan's, statement 0 pointed at an empty stub with no statement box drawn,
    and the ARM9 data-aborted. Applied, one unit, to whichever ROM the harness
    is given (its optional argument; bare, it uses out\\GK2 (Official English,
    DS port).nds), so the fixture proves audit_indexargs.py rather than
    reproducing the fix itself. The ROM must be a FIXED build: a pre-fix ROM
    already fails the audit clean, so this fixture reports NOT PROVEN on it
    until a fixed build is the release output."""
    a, b = spt_span(rom)
    cont = bytes(rom[a:b])
    o, s = struct.unpack_from('<II', cont, 92 * 8)
    off = _find_code_offset(cont[o:o + s], a + o, 1, 0xE11F, 1) if s else None
    if off is None:
        return bytes(rom), 0
    cur = struct.unpack_from('<H', rom, off)[0] ^ XOR
    out = bytearray(rom)
    out[off:off + 2] = enc(cur - 1)
    return bytes(out), 1


def break_staging(rom):
    """Set DS[99] str 5's SECOND {E15B}'s x argument back to 192 - the real
    Case 2 camera fault a tester reported: a scene
    where the camera never returns to its resting position and an officer is
    left out of frame, because the built ROM carried the Collection's own
    re-tuned camera position (192) where the fan (the DS original) holds 140.
    The string carries three {E15B} occurrences; the first and third are 192
    on BOTH sides and were never the fault, so this targets the occurrence by
    its current value (140, only true on a fixed build) rather than by
    position. Applied to whichever ROM the harness is given (its optional
    argument; bare, it uses out\\GK2 (Official English, DS port).nds), so the
    fixture proves audit_staging.py rather than reproducing the fix itself.
    The ROM must be a FIXED build: a pre-fix ROM has no occurrence at 140 to
    find, so this fixture reports NOT PROVEN on it until a fixed build is the
    release output."""
    a, b = spt_span(rom)
    cont = bytes(rom[a:b])
    o, s = struct.unpack_from('<II', cont, 99 * 8)
    off = _find_code_offset_by_value(cont[o:o + s], a + o, 5, 0xE15B, 0, 140) if s else None
    if off is None:
        return bytes(rom), 0
    out = bytearray(rom)
    out[off:off + 2] = enc(192)
    return bytes(out), 1


def _find_boxend_then_staging(e, base, j):
    """(absolute file offset of the box-end unit, arity of the staging
    command right after it) for the FIRST place in string j of entry bytes
    `e` (base = absolute offset `e` starts at) where a box-end code
    (_BOXEND) is immediately followed by a STAGING_CODES occurrence. None if
    string j has no such place."""
    h, recs = spt.parse(e, True)
    starts = [h['dstart']] + [r[1] for r in recs]
    lens = [h['lead']] + [r[2] for r in recs]
    if j >= len(starts):
        return None
    s, ln = starts[j], lens[j]
    u = spt.units(e[s:], ln)
    k, n = 0, len(u)
    prev_code, prev_k = None, None
    while k < n:
        v = u[k]
        if 0xE000 <= v <= 0xF8FF:
            arity = ARGS.get(v, 0)
            if v in STAGING_CODES and prev_code in _BOXEND:
                return base + s + 2 * prev_k, arity
            prev_code, prev_k = v, k
            k += 1 + arity
        else:
            k += 1
    return None


def break_staging_placement(rom):
    """Swap DS[2] str 0's box-end unit with the staging command right after
    it - moving that ONE occurrence one box EARLIER without touching the
    SUBSEQUENCE (same code, same arguments, same order relative to every
    other staging occurrence) or the box-end COUNT (the box-end is still
    there, only its position relative to that one occurrence changes). This
    is a PLACEMENT-only break: audit_staging.py's check 2 (box placement, the
    fan's own occurrence at the same subsequence position must sit in the
    same box) is what must catch it, not check 1 (the subsequence, which
    stays identical on both sides). Same width, same units, only their order
    changes - nothing else in the file moves. Applied to whichever ROM the
    harness is given (its optional argument; bare, it uses out\\GK2 (Official
    English, DS port).nds), so the fixture proves audit_staging.py rather
    than reproducing a real fault."""
    a, b = spt_span(rom)
    cont = bytes(rom[a:b])
    o, s = struct.unpack_from('<II', cont, 2 * 8)
    found = _find_boxend_then_staging(cont[o:o + s], a + o, 0) if s else None
    if found is None:
        return bytes(rom), 0
    off, arity = found
    staging_width = (1 + arity) * 2
    boxend_bytes = rom[off:off + 2]
    staging_bytes = rom[off + 2:off + 2 + staging_width]
    out = bytearray(rom)
    out[off:off + 2 + staging_width] = staging_bytes + boxend_bytes
    return bytes(out), 1


def _find_staging_after_text(e, base, j):
    """(absolute file offset to swap FROM, absolute file offset of the FIRST
    STAGING_CODES occurrence in string j of entry bytes `e` (base = absolute
    offset `e` starts at) that has some VISIBLE text before it since the
    previous box-end OR staging occurrence - a plain unit that is not a
    control code and not a bare {0A} line break, the same coarse
    before/after-text measurement used elsewhere in this project - arity).
    The FROM
    offset anchors right after whichever came before (another staging
    occurrence, or the box-end) rather than always the box's own start, so
    moving the found occurrence there can never cross another staging
    occurrence and change the SUBSEQUENCE - by returning on the FIRST match,
    that anchor is always itself at a point with no text before it since the
    box started, so the move still flips the COARSE property for the whole
    box. None if string j has no such place."""
    h, recs = spt.parse(e, True)
    starts = [h['dstart']] + [r[1] for r in recs]
    lens = [h['lead']] + [r[2] for r in recs]
    if j >= len(starts):
        return None
    s, ln = starts[j], lens[j]
    u = spt.units(e[s:], ln)
    k, n = 0, len(u)
    anchor = 0
    has_text = False
    while k < n:
        v = u[k]
        if 0xE000 <= v <= 0xF8FF:
            arity = ARGS.get(v, 0)
            if v in STAGING_CODES:
                if has_text:
                    return base + s + 2 * anchor, base + s + 2 * k, arity
                anchor = k + 1 + arity
                has_text = False
            elif v in _BOXEND:
                anchor = k + 1 + arity
                has_text = False
            k += 1 + arity
        else:
            if v != 0x0A:
                has_text = True
            k += 1
    return None


def break_staging_point(rom):
    """Move DS[6] str 1's FIRST staging occurrence that has some visible text
    ahead of it (since whichever comes first - the previous box-end, or the
    previous staging occurrence) back to right after that same anchor,
    swapping it past everything in between - on this ROM that is 38 units:
    text plus several non-staging control codes including {E101}, {E107}
    and {E108}. None of those are staging codes and none is a box-end, so
    the SUBSEQUENCE (check 1) and box placement (check 2) stay exactly
    right; only the COARSE before/after-text side (check 3) changes, because
    the anchor itself always has no text ahead of it since the box started
    (see _find_staging_after_text). DS[6] str 1 is one of the strings
    audit_staging.py's check 3 already reports clean on the built ROM,
    chosen so this fixture proves detection rather than landing on a string
    check 3 never evaluates or one already flagged for an unrelated,
    pre-existing reason. Same width, same units, only their order changes -
    nothing else in the file moves. Applied to whichever ROM the harness is
    given (its optional argument; bare, it uses out\\GK2 (Official English,
    DS port).nds)."""
    a, b = spt_span(rom)
    cont = bytes(rom[a:b])
    o, s = struct.unpack_from('<II', cont, 6 * 8)
    found = _find_staging_after_text(cont[o:o + s], a + o, 1) if s else None
    if found is None:
        return bytes(rom), 0
    anchor_off, off, arity = found
    code_width = (1 + arity) * 2
    prefix_bytes = rom[anchor_off:off]
    code_bytes = rom[off:off + code_width]
    out = bytearray(rom)
    out[anchor_off:off + code_width] = code_bytes + prefix_bytes
    return bytes(out), 1


def _find_unit_offset(e, base, j, k):
    """Absolute file offset of unit index `k` (0-based, counted from the
    string's own start, not code-aware) of string j of entry bytes `e`, which
    itself starts at file offset `base`. None if string j has no unit there
    (j out of range, or k at/past its declared length). Same shape as
    _find_code_offset above, but for a plain unit position rather than a
    control code's argument."""
    h, recs = spt.parse(e, True)
    starts = [h['dstart']] + [r[1] for r in recs]
    lens = [h['lead']] + [r[2] for r in recs]
    if j >= len(starts) or k >= lens[j]:
        return None
    return base + starts[j] + 2 * k


def break_zero_text(rom):
    """Zero one ordinary visible-text unit: DS[0] str 4, unit index 166 - well
    inside the string's declared length of 584 and nowhere near DS[95] str 16
    (the one spot the fan itself ships a text-position zero, which
    audit_zeros.py must go on accepting). audit_zeros.py walks every string
    arity-aware and flags a literal 0x0000 in text position before the
    string's declared end - the DS engine's own end-of-string marker
    (DELTA 5, fan_tone/E04X_FINDINGS.md) - so planting one here, with no fan
    zero anywhere nearby to excuse it, is exactly the defect it exists to
    catch. Same width, nothing else moves. No-ops (returns 0) if the site
    already holds 0, so the harness never reports a byte-identical write as a
    patch."""
    a, b = spt_span(rom)
    cont = bytes(rom[a:b])
    o, s = struct.unpack_from('<II', cont, 0 * 8)
    off = _find_unit_offset(cont[o:o + s], a + o, 4, 166) if s else None
    if off is None:
        return bytes(rom), 0
    cur = struct.unpack_from('<H', rom, off)[0] ^ XOR
    if cur == 0:
        return bytes(rom), 0
    out = bytearray(rom)
    out[off:off + 2] = enc(0)
    return bytes(out), 1


def _repack_idlocal(D, repl):
    """Rebuild the idlocal container with entries in `repl` (index -> decompressed
    bytes) stored as literal-only LZ11 - the same shape plates.Plates.rebuild
    writes, so the fixture differs from a real build only in the pixels."""
    n = struct.unpack_from('<I', D, 0)[0] // 8
    ents = [struct.unpack_from('<II', D, i * 8) for i in range(n)]
    order = sorted(range(n), key=lambda i: ents[i][0])
    ext = {}
    for k, i in enumerate(order):
        ext[i] = (ents[i][0], ents[order[k + 1]][0] if k + 1 < n else len(D))
    table = bytearray(n * 8)
    body = bytearray()
    for i in range(n):
        o, s = ents[i]
        comp, size, stored = s & 0x80000000, s & 0x7FFFFFFF, D[ext[i][0]:ext[i][1]]
        if i in repl:
            raw = repl[i]
            lz = bytearray(b'\x11' + len(raw).to_bytes(3, 'little'))
            for p in range(0, len(raw), 8):
                lz.append(0)
                lz += raw[p:p + 8]
            stored, size, comp = bytes(lz), len(raw), 0x80000000
        while (n * 8 + len(body)) % 4:
            body += b'\x00'
        struct.pack_into('<II', table, i * 8, n * 8 + len(body), size | comp)
        body += stored
    return bytes(table) + bytes(body)


def break_titles(_rom_unused):
    """Erase the first letter of four fan title strips.

    audit_titles re-reads every strip by glyph matching and compares to the
    FAN_TITLES table plates.py keys off. A strip missing its first letter reads
    as a different word, which is the misread-strip defect the audit exists for.
    Works on the FAN idlocal.bin the audit reads (not a ROM) and only on strips
    the audit currently reads correctly, so the disagreement count must rise.
    """
    import plates as P
    fan_path = os.path.join(_REPO, 'dump', 'ds_fan', 'jpn', 'idlocal.bin')
    D = open(fan_path, 'rb').read()
    PLA = P.Plates(D)
    T = P.Titles(PLA)
    repl, done = {}, 0
    for i in sorted(P.FAN_TITLES):
        if done >= 4:
            break
        g = T._grid(i)
        runs = T._runs(g)
        # only strips the audit can read today: one glyph run per letter. The
        # hand-squeezed titles fuse letters and already disagree, so breaking
        # one of those would not move the count.
        if not runs or len(runs) != len(P.FAN_TITLES[i].replace(' ', '')):
            continue
        a, b = runs[0]
        for y in range(16):
            for x in range(a, b):
                if g[y][x] == 1:
                    g[y][x] = 2                      # stroke -> bar: letter gone
        repl[i] = T.encode(i, g)
        done += 1
    return _repack_idlocal(D, repl), done


def break_hotspot_burnmark(rom):
    """Put com/cutdata.bin slot 47 back to the JP-retail rectangle
    (111,131)-(187,147), area index 0 - the shape every release since 1.7.0
    shipped, and the exact defect this hotfix addresses: it no longer covers
    "burn" or "mark" in our re-wrapped Coroner's Findings, only "of victim's".
    audit_hotspots.py must fail on this and pass on the real hotfixed slot
    (two rectangles, one per word). No-ops (returns 0) if the ROM's slot 47 is
    already this one record, so the harness never reports a byte-identical
    write as a patch."""
    fat = struct.unpack_from('<I', rom, 0x48)[0]
    fid = file_id(rom, 'com/cutdata.bin')
    a, b = struct.unpack_from('<II', rom, fat + fid * 8)
    cutdata = rom[a:b]
    slots = txtcut.table(cutdata)
    old = slots[47]
    cnt = struct.unpack_from('<H', old, 4)[0]
    recs = [struct.unpack_from('<11i', old, 20 + 44 * k) for k in range(cnt)]
    if cnt == 1 and tuple(v >> 12 for v in recs[0][2:6]) == (111, 131, 187, 147):
        return bytes(rom), 0
    hdr = bytearray(old[:20])
    size = 20 + 44
    struct.pack_into('<H', hdr, 4, 1)
    struct.pack_into('<I', hdr, 8, size << 16)
    struct.pack_into('<I', hdr, 12, size << 16)
    struct.pack_into('<I', hdr, 16, size << 16)
    rec = struct.pack('<11i', 0, 0, 111 << 12, 131 << 12, 187 << 12, 147 << 12, 0, 0, 0, 0, 0)
    new_slot47 = bytes(hdr) + rec
    lz = bytearray(b'\x11' + len(new_slot47).to_bytes(3, 'little'))
    for p in range(0, len(new_slot47), 8):
        lz.append(0)
        lz += new_slot47[p:p + 8]

    n = struct.unpack_from('<I', cutdata, 0)[0] // 8
    orig_slots = [struct.unpack_from('<II', cutdata, i * 8) for i in range(n)]
    live = sorted(o for o, s in orig_slots if o)
    table = bytearray(n * 8)
    body = bytearray()
    for i in range(n):
        o, s = orig_slots[i]
        if not o:
            struct.pack_into('<II', table, i * 8, 0, 0)
            continue
        if i == 47:
            blob, s = bytes(lz), 0x80000000 | len(new_slot47)
        else:
            nxt = [q for q in live if q > o]
            blob = cutdata[o:nxt[0] if nxt else len(cutdata)]
        while (n * 8 + len(body)) % 4:
            body += b'\x00'
        struct.pack_into('<II', table, i * 8, n * 8 + len(body), s)
        body += blob
    new_cutdata = bytes(table) + bytes(body)
    return title_logo.splice(rom, 'com/cutdata.bin', new_cutdata), 1


# (script, what the fixture breaks, how, what the audit reads)
#   'rom'     the audit takes a ROM path; the fixture is a broken copy of out/
#   'idlocal' the audit reads the FAN idlocal.bin; the fixture is a broken copy of
#             that file and the clean run is the audit's default input
FIXTURES = [
    ('audit_boxes.py',   'strip box-ends from many strings (the v1.4.2 defect)', break_boxes,   'rom'),
    ('audit_cmdloss.py', 'delete DS-only E041 codes (the v1.4.3 hang)',          break_dsonly,  'rom'),
    ('audit_arity.py',   'fullwidth E108 arguments (the v1.3.3 Little Thief bug)', break_arity, 'rom'),
    ('audit_empty.py',   'blank whole strings of visible text',                  break_empty,   'rom'),
    ('audit_hint.py',    'shrink SPT buffer hints below their longest string',   break_hint,    'rom'),
    ('audit_widgets.py', 'widen bank-453 option rows past the proven SMALL field (320px+, either font)', break_widgets, 'rom'),
    ('audit_widgets.py', 'push one bank-453 row to 190-200px in SMALL only (247-260px in MAIN, real advances) - just past the field, not merely very wide', break_widgets_narrow, 'rom'),
    ('audit_titles.py',  'erase the first letter of four fan title strips',      break_titles,  'idlocal'),
    ('audit_tails.py',   'zero the units strings keep past their declared length (the 1.8.3 Bound/Larry talk)', break_tails, 'rom'),
    ('audit_choicearg.py', 'point DS[58] str 2 {E187} strip-arg at 170 - 363+170 = idlocal 533, a palette, not a sprite', break_choicearg_strip, 'rom'),
    ('audit_choicearg.py', "drop DS[92] str 18's {E187} target-string index by one (the region_align skew)", break_choicearg_target, 'rom'),
    ('audit_indexargs.py', "decrement DS[92] str 1's first {E11F} argument position 1 by one (the rebuttal statement-index fault)", break_indexarg_e11f, 'rom'),
    ('audit_staging.py', "set DS[99] str 5's second {E15B} x argument back to 192 (the Case 2 camera fault)", break_staging, 'rom'),
    ('audit_staging.py', "move one staging command into the wrong box in a string whose box-end count still matches the fan", break_staging_placement, 'rom'),
    ('audit_staging.py', "move one staging command from after some text to before any text in its own box (same subsequence, same box)", break_staging_point, 'rom'),
    ('audit_zeros.py', "zero one ordinary text unit in DS[0] str 4 (a stray literal 0x0000 in text position - the DELTA 5 zero-in-text hang)", break_zero_text, 'rom'),
    ('measure_linewidth.py', "widen DS[18] str5 (a narration line with no {E101}) past 240px - the 2026-09-27 blind-spot fix", break_narration_width, 'rom'),
    ('audit_hotspots.py', "put com/cutdata.bin slot 47 back to the JP-retail rectangle (111,131)-(187,147) - the pre-hotfix box that misses 'burn'/'mark'", break_hotspot_burnmark, 'rom'),
]


def run_full(script, arg):
    """(stdout, returncode) for one audit invocation."""
    cmd = [sys.executable, os.path.join(RIG, script)] + ([arg] if arg else [])
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    return p.stdout.strip(), p.returncode


def run(script, arg):
    return run_full(script, arg)[0]


def _first_diff(clean, dirty):
    """The first output line that changed, so the summary says WHAT the audit
    noticed rather than only that something differed."""
    c, d = clean.splitlines(), dirty.splitlines()
    for x, y in zip(c, d):
        if x != y:
            return y.strip()
    return (d[len(c)] if len(d) > len(c) else '').strip()


def main():
    os.makedirs(WORK, exist_ok=True)
    # DELTA 1: optional ROM path argument, default unchanged (REAL, the
    # currently-built ROM out/ points at). REAL is the PRE-fix build for the
    # index-args audit until a build carrying the fix is passed here - see
    # the audit_indexargs.py entry below, which checks exit codes rather than
    # a text diff for exactly this reason.
    clean_path = sys.argv[1] if len(sys.argv) > 1 else REAL
    rom = open(clean_path, 'rb').read()
    results = []
    for script, what, make, kind in FIXTURES:
        print('\n=== %s ===' % script)
        print('  fixture: %s' % what)
        broken, n = make(rom)
        if not n:
            print('  COULD NOT BUILD THE FIXTURE')
            results.append((script, 'no fixture'))
            continue
        print('  patched %d site(s)' % n)
        path = os.path.join(WORK, script.replace('.py', '.nds' if kind == 'rom' else '.bin'))
        open(path, 'wb').write(broken)
        clean_arg = clean_path if kind == 'rom' else None
        if script in ('audit_indexargs.py', 'audit_zeros.py', 'audit_staging.py',
                      'audit_widgets.py', 'measure_linewidth.py', 'audit_tails.py',
                      'audit_hotspots.py'):
            # should-fix 2: an audit that already fails on the clean ROM would
            # make the ordinary text-diff test trivially pass. Require the
            # clean ROM to exit 0 (nothing wrong) and the broken copy to
            # exit 1 (audit_indexargs.py's / audit_zeros.py's / audit_widgets.py's
            # / measure_linewidth.py's own sys.exit(1)/return 1 on any hit).
            # audit_widgets.py added 2026-09-27 when it gained a real exit
            # code (rc=1 on any bank-453/454/455 row over its proven SMALL
            # field, or any 453-455 row that lost a line) - before that it
            # only ever printed, so the text-diff path below was the only way
            # to prove break_widgets (bank 453, still exercised here) was
            # noticed at all.
            # measure_linewidth.py added the same day, when its scope widened
            # to measure narration (strings with no {E101}) as well as
            # dialogue - see break_narration_width above, which this entry
            # exercises.
            # audit_tails.py gained its own exit code in the skip-guard round 2
            # fix (it previously only ever printed a LOST count) - break_tails
            # below (zeroing every kept fan tail) is the same fixture that used
            # to only be provable by a text diff.
            clean_out, clean_rc = run_full(script, clean_arg)
            dirty_out, dirty_rc = run_full(script, path)
            ok = clean_rc == 0 and dirty_rc == 1
            print('  clean exit: %d  dirty exit: %d' % (clean_rc, dirty_rc))
            if ok:
                print('  first changed line: %s' % _first_diff(clean_out, dirty_out))
            else:
                print('  >>> exit codes do not prove detection (clean=%d dirty=%d, want 0/1)'
                      % (clean_rc, dirty_rc))
        else:
            clean, dirty = run(script, clean_arg), run(script, path)
            ok = clean != dirty
            print('  audit notices: %s' % ok)
            if ok:
                print('  first changed line: %s' % _first_diff(clean, dirty))
            else:
                print('  >>> identical output on an input it should object to')
        results.append((script, 'DETECTED' if ok else 'MISSED'))
        os.remove(path)

    print('\n=== summary ===')
    for s, r in results:
        print('  %-20s %s' % (s, r))
    bad = [s for s, r in results if r != 'DETECTED']
    if bad:
        print('\nNOT PROVEN: %s' % ', '.join(bad))
        return 1
    print('\nevery fixture was detected - these audits can fail')
    return 0


if __name__ == '__main__':
    sys.exit(main())
