# -*- coding: utf-8 -*-
"""Restore the fan's field-tap switches, {E11C:n}.

{E11C:n} writes bit 0 of the flag halfword at +2 of the main game-state block:
0 switches stylus taps on field hotspots off, 1 switches them on. The bit has
exactly one reader, the per-frame tap test of the field's tappable hotspot
objects (overlay 7 0x020BC8DC); nothing in the Logic, Organizer or Save path
reads it. The Collection script does not model the flag, so the converted rows
lost 15 of the fan's 91 {E11C} commands and carry three {E11C:0} the fan never
has (entries 22, 293 and 387). Each stray {E11C:0} leaves field taps off until
the next {E11C:1}; each lost one leaves them live during a scripted scene.
This module puts the fan's set back and nothing else: the fan's tap behaviour,
no wording, no layout. Derivation and evidence: playtest/SOLVE_E11C.md.

HOW A SITE IS FIXED. E11C_SITES is a hard-coded table, one entry per
(entry, row):
  - 'guard': sha1 (first 16 hex) of the row's ordered (code, args) list as it
    stands when this pass runs. A mismatch RAISES: the row is not the one the
    table was built against, and this module never searches for another spot.
  - 'fan': the fan ROM's ordered list of {E11C} arguments for the row. After
    the edit the row's own list must equal it, or the build fails.
  - 'ins': the {E11C} commands to add, in fan order. Each names its argument
    and an anchor: (side, code, args, occurrence), the occurrence-th exact
    (code, args) in the row counted from 0, with the new command going right
    after ('after') or right before ('before') it. The anchors are fan
    neighbours that are not presentation codes (the converter re-lays those,
    so they cannot anchor anything); a row that begins with its {E11C} is
    anchored 'before' its first code, one that ends with it 'after' its last.
  - 'del': (previous code, next code) around the one port-only {E11C:0} to
    remove; each neighbour is (code, args) or None at a row edge. The row must
    hold exactly one {E11C}, with argument 0 and those neighbours.
The guard hash pins the whole code sequence, so the fan-side check that only
presentation codes stand between the neighbours is already implied.

One inserted command is two halfwords (the code and its argument) and changes
no text. The argument is a value, not a string index, so no INDEX_ARGS entry is
needed; build_ds recomputes the row's offsets and every other row's units are
untouched. Runs after skipguard and sentence_breaks (their tables key on row
content) and before rowsplit, which must stay the last pass.

Every check raises an exception (so it also runs under python -O).
"""
import hashlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from spt import all_strings, parse, tails as _spt_tails
from build_spt import build_ds
from rowsplit import ARITY

E11C = 0xE11C
EXPECT_INSERTED = 15
EXPECT_REMOVED = 3

# Anchors are written (side, code, args, occurrence).
E11C_SITES = {
    (16, 6): {
        'guard': 'f06e1cc0dc0efca0', 'fan': (0, 1),
        'ins': ((0, 'after', 0xE12E, (1, 205, 1, 8), 0),
                (1, 'after', 0xE155, (0, 3, 3), 0))},
    (16, 33): {
        'guard': '8998961cfec9f695', 'fan': (0, 1),
        'ins': ((0, 'before', 0xE080, (35,), 0),
                (1, 'after', 0xE13E, (0,), 0))},
    (16, 34): {
        'guard': '144b01f2264f1233', 'fan': (0, 1),
        'ins': ((0, 'before', 0xE080, (35,), 0),
                (1, 'after', 0xE13E, (0,), 0))},
    (22, 0): {
        'guard': '8ec2645a00f3b554', 'fan': (),
        'del': ((0xE10E, ()), (0xE172, (2, 0)))},
    (89, 1): {
        'guard': '558da36f09c1be52', 'fan': (1, 0),
        'ins': ((0, 'after', 0xE11D, (2, 1188), 0),)},
    (89, 2): {
        'guard': '870f4cc3dff12143', 'fan': (0,),
        'ins': ((0, 'before', 0xE16F, (0, 225, 230, 0), 0),)},
    (101, 5): {
        'guard': 'e27474c496597e92', 'fan': (0, 1),
        'ins': ((0, 'after', 0xE150, (2, 36), 0),)},
    (177, 5): {
        'guard': '4892e1745eeaeba5', 'fan': (1, 0, 1, 0),
        'ins': ((0, 'after', 0xE176, (3, 0), 0),)},
    (231, 48): {
        'guard': '11b0fadedee1c591', 'fan': (0, 1),
        'ins': ((0, 'after', 0xE10F, (2, 0), 0),)},
    (264, 0): {
        'guard': '49160566020f5864', 'fan': (1, 0),
        'ins': ((0, 'after', 0xE150, (7, 5), 0),)},
    (277, 1): {
        'guard': '646090a3c999f343', 'fan': (1, 0, 1),
        'ins': ((0, 'after', 0xE131, (10,), 0),)},
    (293, 9): {
        'guard': 'c40658a52b6fdf9b', 'fan': (),
        'del': (None, (0xE10D, (1, 1, 2)))},
    (310, 17): {
        'guard': '766c0cd00a222ddb', 'fan': (0, 1),
        'ins': ((0, 'before', 0xE12C, (5, 4347), 0),)},
    (310, 23): {
        'guard': '8fa8c5047440abdb', 'fan': (0, 1),
        'ins': ((0, 'after', 0xE12C, (5, 4360), 0),)},
    (387, 1): {
        'guard': 'da41bfd422edb3e5', 'fan': (),
        'del': ((0xE100, (1,)), (0xE227, ()))},
}


