# -*- coding: utf-8 -*-
"""Condense a handful of official evidence descriptions to fit the DS box.

Only descriptions whose FAN wording factually contradicts the official dialogue
are touched (the Ep2 autopsy cluster: the rebuttal cites a stab wound while the
fan description says 'single blow'). Everything else that overflows keeps the
fan's wording - see the README's 'what doesn't port' section for why wholesale
condensing was rejected.

This table contains NO game text. Each entry is keyed by a hash of the
description's Japanese source, and holds word-index edit operations (deletions
and a few generic English substitutions) applied to the OFFICIAL text the user
extracts from their own Collection - plus a hash of the expected result, so a
Collection with different wording falls back to the fan line instead of
applying stale edits.
"""
import hashlib

CONDENSE = {
    # Knightley's body, autopsy v1 (Ep2)
    'ee54df8a876bed8f': {
        'ops': [['sub', 9, 12, ['was']], ['sub', 13, 17, ['A']], ['del', 23, 26]],
        'want': 'fddff143f30504be',
    },
    # autopsy v2: body moved, covered in dirt
    '998d10737b0eff91': {
        'ops': [['sub', 9, 13, ['Covered']], ['sub', 15, 19, ['A']],
                ['del', 25, 28], ['sub', 29, 33, ['blow.']]],
        'want': '77f8dc8d5dd2224a',
    },
    # autopsy v3: the sweet scent
    '79178f54434b23a8': {
        'ops': [['sub', 9, 13, ['A']], ['del', 19, 22], ['sub', 29, 33, ['scent.']]],
        'want': '7d8e3e92de833986',
    },
}


def key(norm_ja):
    return hashlib.sha1(norm_ja.encode('utf-8')).hexdigest()[:16]


def apply(norm_ja, eng):
    """Return the condensed official text for this row, or None to leave it alone."""
    e = CONDENSE.get(key(norm_ja))
    if not e:
        return None
    w = eng.replace('\n', ' ').split()
    off = 0
    for op in e['ops']:
        if op[0] == 'del':
            a, b = op[1], op[2]
            w[a + off:b + off] = []
            off -= (b - a)
        elif op[0] == 'sub':
            a, b = op[1], op[2]
            w[a + off:b + off] = op[3]
            off += len(op[3]) - (b - a)
        else:
            a = op[1]
            w[a + off:a + off] = op[2]
            off += len(op[2])
    out = ' '.join(w)
    want = e['want']
    if want and hashlib.sha1(out.encode('utf-8')).hexdigest()[:16] != want:
        return None          # the Collection's wording differs - do not touch
    return out
