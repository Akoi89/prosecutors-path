# -*- coding: utf-8 -*-
"""One-time structural edit to idlocal entry 25's RECN + RNAN so the end
banner's "Checkmate" is drawn by one NCER cell instead of two.

Why: an NCER cell's OBJs each scale about that cell's own origin - screen
centre = px + scale*(OAM x + 64), half-width 32*scale for a 64x64 double-size
affine object (px/py/scale come from the RNAN sequence element that is
driving the cell that frame). At rest, cell 9 (tile field 144, OAM x -84) is
driven by its own sequence at px=-40, while cell 10 (fields 160 at OAM x -86
and 176 at -22) is driven by a SEPARATE sequence at px=26 - a 66px gap
between the two cells' own pivots. Above 1x scale, cell 9's pivot (further
left) makes its right edge slide under cell 10's left edge as both cells
enlarge about their own separate centres, hiding letters ("Clckmate",
"Chckmate", ... - each cell keeps scaling correctly on its own, the split
between them is what breaks). Moving all three tile fields onto cell 9 alone
removes the second pivot: every frame then scales about the same origin, so
the word never splits. Cell 10 is kept (its own OAM record count must not
change the cell table's overall size) but its two objects are retargeted to
tile field 96, which is blank in this ROM (checked below), so it draws
nothing; its own x is left as whatever this module's copy-and-retile leaves
in it, since a blank tile's position is never visible.

RECN (KBEC) layout, measured off the fan source's own entry 25:
  header (24 B) + KBEC 8B section header + KBEC body, where the body is
  24 B of cell-table header fields, then 45 cells x 8 B (attr bit 0 clear,
  so no per-cell user extension), then a single shared pool of 6-byte OAM
  records addressed by each cell's (n_oam, oam_off). Cell 9 owns 1 record
  (field 144) immediately followed by cell 10's 2 records (fields 160, 176):
  inserting 2 new 6-byte records for cell 9 (copies of cell 10's, tile field
  unchanged), bumping cell 9's n_oam to 3, and adding 12 to every LATER
  cell's oam_off (cells 10..44) is a pure insertion - nothing else in the
  KBEC body moves. The RECN file also carries LBAL (12 B, no names) and TXEU
  (12 B) sections after KBEC, and a 2-byte pad the header's own size field
  does not count (declared 726, actual file 728) - preserved here by growing
  both the true file length and the declared header field by the same +12,
  keeping that same 2-byte undercount rather than "fixing" it, since a
  byte-exact round trip on the UNCHANGED file is what proves this
  reader/writer pair is not guessing (and is checked again below, after the
  edit, against the invariants this module was written to produce).

RNAN: exam_end_07 (cell 9's own sequence: 114 ticks blank, zoom f02..f07,
99-tick rest f08..f10 sharing one stored element, squash f11..f19 on cells
39-41) pivots at px=-40 for every one of those frames (f02..f10, 7 distinct
stored records - f08/f09/f10 share one record). With cell 9 now carrying the
whole word, px moves to +4 for all 7 records (all three list entries sharing
the f08 record must be edited together, or the shared record reverts to
whichever is packed last). No other frame of exam_end_07 itself, and no
other sequence, references these 7 element offsets (checked below, not
assumed - both before AND after the edit, since the check is only useful if
it also proves the edit didn't accidentally touch something it does share).
The new pivot changes cell 9's real REST screen position too, by design: the
pivot must be one constant across the zoom AND the following rest, or the
word would visibly jump the instant the zoom settles at 1x. mindchess.py
compensates by keying its own OAM-x placement formula off this new pivot for
cell 9's records specifically (see TX and END_LEGACY_TX in mindchess.py),
which reproduces the exact same on-screen ink as before regardless of what
the pivot number is, while leaving cell 9's own palette-bank squash copies
(cells 39-41) and cell 10's squash copies (cells 42-44) exactly as they were.
"""
import struct
import rnan25

EXAM_END_07_PIVOT_FRAMES = range(2, 11)   # f02..f10 inclusive (7 distinct records)
EXAM_END_07_NEW_PX = 4
EXAM_END_07_OLD_PX = -40
BLANK_FIELD = 96


def _kbec_layout(recn_bytes):
    if recn_bytes[16:20] != b'KBEC':
        raise ValueError('entry 25 RECN layout changed: expected KBEC as the first '
                          'section, found %r' % (recn_bytes[16:20],))
    body = recn_bytes[24:]
    n_cells, attr = struct.unpack_from('<HH', body, 0)
    cell_off, mapping = struct.unpack_from('<II', body, 4)
    rec = 16 if (attr & 1) else 8
    oam_base = cell_off + n_cells * rec
    return body, n_cells, cell_off, rec, oam_base


