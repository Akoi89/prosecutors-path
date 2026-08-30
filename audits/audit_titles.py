# Audit 1: independently re-read every title strip by template-matching the
# harvested glyphs, and compare to the FAN_TITLES readings plates.py relies on.
# A misread strip = a card that now carries the wrong official name.
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

import sys, json, collections

import plates as P

# SCOPE - what this does NOT look at:
#   * Only the evidence/profile title strips and nameplates in jpn/idlocal.bin.
#     No other graphic in the game is checked by anything.
#   * Reads the FAN artwork and compares against the expected tables; it cannot
#     tell whether our redrawn output is correct, only whether the source we keyed
#     off matches. The redrawn result has no automated check at all.
#   * Glyph matching cannot split the hand-squeezed long titles; those 12 were
#     confirmed by eye once and are taken on trust since.

PLA = P.Plates(open(_os.path.join(_REPO, 'dump', 'ds_fan', 'jpn', 'idlocal.bin'), 'rb').read())
T = P.Titles(PLA)

def runs_of(g):
    txt = [any(g[y][x] == 1 for y in range(16)) for x in range(128)]
    out, s = [], None
    for x in range(128):
        if txt[x] and s is None: s = x
        if not txt[x] and s is not None: out.append((s, x)); s = None
    if s is not None: out.append((s, 128))
    return out

def cut(g, a, b):
    return [tuple(1 if g[y][x] == 1 else 0 for y in range(16)) for x in range(a, b)]

def match(cols):
    """Best glyph for these columns; returns (char, distance)."""
    best, bd = None, 1e9
    for ch, gc in T.glyphs.items():
        if abs(len(gc) - len(cols)) > 1:
            continue
        w = max(len(gc), len(cols))
        d = 0
        for i in range(w):
            c1 = cols[i] if i < len(cols) else tuple([0]*16)
            c2 = gc[i] if i < len(gc) else tuple([0]*16)
            d += sum(1 for y in range(16) if c1[y] != c2[y])
        d /= float(w)
        if d < bd: best, bd = ch, d
    return best, bd

def read_strip(i):
    g = T._grid(i)
    out, worst = [], 0.0
    prev_end = None
    for (a, b) in runs_of(g):
        if prev_end is not None and a - prev_end >= 4:
            out.append(' ')
        ch, d = match(cut(g, a, b))
        out.append(ch if ch else '?')
        worst = max(worst, d)
        prev_end = b
    return ''.join(out), worst

print('=== A. re-reading each fan title strip ===')
bad = []
for i, expected in sorted(P.FAN_TITLES.items()):
    got, worst = read_strip(i)
    if got.replace(' ', '') != expected.replace(' ', ''):
        bad.append((i, expected, got, round(worst, 2)))
print('strips checked: %d' % len(P.FAN_TITLES))
print('readings that disagree with plates.py: %d' % len(bad))
for i, exp, got, w in bad:
    print('   %3d expected %-30r got %-30r worstdist %.2f' % (i, exp, got, w))

print()
print('=== B. every official title must exist in Capcom\'s own tables ===')
en = json.load(open(_os.path.join(_REPO, 'dump', 'loc_en.json'), encoding='utf-8'))
known = set()
for k, rows in en.items():
    for _, t in rows:
        if t:
            known.add(t.strip())
missing = []
for i, (fan, off) in sorted(P.TITLES.items()):
    base = P.Titles.TRIMS.get(off, off)
    if off not in known:
        missing.append((i, off))
print('official names checked: %d' % len(P.TITLES))
print('not found verbatim in the Collection tables: %d' % len(missing))
for i, off in missing:
    print('   %3d %r' % (i, off))

print()
print('=== C. the fan text plates.py expects must match the strip it edits ===')
mismatch = [(i, P.FAN_TITLES.get(i), fan) for i, (fan, off) in sorted(P.TITLES.items())
            if P.FAN_TITLES.get(i) != fan]
print('TITLES rows whose guard text disagrees with FAN_TITLES: %d' % len(mismatch))
for m in mismatch: print('   ', m)
