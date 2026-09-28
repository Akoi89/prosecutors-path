# -*- coding: utf-8 -*-
"""Split script rows that are too long for the field engine's script buffer.

The field engine (overlay 7) loads the script entry for the current map or
scene into one of five FIXED 0x2000-byte buffers. It reads
    0xC + ncnt * 8 + 2 * (longest_row + 1)
bytes into that buffer and never compares the size with 0x2000. An entry that
needs more than that writes past the end of its buffer. For the NPC and check
scripts (slot 3) the overrun lands on the free-list header the teardown later
trusts, which is the Case 4 freeze after talking to Lotta: entry 230 row 82,
the auction conversation, made that entry need 0x2400 bytes. Chapter scene
scripts (slot 4) spill into the arena behind the last buffer instead, which is
why they got away with it so far. Splitting a long row costs nothing but one
more row, so this build enforces one rule for every field-slot entry: it needs
at most 0x2000 bytes. Capcom's words are never cut or condensed.

HOW A ROW IS SPLIT. {E081:n} is a plain jump to string n of the SAME entry.
It changes only the interpreter's row index and read position; box state,
nameplate, pacing, actors and script variables stay as they are. A long row is
therefore cut at a box boundary, the first piece is ended with {E081:new}, and
the rest is appended to the end of the entry as a new row. The row keeps its
own index (so every {E081}, {E091}, {E187} and map record that points at it
stays valid) and no existing index shifts. Where the cut may fall: just after an
{E102} (wait for a button, close the box) whose next code is {E100} or {E101}
(an explicit box opener). That is the shape of the fan's own row boundaries, and
it can never land inside a construct (a choice, a testimony setup, an actor
load), because none of those has an {E102} inside it. The continuation is the
verbatim remainder of the original row, its original ending ({E081}, {E185} or
nothing) and its terminator-slot tail included, with no prologue.

READ MARKS. Each row has a 32-bit "already read" base in the row table (the A
field of the NEXT record; the trailer holds the last row's). A box uses
mark + a per-row box counter. A continuation gets mark(original row) plus the
count of {E102}, {E104} and {E185} in the part before its cut, which is exactly
the id its boxes use today. ffffffff (untracked) stays ffffffff.

WHERE IT RUNS. Last, after every per-index pass in inject.py (region_align,
_restore_index_args, recut, the positional {E081} rewrite, keep/tails,
skipguard, sentence_breaks). Those passes walk min(len(fan), len(ours)) rows or
need equal row counts, so appended rows must not exist until they are done.
Audits that compare rows to the fan per index must ignore indices at or past the
fan's row count, or read the manifest this module writes.

THE HEADER HINT. inject.py normally passes the fan's header "longest" as
min_longest so the read size never drops below the fan's. For a split entry
that would keep the read oversized, so the rebuild passes 0 and build_ds writes
the true longest row.

Every check here raises an exception (so it also runs under python -O), and a final whole-archive check fails
the build if any field-slot entry still needs more than 0x2000 bytes.
"""
import math
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from spt import all_strings, parse, tails as _spt_tails
from build_spt import build_ds
import dstext

SLOT_BUF = 0x2000
CHAIN = 0xE081
CLOSE = 0xE102
OPENERS = (0xE100, 0xE101)
MARK_CODES = (0xE102, 0xE104, 0xE185)
UNTRACKED = 0xFFFFFFFF
# Collection-only codes: dstext converts or drops them, so a built row must not
# hold one (their arity here would differ from the DS engine's, which is 0).
COLLECTION_ONLY = (0xE2A0, 0xE2B0)

# The DS engine's own argument counts (arm9 table at 0x0205f67c) are what the
# cut-point walk must use. ctrl_args.json (dstext.ARGS) already equals that
# table for every code it lists, but omits these 46 codes, and it lists the two
# Collection-only codes above with arities the DS engine does not have. So the
# table used here is dstext.ARGS, minus those two, plus these.
_ARM9_ONLY = {
    0xE090: 2, 0xE0A0: 1, 0xE0A1: 1, 0xE0A2: 1, 0xE0A3: 1, 0xE0A4: 1, 0xE0A5: 1, 0xE0A6: 1,
    0xE0A7: 1, 0xE0A8: 1, 0xE0A9: 1, 0xE0AA: 1, 0xE0AB: 1, 0xE0AC: 1, 0xE0AD: 1, 0xE0AE: 1,
    0xE0AF: 1, 0xE0B1: 2, 0xE136: 4, 0xE138: 4, 0xE139: 2, 0xE170: 4, 0xE18A: 3, 0xE18C: 2,
    0xE18E: 2, 0xE1A4: 1, 0xE1B4: 5, 0xE1B5: 5, 0xE1B6: 1, 0xE1BF: 3, 0xE1C7: 5, 0xE1C8: 3,
    0xE1E1: 3, 0xE223: 1, 0xE237: 3, 0xE238: 4, 0xE239: 5, 0xE23A: 6, 0xE23B: 7, 0xE23C: 8,
    0xE258: 3, 0xE259: 4, 0xE25C: 6, 0xE266: 1, 0xE2C4: 8, 0xE2C5: 5,
}
ARITY = {k: v for k, v in dstext.ARGS.items() if k not in COLLECTION_ONLY}
ARITY.update(_ARM9_ONLY)