def _cell_rec(body, cell_off, rec, i):
    p = cell_off + i * rec
    n_oam, oam_off = struct.unpack_from('<HxxI', body, p)
    return p, n_oam, oam_off


def onecell_recn(recn_bytes):
    """-> new RECN bytes: cell 9 gains fields 160 and 176 (copied from cell
    10's own stored records, unchanged tile ids), cell 10's two records
    retarget to blank field 96. Raises ValueError if entry 25's RECN does not
    match the measured layout this was written against (never silently
    mis-patches a different shape); re-reads its own output afterwards and
    raises if the result does not have the shape it was meant to produce."""
    recn = bytearray(recn_bytes)
    body, n_cells, cell_off, rec, oam_base = _kbec_layout(bytes(recn))
    if rec != 8 or n_cells != 45:
        raise ValueError('entry 25 RECN cell table changed shape: rec=%d n_cells=%d '
                          '(expected 8, 45)' % (rec, n_cells))

    p9, n9, off9 = _cell_rec(body, cell_off, rec, 9)
    p10, n10, off10 = _cell_rec(body, cell_off, rec, 10)
    if n9 != 1 or n10 != 2:
        raise ValueError('unexpected cell 9/10 OAM counts: %d, %d (expected 1, 2)' % (n9, n10))
    if off9 + n9 * 6 != off10:
        raise ValueError('cell 9/10 OAM records are not adjacent as measured '
                          '(cell 9 ends at %d, cell 10 starts at %d)' % (off9 + n9 * 6, off10))

    rec144 = bytes(body[oam_base + off9:oam_base + off9 + 6])
    rec160 = bytes(body[oam_base + off10:oam_base + off10 + 6])
    rec176 = bytes(body[oam_base + off10 + 6:oam_base + off10 + 12])
    for r, tile in ((rec144, 144), (rec160, 160), (rec176, 176)):
        got = struct.unpack_from('<H', r, 4)[0] & 0x3FF
        if got != tile:
            raise ValueError('stored tile id moved: expected field %d, found %d' % (tile, got))

    def retile(r, newtile):
        r = bytearray(r)
        a2 = struct.unpack_from('<H', r, 4)[0]
        struct.pack_into('<H', r, 4, (a2 & ~0x3FF) | (newtile & 0x3FF))
        return bytes(r)

    rec160_blank = retile(rec160, BLANK_FIELD)
    rec176_blank = retile(rec176, BLANK_FIELD)

    new_body = bytearray(body)
    ins_at = oam_base + off9 + n9 * 6            # == oam_base + off10
    new_body[ins_at:ins_at] = rec160 + rec176     # +12 bytes, cell 9 keeps fields 160/176
    struct.pack_into('<H', new_body, p9, 3)       # cell 9 n_oam: 1 -> 3

    off10_new = off10 + 12
    q = oam_base + off10_new
    new_body[q:q + 6] = rec160_blank              # cell 10's records -> blank field 96
    new_body[q + 6:q + 12] = rec176_blank

    for i in range(n_cells):                      # cells 10..44: oam_off += 12
        p = cell_off + i * rec
        n_oam, oam_off = struct.unpack_from('<HxxI', new_body, p)
        if oam_off >= off10:
            struct.pack_into('<I', new_body, p + 4, oam_off + 12)

    new_recn = bytearray(recn[:24]) + new_body
    kbec_size = struct.unpack_from('<I', new_recn, 20)[0]
    struct.pack_into('<I', new_recn, 20, kbec_size + 12)     # KBEC size: 686 -> 698
    hdr_size = struct.unpack_from('<I', new_recn, 8)[0]
    struct.pack_into('<I', new_recn, 8, hdr_size + 12)       # RECN header: 726 -> 738
    out = bytes(new_recn)

    if len(out) != len(recn_bytes) + 12:
        raise ValueError('onecell_recn: output grew by %d bytes, expected 12'
                          % (len(out) - len(recn_bytes)))
    _verify_recn(out, n_cells, cell_off, rec)
    return out


