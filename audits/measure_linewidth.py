# -*- coding: utf-8 -*-
"""THE canonical instrument for "dialogue lines wider than the 240px box".

    python audits/measure_linewidth.py [ROM ...]

With no argument it measures the built ROM in out/. Pass one or more ROMs to
compare them, oldest first. The per-glyph advances come from your own AAI2 Final
v2 ROM, found the same way build.py finds it, or passed with --fan-rom.

Four different walkers were written for this figure during the 2026-09-19 review
and they disagreed wildly on TOTALS while agreeing exactly on the OVER-240 COUNT.
The disagreement was always scope, never arithmetic. So the scope is pinned here,
and any figure taken from it must be quoted together with this command:

SCOPE, exactly:
  * jpn/spt.bin out of the ROM's own filesystem, every ' TPS' entry.
  * DIALOGUE ONLY: a string counts only if it contains E101 (speaker_control).
    This is what excludes the option-widget banks, which have their own boxes and
    their own budgets and are audited by audits/audit_widgets.py instead.
  * A control code consumes its arguments (dump/ctrl_args.json) so argument units
    are never measured as text.
  * A line ends at 0x0A or at a box-terminating code (dstext.RESET).
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
from dstext import RESET
SPEAKER = 0xE101


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


def entries(blob):
    n = struct.unpack_from('<I', blob, 0)[0] // 8
    for i in range(n):
        o, s = struct.unpack_from('<II', blob, i * 8)
        if s and blob[o:o + 4] == b' TPS':
            yield i, blob[o:o + s]


def lines_of(blob, W, args):
    out = []
    for ei, ent in entries(blob):
        for idx, _a, _ln, u in all_strings(ent, ds=True):
            if SPEAKER not in u:
                continue
            cur, i, n = 0, 0, len(u)
            while i < n:
                v = u[i]
                if CTRL(v):
                    i += 1
                    for _ in range(args.get(v, 0)):
                        if i < n and not CTRL(u[i]):
                            i += 1
                    if v in RESET:
                        if cur:
                            out.append((cur, ei, idx))
                        cur = 0
                    continue
                if v == 0x0A:
                    if cur:
                        out.append((cur, ei, idx))
                    cur = 0; i += 1; continue
                if v == 0:
                    i += 1; continue
                cur += W.get(v, 14); i += 1
            if cur:
                out.append((cur, ei, idx))
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

    print('box budget: %d real px      dialogue = strings containing E101' % BOX)
    print('advances from: %s' % _os.path.basename(fan))
    print()
    print('%-44s %8s %9s %7s  %s' % ('rom', 'lines', 'over %d' % BOX, 'max', 'widest at'))
    for r in roms:
        L = lines_of(spt_of(r), W, args)
        over = [x for x in L if x[0] > BOX]
        mx = max(L)
        print('%-44s %8d %9d %7d  entry %d str %d'
              % (_os.path.basename(r)[:44], len(L), len(over), mx[0], mx[1], mx[2]))


if __name__ == '__main__':
    main(_sys.argv[1:])
