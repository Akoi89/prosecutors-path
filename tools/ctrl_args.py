# -*- coding: utf-8 -*-
"""Derive control-code argument counts from the English corpus.

Every control code (0xE000-0xF8FF) consumes a fixed number of following units as
arguments - portrait ids, speaker ids, timings, sentinels. Those must pass through
the converter untouched; treating them as text corrupts the script.

The arity is recovered statistically. For each code, look at how many non-control
units follow it before the next control code, across every occurrence, and take the
MINIMUM. A code that always takes 2 arguments can be followed by 2, or by 2 plus a
run of dialogue - but never by fewer than 2. (min == p01 == p05 for every code,
which is exactly what a fixed arity looks like.)

That alone over-estimates. A code with arity 0 sitting mid-sentence is always
followed by several letters, so its minimum run is large: {E04C} came out as 9 and
{E04D} as 20, and both swallowed whole words ("Find out{E04C}whether t he
investigation"). The correction: if a code is followed by a LETTER in more than 85%
of its occurrences, it is inline markup, not a command - force arity 0. Arguments
are small binary values and essentially never letters.

The 85% test needs a population to be meaningful. {E255} occurs 3 times, all
followed by a letter, but its minimum run is 5 - a genuine arity. Codes with fewer
than 5 occurrences keep their measured minimum.

One more correction, learned the hard way: an argument whose fixed VALUE happens
to be an ASCII letter looks exactly like inline markup to the letter test. {E1E2}
is always followed by 68 - the letter 'D' - so the test forced it to arity 0, the
converter turned that 68 into a fullwidth D, and the engine hung on the corrupted
argument (v1.3.2's Little Thief hang). Prose after a real inline code VARIES;
a constant first unit is an argument. So the letter test is overridden when one
single value accounts for nearly every following unit.

    python tools/ctrl_args.py --check          compare against the shipped table
    python tools/ctrl_args.py -o out.json      write a freshly derived table

Needs dump/eng and dump/eng_trial (see BUILDING.md).
"""
import sys, os, glob, json, argparse, collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from spt import all_strings
from paths import data, work

CTRL = lambda v: 0xE000 <= v <= 0xF8FF
LETTER = lambda v: 0x41 <= v <= 0x5A or 0x61 <= v <= 0x7A
INLINE_RATIO = 0.85       # followed by a letter this often -> inline markup, arity 0
MIN_SUPPORT = 5           # ...but only when there are enough occurrences to judge
CONST_RATIO = 0.99        # one constant following value this often -> argument, not prose


def derive(folders):
    runs = collections.defaultdict(list)
    letters, total = collections.Counter(), collections.Counter()
    following = collections.defaultdict(collections.Counter)
    for folder in folders:
        for p in sorted(glob.glob(os.path.join(folder, '*.bin'))):
            try:
                strings = list(all_strings(open(p, 'rb').read(), False))
            except Exception:
                continue
            for _, _, _, u in strings:
                n = len(u)
                for k, v in enumerate(u):
                    if not CTRL(v):
                        continue
                    j = k + 1
                    while j < n and not CTRL(u[j]):
                        j += 1
                    runs[v].append(j - k - 1)
                    total[v] += 1
                    if k + 1 < n and LETTER(u[k + 1]):
                        letters[v] += 1
                    if k + 1 < n:
                        following[v][u[k + 1]] += 1
    out = {}
    for c, rs in runs.items():
        a = min(rs)
        if total[c] >= MIN_SUPPORT and letters[c] / total[c] > INLINE_RATIO:
            # constant following value = a fixed argument, not prose ({E1E2}'s
            # first argument is 68, the letter 'D' - see the docstring)
            top = following[c].most_common(1)
            const = top and top[0][1] / sum(following[c].values()) >= CONST_RATIO
            if not const:
                a = 0
        out['%04X' % c] = a
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(prog='ctrl_args')
    ap.add_argument('--check', action='store_true',
                    help='compare a fresh derivation against the shipped table')
    ap.add_argument('-o', '--out', help='write the derived table here')
    a = ap.parse_args(argv)
    os.chdir(work())
    folders = ['dump/eng', 'dump/eng_trial']
    for f in folders:
        if not os.path.isdir(f):
            raise SystemExit('%s not found - see BUILDING.md for how to extract it' % f)
    fresh = derive(folders)
    if a.out:
        json.dump(fresh, open(a.out, 'w'), indent=1, sort_keys=True)
        print('%d codes -> %s' % (len(fresh), a.out))
    if a.check or not a.out:
        ship = {k.upper(): v for k, v in json.load(open(data('ctrl_args.json'))).items()}
        common = sorted(set(fresh) & set(ship))
        diff = [k for k in common if fresh[k] != ship[k]]
        extra = sorted(k for k in set(fresh) - set(ship) if fresh[k])
        print('shipped %d codes, derived %d, %d in common' % (len(ship), len(fresh), len(common)))
        print('disagreements on shared codes: %d %s'
              % (len(diff), ['%s %d->%d' % (k, ship[k], fresh[k]) for k in diff[:8]]))
        print('codes with arguments that the shipped table omits: %d' % len(extra))
        if extra:
            print('  ' + ', '.join('%s:%d' % (k, fresh[k]) for k in extra))
            print('  These are a KNOWN GAP - see BUILDING.md. Adding them changes the')
            print('  built ROM, so the shipped table stays frozen at the tested state.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