def _verify_recn(new_recn, n_cells, cell_off, rec):
    """Re-reads the bytes onecell_recn() just produced and checks the three
    invariants the edit is supposed to establish, so a mistake in the byte
    surgery above is caught here rather than shipped: cell 9 has exactly 3
    OAM records (fields 144, 160, 176, in that order); cell 10's 2 records
    both point at the blank field; and the section sizes agree with each
    other (declared KBEC size, declared RECN header size, actual length)."""
    body, n_cells2, cell_off2, rec2, oam_base = _kbec_layout(new_recn)
    if (n_cells2, cell_off2, rec2) != (n_cells, cell_off, rec):
        raise ValueError('onecell_recn: cell table shape changed unexpectedly after writing')
    p9, n9, off9 = _cell_rec(body, cell_off, rec, 9)
    if n9 != 3:
        raise ValueError('onecell_recn: cell 9 has %d OAM records after writing, expected 3' % n9)
    tiles9 = [struct.unpack_from('<H', body, oam_base + off9 + j * 6 + 4)[0] & 0x3FF
              for j in range(3)]
    if tiles9 != [144, 160, 176]:
        raise ValueError('onecell_recn: cell 9 draws fields %r after writing, expected '
                          '[144, 160, 176]' % tiles9)
    p10, n10, off10 = _cell_rec(body, cell_off, rec, 10)
    if n10 != 2:
        raise ValueError('onecell_recn: cell 10 has %d OAM records after writing, expected 2' % n10)
    tiles10 = [struct.unpack_from('<H', body, oam_base + off10 + j * 6 + 4)[0] & 0x3FF
               for j in range(2)]
    if tiles10 != [BLANK_FIELD, BLANK_FIELD]:
        raise ValueError('onecell_recn: cell 10 draws fields %r after writing, expected '
                          '[%d, %d]' % (tiles10, BLANK_FIELD, BLANK_FIELD))
    # actual physical length = 16 (RECN header) + kbec_size (includes its own
    # 8-byte magic+size) + 2 pad bytes + LBAL (12) + TXEU (12); the declared
    # header size field is that actual length minus the same 2-byte undercount
    # the fan's own header already has (see this module's docstring)
    kbec_size = struct.unpack_from('<I', new_recn, 20)[0]
    hdr_size = struct.unpack_from('<I', new_recn, 8)[0]
    expected_actual = 16 + kbec_size + 2 + 12 + 12
    if len(new_recn) != expected_actual:
        raise ValueError('onecell_recn: actual RECN length %d does not match sections '
                          '(16 + KBEC %d + 2 pad + LBAL 12 + TXEU 12 = %d)'
                          % (len(new_recn), kbec_size, expected_actual))
    if hdr_size != expected_actual - 2:
        raise ValueError('onecell_recn: declared header size %d does not match actual '
                          'length %d minus the 2-byte undercount' % (hdr_size, len(new_recn)))


def onecell_rnan(rnan_bytes):
    """-> new RNAN bytes: exam_end_07 f02..f10 px -40 -> +4 (7 distinct stored
    records, edited together so the shared f08/f09/f10 record ends up
    consistent regardless of write order). Length is unchanged - this is a
    value edit in place, no records added or removed. Round trips through
    rnan25's non-canonical serialiser, which keeps the stored (non-canonical)
    pool layout rather than rebuilding it. Re-parses its own output
    afterwards and raises if the 7 records do not all read px=4."""
    d = rnan25.parse(rnan_bytes)
    if not d['labels']:
        raise ValueError('onecell_rnan: entry 25 RNAN has no sequence labels')
    if 'exam_end_07' not in d['labels']:
        raise ValueError('onecell_rnan: exam_end_07 label not found')
    idx = d['labels'].index('exam_end_07')
    seq = d['seqs'][idx]
    touched = set()
    for k in EXAM_END_07_PIVOT_FRAMES:
        el = seq['frames'][k]['el']
        if el['cell'] != 9 or el['px'] != EXAM_END_07_OLD_PX:
            raise ValueError('onecell_rnan: exam_end_07 frame %d is %r, expected '
                              'cell 9 at px %d' % (k, el, EXAM_END_07_OLD_PX))
        el['px'] = EXAM_END_07_NEW_PX
        touched.add(seq['frames'][k]['elem_off'])
    # no other frame - including exam_end_07's OWN untouched frames (f00/f01
    # blank, f11-f19 squash, f20 final) - may share one of the 7 edited
    # element offsets; sharing there would mean serialise() writes whichever
    # frame packs last, silently reverting some of the 7 to px -40.
    for i, sq in enumerate(d['seqs']):
        for k, fr in enumerate(sq['frames']):
            if i == idx and k in EXAM_END_07_PIVOT_FRAMES:
                continue
            if fr['elem_off'] in touched:
                raise ValueError('onecell_rnan: sequence %d frame %d shares an edited '
                                  'exam_end_07 element record (offset %d) - the pivot '
                                  'edit would not be self-consistent'
                                  % (i, k, fr['elem_off']))
    out = rnan25.serialise(d)
    if len(out) != len(rnan_bytes):
        raise ValueError('onecell_rnan: output length %d != input length %d'
                          % (len(out), len(rnan_bytes)))
    d2 = rnan25.parse(out)
    seq2 = d2['seqs'][d2['labels'].index('exam_end_07')]
    for k in EXAM_END_07_PIVOT_FRAMES:
        if seq2['frames'][k]['el']['px'] != EXAM_END_07_NEW_PX:
            raise ValueError('onecell_rnan: after writing, exam_end_07 frame %d reads '
                              'px %d, expected %d' % (k, seq2['frames'][k]['el']['px'],
                                                       EXAM_END_07_NEW_PX))
    return out


