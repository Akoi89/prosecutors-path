# -*- coding: utf-8 -*-
"""Test for the scream-newline rule in dstext.convert(). No ROM needed:
    python tools/test_dstext_scream.py
Runs the in-module self check, spot-checks the run-length boundary, and proves
the rule can fail (switched off, the old gap comes back)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dstext


def units(s):
    return [ord(c) for c in s]


def main():
    bad = dstext.selfcheck_scream_newlines() + dstext.selfcheck_hyphen_newlines()
    for b in bad:
        print('FAIL', b)
    # boundary: a run of 2 on one side is not a scream, 3 and 3 is
    for s, joined in (('AAA\nAAA', True), ('AA\nAAA', False), ('AAA\nAA', False), ('aaa\nAAA', True)):
        out, _ = dstext.convert(units(s))
        got = dstext.SPACE not in out
        print('%-10r joined=%s expected=%s' % (s, got, joined))
        if got != joined:
            bad.append('boundary %r' % s)
    dstext.SCREAM_NL_FIX = False
    try:
        off, _ = dstext.convert(units('AAAAAAAA\nAAAAAAAA'))
    finally:
        dstext.SCREAM_NL_FIX = True
    on, _ = dstext.convert(units('AAAAAAAA\nAAAAAAAA'))
    if off == on:
        bad.append('switching the rule off changed nothing')
    print('all passed' if not bad else 'FAILED: %s' % bad)
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