class E11CError(ValueError):
    pass


def _codes(u):
    """[(unit index, code, args)] using the DS engine's own argument counts."""
    out, i = [], 0
    while i < len(u):
        v = u[i]
        if 0xE000 <= v <= 0xF8FF:
            a = ARITY.get(v, 0)
            out.append((i, v, tuple(u[i + 1:i + 1 + a])))
            i += 1 + a
        else:
            i += 1
    return out


def guard_of(units):
    """sha1 (16 hex) of the ordered (code, args) list, the table's guard."""
    seq = [(c, a) for _p, c, a in _codes(units)]
    return hashlib.sha1(bytes(str(seq), 'utf-8')).hexdigest()[:16]


def _e11c_args(units):
    return tuple(a[0] if a else None for _p, c, a in _codes(units) if c == E11C)


def _find(units, code, args, occ):
    n = -1
    for p, c, a in _codes(units):
        if c == code and a == args:
            n += 1
            if n == occ:
                return p, p + 1 + len(a)
    return None


def apply(entry, row, units):
    """Return (new_units, inserted, removed) for the row's site, or
    (units, 0, 0) when the row is not a site. Raises E11CError on any
    mismatch: guard, anchor, neighbours or final list."""
    site = E11C_SITES.get((entry, row))
    if site is None:
        return units, 0, 0
    tag = '%d/%d' % (entry, row)
    u = list(units)
    if guard_of(u) != site['guard']:
        raise E11CError('%s: row does not match the E11C table (guard %s, table %s)'
                        % (tag, guard_of(u), site['guard']))
    ins = rem = 0
    for arg, side, code, args, occ in site.get('ins', ()):
        hit = _find(u, code, args, occ)
        if hit is None:
            raise E11CError('%s: anchor {%04X %s} #%d not found' % (tag, code, args, occ))
        if side == 'after':
            at = hit[1]
        elif side == 'before':
            at = hit[0]
        else:
            raise E11CError('%s: bad side %r' % (tag, side))
        u[at:at] = [E11C, arg]
        ins += 1
    if 'del' in site:
        want_prev, want_next = site['del']
        cs = _codes(u)
        idx = [k for k, (_p, c, _a) in enumerate(cs) if c == E11C]
        if len(idx) != 1 or cs[idx[0]][2] != (0,):
            raise E11CError('%s: expected exactly one {E11C:0} to remove' % tag)
        k = idx[0]
        got_prev = (cs[k - 1][1], cs[k - 1][2]) if k > 0 else None
        got_next = (cs[k + 1][1], cs[k + 1][2]) if k + 1 < len(cs) else None
        if got_prev != want_prev or got_next != want_next:
            raise E11CError('%s: {E11C:0} neighbours %r/%r, table %r/%r'
                            % (tag, got_prev, got_next, want_prev, want_next))
        p = cs[k][0]
        del u[p:p + 2]
        rem += 1
    if _e11c_args(u) != tuple(site['fan']):
        raise E11CError('%s: E11C list %r after the edit, fan %r'
                        % (tag, _e11c_args(u), tuple(site['fan'])))
    return u, ins, rem


def patch_entry(entry_id, entry_bytes):
    """Apply every E11C_SITES row of this entry. Returns (new_bytes, inserted,
    removed). Raises E11CError when the entry is missing or not an SPT, or a
    listed row is absent. Every string's tail (spt.tails) is carried over
    unchanged, as in tools/skipguard.py."""
    rows = [si for (ei, si) in E11C_SITES if ei == entry_id]
    if not rows:
        return entry_bytes, 0, 0
    if not entry_bytes or entry_bytes[:4] != b' TPS':
        raise E11CError('entry %d: not a script entry' % entry_id)
    h = parse(entry_bytes, True)[0]
    keep = _spt_tails(entry_bytes, True)
    S = list(all_strings(entry_bytes, True))
    have = {si for si, _a, _ln, _u in S}
    for si in rows:
        if si not in have:
            raise E11CError('entry %d row %d: missing' % (entry_id, si))
    ins = rem = 0
    new = []
    for si, a, _ln, u in S:
        nu, i, r = apply(entry_id, si, u) if si in rows else (u, 0, 0)
        new.append((a, list(nu)))
        ins += i
        rem += r
    if not (ins or rem):
        return entry_bytes, 0, 0
    return (build_ds(new[0][1], new[1:], h['term'], h['scale'], h['last'], tails=keep),
            ins, rem)


def check_totals(inserted, removed):
    if inserted != EXPECT_INSERTED or removed != EXPECT_REMOVED:
        raise E11CError('E11C pass did %d inserts and %d removals, table expects %d and %d'
                        % (inserted, removed, EXPECT_INSERTED, EXPECT_REMOVED))