def apply(blob25):
    """-> new entry-25 blob bytes with the one-cell Checkmate structural edit
    (RECN +12, RNAN unchanged length), the Capcom-layout Commence structural
    edit (RECN +48, RGCN +4096, RNAN unchanged length) AND the END06 sliver
    fix (RNAN unchanged length, a value edit only) all applied, section
    offsets updated. RGCN starts unchanged only by the first edit; the second
    edit grows it, so the final RGCN offset reflects both RECN deltas plus
    nothing from RNAN (none of the three edits change its length)."""
    b = bytes(blob25)
    o = struct.unpack_from('<3I', b, 0)
    recn, rn, rgcn = b[o[0]:o[1]], b[o[1]:o[2]], b[o[2]:]
    recn1 = onecell_recn(recn)
    rn1 = onecell_rnan(rn)
    d1 = len(recn1) - len(recn)
    if d1 != 12 or len(rn1) != len(rn):
        raise ValueError('apply: unexpected size change after onecell edit (RECN %+d, '
                          'expected +12; RNAN %+d, expected 0)' % (d1, len(rn1) - len(rn)))
    rn1b = fix_end06_stray_cell(rn1)
    if len(rn1b) != len(rn1):
        raise ValueError('apply: unexpected size change after the END06 sliver fix '
                          '(RNAN %+d, expected 0)' % (len(rn1b) - len(rn1)))
    recn2 = capcom_recn(recn1)
    rn2 = capcom_rnan(rn1b)
    rgcn2 = capcom_rgcn(rgcn)
    d2 = len(recn2) - len(recn1)
    if d2 != 48 or len(rn2) != len(rn1b) or len(rgcn2) - len(rgcn) != 4096:
        raise ValueError('apply: unexpected size change after capcom edit (RECN %+d, '
                          'expected +48; RNAN %+d, expected 0; RGCN %+d, expected +4096)'
                          % (d2, len(rn2) - len(rn1b), len(rgcn2) - len(rgcn)))
    new_o = (o[0], o[0] + len(recn2), o[0] + len(recn2) + len(rn2))
    return struct.pack('<3I', *new_o) + recn2 + rn2 + rgcn2


# ============================================================================
# Capcom layout: START banner "Mind Chess" / "Commence"
# ============================================================================
"""
RECN: cells 7 and 8 (the fan's "Be"/"gin" pieces) each gain a SECOND OAM
object - new tile field 192 for cell 7's family (existing field 112), new
field 208 for cell 8's family (existing field 128) - so "Commence" splits
Comm/ence across two cells each, mirroring how Checkmate splits across cell
9's three fields. The palette-bank copies used during cell 7/8's own
squash-out (cells 33-35 for cell 7, cells 36-38 for cell 8 - confirmed by
reading the RNAN: exam_sta_07/08's own f17-21 squash frames reference cells
33-35/36-38 directly, the SAME sequence and SAME px as cell 7/8's own rest
pose, not a different sequence with a different pivot like the END banner's
cell 9/10 bank copies) get the same second object. Because px never changes
across cell 7/8's own frames and their bank copies' frames (confirmed above),
every one of these 8 new records gets the SAME formula-derived OAM x as its
owning cell - no legacy/new pivot split is needed here, unlike END_FIELDS in
mindchess.py.

Each insertion copies the cell's own existing 6-byte OAM record (same y,
double-size-affine flag, rotscale select bits) and only changes the tile id,
the same "copy a sibling record, retile it" pattern onecell_recn() uses for
cell 9's growth - OAM x is left at whatever the copy carries and is
overwritten afterwards by mindchess.py's own per-record placement formula.
"""
CAPCOM_INSERTIONS = ((7, 192), (33, 192), (34, 192), (35, 192),
                     (8, 208), (36, 208), (37, 208), (38, 208))


