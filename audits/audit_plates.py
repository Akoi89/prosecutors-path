# -*- coding: utf-8 -*-
"""Nameplate audit: margins, borders, spacing and letters of every dialogue nameplate in a built ROM.

The 28 plates the build redraws (plates.PLATES) and the 31 it leaves alone are read back out of the
ROM's own jpn/idlocal.bin and measured against the fan's own plates in the fan ROM:

  1. no ink on the bar's border: every text pixel of every plate is inside the fill, columns 51-92;
  2. margin: the blank columns between the text and the fill's edge are never below the fan's
     smallest (taken from its untouched plates; 0 today), and a redrawn plate's left and right margins
     differ by no more than the fan's own plates do (1 today);
  3. letters: a redrawn plate's ink splits into exactly the letters of its official name (no letters
     touching, none split);
  4. word gap: the blank columns between two words are at least plates.WORD_GAP (3), except the plates
     listed in plates.THIN_EXCEPTIONS with the exact gaps they must have (any other gaps fail, as does a
     stale entry);
  5. pixels: a redrawn plate differs from the fan's only where the fan had text (now fill) or where the
     new text sits, inside the fill; an untouched plate is the fan's, pixel for pixel.

Exit status 1 and a line per failure when any check fails. `--selftest` feeds deliberately broken
plates through the same code and requires each to be caught.

    python audits/audit_plates.py [rom.nds] [fan_rom.nds]
    python audits/audit_plates.py --selftest [rom.nds] [fan_rom.nds]
"""
import os as _os
import struct
import sys

_REPO = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
sys.path.insert(0, _os.path.join(_REPO, 'tools'))

import plates as P

TEXT = P.TEXT
A, B = P.FILL_A, P.FILL_B - 1           # visible fill, inclusive
C0, C1 = P.CLEAR_A, P.CLEAR_B           # the bar piece the build redraws
FIRST, LAST = 27, 85                    # 86 is empty in the fan too


def _default_built():
    p = _os.path.join(_REPO, 'out', 'GK2 (Official English, DS port).nds')
    if _os.path.exists(p):
        return p
    cand = [f for f in _os.listdir(_os.path.join(_REPO, 'out'))
            if f.lower().endswith('.nds')] if _os.path.isdir(_os.path.join(_REPO, 'out')) else []
    if len(cand) == 1:
        return _os.path.join(_REPO, 'out', cand[0])
    raise SystemExit('no built ROM in %s - run a build first, or pass one as the first argument'
                     % _os.path.join(_REPO, 'out'))


def _default_fan():
    import locate
    rom, _ = locate.find_fan_rom([_REPO, _os.path.dirname(_REPO), _os.getcwd()])
    if not rom:
        raise SystemExit('could not find your AAI2 Final v2 ROM - pass it as the second argument')
    return rom


def _idlocal(path):
    import bufcheck
    return bufcheck.rom_file(open(path, 'rb').read(), 'jpn/idlocal.bin')


def ink_cols(g):
    return [x for x in range(C0, C1) if any(g[y][x] == TEXT for y in range(8))]


def runs(cols):
    out, s, p = [], None, None
    for x in cols:
        if s is None:
            s = p = x
        elif x == p + 1:
            p = x
        else:
            out.append((s, p)); s = p = x
    if s is not None:
        out.append((s, p))
    return out


def margins(g):
    c = ink_cols(g)
    return c[0] - A, B - c[-1]


def measure(fan_grids):
    """(smallest margin, largest left-right difference) over the fan's untouched plates."""
    sides, diffs = [], []
    for i in range(FIRST, LAST + 1):
        if i in P.PLATES:
            continue
        l, r = margins(fan_grids[i])
        sides += [l, r]; diffs.append(abs(l - r))
    return min(sides), max(diffs)


