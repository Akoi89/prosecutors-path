# -*- coding: utf-8 -*-
"""Swap the fan translation's AAI2 episode names for the official Collection ones.

All 27 title strings live in DS[460] (strings 24-93) of jpn/spt.bin - nowhere else in
the ROM. Each is two lines: the episode name, then a part subtitle padded with U+FF3F
to centre it under the name. The official names come from the Collection's
localization-string-tables-english(en) bundle, which is where the Collection keeps
its episode list (the DS-era `detailMsg`/title files never got them).
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from spt import all_strings, parse
from build_spt import build_ds
from dstext import _w, SPACE

OFFICIAL = {
    'Turnabout Target':         'Turnabout Trigger',
    'The Imprisoned Turnabout': 'The Captive Turnabout',
    'The Inherited Turnabout':  'Turnabout Legacy',
    'The Forgotten Turnabout':  'A Turnabout Forsaken',
    'The Grand Turnabout':      'Turnabout for the Ages',
}

def _fw(s):
    return [0xFF3F if c == ' ' else (ord(c) - 0x21 + 0xFF01 if 0x21 <= ord(c) <= 0x7E else ord(c))
            for c in s]

def _plain(units):
    out = []
    for v in units:
        if v == SPACE: out.append(' ')          # must precede the fullwidth range
        elif 0xFF01 <= v <= 0xFF5E: out.append(chr(v - 0xFF01 + 0x21))
        elif v == 0x0A: out.append('\n')
        elif 0xE000 <= v <= 0xF8FF: pass
        elif v >= 0x20: out.append(chr(v))
    return ''.join(out)

def retitle(entry):
    """Rewrite the episode names in a DS[460] entry. Returns (bytes, count)."""
    L = list(all_strings(entry, True))
    h = parse(entry, True)[0]
    changed = 0
    new = []
    for idx, (_, a, _, u) in enumerate(L):
        txt = _plain(u)
        hit = next((f for f in OFFICIAL if txt.startswith(f + '\n') or txt == f), None)
        if not hit:
            new.append((a, u)); continue
        official = OFFICIAL[hit]
        tail = u[len(_fw(hit)):]                     # newline + padded subtitle + codes
        # re-centre the subtitle under the new, differently sized name
        sub = [v for v in tail if v != SPACE or True]
        nl = tail.index(0x0A) if 0x0A in tail else None
        if nl is not None:
            rest = tail[nl+1:]
            k = 0
            while k < len(rest) and rest[k] == SPACE: k += 1
            body = rest[k:]
            w_name = sum(_w(chr(v)) for v in _fw(official))
            w_body = sum(_w(chr(v)) for v in body if not (0xE000 <= v <= 0xF8FF))
            pad = max(0, round((w_name - w_body) / 2 / _w(chr(SPACE))))
            tail = tail[:nl+1] + [SPACE] * pad + body
        new.append((a, _fw(official) + tail))
        changed += 1
    if not changed:
        return entry, 0
    return build_ds(new[0][1], new[1:], h['term'], h['scale'], h['last']), changed