def _insert_second_oam(recn_bytes, cell, newtile):
    """-> new RECN bytes with `cell` gaining a second OAM record, a copy of
    its own (only) existing record with the tile id changed to `newtile`,
    inserted immediately after it. Raises if `cell` does not have exactly 1
    OAM record before the edit (never silently mis-patches a cell that has
    already been touched or has an unexpected shape)."""
    recn = bytearray(recn_bytes)
    body, n_cells, cell_off, rec, oam_base = _kbec_layout(bytes(recn))
    if rec != 8:
        raise ValueError('capcom_recn: entry 25 RECN cell record size changed '
                          '(rec=%d, expected 8)' % rec)
    p, n_oam, oam_off = _cell_rec(body, cell_off, rec, cell)
    if n_oam != 1:
        raise ValueError('capcom_recn: cell %d has %d OAM records, expected exactly '
                          '1 before this edit' % (cell, n_oam))
    old_rec = bytes(body[oam_base + oam_off:oam_base + oam_off + 6])
    new_rec = bytearray(old_rec)
    a2 = struct.unpack_from('<H', new_rec, 4)[0]
    struct.pack_into('<H', new_rec, 4, (a2 & ~0x3FF) | (newtile & 0x3FF))

    ins_at = oam_base + oam_off + 6   # right after this cell's own (only) record
    new_body = bytearray(body)
    new_body[ins_at:ins_at] = bytes(new_rec)
    struct.pack_into('<H', new_body, p, 2)   # this cell's n_oam: 1 -> 2

    for i in range(n_cells):
        pp = cell_off + i * rec
        n_oam_i, oam_off_i = struct.unpack_from('<HxxI', new_body, pp)
        if oam_base + oam_off_i >= ins_at and i != cell:
            struct.pack_into('<I', new_body, pp + 4, oam_off_i + 6)

    new_recn = bytearray(recn[:24]) + new_body
    kbec_size = struct.unpack_from('<I', new_recn, 20)[0]
    struct.pack_into('<I', new_recn, 20, kbec_size + 6)
    hdr_size = struct.unpack_from('<I', new_recn, 8)[0]
    struct.pack_into('<I', new_recn, 8, hdr_size + 6)
    out = bytes(new_recn)
    if len(out) != len(recn_bytes) + 6:
        raise ValueError('capcom_recn: cell %d insertion grew RECN by %d bytes, '
                          'expected 6' % (cell, len(out) - len(recn_bytes)))
    return out


def capcom_recn(recn_bytes):
    """-> new RECN bytes: cells 7, 33, 34, 35 gain field 192 as their second
    OAM object; cells 8, 36, 37, 38 gain field 208 - 8 insertions total (+48
    bytes), done one at a time since the 8 target cells are not contiguous
    in the shared OAM pool (unlike onecell_recn's single insertion for cell
    9). Re-reads its own output afterwards and raises if the result does not
    have the shape it was meant to produce."""
    out = recn_bytes
    for cell, newtile in CAPCOM_INSERTIONS:
        out = _insert_second_oam(out, cell, newtile)
    if len(out) != len(recn_bytes) + 48:
        raise ValueError('capcom_recn: output grew by %d bytes, expected 48'
                          % (len(out) - len(recn_bytes)))
    _verify_capcom_recn(out)
    return out


def _verify_capcom_recn(new_recn):
    body, n_cells, cell_off, rec, oam_base = _kbec_layout(new_recn)
    for cell, newtile in CAPCOM_INSERTIONS:
        oldtile = 112 if newtile == 192 else 128
        p, n_oam, oam_off = _cell_rec(body, cell_off, rec, cell)
        if n_oam != 2:
            raise ValueError('capcom_recn: cell %d has %d OAM records after writing, '
                              'expected 2' % (cell, n_oam))
        tiles = [struct.unpack_from('<H', body, oam_base + oam_off + j * 6 + 4)[0] & 0x3FF
                 for j in range(2)]
        if tiles != [oldtile, newtile]:
            raise ValueError('capcom_recn: cell %d draws fields %r after writing, '
                              'expected [%d, %d]' % (cell, tiles, oldtile, newtile))
    kbec_size = struct.unpack_from('<I', new_recn, 20)[0]
    hdr_size = struct.unpack_from('<I', new_recn, 8)[0]
    # same 2-byte fan-header undercount preserved by onecell_recn's own math,
    # now further grown by the 48 bytes this module inserted
    expected_actual = 16 + kbec_size + 2 + 12 + 12
    if len(new_recn) != expected_actual:
        raise ValueError('capcom_recn: actual RECN length %d does not match sections '
                          '(16 + KBEC %d + 2 pad + LBAL 12 + TXEU 12 = %d)'
                          % (len(new_recn), kbec_size, expected_actual))
    if hdr_size != expected_actual - 2:
        raise ValueError('capcom_recn: declared header size %d does not match actual '
                          'length %d minus the 2-byte undercount' % (hdr_size, len(new_recn)))