# Argument positions of codes that take an id which is NOT a string of this
# entry (bank rows, strip ids); the bounds check below leaves them alone.
# Mirrors the notes in inject.INDEX_ARGS.
NOT_THIS_ENTRY = {0xE187: (0,), 0xE200: (1,), 0xE1FD: (1,), 0xE20A: (1,)}


class RowSplitError(ValueError):
    pass


def slot_kind(entry_id, mapping):
    """'slot3' (map npc/check script), 'slot4' (chapter scene) or 'other', from
    the DS-to-Collection map's entry names, the same test the size scanner uses."""
    v = mapping.get(str(entry_id)) or {}
    n = v.get('name') or ''
    if '_m' in n and ('_npc' in n or '_check' in n):
        return 'slot3'
    if n.startswith('sce') and '_c' in n:
        return 'slot4'
    return 'other'


def need_of(ent):
    """Bytes the engine reads for this entry, from the BUILT header
    (ncnt at 6, longest at 8), or None when it is not an SPT."""
    if not ent or ent[:4] != b' TPS':
        return None
    return (0xC + struct.unpack_from('<H', ent, 6)[0] * 8
            + 2 * (struct.unpack_from('<H', ent, 8)[0] + 1))


def _codes(u):
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


def _cutpoints(u):
    cs = _codes(u)
    return [p + 1 for k, (p, c, _a) in enumerate(cs)
            if c == CLOSE and k + 1 < len(cs) and cs[k + 1][1] in OPENERS]


def _marks_of(ent, ncnt):
    return [struct.unpack_from('<I', ent, 0x10 + 8 * r)[0] for r in range(ncnt)]


def _pick(u, cps, parts):
    """parts-1 legal cut points nearest to k*len/parts; None if not enough."""
    L = len(u)
    chosen = []
    for k in range(1, parts):
        cand = [c for c in cps if c not in chosen]
        if not cand:
            return None
        want = round(L * k / parts)
        chosen.append(min(cand, key=lambda x: abs(x - want)))
    return sorted(chosen)


def _pieces(u, chosen):
    ps, pos = [], 0
    for c in chosen:
        ps.append(u[pos:c] + [CHAIN, -1])
        pos = c
    ps.append(u[pos:])
    return ps


def _plan_rows(entry_id, rows, ncnt):
    """{row: (chosen cut offsets, pieces)} so that every piece fits the buffer.
    The budget shrinks by 4 units for every row added, so it is iterated."""
    added = 0
    plan = {}
    for _ in range(50):
        budget = (SLOT_BUF - (0xC + (ncnt + added) * 8)) // 2 - 1
        over = [r for r in range(ncnt) if len(rows[r]) > budget and r not in plan]
        bad = [r for r, (_c, ps) in plan.items() if max(len(p) for p in ps) > budget]
        if not over and not bad:
            return plan
        for r in over + bad:
            u = rows[r]
            L = len(u)
            parts = math.ceil((L + 2) / budget)
            cps = _cutpoints(u)
            chosen = _pick(u, cps, parts)
            if chosen is None:
                raise RowSplitError('entry %d row %d: not enough legal cut points (%d needed, %d available)'
                                    % (entry_id, r, parts - 1, len(cps)))
            ps = _pieces(u, chosen)
            if max(len(p) for p in ps) > budget:
                parts += 1
                chosen = _pick(u, cps, parts)
                if chosen is None:
                    raise RowSplitError('entry %d row %d: not enough legal cut points' % (entry_id, r))
                ps = _pieces(u, chosen)
                if max(len(p) for p in ps) > budget:
                    raise RowSplitError('entry %d row %d: %d units cannot be cut under %d with the legal cut points'
                                        % (entry_id, r, L, budget))
            if r in plan:
                added -= len(plan[r][1]) - 1
            plan[r] = (chosen, ps)
            added += len(ps) - 1
    raise RowSplitError('entry %d: the split plan did not converge' % entry_id)


