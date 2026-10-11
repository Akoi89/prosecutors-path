# -*- coding: utf-8 -*-
"""Does any centred row sit at an engine offset the engine cannot draw?

{E20D} centres the row it opens. At runtime the engine turns it into {E050 n} in
its laid-out buffer, n = (240 - w) // 2, w = the row's width in pixels in the
dialogue font. Two values of n break, because the engine reads them as control
units. n = 10 is the same number as 0x0A, a newline, so that row is drawn FLUSH
LEFT instead of centred (title card of Episode 3, "of the So-Called "President"
--", 219 px: the row sat at the left edge; rows at n = 9, 11, 12, 13, 14, 32 and
70 centred, and a static {E050 11}, {E050 9} or {E050 13} centred too). n = 0
(a row 239 or 240 px wide) is the end-of-text unit: a statement box whose first
row was a 239 px {E20D} row printed completely empty, while rows at n = 1 and 2
printed fine. Both were shown on an emulator on 2026-10-10. The converter
(tools/dstext.py fix_centre_offsets) writes {E050 11} in place of {E20D} on a row
that would land on 10 and drops the {E20D} of a row that would land on 0; this
audit is the standing guard.

Method: for every string of every entry in the built ROM's jpn/spt.bin, take
each {E20D} row (the units after the code up to the next 0x0A, {E102}, {E104} or
the end; codes skipped with their argument count), add the real glyph advances
of the fan font (read from the player's own AAI2 Final v2, as audit_widgets.py
does), and compute n. BAD is any row with n == 0 or n == 10, any row wider than
the 240 px line (n < 0), and any STATIC {E050 0} or {E050 10} (the engine reads
those as a control unit whatever the width). A row that starts with a static
{E050 n} instead of {E20D} is not measured: its offset is the number written
there, so it is counted as information only.

    python audits\\audit_centring.py [built.nds [fan.nds]]

SCOPE - what this does NOT look at:
  * Only the dialogue face. A widget that draws {E20D} rows in another face
    (description card, Logic cards, Mind Chess) would have another n; none of
    them carries {E20D} today, and this audit does not model them.
  * Whether the row is centred well, only that it is not at an offset that
    breaks. A row at n = 11 is 1 px right of true centre for 219 and 220 px.
  * The spt.bin is read as the engine reads it (split rows are NOT folded back).
  * Entries or strings that fail to parse (spt.all_strings raises): counted
    and printed, not silently passed.
"""
import os as _os
import sys as _sys

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


import struct

import spt
import dstext
import fontwidths
from inject import file_id

OURS_ROM = _sys.argv[1] if len(_sys.argv) > 1 else _default_built()
FAN_ROM = _sys.argv[2] if len(_sys.argv) > 2 else _default_fan()

_adv, _px = fontwidths.widths(FAN_ROM)
if not dstext.use_real_widths(_adv, _px):
    # Without the real advances n cannot be told from an estimate; a pass would
    # mean nothing, so refuse rather than print OK.
    raise SystemExit('cannot read the dialogue font advances from %s - this audit '
                     'needs the real widths' % FAN_ROM)


def rs(rom, path):
    fat = struct.unpack_from('<I', rom, 0x48)[0]
    fid = file_id(rom, path)
    a, b = struct.unpack_from('<II', rom, fat + fid * 8)
    return rom[a:b]


ROM = open(OURS_ROM, 'rb').read()
SPT = rs(ROM, 'jpn/spt.bin')


def text_of(u, start):
    out = []
    k = start + 1
    while k < len(u):
        v = u[k]
        if v == 0x0A or v in dstext.ROW_END_CODES:
            break
        if dstext.CTRL(v):
            k += 1 + dstext.ARGS.get(v, dstext.DEFAULT_ARGS)     # skip the code and its arguments
            continue
        out.append(' ' if v in (0xFF3F, 0x3000)
                   else chr(v - 0xFEE0) if 0xFF01 <= v <= 0xFF5E else chr(v))
        k += 1
    return ''.join(out)


def static_row_starts(u):
    """Rows that open with a static {E050 n}: a row starts at the string start, after 0x0A and
    after {E102}/{E104}; codes are skipped with their argument count, so an argument that
    happens to equal 10 is never read as a newline; the first {E050} before any visible text
    of the row is the one that opens it."""
    count, k, fresh = 0, 0, True
    while k < len(u):
        v = u[k]
        if dstext.CTRL(v):
            if fresh and v == dstext.CENTRE_OFFSET_CODE:
                count += 1
                fresh = False
            elif v in dstext.ROW_END_CODES:
                fresh = True
            k += 1 + dstext.ARGS.get(v, dstext.DEFAULT_ARGS)
            continue
        fresh = (v == 0x0A)
        k += 1
    return count


rows_bad, static_bad = [], []
n_entries = n_strings = n_fail = n_rows = n_static_start = 0
n = struct.unpack_from('<I', SPT, 0)[0] // 8
for i in range(n):
    o, s = struct.unpack_from('<II', SPT, i * 8)
    e = SPT[o:o + s] if s else b''
    if e[:4] != b' TPS':
        continue
    n_entries += 1
    try:
        strs = [list(u) for _, _, _, u in spt.all_strings(e, True)]
    except Exception:
        n_fail += 1
        continue
    for j, u in enumerate(strs):
        n_strings += 1
        for start, px, off in dstext.centre_rows(u):
            n_rows += 1
            if dstext.unusable_offset(off):
                rows_bad.append((i, j, px, off, text_of(u, start)))
        for k in dstext.static_bad_offsets(u):
            static_bad.append((i, j, k))
        n_static_start += static_row_starts(u)

print('spt entries scanned: %d, strings: %d, entries that failed to parse (skipped): %d'
      % (n_entries, n_strings, n_fail))
print('{E20D} rows measured with the fan font advances: %d' % n_rows)
print('rows opened by a static {E050 n} (information only): %d' % n_static_start)
print('BAD - {E20D} rows whose engine offset n is in %s or below 0 (flush left, empty box, or too wide): %d'
      % (sorted(dstext.BAD_CENTRE_OFFSETS), len(rows_bad)))
for i, j, px, off, t in rows_bad[:40]:
    print('  entry %d str %d  %d px  n=%d  %s' % (i, j, px, off, t))
print('BAD - static {E050 0} / {E050 10}: %d' % len(static_bad))
for i, j, k in static_bad[:40]:
    print('  entry %d str %d unit %d' % (i, j, k))
if rows_bad or static_bad:
    print('BAD')
    _sys.exit(1)
if n_fail:
    print('NOT PROVEN - %d entries did not parse' % n_fail)
    _sys.exit(1)
print('OK')