CAPCOM_NAME_RANGE = tuple(range(1, 18))   # f01..f17 inclusive, 17 frames
CAPCOM_VERB_RANGE = tuple(range(2, 22))   # f02..f21 inclusive, 20 frames
CAPCOM_VERB_PY = 24


def capcom_rnan(rnan_bytes):
    """-> new RNAN bytes: for n = 0..6, exam_sta_0n's own f01..f17 py values
    are overwritten with exam_end_0n's OWN f01..f17 py values, read live from
    THIS SAME RNAN blob (not a fixed table), so each name cell's own fly-in
    overshoot is reproduced exactly, not approximated by a shared curve.

    exam_end_0n's OWN f01..f17 is not always 17 frames of REAL content for
    this row: every frame's element names a cell, and only cells in this
    row's own family (n itself, plus its 3 palette-bank copies - checked
    directly against the built blob: exam_end_00 only ever uses cells
    {0, 12, 13, 14}, exam_end_01 only {1, 15, 16, 17}, and so on) are this
    row's own letter. Two situations put a NON-family cell in an otherwise
    ordinary-looking frame:
      - the shared filler cell (11, px=0, py=0) before a piece's own fly-in
        starts, or after its own timeline ends (settling by f16 and reusing
        the leading filler record at f17, since exam_end_0n's own timeline
        can be shorter than exam_sta_0n's);
      - exam_end_06 specifically carries one frame (its own f05, 2 ticks)
        whose element draws cell 7 - a pre-existing fan-data mismatch (see
        fix_end06_stray_cell() above), not a filler and not this row's own
        family either.
    Both cases are treated the same way here: content_py() below only trusts
    a frame's py if its cell is in the row's own family, and fills every
    other frame index by LINEAR INTERPOLATION between the nearest family
    frames before and after it (or by holding the one available side, at
    either end of the range) - not by holding the last value forward, which
    would ignore that the row's OWN fly-in curve is still moving through the
    gap. Checked against exam_end_06's own data: its f04 (family, py=-44) and
    f06 (family, py=-26) bracket the stray f05, interpolating to py=-35 at f05
    - the value this function now assigns to exam_sta_06's own f05.

    exam_sta_07/08's own f02..f21 py are set to a flat 24, the row Checkmate
    already occupies. Length is unchanged - this is a value edit in place.
    Raises if the write would not be self-consistent (a touched element
    record shared with an untouched frame, or with two different intended
    values)."""
    d = rnan25.parse(rnan_bytes)
    labels = d['labels']
    if not labels:
        raise ValueError('capcom_rnan: entry 25 RNAN has no sequence labels')
    idx = {lab: i for i, lab in enumerate(labels)}

    def content_py(seq, upto, family):
        """-> [py for frame 1..upto]. A frame's OWN py is trusted only if its
        element's cell is in `family` (this row's own settled cell + its 3
        bank copies); every other frame index (the shared filler cell, or a
        stray reference like exam_end_06's own f05 - see this function's
        caller and fix_end06_stray_cell()) is filled by linear interpolation
        between the nearest family frames before and after it, or by holding
        the one available side if the gap runs off either end of the range.
        Raises if NO frame in 1..upto belongs to the family at all."""
        known = {}
        for k in range(1, upto + 1):
            el = seq['frames'][k]['el']
            if el['cell'] in family:
                known[k] = el['py']
        if not known:
            raise ValueError('capcom_rnan: no frame in 1..%d belongs to cell family %r'
                              % (upto, sorted(family)))
        out = []
        for k in range(1, upto + 1):
            if k in known:
                out.append(known[k])
                continue
            befores = [kk for kk in known if kk < k]
            afters = [kk for kk in known if kk > k]
            if befores and afters:
                kb, ka = max(befores), min(afters)
                py = known[kb] + (known[ka] - known[kb]) * (k - kb) / (ka - kb)
                out.append(round(py))
            elif befores:
                out.append(known[max(befores)])
            else:
                out.append(known[min(afters)])
        return out

    assignments = {}   # (seq_idx, frame_idx) -> new py
    for n in range(7):
        sta_lab, end_lab = 'exam_sta_%02d' % n, 'exam_end_%02d' % n
        for lab in (sta_lab, end_lab):
            if lab not in idx:
                raise ValueError('capcom_rnan: sequence %r not found' % lab)
        sta = d['seqs'][idx[sta_lab]]
        end = d['seqs'][idx[end_lab]]
        need = max(CAPCOM_NAME_RANGE)
        if len(sta['frames']) <= need or len(end['frames']) <= need:
            raise ValueError('capcom_rnan: %s (%d frames) / %s (%d frames) do not '
                              'both have frame %d' % (sta_lab, len(sta['frames']),
                                                       end_lab, len(end['frames']), need))
        family = {n, 12 + 3 * n, 13 + 3 * n, 14 + 3 * n}
        src_py = content_py(end, need, family)
        for k in CAPCOM_NAME_RANGE:
            assignments[(idx[sta_lab], k)] = src_py[k - 1]
    for lab in ('exam_sta_07', 'exam_sta_08'):
        if lab not in idx:
            raise ValueError('capcom_rnan: sequence %r not found' % lab)
        seq = d['seqs'][idx[lab]]
        need = max(CAPCOM_VERB_RANGE)
        if len(seq['frames']) <= need:
            raise ValueError('capcom_rnan: %s does not have frame %d' % (lab, need))
        for k in CAPCOM_VERB_RANGE:
            assignments[(idx[lab], k)] = CAPCOM_VERB_PY

    # every touched frame's OWN stored element offset, and what this edit
    # intends to write there
    touched_offsets = {}   # elem_off -> set of intended py values
    frame_offset = {}      # (seq_idx, frame_idx) -> elem_off
    for (si, k), py in assignments.items():
        eoff = d['seqs'][si]['frames'][k]['elem_off']
        frame_offset[(si, k)] = eoff
        touched_offsets.setdefault(eoff, set()).add(py)
    conflicts = {o: v for o, v in touched_offsets.items() if len(v) > 1}
    if conflicts:
        raise ValueError('capcom_rnan: element offset(s) %r are targeted by this edit '
                          'with more than one intended py value %r - the shared record '
                          'would not be self-consistent' % (list(conflicts), conflicts))
    for i, sq in enumerate(d['seqs']):
        for k, fr in enumerate(sq['frames']):
            if (i, k) in assignments:
                continue
            if fr['elem_off'] in touched_offsets:
                raise ValueError('capcom_rnan: sequence %d frame %d shares an edited '
                                  'element record (offset %d) with a touched frame - '
                                  'the py edit would not be self-consistent'
                                  % (i, k, fr['elem_off']))

    for (si, k), py in assignments.items():
        d['seqs'][si]['frames'][k]['el']['py'] = py

    out = rnan25.serialise(d)
    if len(out) != len(rnan_bytes):
        raise ValueError('capcom_rnan: output length %d != input length %d'
                          % (len(out), len(rnan_bytes)))

    d2 = rnan25.parse(out)
    for (si, k), py in assignments.items():
        got = d2['seqs'][si]['frames'][k]['el']['py']
        if got != py:
            raise ValueError('capcom_rnan: after writing, sequence %d frame %d reads '
                              'py %d, expected %d' % (si, k, got, py))
    return out


