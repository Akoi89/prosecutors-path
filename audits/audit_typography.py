# -*- coding: utf-8 -*-
"""Typographic anomalies in the dialogue, compared against an older build.

    python audits/audit_typography.py [NEW.nds] [OLD.nds]
    python audits/audit_typography.py --selftest

Every other check in here measures WIDTH. None of them can see a spurious space,
an empty bracket, or a line that opens with a comma, because none of those make a
line too wide. That is exactly how v1.9.0's development build came to put a space
after 144 re-opened brackets ("( but maybe" instead of "(but maybe") and survive a
full review: the text was the wrong shape, not the wrong size.

It is COMPARATIVE on purpose. Several of these quirks exist in the fan patch and
in every release we have made, so an absolute count means nothing; what matters is
whether a class got WORSE than the build you are comparing to. Exit code is 1 only
if something did.

--selftest feeds it eight deliberately broken strings and checks it catches each,
the same discipline as audits/audit_fixtures.py. An instrument that reports zero is
worthless until you have watched it report something.
"""
import os as _os
import sys as _sys

_REPO = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
_sys.path.insert(0, _os.path.join(_REPO, 'tools'))

import struct, json, collections

from inject import file_id
from spt import all_strings
from dstext import RESET

CTRL = lambda v: 0xE000 <= v <= 0xF8FF
SPEAKER = 0xE101
SPACE, PAREN_OPEN, PAREN_CLOSE = 0xFF3F, 0xFF08, 0xFF09
# fullwidth . , ! ? ; : and the closing bracket
TIGHT = {0xFF0E, 0xFF0C, 0xFF01, 0xFF1F, 0xFF1B, 0xFF1A, 0xFF09}
ARGS = {int(k, 16): v for k, v in
        json.load(open(_os.path.join(_REPO, 'dump', 'ctrl_args.json'))).items()}


def boxes(u):
    """[[line, line, ...], ...] of visible units, control codes and their args gone."""
    out, box, line, i, n = [], [], [], 0, len(u)
    while i < n:
        v = u[i]
        if CTRL(v):
            i += 1
            for _ in range(ARGS.get(v, 0)):
                if i < n and not CTRL(u[i]):
                    i += 1
            if v in RESET:
                box.append(line); out.append(box); box, line = [], []
            continue
        if v == 0x0A:
            box.append(line); line = []; i += 1; continue
        if v == 0:
            i += 1; continue
        line.append(v); i += 1
    box.append(line); out.append(box)
    return [b for b in out if any(b)]


def anomalies(u):
    """Set of anomaly names present in one string."""
    found = set()
    for box in boxes(u):
        for li, line in enumerate(box):
            if not line:
                if 0 < li < len(box) - 1 and box[li - 1] and box[li + 1]:
                    found.add('empty line between two full ones')
                continue
            if line[0] == SPACE:
                found.add('line starts with a space')
            if line[-1] == SPACE:
                found.add('line ends with a space')
            if line[0] in TIGHT:
                found.add('line starts with punctuation')
            for j in range(len(line) - 1):
                a, b = line[j], line[j + 1]
                if a == SPACE and b == SPACE:
                    found.add('double space')
                if a == SPACE and b in TIGHT:
                    found.add('space before punctuation')
                if a == PAREN_OPEN and b == SPACE:
                    found.add('space after an open bracket')
                if a == PAREN_OPEN and b == PAREN_CLOSE:
                    found.add('empty brackets')
    return found


def scan(path):
    rom = open(path, 'rb').read()
    fat = struct.unpack_from('<I', rom, 0x48)[0]
    s, e = struct.unpack_from('<II', rom, fat + file_id(rom, 'jpn/spt.bin') * 8)
    blob = rom[s:e]
    n = struct.unpack_from('<I', blob, 0)[0] // 8
    c = collections.Counter()
    where = collections.defaultdict(list)
    for i in range(n):
        o, sz = struct.unpack_from('<II', blob, i * 8)
        if not sz or blob[o:o + 4] != b' TPS':
            continue
        for si, _a, _l, u in all_strings(blob[o:o + sz], ds=True):
            if SPEAKER not in u:
                continue
            for k in anomalies(u):
                c[k] += 1
                if len(where[k]) < 5:
                    where[k].append((i, si))
    return c, where


def _fw(s):
    return [SPACE if ch == ' ' else ord(ch) - 0x21 + 0xFF01 for ch in s]


FIXTURES = [
    ('space after an open bracket',       [PAREN_OPEN, SPACE] + _fw('but maybe')),
    ('double space',                      _fw('a') + [SPACE, SPACE] + _fw('b')),
    ('space before punctuation',          _fw('yes') + [SPACE, 0xFF01]),
    ('line starts with a space',          [SPACE] + _fw('hello')),
    ('line ends with a space',            _fw('hello') + [SPACE]),
    ('line starts with punctuation',      [0xFF0C] + _fw('then')),
    ('empty brackets',                    [PAREN_OPEN, PAREN_CLOSE]),
    ('empty line between two full ones',  _fw('a') + [0x0A, 0x0A] + _fw('b')),
]


def selftest():
    bad = 0
    for name, units in FIXTURES:
        got = anomalies(units + [0xE102])
        ok = name in got
        print('  %-38s %s' % (name, 'DETECTED' if ok else '*** MISSED ***'))
        bad += not ok
    clean = anomalies(_fw('Just a normal line of dialogue.') + [0xE102])
    print('  %-38s %s' % ('clean control flags nothing', 'ok' if not clean else '*** %s ***' % clean))
    bad += bool(clean)
    print()
    print('selftest: %d of %d fixtures detected' % (len(FIXTURES) - bad + 0, len(FIXTURES)))
    return 1 if bad else 0


def _default(name):
    p = _os.path.join(_REPO, 'out', name)
    if not _os.path.exists(p):
        raise SystemExit('no %s in out/ - pass the ROMs as arguments' % name)
    return p


def main(argv):
    if '--selftest' in argv:
        return selftest()
    new = argv[0] if argv else _default('GK2 (Official English, DS port).nds')
    if len(argv) > 1:
        old = argv[1]
    else:
        raise SystemExit('pass the older ROM as the second argument: this check is '
                         'comparative, and an absolute count here means nothing')
    cn, wn = scan(new)
    co, _wo = scan(old)
    print('%-38s %10s %10s %9s' % ('anomaly', 'older', 'this build', 'change'))
    print('-' * 70)
    worse = []
    for k in sorted(set(co) | set(cn)):
        a, b = co[k], cn[k]
        d = b - a
        print('%-38s %10d %10d %+9d%s'
              % (k, a, b, d, '  WORSE' if d > 0 else ('  better' if d < 0 else '')))
        if d > 0:
            worse.append(k)
    print()
    if not worse:
        print('no anomaly class got worse')
        return 0
    print('REGRESSIONS:')
    for k in worse:
        print('  %s' % k)
        for ei, si in wn[k]:
            print('      entry %d str %d' % (ei, si))
    return 1


if __name__ == '__main__':
    _sys.exit(main(_sys.argv[1:]))
