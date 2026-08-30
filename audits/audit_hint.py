# Is every SPT buffer-size hint big enough for the strings actually stored?
#
# Prompted by claude-2f's DSP-ADPCM finding: 17 audio clips declared a sample
# count far below what their data held, and an earlier audit passed them because
# it checked each index entry against its file and both agreed on a number that
# was simply too small. Consistency is not correctness.
#
# The same shape exists here. Each ' TPS' header carries a u16 at 0x08 that the
# engine uses as a buffer-size hint. It is NOT derived from the records, so a
# build that copies it from the source while writing LONGER strings would leave a
# hint that is internally consistent with nothing and too small for the data.
# Capcom's English is routinely longer than the Japanese it replaces, so this is
# exactly the direction that would bite.
#
# Checks the hint against the ACTUAL longest string in each entry, not against
# any other stored copy of the value.
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

import sys, struct, collections


import spt
from inject import file_id

# SCOPE - what this does NOT look at:
#   * Only entries that parse as ' TPS'. Anything that fails to parse is skipped
#     silently, which is why the entry count is printed.
#   * Only the 0x08 buffer hint. Other header fields are unchecked.
#   * A margin of +0 is normal, not tight - the fan ROM ships 394 entries at
#     exactly hint == longest.

# Optional ROM override, so a deliberately broken fixture can be audited
# without touching out/. See rig\audit_fixtures.py.
OURS_ROM = sys.argv[1] if len(sys.argv) > 1 else _default_built()



def rs(path):
    rom = open(path, 'rb').read()
    fat = struct.unpack_from('<I', rom, 0x48)[0]
    fid = file_id(rom, 'jpn/spt.bin')
    a, b = struct.unpack_from('<II', rom, fat + fid * 8)
    return rom[a:b]


def entry(c, i):
    o, s = struct.unpack_from('<II', c, i * 8)
    return c[o:o + s] if s else b''


OURS = rs(OURS_ROM)
FAN = rs((sys.argv[2] if len(sys.argv) > 2 else _default_fan()))

n = struct.unpack_from('<I', OURS, 0)[0] // 8
short = []
checked = 0
margin = collections.Counter()

for i in range(n):
    e = entry(OURS, i)
    if not e or e[:4] != b' TPS':
        continue
    hint = struct.unpack_from('<H', e, 0x08)[0]
    try:
        longest = max(len(u) for _, _, _, u in spt.all_strings(e, True))
    except Exception:
        continue
    checked += 1
    if hint < longest:
        f = entry(FAN, i)
        fhint = struct.unpack_from('<H', f, 0x08)[0] if f[:4] == b' TPS' else -1
        short.append((i, hint, longest, fhint))
    else:
        margin[min(hint - longest, 999)] += 1

print('entries checked: %d' % checked)
print('hints SMALLER than the longest string they must hold: %d' % len(short))
if short:
    print()
    print('%-6s %8s %9s %9s' % ('entry', 'hint', 'longest', 'fan hint'))
    for i, h, l, fh in short[:30]:
        print('%-6d %8d %9d %9d   short by %d' % (i, h, l, fh, l - h))
else:
    tight = sum(v for k, v in margin.items() if k < 8)
    print('smallest margins: %s' % sorted(margin)[:6])
    print('entries with under 8 units of headroom: %d' % tight)

# Second angle: did we SHRINK any hint relative to the fan ROM while making its
# strings longer? That is the combination that would be actively wrong.
worse = 0
for i in range(n):
    a, b = entry(OURS, i), entry(FAN, i)
    if not a or a[:4] != b' TPS' or not b or b[:4] != b' TPS':
        continue
    ah = struct.unpack_from('<H', a, 0x08)[0]
    bh = struct.unpack_from('<H', b, 0x08)[0]
    try:
        al = max(len(u) for _, _, _, u in spt.all_strings(a, True))
        bl = max(len(u) for _, _, _, u in spt.all_strings(b, True))
    except Exception:
        continue
    if ah < bh and al > bl:
        worse += 1
        print('  entry %d: hint %d -> %d while longest %d -> %d' % (i, bh, ah, bl, al))
print()
print('entries where the hint shrank while the text grew: %d' % worse)