def capcom_rgcn(rgcn_bytes, n_new_fields=2, tiles_per_field=64, tile_bytes=32):
    """-> new RGCN bytes with `n_new_fields` worth of blank (zero) 4bpp tiles
    appended after the existing tile data - room for mindchess.py to write
    the two new "Commence" tile fields (192, 208) into. Only the tile data
    length changes; NCGR format/mapping fields, the tile data's own start
    offset and everything about how existing tiles are addressed (RECN's own
    field-number-times-boundary convention) are untouched. Raises if entry
    25's RGCN does not match the measured single-RAHC-section, 4bpp,
    contiguous-tile-data shape this was written against."""
    rgcn = bytes(rgcn_bytes)
    if rgcn[0:4] != b'RGCN':
        raise ValueError('capcom_rgcn: not an RGCN container (got %r)' % (rgcn[0:4],))
    nsec = struct.unpack_from('<H', rgcn, 14)[0]
    if nsec != 1 or rgcn[16:20] != b'RAHC':
        raise ValueError('capcom_rgcn: expected exactly one RAHC section, found '
                          '%d section(s) starting %r' % (nsec, rgcn[16:20]))
    rahc_size = struct.unpack_from('<I', rgcn, 20)[0]
    if 16 + rahc_size != len(rgcn):
        raise ValueError('capcom_rgcn: RAHC declared size %d does not run to the end '
                          'of the RGCN blob (blob is %d bytes)' % (rahc_size, len(rgcn)))
    body = rgcn[24:16 + rahc_size]
    fmt = struct.unpack_from('<I', body, 4)[0]
    if fmt != 3:
        raise ValueError('capcom_rgcn: NCGR format %d != 3 (4bpp); layout changed' % fmt)
    dsize = struct.unpack_from('<I', body, 16)[0]
    doff = struct.unpack_from('<I', body, 20)[0]
    if doff != 24 or dsize + doff != len(body):
        raise ValueError('capcom_rgcn: tile data does not run exactly to the end of '
                          'the RAHC body (doff=%d dsize=%d bodylen=%d)'
                          % (doff, dsize, len(body)))
    if dsize % tile_bytes:
        raise ValueError('capcom_rgcn: tile data size %d is not a whole number of '
                          '%d-byte tiles' % (dsize, tile_bytes))

    add_bytes = n_new_fields * tiles_per_field * tile_bytes
    new_body = bytearray(body)
    struct.pack_into('<I', new_body, 16, dsize + add_bytes)
    new_body += bytes(add_bytes)
    new_rahc = b'RAHC' + struct.pack('<I', len(new_body) + 8) + bytes(new_body)
    new_filesize = 16 + len(new_rahc)
    out = rgcn[0:8] + struct.pack('<I', new_filesize) + rgcn[12:16] + new_rahc

    if len(out) != len(rgcn) + add_bytes:
        raise ValueError('capcom_rgcn: output grew by %d bytes, expected %d'
                          % (len(out) - len(rgcn), add_bytes))
    body2 = out[24:16 + struct.unpack_from('<I', out, 20)[0]]
    dsize2 = struct.unpack_from('<I', body2, 16)[0]
    if dsize2 != dsize + add_bytes or dsize2 % tile_bytes:
        raise ValueError('capcom_rgcn: after writing, declared tile data size %d is '
                          'not old size + %d new bytes' % (dsize2, add_bytes))
    return out


