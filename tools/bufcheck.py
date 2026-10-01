# -*- coding: utf-8 -*-
"""Build checks against fixed-buffer overflows, computed from the BUILT bytes.

The port's data can outgrow a fixed buffer in the game without any visible
error at build time. playtest/SOLVE_buffers.md traced every loader and text
buffer in the engine; none overflows today, and checks a to e keep it that
way (f is the Logic keyword cards, g the bag model texture, h the room names). They read jpn/spt.bin, jpn/idlocal.bin,
com/cutdata.bin, jpn/logic_keyword_local.bin and jpn/modelitemlocal.bin out of the finished ROM (after
the last step that writes any of them), compare idlocal, the logic cards and the model file with the
fan's, and RAISE BufCheckError naming the entry and the
numbers. Every check raises an exception (so it also runs under python -O).

a. spt need. The field engine loads a script entry into a fixed 0x2000-byte
   buffer sized 0xC + ncnt*8 + 2*(longest+1) with no clamp. The size is taken
   from the header's "longest" hint; the row table's own longest row is
   checked the same way, so a lying hint cannot hide a long row. Entry 342 is
   byte-identical to the fan's and goes through an exact-size loader, so it
   is the one exemption.
b. text box length. The arm9 text interpreter appends every plain unit of a
   box (opener {E100}/{E101} up to {E102}/{E104}, or the end of the row) to
   the per-box buffer with no bound; the proven room is 398 units, so a box
   over 200 units is refused. The port's longest today is 110. Plain text
   that follows a close code (or starts a row) with no new opener is counted
   too, as a "loose run" between any two of the four codes; no limit is known
   for it (the fan has runs of 761 units), so it is reported in the log line,
   never failed.
c. exam rows. Entries 453-458 (the examination contexts) have 0x80-byte
   buffers, 64 units, and their rows are plain text with no box opener; a
   row over 63 plain units is refused.
d. idlocal sizes. Every idlocal entry decodes to the size the fan's does,
   except entry 25 (the Mind Chess banner, 768 -> 896 tiles), which is also
   decoded in full and must match its own size field, and its stored size
   must stay under 16 KB (9,008 bytes today; the literal-only form is 45,064
   and needs a 45 KB temporary buffer on top of its 40 KB destination).
e. cutdata slot 47. The cut-record loader appends matching records to a
   16-entry array; the slot may hold at most 16 records and 1604 decoded
   bytes (the fan's largest slot).
f. logic keyword cards. Every rewritten card keeps the fan's decoded size, declares it in both the
   table and its LZ11 header, and is stored no larger than the literal-only form (the form every
   rewritten card has had since 1.8.5; the fan's own stored sizes are smaller, and this file's
   loader sizes its buffer from the decoded size, so it is not the idlocal case); check_logic_names
   requires the six punctuation-matched slots to be rewritten. Cards 242, 244 and 246 (banners) have six 32x16 OBJs, 1536 bytes of
   tiles, but the fan's RGCN declares 1280 and stores its phrase tail after the declared
   data; the game shows those bytes. Read from the built jpn/logic_keyword_local.bin: every
   card's OBJs must lie inside the bytes the RGCN part holds, and a card whose OBJs reach
   past the declared data must have been rewritten, with a tail different from the fan's.
g. bag model texture. Entry 1 of jpn/modelitemlocal.bin (the BTX0 with texture bag_01, which
   bag_tex.py redraws) must decode to the fan's size, be stored in no more bytes than the
   fan's, and every other entry must be the fan's bytes.
h. room names. Entries 321, 324 and 327 of jpn/idlocal.bin and entry 10 of
   jpn/cutobj_local.bin (tools/room_names.py re-letters them in place) must decode to exactly
   the fan's size, their stream header must agree with the table, and each must be stored in no
   more bytes than the fan's entry; every other cutobj_local entry must be byte for byte the
   fan's.
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lz11
from spt import all_strings
from rowsplit import ARITY

SPT_LIMIT = 0x2000
SPT_EXEMPT = (342,)
BOX_LIMIT = 200
EXAM_ENTRIES = (453, 454, 455, 456, 457, 458)
EXAM_ROW_LIMIT = 63
IDLOCAL_SIZE_EXCEPTIONS = (25,)
IDLOCAL_25_STORED_MAX = 16 * 1024
CUT_SLOT = 47
CUT_MAX_RECORDS = 16
CUT_MAX_DSIZE = 1604
MODEL_ENTRY = 1
# Logic keyword slots whose Capcom name the build must draw: the six whose description differs from
# Capcom's by a comma (tools/logic_names.py ignores punctuation since 1.11.1). Cards are entries
# slot + 1 (style A) and slot + 135 (style B).
LOGIC_PUNCT_SLOTS = (40, 56, 59, 60, 117, 120)
LOGIC_PUNCT_ENTRIES = tuple(sorted([k + 1 for k in LOGIC_PUNCT_SLOTS] + [k + 135 for k in LOGIC_PUNCT_SLOTS]))
ROOM_IDLOCAL = (321, 324, 327)
ROOM_CUTOBJ = 10

OPEN = (0xE100, 0xE101)
CLOSE = (0xE102, 0xE104)


class BufCheckError(ValueError):
    pass


def _table(d):
    """(offset, size field) for every slot of an archive whose table is
    u32 offset, u32 size at the front (spt, idlocal, cutdata)."""
    if len(d) < 8:
        raise BufCheckError('archive is %d bytes, too short for a table' % len(d))
    n = struct.unpack_from('<I', d, 0)[0] // 8
    if n * 8 > len(d):
        raise BufCheckError('archive table of %d slots does not fit in %d bytes' % (n, len(d)))
    return [struct.unpack_from('<II', d, i * 8) for i in range(n)]


def spt_entries(d):
    """{entry index: bytes} for every non-empty slot of a jpn/spt.bin."""
    out = {}
    for i, (o, l) in enumerate(_table(d)):
        if l:
            if o + l > len(d):
                raise BufCheckError('spt entry %d runs past the end of the file' % i)
            out[i] = d[o:o + l]
    return out


def _is_spt(ent):
    return len(ent) >= 12 and ent[:4] == b' TPS'


def spt_need(ent):
    """(hint need, record-table need, header longest, record longest) for an
    SPT entry, all from the built bytes. need = 0xC + ncnt*8 + 2*(longest+1),
    the size the engine reads into its buffer."""
    ncnt, hint = struct.unpack_from('<HH', ent, 6)
    if 0xC + 8 * ncnt > len(ent):
        raise BufCheckError('spt row table of %d rows does not fit in %d bytes' % (ncnt, len(ent)))
    real = max(struct.unpack_from('<H', ent, 0xC + 8 * r + 2)[0] for r in range(ncnt)) if ncnt else 0
    base = 0xC + ncnt * 8
    return base + 2 * (hint + 1), base + 2 * (real + 1), hint, real


def check_spt_need(entries):
    """Check a. -> (worst entry, worst need, exempt needs {entry: need}, count)."""
    worst = (None, 0)
    exempt = {}
    count = 0
    for i in sorted(entries):
        ent = entries[i]
        if not _is_spt(ent):
            continue
        count += 1
        by_hint, by_rec, hint, real = spt_need(ent)
        need = max(by_hint, by_rec)
        if i in SPT_EXEMPT:
            exempt[i] = need
            continue
        if need > SPT_LIMIT:
            raise BufCheckError(
                'spt entry %d needs %#x bytes (header longest %d -> %#x, longest row %d -> %#x), '
                'over the %#x script buffer' % (i, need, hint, by_hint, real, by_rec, SPT_LIMIT))
        if need > worst[1]:
            worst = (i, need)
    return worst[0], worst[1], exempt, count


def _skip_code(v):
    return 0xE000 <= v <= 0xF8FF


def text_runs(u):
    """Yield (opened, units) for every run of plain text in a row, a run being
    the non-control units (control codes and their arguments excluded)
    between two of {E100}, {E101}, {E102}, {E104}, or a row edge. `opened` is
    True for a run that starts at an opener {E100}/{E101}, that is a text
    box; False for a loose run that starts at the row start or after a close
    code. Empty runs are not yielded."""
    i, opened, app = 0, False, 0
    while i < len(u):
        v = u[i]
        if _skip_code(v):
            if v in OPEN or v in CLOSE:
                if app:
                    yield opened, app
                opened, app = v in OPEN, 0
            i += 1 + ARITY.get(v, 0)
        else:
            app += 1
            i += 1
    if app:
        yield opened, app


def plain_units(u):
    """Non-control units of a row, arguments of control codes excluded."""
    i, n = 0, 0
    while i < len(u):
        v = u[i]
        if _skip_code(v):
            i += 1 + ARITY.get(v, 0)
        else:
            n += 1
            i += 1
    return n


def check_boxes(entries):
    """Check b. -> (max units in one box, (entry, row) of it, boxes counted,
    max units in one loose run, (entry, row) of it). Only boxes are limited."""
    best, where, boxes = 0, None, 0
    lbest, lwhere = 0, None
    for i in sorted(entries):
        ent = entries[i]
        if not _is_spt(ent):
            continue
        for r, _a, _ln, u in all_strings(ent, ds=True):
            for opened, app in text_runs(u):
                if not opened:
                    if app > lbest:
                        lbest, lwhere = app, (i, r)
                    continue
                boxes += 1
                if app > BOX_LIMIT:
                    raise BufCheckError('spt entry %d row %d holds a text box of %d units, over the %d limit'
                                        % (i, r, app, BOX_LIMIT))
                if app > best:
                    best, where = app, (i, r)
    return best, where, boxes, lbest, lwhere


def check_exam_rows(entries):
    """Check c. -> (max plain units in a row, (entry, row) of it)."""
    best, where = 0, None
    for i in EXAM_ENTRIES:
        ent = entries.get(i)
        if ent is None or not _is_spt(ent):
            raise BufCheckError('exam context entry %d is missing or not a script' % i)
        for r, _a, _ln, u in all_strings(ent, ds=True):
            n = plain_units(u)
            if n > EXAM_ROW_LIMIT:
                raise BufCheckError('exam entry %d row %d has %d plain units, over the %d limit'
                                    % (i, r, n, EXAM_ROW_LIMIT))
            if n > best:
                best, where = n, (i, r)
    return best, where


def _decode(b, what):
    """lz11.decompress, with a malformed stream reported as a BufCheckError."""
    try:
        return lz11.decompress(b)
    except (IndexError, ValueError) as e:
        raise BufCheckError('%s: the LZ11 stream does not decode (%s)' % (what, e))


def _stream_size(b):
    """Decoded size an LZ11 stream declares in its own header."""
    if b[:1] != b'\x11' or len(b) < 4:
        raise BufCheckError('not an LZ11 stream (starts %r)' % (b[:4],))
    n = int.from_bytes(b[1:4], 'little')
    if n == 0 and len(b) >= 8:
        n = int.from_bytes(b[4:8], 'little')
    return n


def check_idlocal(port, fan):
    """Check d. Every entry's decoded size (table size field) equals the fan's
    except IDLOCAL_SIZE_EXCEPTIONS; a compressed entry's stream header must
    agree with its table size, and an excepted entry is decoded in full.
    -> (entries compared, {entry: (fan size, port size, port stored bytes)})."""
    pt, ft = _table(port), _table(fan)
    if len(pt) != len(ft):
        raise BufCheckError('idlocal has %d entries, the fan has %d' % (len(pt), len(ft)))
    order = sorted(range(len(pt)), key=lambda k: pt[k][0])
    nxt = {k: (pt[order[j + 1]][0] if j + 1 < len(order) else len(port)) for j, k in enumerate(order)}
    changed = {}
    for i, ((po, ps), (_fo, fs)) in enumerate(zip(pt, ft)):
        psize, fsize = ps & 0x7FFFFFFF, fs & 0x7FFFFFFF
        stored = port[po:nxt[i]]
        if ps & 0x80000000 and psize:
            if _stream_size(stored) != psize:
                raise BufCheckError('idlocal entry %d: stream declares %d bytes, table says %d'
                                    % (i, _stream_size(stored), psize))
        if i in IDLOCAL_SIZE_EXCEPTIONS:
            if not ps & 0x80000000:
                raise BufCheckError('idlocal entry %d is expected to be an LZ11 stream' % i)
            got = len(_decode(stored, 'idlocal entry %d' % i))
            if got != psize:
                raise BufCheckError('idlocal entry %d decodes to %d bytes, table says %d' % (i, got, psize))
            if len(stored) >= IDLOCAL_25_STORED_MAX:
                raise BufCheckError('idlocal entry %d is stored in %d bytes, over the %d limit (literal-only '
                                    'storage?)' % (i, len(stored), IDLOCAL_25_STORED_MAX))
            changed[i] = (fsize, psize, len(stored))
            continue
        if psize != fsize:
            raise BufCheckError('idlocal entry %d decodes to %d bytes, the fan\'s to %d' % (i, psize, fsize))
    return len(pt), changed


def _extents(t, total):
    """{entry: (start, end)} of every slot of a table, each ending where the next
    one in file order begins."""
    order = sorted(range(len(t)), key=lambda k: t[k][0])
    return {k: (t[k][0], t[order[j + 1]][0] if j + 1 < len(order) else total) for j, k in enumerate(order)}


def check_model_item(built, fan):
    """Check g. jpn/modelitemlocal.bin holds the bag model's textures; entry 1 (BTX0, bag_01)
    carries the redrawn plan paper. The loader sizes its buffer from the table, so the entry
    must decode to exactly the fan's size, be stored in no more bytes than the fan's, and
    still be the same BTX0; every other entry must be byte for byte the fan's.
    -> (decoded size, stored size, fan's stored size)."""
    pt, ft = _table(built), _table(fan)
    if len(pt) != len(ft):
        raise BufCheckError('modelitemlocal has %d entries, the fan has %d' % (len(pt), len(ft)))
    if MODEL_ENTRY >= len(pt):
        raise BufCheckError('modelitemlocal has no entry %d' % MODEL_ENTRY)
    pe, fe = _extents(pt, len(built)), _extents(ft, len(fan))
    for i in range(len(pt)):
        if pt[i][1] != ft[i][1]:
            raise BufCheckError('modelitemlocal entry %d: table field %#x, the fan\'s %#x' % (i, pt[i][1], ft[i][1]))
        if i != MODEL_ENTRY and built[pe[i][0]:pe[i][1]] != fan[fe[i][0]:fe[i][1]]:
            raise BufCheckError('modelitemlocal entry %d is not the fan\'s bytes' % i)
    psize = pt[MODEL_ENTRY][1] & 0x7FFFFFFF
    if not pt[MODEL_ENTRY][1] & 0x80000000:
        raise BufCheckError('modelitemlocal entry %d is expected to be an LZ11 stream' % MODEL_ENTRY)
    stored = built[pe[MODEL_ENTRY][0]:pe[MODEL_ENTRY][1]]
    fan_stored = fe[MODEL_ENTRY][1] - fe[MODEL_ENTRY][0]
    if _stream_size(stored) != psize:
        raise BufCheckError('modelitemlocal entry %d: stream declares %d bytes, table says %d'
                            % (MODEL_ENTRY, _stream_size(stored), psize))
    blob = _decode(stored, 'modelitemlocal entry %d' % MODEL_ENTRY)
    if len(blob) != psize:
        raise BufCheckError('modelitemlocal entry %d decodes to %d bytes, table says %d'
                            % (MODEL_ENTRY, len(blob), psize))
    if blob[:4] != b'BTX0' or struct.unpack_from('<I', blob, 8)[0] != psize:
        raise BufCheckError('modelitemlocal entry %d is not a BTX0 of its own size' % MODEL_ENTRY)
    if len(stored) > fan_stored:
        raise BufCheckError('modelitemlocal entry %d is stored in %d bytes, over the fan\'s %d'
                            % (MODEL_ENTRY, len(stored), fan_stored))
    return psize, len(stored), fan_stored


def check_rooms(built_idl, fan_idl, built_co, fan_co):
    """Check h. Entries ROOM_IDLOCAL of idlocal and ROOM_CUTOBJ of cutobj_local keep the
    fan's decoded size, are real LZ11 streams that decode to it, and are stored in no more
    bytes than the fan's; the other cutobj_local entries are the fan's bytes.
    -> {('idlocal', 321): (decoded, stored, fan stored), ..., ('cutobj_local', 10): ...}."""
    out = {}
    for name, built, fan, entries in (('idlocal', built_idl, fan_idl, ROOM_IDLOCAL),
                                      ('cutobj_local', built_co, fan_co, (ROOM_CUTOBJ,))):
        pt, ft = _table(built), _table(fan)
        if len(pt) != len(ft):
            raise BufCheckError('%s has %d entries, the fan has %d' % (name, len(pt), len(ft)))
        pe, fe = _extents(pt, len(built)), _extents(ft, len(fan))
        for i in entries:
            if i >= len(pt):
                raise BufCheckError('%s has no entry %d' % (name, i))
            if pt[i][1] != ft[i][1]:
                raise BufCheckError('%s entry %d: table field %#x, the fan\'s %#x' % (name, i, pt[i][1], ft[i][1]))
            size = pt[i][1] & 0x7FFFFFFF
            if not pt[i][1] & 0x80000000:
                raise BufCheckError('%s entry %d is expected to be an LZ11 stream' % (name, i))
            stored = built[pe[i][0]:pe[i][1]]
            fan_stored = fe[i][1] - fe[i][0]
            if _stream_size(stored) != size:
                raise BufCheckError('%s entry %d: stream declares %d bytes, table says %d'
                                    % (name, i, _stream_size(stored), size))
            got = len(_decode(stored, '%s entry %d' % (name, i)))
            if got != size:
                raise BufCheckError('%s entry %d decodes to %d bytes, table says %d' % (name, i, got, size))
            if len(stored) > fan_stored:
                raise BufCheckError('%s entry %d is stored in %d bytes, over the fan\'s %d'
                                    % (name, i, len(stored), fan_stored))
            out[(name, i)] = (size, len(stored), fan_stored)
        if name == 'cutobj_local':
            for i in range(len(pt)):
                if i != ROOM_CUTOBJ and built[pe[i][0]:pe[i][1]] != fan[fe[i][0]:fe[i][1]]:
                    raise BufCheckError('cutobj_local entry %d is not the fan\'s bytes' % i)
    return out


def check_cutdata(cd):
    """Check e. -> (records, decoded size) of slot 47."""
    t = _table(cd)
    if CUT_SLOT >= len(t):
        raise BufCheckError('cutdata has %d slots, no slot %d' % (len(t), CUT_SLOT))
    o, s = t[CUT_SLOT]
    dsize = s & 0x7FFFFFFF
    live = sorted(q for q, _z in t if q > o)
    raw = cd[o:live[0] if live else len(cd)]
    blob = _decode(raw, 'cutdata slot %d' % CUT_SLOT) if s & 0x80000000 else raw[:dsize]
    if len(blob) != dsize:
        raise BufCheckError('cutdata slot %d decodes to %d bytes, table says %d' % (CUT_SLOT, len(blob), dsize))
    if len(blob) < 6:
        raise BufCheckError('cutdata slot %d is %d bytes, too short for a header' % (CUT_SLOT, len(blob)))
    records = struct.unpack_from('<H', blob, 4)[0]
    if records > CUT_MAX_RECORDS:
        raise BufCheckError('cutdata slot %d has %d records, over the %d-entry array'
                            % (CUT_SLOT, records, CUT_MAX_RECORDS))
    if dsize > CUT_MAX_DSIZE:
        raise BufCheckError('cutdata slot %d decodes to %d bytes, over the %d the fan\'s largest slot has'
                            % (CUT_SLOT, dsize, CUT_MAX_DSIZE))
    return records, dsize


def check_blobs(spt, idlocal, cutdata, fan_idlocal):
    """Run checks a-e on the three built files (bytes) and the fan's idlocal.
    Returns the one-line summary; raises BufCheckError on the first failure."""
    entries = spt_entries(spt)
    a_entry, a_need, exempt, n_spt = check_spt_need(entries)
    b_max, b_where, n_boxes, l_max, l_where = check_boxes(entries)
    c_max, c_where = check_exam_rows(entries)
    n_id, changed = check_idlocal(idlocal, fan_idlocal)
    e_rec, e_size = check_cutdata(cutdata)
    ex = ', '.join('%d at %#x' % kv for kv in sorted(exempt.items())) or 'none'
    ch = ', '.join('%d %d->%d bytes (stored %d)' % ((k,) + v) for k, v in sorted(changed.items())) or 'none'
    return ('buffer checks passed: (a) spt need max %#x of %#x at entry %d over %d entries (exempt: %s); '
            '(b) text box max %d of %d units at entry %d row %d over %d non-empty boxes '
            '(loose text runs, reported not limited: max %d at entry %d row %d); '
            '(c) exam rows max %d of %d plain units at entry %d row %d; '
            '(d) idlocal %d entries same size as the fan except %s; '
            '(e) cutdata slot %d has %d of %d records, %d of %d bytes'
            % (a_need, SPT_LIMIT, a_entry, n_spt, ex,
               b_max, BOX_LIMIT, b_where[0], b_where[1], n_boxes, l_max, l_where[0], l_where[1],
               c_max, EXAM_ROW_LIMIT, c_where[0], c_where[1],
               n_id, ch,
               CUT_SLOT, e_rec, CUT_MAX_RECORDS, e_size, CUT_MAX_DSIZE))


def check_logic_cards(built, fan):
    """Check f on the built and the fan's jpn/logic_keyword_local.bin bytes.
    Returns (cards checked, {entry: (declared, extent)} for cards whose OBJs pass the declared
    data); raises BufCheckError."""
    import logic_cards as L
    from nitro import ncgr
    from ncer import ncer
    B, F = L.table(built), L.table(fan)
    if len(B) != len(F):
        raise BufCheckError('logic_keyword_local.bin has %d entries, the fan has %d' % (len(B), len(F)))
    n, past = 0, {}
    for e, sub in enumerate(B):
        if sub[:4] != L.SUB_MAGIC:
            continue
        parts = L.sub_split(sub)
        gfx = next((p for p in parts if p[:4] == b'RGCN'), None)
        rec = next((p for p in parts if p[:4] == b'RECN'), None)
        cells = ncer(rec)[0] if rec else []
        objs = next((c for c in cells if c), None)
        if gfx is None or objs is None:
            continue
        n += 1
        tiles, bpp = ncgr(gfx)[:2]
        need = L.obj_extent(objs, bpp)
        start = 0x18 + struct.unpack_from('<I', gfx, 0x18 + 20)[0]
        held = len(gfx) - start
        if need > held:
            raise BufCheckError('logic card %d: its OBJs reach tile byte %d but the RGCN part holds only %d'
                                % (e, need, held))
        if need <= len(tiles):
            continue
        past[e] = (len(tiles), need)
        if sub == F[e]:
            continue    # the fan card kept whole: its tail is the end of its own phrase
        if F[e][:4] != L.SUB_MAGIC:
            raise BufCheckError('logic card %d has no fan card to compare its tail with' % e)
        fg = next(p for p in L.sub_split(F[e]) if p[:4] == b'RGCN')
        fs = 0x18 + struct.unpack_from('<I', fg, 0x18 + 20)[0]
        fan_tail = fg[fs + len(tiles):fs + need]
        if any(fan_tail) and gfx[start + len(tiles):start + need] == fan_tail:
            raise BufCheckError('logic card %d: bytes %d..%d, past the declared data but inside its OBJs, '
                                'are still the fan tail' % (e, len(tiles), need))
    check_logic_sizes(built, fan)
    return n, past


def _lz11_literal_bound(n):
    """Stored bytes of n decoded bytes in literal-only LZ11 (4 header, one flag byte per 8 bytes), 4-aligned."""
    return (4 + n + (n + 7) // 8 + 3) // 4 * 4


def check_logic_sizes(built, fan):
    """Every logic_keyword_local.bin card that differs from the fan's decodes to the fan's size,
    says so in the table and in its LZ11 header, and is stored in no more than the literal-only
    form needs. Raises BufCheckError; returns the number of rewritten cards."""
    import logic_cards as L
    pt, ft = _table(built), _table(fan)
    if len(pt) != len(ft):
        raise BufCheckError('logic_keyword_local.bin has %d entries, the fan has %d' % (len(pt), len(ft)))
    B, F = L.table(built), L.table(fan)
    ext = _extents(pt, len(built))
    n = 0
    for e in range(len(pt)):
        if B[e] == F[e]:
            continue
        n += 1
        if len(B[e]) != len(F[e]):
            raise BufCheckError('logic card %d decodes to %d bytes, the fan card to %d' % (e, len(B[e]), len(F[e])))
        if (pt[e][1] & 0x80000000) != (ft[e][1] & 0x80000000):
            raise BufCheckError('logic card %d is stored %s, the fan card %s'
                                % (e, 'compressed' if pt[e][1] & 0x80000000 else 'raw',
                                   'compressed' if ft[e][1] & 0x80000000 else 'raw'))
        if pt[e][1] & 0x7FFFFFFF != len(F[e]):
            raise BufCheckError('logic card %d: table size field %d, the fan card decodes to %d'
                                % (e, pt[e][1] & 0x7FFFFFFF, len(F[e])))
        stored = built[ext[e][0]:ext[e][1]]
        if pt[e][1] & 0x80000000 and _stream_size(stored) != len(F[e]):
            raise BufCheckError('logic card %d: LZ11 header declares %d bytes, the fan card decodes to %d'
                                % (e, _stream_size(stored), len(F[e])))
        if len(stored) > _lz11_literal_bound(len(F[e])):
            raise BufCheckError('logic card %d is stored in %d bytes, over the %d the literal-only form needs'
                                % (e, len(stored), _lz11_literal_bound(len(F[e]))))
    return n


def check_logic_names(built, fan):
    """The six keyword slots whose description differs from Capcom's by a comma must have both
    cards rewritten (not the fan's drawings). Raises BufCheckError."""
    import logic_cards as L
    B, F = L.table(built), L.table(fan)
    for e in LOGIC_PUNCT_ENTRIES:
        if B[e] == F[e]:
            raise BufCheckError("logic card %d still has the fan drawing; slot %d should carry Capcom's name"
                                % (e, e - 1 if e < 135 else e - 135))
    return len(LOGIC_PUNCT_ENTRIES)


def rom_file(rom, path):
    """One file's bytes out of a ROM image."""
    from inject import file_id
    fid = file_id(rom, path)
    if fid is None:
        raise BufCheckError('%s is not in the ROM' % path)
    fat = struct.unpack_from('<I', rom, 0x48)[0]
    a, b = struct.unpack_from('<II', rom, fat + fid * 8)
    return bytes(rom[a:b])


def rom_files(rom):
    """The three files out of a ROM image: (spt, idlocal, cutdata) bytes."""
    return tuple(rom_file(rom, p) for p in ('jpn/spt.bin', 'jpn/idlocal.bin', 'com/cutdata.bin'))


def run(rom_path, dumpdir):
    """Check the built ROM at rom_path against the fan's idlocal in dumpdir.
    Returns the summary line; raises BufCheckError."""
    with open(rom_path, 'rb') as f:
        rom = f.read()
    with open(os.path.join(dumpdir, 'ds_fan', 'jpn', 'idlocal.bin'), 'rb') as f:
        fan = f.read()
    spt, idl, cut = rom_files(rom)
    line = check_blobs(spt, idl, cut, fan)
    with open(os.path.join(dumpdir, 'ds_fan', 'jpn', 'logic_keyword_local.bin'), 'rb') as f:
        fan_logic = f.read()
    n, past = check_logic_cards(rom_file(rom, 'jpn/logic_keyword_local.bin'), fan_logic)
    n_named = check_logic_names(rom_file(rom, 'jpn/logic_keyword_local.bin'), fan_logic)
    ps = ', '.join('%d (%d->%d bytes)' % (k, v[0], v[1]) for k, v in sorted(past.items())) or 'none'
    with open(os.path.join(dumpdir, 'ds_fan', 'jpn', 'modelitemlocal.bin'), 'rb') as f:
        fan_model = f.read()
    g_size, g_stored, g_fan = check_model_item(rom_file(rom, 'jpn/modelitemlocal.bin'), fan_model)
    with open(os.path.join(dumpdir, 'ds_fan', 'jpn', 'cutobj_local.bin'), 'rb') as f:
        fan_co = f.read()
    h = check_rooms(rom_file(rom, 'jpn/idlocal.bin'), fan, rom_file(rom, 'jpn/cutobj_local.bin'), fan_co)
    hs = ', '.join('%s %d decodes %d, stored %d of the fan\'s %d' % ((k[0], k[1]) + v) for k, v in sorted(h.items()))
    return ('%s; (f) logic cards: %d checked, every OBJ inside the RGCN bytes, cards with OBJs past the '
            'declared data (rewritten, no fan tail): %s, %d punctuation-matched name cards rewritten; (g) modelitemlocal entry %d decodes to %d bytes like '
            "the fan's, stored %d of the fan's %d, the other entries are the fan's bytes; "
            "(h) room names: %s, the other cutobj_local entries are the fan's bytes"
            % (line, n, ps, n_named, MODEL_ENTRY, g_size, g_stored, g_fan, hs))


if __name__ == '__main__':
    print(run(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else 'dump'))