def _check_index_bounds(entry_id, rows, ncnt, index_args):
    for r, u in enumerate(rows):
        for p, c, a in _codes(u):
            if c == CHAIN:
                if len(a) != 1 or a[0] >= ncnt:
                    raise RowSplitError('entry %d row %d: {E081} target %s outside %d rows'
                                        % (entry_id, r, a, ncnt))
            if index_args and c in index_args:
                skip = NOT_THIS_ENTRY.get(c, ())
                for pos in index_args[c]:
                    if pos in skip or pos >= len(a):
                        continue
                    if a[pos] >= ncnt:
                        raise RowSplitError('entry %d row %d: {%04X} argument %d is %d, outside %d rows'
                                            % (entry_id, r, c, pos, a[pos], ncnt))


def patch_entry(entry_id, entry_bytes, index_args=None):
    """Split every row of this entry that makes it need more than 0x2000 bytes.

    Returns (new_bytes, manifest). Untouched (same bytes object, empty
    manifest) when the entry already fits. manifest is one dict per appended
    row: entry, row (the original row), piece (1 for the first continuation),
    cut_unit (offset in the ORIGINAL row where the continuation begins),
    new_index, mark (hex), units. Raises RowSplitError on anything unexpected."""
    if need_of(entry_bytes) is None or need_of(entry_bytes) <= SLOT_BUF:
        return entry_bytes, []
    h = parse(entry_bytes, True)[0]
    if h['ver'] != 0x0100 or h['mark'] != 0x55AA:
        raise RowSplitError('entry %d: unexpected SPT header (version %#x, key %#x)'
                            % (entry_id, h['ver'], h['mark']))
    S = list(all_strings(entry_bytes, True))
    rows = [list(t[3]) for t in S]
    ncnt = len(rows)
    if ncnt != h['ncnt']:
        raise RowSplitError('entry %d: row count %d does not match the header %d' % (entry_id, ncnt, h['ncnt']))
    for r, u in enumerate(rows):
        if any(c in COLLECTION_ONLY for _p, c, _a in _codes(u)):
            raise RowSplitError('entry %d row %d: Collection-only control code in a built row' % (entry_id, r))
    tails = _spt_tails(entry_bytes, True)
    marks = _marks_of(entry_bytes, ncnt)          # marks[r] is row r's base; marks[-1] is the trailer

    plan = _plan_rows(entry_id, rows, ncnt)
    if not plan:
        raise RowSplitError('entry %d needs %#x bytes but no row is over budget (header hint only)'
                            % (entry_id, need_of(entry_bytes)))

    # indices: a row keeps its own; continuations take ncnt, ncnt+1, ... in row order
    new_units, new_marks, appended, manifest = list(rows), list(marks), [], []
    nxt = ncnt
    for r in sorted(plan):
        chosen, ps = plan[r]
        ids = [r] + list(range(nxt, nxt + len(ps) - 1))
        nxt += len(ps) - 1
        boxes = 0
        for k, p in enumerate(ps):
            last = k == len(ps) - 1
            if not last:
                p[-1] = ids[k + 1]
            if k:
                if marks[r] == UNTRACKED:
                    m = UNTRACKED
                else:
                    m = marks[r] + boxes
                    if (m >> 24) != (marks[r] >> 24):
                        raise RowSplitError('entry %d row %d: read mark overflows its bitmap' % (entry_id, r))
                appended.append((ids[k], p, m, r, tails[r] if last else None))
                manifest.append(dict(entry=entry_id, row=r, piece=k, cut_unit=chosen[k - 1],
                                     new_index=ids[k], mark='%08x' % m, units=len(p)))
            body = p if last else p[:-2]
            boxes += sum(1 for _q, c, _a in _codes(body) if c in MARK_CODES)
        new_units[r] = ps[0]
    appended.sort(key=lambda t: t[0])
    if [t[0] for t in appended] != list(range(ncnt, ncnt + len(appended))):
        raise RowSplitError('entry %d: appended row indices are not contiguous' % entry_id)

    # records: existing rows keep their A field (the mark of the row before them);
    # an appended row's A is the mark of the row before it, the trailer becomes
    # the mark of the last appended row.
    for idx, _p, m, _r, _t in appended:
        new_marks.append(m)
    recs = [(S[i][1], new_units[i]) for i in range(1, ncnt)]
    for idx, p, _m, _r, _t in appended:
        recs.append((new_marks[idx - 1], p))
    trailer = new_marks[-1]
    keep = [t if t != [0] else None for t in tails]
    for r in plan:
        keep[r] = None
    keep += [t if t is not None and t != [0] else None for *_x, t in appended]
    out = build_ds(new_units[0], recs, trailer, h['scale'], 0, keep)
    _verify(entry_id, out, rows, [t[1] for t in S], tails, marks, plan, appended, index_args)
    return out, manifest