# ============================================================================
# END banner sliver fix: exam_end_06's own stray cell-7 reference
# ============================================================================
END06_FAMILY = {6, 30, 31, 32}   # exam_end_06's own settled cell (the blank
                                  # 7th name-row slot) plus its 3 palette-bank
                                  # copies - the ONLY cells every other frame
                                  # of this sequence ever draws (checked
                                  # against the built blob)
END06_STRAY_CELL = 7             # the one frame that draws outside that
                                  # family (its own f05, 2 ticks) points at
                                  # cell 7 instead - a pre-existing fan-data
                                  # mismatch. Before this fix it drew the
                                  # fan's own harmless "Be" piece there; now
                                  # that cell 7 carries a second OAM object
                                  # for "Comm" (capcom_recn above), the same
                                  # 2 ticks draw a real sliver of ink at the
                                  # far left screen edge instead


def fix_end06_stray_cell(rnan_bytes):
    """-> new RNAN bytes: entry 25's exam_end_06 sequence has exactly one
    frame whose element draws a cell outside its own family (END06_FAMILY) -
    repoints THAT element at the shared filler cell (11, which owns zero OAM
    records and so always draws nothing), after confirming the element's own
    offset is not shared by any other frame of any sequence (so the repoint
    cannot affect anything else). Raises if the stray frame is not exactly
    the one measured (cell END06_STRAY_CELL), if there is more than one
    stray frame, or if the element offset turns out to be shared."""
    d = rnan25.parse(rnan_bytes)
    if 'exam_end_06' not in d['labels']:
        raise ValueError('fix_end06_stray_cell: exam_end_06 label not found')
    idx = d['labels'].index('exam_end_06')
    seq = d['seqs'][idx]
    strays = [(k, fr) for k, fr in enumerate(seq['frames'])
              if fr['el']['cell'] not in END06_FAMILY and fr['el']['cell'] != 11]
    if len(strays) != 1:
        raise ValueError('fix_end06_stray_cell: expected exactly 1 stray frame in '
                          'exam_end_06 outside its own cell family %r, found %d: %r'
                          % (sorted(END06_FAMILY), len(strays), strays))
    k, fr = strays[0]
    el = fr['el']
    if el['cell'] != END06_STRAY_CELL:
        raise ValueError('fix_end06_stray_cell: exam_end_06 frame %d draws cell %d, '
                          'expected the known stray cell %d' % (k, el['cell'], END06_STRAY_CELL))
    target_off = fr['elem_off']
    hits = [(i, kk) for i, sq in enumerate(d['seqs']) for kk, ffr in enumerate(sq['frames'])
            if ffr['elem_off'] == target_off]
    if hits != [(idx, k)]:
        raise ValueError('fix_end06_stray_cell: element offset %d is shared by more than '
                          'this one frame (%r) - refusing to repoint it' % (target_off, hits))

    el['cell'] = 11
    el['px'] = 0
    el['py'] = 0

    out = rnan25.serialise(d)
    if len(out) != len(rnan_bytes):
        raise ValueError('fix_end06_stray_cell: output length %d != input length %d'
                          % (len(out), len(rnan_bytes)))
    d2 = rnan25.parse(out)
    got = d2['seqs'][idx]['frames'][k]['el']
    if got['cell'] != 11:
        raise ValueError('fix_end06_stray_cell: after writing, frame %d reads cell %d, '
                          'expected 11' % (k, got['cell']))
    return out
