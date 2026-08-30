# Audit 3: the option-widget banks (confrontation / Logic Chess lines, Logic
# keywords). Every row of the shipped ROM must still be ONE line and no wider
# than the widest line the fan translation ever put in that same widget.
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
#   * The budget is the widest line the FAN ROM proved in that widget. Where the
#     fan left a bank near-empty the budget bounds almost nothing, which is why
#     banks 456/457 report rows over a budget that means little.
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
    """widths of each display line, and the line count."""
    out, cur = [], 0.0
    for v in u:
        if v == 0x0A or v in BOXEND:
            out.append(cur); cur = 0.0
        elif not CTRL(v) and v >= 0x20:
            cur += dstext._w(chr(v))
    out.append(cur)
    return out

OURS = rom_spt(OURS_ROM)
FAN  = rom_spt((sys.argv[2] if len(sys.argv) > 2 else _default_fan()))

BANKS = [453, 454, 455, 456, 457, 395, 391, 432, 438]
print('%-6s %8s %8s %8s %8s   %s' % ('entry', 'rows', 'fanmax', 'ourmax', 'over', 'multiline rows (ours)'))
problems = []
for i in BANKS:
    eo, ef = entry(OURS, i), entry(FAN, i)
    if not eo or eo[:4] != b' TPS' or not ef or ef[:4] != b' TPS':
        continue
    try:
        SO = {si: list(u) for si, a, ln, u in spt.all_strings(eo, True)}
        SF = {si: list(u) for si, a, ln, u in spt.all_strings(ef, True)}
    except Exception as e:
        print(i, 'parse fail', e); continue
    fanmax = 0.0
    for u in SF.values():
        w = lines_of(u)
        if w: fanmax = max(fanmax, max(w))
    ourmax = 0.0
    over = 0
    multi = []
    for si, u in SO.items():
        w = lines_of(u)
        if not w: continue
        ourmax = max(ourmax, max(w))
        # compare against this row's own fan width too (per-row floor)
        fw = lines_of(SF[si]) if si in SF else [0]
        if max(w) > fanmax + 0.5 and max(w) > max(fw) + 0.5:
            over += 1
            problems.append((i, si, max(w), fanmax, max(fw)))
        if i in (453, 454, 455, 456, 457) and len(w) > 1 and si in SF and len(lines_of(SF[si])) == 1:
            multi.append(si)
    print('%-6d %8d %8.0f %8.0f %8d   %s' % (i, len(SO), fanmax, ourmax, over,
                                             (multi[:6] if multi else 'none')))

print()
print('rows wider than BOTH the widget max and their own fan row: %d' % len(problems))
for p in problems[:20]:
    print('   DS[%d] str%d  %.0fpx  (widget fan max %.0f, this row fan %.0f)' % p)