def check(built, fan, fan_min=None, fan_diff=None):
    """built, fan: {entry: grid}. -> (failures, report lines)."""
    if fan_min is None:
        fan_min, fan_diff = measure(fan)
    bad, lines = [], []
    for i in range(FIRST, LAST + 1):
        g, f = built[i], fan[i]
        cols = ink_cols(g)
        name = P.PLATES.get(i)
        tag = '%d %s' % (i, name or '(fan)')
        if not cols:
            bad.append('%s: no text' % tag); continue
        out = [x for x in cols if x < A or x > B]
        if out:
            bad.append('%s: ink on the border at column(s) %s (fill is %d-%d)' % (tag, out, A, B))
        l, r = cols[0] - A, B - cols[-1]
        if min(l, r) < fan_min:
            bad.append('%s: margin %d/%d is below the fan\'s smallest %d' % (tag, l, r, fan_min))
        if name is None:
            if g != f:
                bad.append('%s: an untouched plate differs from the fan\'s' % tag)
            lines.append('%-18s untouched   L%-2d R%-2d' % (tag, l, r))
            continue
        if abs(l - r) > fan_diff:
            bad.append('%s: margins %d/%d differ by %d, the fan\'s own plates by at most %d' % (tag, l, r, abs(l - r), fan_diff))
        # pixels: only text may differ, and new ink only inside the fill
        for y in range(8):
            for x in range(len(g[0])):
                if g[y][x] == f[y][x]:
                    continue
                if f[y][x] == TEXT and g[y][x] == P.FILL and C0 <= x < C1:
                    continue
                if g[y][x] == TEXT and A <= x <= B and f[y][x] in (P.FILL, TEXT):
                    continue
                bad.append('%s: pixel (%d,%d) is %d, the fan\'s %d, outside what a redraw may change' % (tag, x, y, g[y][x], f[y][x]))
                break
            else:
                continue
            break
        # letters
        rr = runs(cols)
        words = name.split(' ')
        letters = sum(len(w) for w in words)
        if len(rr) != letters:
            bad.append('%s: ink splits into %d letters, the name has %d (letters touching or broken)' % (tag, len(rr), letters))
        # word gaps
        gaps, k = [], 0
        if len(rr) == letters:
            for w in words[:-1]:
                k += len(w)
                gaps.append(rr[k][0] - rr[k - 1][1] - 1)
            low = [x for x in gaps if x < P.WORD_GAP]
            exc = P.THIN_EXCEPTIONS.get(i)
            if exc is None:
                if low:
                    bad.append('%s: word gap %s is below %d and the plate has no exception' % (tag, gaps, P.WORD_GAP))
            else:
                if gaps != list(exc[0]):
                    bad.append('%s: word gaps %s do not match the listed %s' % (tag, gaps, list(exc[0])))
                if not any(x < P.WORD_GAP for x in exc[0]):
                    bad.append('%s: listed in THIN_EXCEPTIONS but its expected word gaps %s are all %d or more' % (tag, list(exc[0]), P.WORD_GAP))
            if any(x < 2 for x in gaps):
                bad.append('%s: word gap %s is under 2' % (tag, gaps))
        lines.append('%-18s redrawn     L%-2d R%-2d  ink %-2d  letters %2d  word gaps %s' % (tag, l, r, cols[-1] - cols[0] + 1, len(rr), gaps or '-'))
    stale = [i for i in P.THIN_EXCEPTIONS if i not in P.PLATES]
    if stale:
        bad.append('THIN_EXCEPTIONS names entries %s that are not redrawn plates' % stale)
    return bad, lines


def load(path):
    pl = P.Plates(_idlocal(path))
    return {i: pl._grid(i) for i in range(FIRST, LAST + 1)}