def _verify(entry_id, new, rows, a_old, tails, marks, plan, appended, index_args):
    """Re-read the built entry and prove the split against the source entry."""
    ncnt = len(rows)
    new_ncnt = ncnt + len(appended)
    nh = parse(new, True)[0]
    N = list(all_strings(new, True))
    if nh['ncnt'] != new_ncnt or len(N) != new_ncnt:
        raise RowSplitError('entry %d: rebuilt entry has %d rows, expected %d' % (entry_id, len(N), new_ncnt))
    nrows = [list(t[3]) for t in N]
    ntails = _spt_tails(new, True)
    nmarks = _marks_of(new, new_ncnt)
    if nmarks[:ncnt] != marks or [t[1] for t in N[:ncnt]] != a_old:
        raise RowSplitError('entry %d: an existing row mark changed' % entry_id)
    by_index = {t[0]: t for t in appended}
    for r in range(ncnt):
        if r not in plan:
            if nrows[r] != rows[r] or ntails[r] != tails[r]:
                raise RowSplitError('entry %d row %d: a row that is not split changed' % (entry_id, r))
            continue
        chosen, ps = plan[r]
        u = rows[r]
        # (a) the pieces without their added {E081} tails, joined, are the original row
        # (c) each chain target is the continuation appended for this row
        joined, idx = [], r
        for k in range(len(ps)):
            piece = nrows[idx]
            if k < len(ps) - 1:
                if len(piece) < 2 or piece[-2] != CHAIN:
                    raise RowSplitError('entry %d row %d: piece %d does not end in a chain' % (entry_id, r, k))
                idx = piece[-1]
                piece = piece[:-2]
                if idx not in by_index or by_index[idx][3] != r:
                    raise RowSplitError('entry %d row %d: chain target %d is not a continuation of it'
                                        % (entry_id, r, idx))
            joined += piece
        if joined != u:
            raise RowSplitError('entry %d row %d: pieces do not join back to the original row' % (entry_id, r))
        # (b) every cut sits right after {E102} and right before {E100} or {E101}
        legal = set(_cutpoints(u))
        for c in chosen:
            if c not in legal or u[c - 1] != CLOSE or u[c] not in OPENERS:
                raise RowSplitError('entry %d row %d: cut at unit %d is not a legal cut point' % (entry_id, r, c))
        if ntails[r] != [0]:
            raise RowSplitError('entry %d row %d: the first piece kept a terminator tail' % (entry_id, r))
    # (d) every appended row's mark is the original row's mark plus the boxes before its cut
    for idx, p, m, r, t in appended:
        if nrows[idx] != p or nmarks[idx] != m:
            raise RowSplitError('entry %d row %d: appended row %d or its mark did not round-trip' % (entry_id, r, idx))
        chosen = plan[r][0]
        k = [q[0] for q in appended if q[3] == r].index(idx)
        before = sum(1 for _q, c, _a in _codes(rows[r][:chosen[k]]) if c in MARK_CODES)
        want = UNTRACKED if marks[r] == UNTRACKED else marks[r] + before
        if nmarks[idx] != want:
            raise RowSplitError('entry %d row %d: mark of row %d is %08x, expected %08x'
                                % (entry_id, r, idx, nmarks[idx], want))
        if ntails[idx] != (t if t is not None else [0]):
            raise RowSplitError('entry %d row %d: terminator tail of row %d changed' % (entry_id, r, idx))
    if nmarks[-1] != appended[-1][2]:
        raise RowSplitError('entry %d: trailer is not the mark of the last row' % entry_id)
    _check_index_bounds(entry_id, nrows, new_ncnt, index_args)
    if need_of(new) > SLOT_BUF:
        raise RowSplitError('entry %d still needs %#x bytes after the split' % (entry_id, need_of(new)))


def split_all(entries, mapping, index_args=None):
    """Run patch_entry over every field-slot entry in `entries` (dict id -> bytes,
    edited in place), then check the whole archive. Returns (rows_added,
    entries_touched, manifest_dict {entry: [record, ...]})."""
    manifest = {}
    rows_added = 0
    for i in sorted(entries):
        if slot_kind(i, mapping) == 'other':
            continue
        new, man = patch_entry(i, entries[i], index_args)
        if man:
            entries[i] = new
            manifest[i] = man
            rows_added += len(man)
    check_all(entries, mapping)
    return rows_added, len(manifest), manifest


def check_all(entries, mapping):
    """Final gate: no field-slot entry may need more than 0x2000 bytes."""
    for i in sorted(entries):
        if slot_kind(i, mapping) == 'other':
            continue
        n = need_of(entries[i])
        if n is not None and n > SLOT_BUF:
            raise RowSplitError('field-slot entry %d needs %#x bytes, over the %#x script buffer'
                                % (i, n, SLOT_BUF))