def selftest(built, fan):
    """Each broken copy of the real plates must be caught."""
    import copy
    fmin, fdiff = measure(fan)
    ok, _ = check(built, fan, fmin, fdiff)
    if ok:
        raise SystemExit('selftest: the unbroken plates already fail: %s' % ok[0])

    def shifted(i, dx):
        g = copy.deepcopy(built); gi = g[i]
        for y in range(8):
            row = [(6 if gi[y][x] == TEXT else gi[y][x]) for x in range(len(gi[y]))]
            for x in range(len(gi[y])):
                if built[i][y][x] == TEXT and 0 <= x + dx < len(row):
                    row[x + dx] = TEXT
            gi[y] = row
        return g

    def join_letters(i):
        """the blank columns between the first two letters filled, so they touch"""
        g = copy.deepcopy(built)
        rr = runs(ink_cols(built[i]))
        for x in range(rr[0][1] + 1, rr[1][0]):
            for y in range(2, 6):
                g[i][y][x] = TEXT
        return g

    def pixel(i, y, x, v):
        g = copy.deepcopy(built); g[i][y][x] = v
        return g

    def closed(sh):
        """Man in Black with its second and third words moved sh columns left (first word gap 3 - sh)"""
        g = copy.deepcopy(built)
        start = runs(ink_cols(built[79]))[3][0]
        for y in range(8):
            r = g[79][y]
            for x in range(start, C1):
                if r[x] == TEXT:
                    r[x] = P.FILL
            for x in range(start, C1):
                if built[79][y][x] == TEXT:
                    r[x - sh] = TEXT
        return g

    cases = [
        ('Stand Owner pushed 2 px right (overruns the border)', shifted(84, 2), 'border'),
        ("Man in Black pushed 3 px left (margin below the fan's, off-centre)", shifted(79, -3), 'margin'),
        ('Hart pushed 4 px right (margins differ)', shifted(41, 4), 'differ'),
        ('Wang with the gap after its first letter filled (letters touch)', join_letters(43), 'letters'),
        ('Edgeworth (untouched) with one pixel changed', pixel(27, 3, 60, 6 if built[27][3][60] == TEXT else TEXT), 'untouched'),
        ('Excelsius with a non-text pixel changed', pixel(63, 7, 50, 1), 'outside what a redraw'),
        ('Man in Black with its first word gap closed from 3 to 1', closed(2), 'word gap'),
        ('Man in Black with word gaps 2 and 2 (the reported defect)', closed(1), 'do not match the listed'),
    ]
    for label, grids_, key in cases:
        bad, _ = check(grids_, fan, fmin, fdiff)
        if not any(key in b for b in bad):
            raise SystemExit('selftest FAILED: %s was not caught (%s)' % (label, bad[:2]))
        print('  caught  %-70s %s' % (label, [b for b in bad if key in b][0][:90]))
    saved = dict(P.THIN_EXCEPTIONS)
    try:
        P.THIN_EXCEPTIONS[27] = ([2], 'bogus')
        bad, _ = check(built, fan, fmin, fdiff)
        if not any('not redrawn' in b for b in bad):
            raise SystemExit('selftest FAILED: a bogus exception was accepted')
        print('  caught  %-70s %s' % ('THIN_EXCEPTIONS naming an untouched plate', [b for b in bad if 'not redrawn' in b][0][:90]))
        P.THIN_EXCEPTIONS.clear(); P.THIN_EXCEPTIONS[74] = ([], 'bogus')
        bad, _ = check(built, fan, fmin, fdiff)
        if not any('listed in THIN_EXCEPTIONS' in b for b in bad):
            raise SystemExit('selftest FAILED: a stale exception was accepted')
        print('  caught  %-70s %s' % ('a stale exception (Cameraman has no word gap)', [b for b in bad if 'THIN_EXC' in b][0][:90]))
        P.THIN_EXCEPTIONS.clear()
        bad, _ = check(built, fan, fmin, fdiff)
        if not any('no exception' in b for b in bad):
            raise SystemExit('selftest FAILED: removing the exceptions was not caught')
        print('  caught  %-70s %s' % ('exceptions removed (word gap 2 without a listing)', [b for b in bad if 'no exception' in b][0][:90]))
    finally:
        P.THIN_EXCEPTIONS.clear(); P.THIN_EXCEPTIONS.update(saved)
    print('selftest passed: every broken plate was caught')


def main(argv):
    st = '--selftest' in argv
    argv = [a for a in argv if a != '--selftest']
    built_path = argv[0] if argv else _default_built()
    fan_path = argv[1] if len(argv) > 1 else _default_fan()
    built, fan = load(built_path), load(fan_path)
    fmin, fdiff = measure(fan)
    print('fan untouched plates: smallest margin %d, largest left/right difference %d' % (fmin, fdiff))
    bad, lines = check(built, fan, fmin, fdiff)
    for ln in lines:
        print(ln)
    print('word gap limit %d, exceptions: %s' % (P.WORD_GAP, ', '.join('%d (gaps %s: %s)' % (k, v[0], v[1]) for k, v in sorted(P.THIN_EXCEPTIONS.items())) or 'none'))
    if st:
        selftest(built, fan)
    if bad:
        print('\n%d FAILURE(S):' % len(bad))
        for b in bad:
            print('  ' + b)
        return 1
    print('\nnameplate audit passed: %d plates, %d redrawn' % (LAST - FIRST + 1, len(P.PLATES)))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
