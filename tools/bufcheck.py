# -*- coding: utf-8 -*-
"""Build checks against fixed-buffer overflows, computed from the BUILT bytes.

The port's data can outgrow a fixed buffer in the game without any visible
error at build time. playtest/SOLVE_buffers.md traced every loader and text
buffer in the engine; none overflows today, and checks a to e keep it that
way (f is the Logic keyword cards, g the bag model texture, h the room names, i the opening card,
j the evidence icons, k the nameplates, l the marker letters, m the item pictures, n the menu button,
o the Bigg Building pictures, p the map pieces and plans, q the nurse's cap, s the background signs).
They read jpn/spt.bin, jpn/idlocal.bin, com/cutdata.bin,
jpn/logic_keyword_local.bin, jpn/modelitemlocal.bin, jpn/cutobj_local.bin, jpn/opening_local.bin and
com/idcom.bin out of the finished ROM (after the last step that writes any of them), compare idlocal,
the logic cards, the model file, cutobj_local, the opening file and idcom with the fan's, and RAISE
BufCheckError naming the entry and the
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
   Entry 172 (the Promise Notebook title strip, stored as real LZ11 and 410 bytes where the fan's
   slot held 352) must decode inside its stored bytes, and may not be stored in more bytes than
   the literal-only form of its decoded size (the form the 119 other redrawn strips ship in:
   size + size/8 rounded up + 4, 1,480 for these 1,312 bytes).
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
   more bytes than the fan's entry; every cutobj_local entry outside CUTOBJ_CHANGED (2 4 6 8 10 16 18
   20 22 24 26: the room names, Bigg Building, the city map patches and the marker letters) must be byte
   for byte the fan's.
i. opening card. jpn/opening_local.bin entries 13 (RGCN, which opening_card.py redraws) and 14
   (RLCN) are read by the sprite bundle loader into a buffer of the table's decoded size, through
   a temporary copy of the stored entry. Every table field must be the fan's (decoded sizes and
   compression flags), entry 13 must be an LZ11 stream decoding to an RGCN of that size and be
   stored in no more bytes than the fan's, entry 14 must stay uncompressed, and every other entry
   except 0 (the splash title tiles title_text.py rewrites) must decode to the fan's bytes.
j. evidence icons. com/idcom.bin entries 281, 573 and 575 (the business card and the victim's
   letter, redrawn by idcom_icons.py, with their palette entries 280, 572 and 574; and, with the
   item pictures, 327 the weight, 485 487 489 735 737 the bottle labels, 539 541 547 549 the ticket and pamphlet) are written in
   place: the file is as long as the fan's, its whole table is the fan's, every other entry is
   the fan's bytes, each icon decodes to the fan's size and its LZ11 stream fits in the bytes the
   fan's entry held (so it is stored in no more than the fan's), only the tile data of an icon
   and only the 16 colours of a palette differ from the fan's, and no pixel is index 0 (the
   transparent key, which would punch a hole in the sprite).
   Exception (IDCOM_GROW: 483 519 563, the notebook, the licence and the law-office card): these may be stored larger
   than the fan's, and then the whole file is laid out again (idcom_icons.relayout). The table must keep its slot
   count and every size field, start right after itself, end with the slot (file length, 0), list the entries in the
   fan's order, keep every offset's value mod 4; every entry that is not an icon must be the fan's bytes, moved; a grown icon must still decode to the
   fan's size and no more than 2,320 bytes (the block the column +8 icons are read into, sized from entry 129).
k. nameplates. The 28 redrawn dialogue nameplates (idlocal entries of plates.PLATES, stored as real LZ11,
   not the literal-only form of 1.11.1) keep the fan's decoded size (the table field is the fan's), are LZ11 streams that
   declare and decode to that size, differ from the fan's decoded entry only inside the tile data,
   and are stored in no more bytes than the fan's slot, except the entries of PLATE_STORED_OVER, which
   are measured, listed, and bounded by that number and by the literal-only form (the form the
   1.11.1 plates shipped in, 708 bytes). Every other nameplate slot (27-86) is the fan's bytes.
l. marker letters. jpn/cutobj_local.bin entries MARKER_CUTOBJ (tools/marker_letters.py: the letter in
   the round character markers) keep the fan's table field, are real LZ11 streams that decode to the
   fan's size and are stored in no more bytes than the fan's entry; in the entries that only this step
   changes, every byte before and after the 4bpp tile data is the fan's and the tile data is as long
   as the fan's; every cutobj_local entry outside CUTOBJ_CHANGED (2 4 6 8 10 12 16 18 20 22 24 26: the room
   names' entry 10, the plans' entry 12, the city map's entries 18 and 26, and the marker letters' ten) is the
   fan's bytes.
m. item pictures. jpn/upcut_local.bin entries ITEM_UPCUT and ITEM_UPCUT_BIG (tools/item_pics.py, tools/cg_names.py)
   keep the fan's table field (and stay under the UPCUT_FIXED_CAP picture buffer), are real LZ11 streams that
   declare and decode to that size, are stored in no more bytes than the fan's entry (ITEM_UPCUT_BIG, the keycard log
   pictures 210 and 242, are exempt from that one rule), keep the fan's palette entry and differ from the fan's
   picture only inside the tile data; com/logic_keyword.bin entries LOGIC_ICON_ENTRIES as in j.
n. menu button. jpn/idlocal.bin entry 357 (tools/menu_button.py) keeps the fan's table field, is a real LZ11 stream
   stored in no more bytes than the fan's and differs from it only in its tile data; 356 and 358 are the fan's bytes.
o. Bigg Building. jpn/idlocal.bin entries BIGG_IDLOCAL, jpn/upcut_local.bin entries BIGG_UPCUT and
   jpn/cutobj_local.bin entries BIGG_CUTOBJ and PATCH_CUTOBJ (tools/bigg_building.py: the tower's name on the place
   cards, the city map and the cross-section pictures; tools/city_labels.py, tools/city_patches.py: Capcom's
   wording on the city map, its highlight patches, the room label and the 50th floor strip) keep the fan's table field, are real LZ11
   streams that decode to the fan's size and are stored in no more bytes than the fan's entry; the
   other cutobj_local entries are the fan's bytes except the ones in CUTOBJ_CHANGED (2 4 6 8 10 12 16 18 20 22 24 26).
p. map pieces and plans in Capcom's wording. The jpn/idlocal.bin entries PLAN_IDLOCAL and the
   jpn/upcut_local.bin entries PLAN_UPCUT (tools/plan_labels.py re-letters them in place) must decode to exactly the fan's size with
   the fan's table field, be real LZ11 streams whose header agrees with the table, and be stored
   in no more bytes than the fan's entry (entries in PLAN_LARGER and PLAN_UP_LARGER: the slot may hold the
   literal-only form of the decoded size plus 3 alignment bytes; idlocal entry 172's bound is the literal-only form
   alone, without the 3). upcut_local entries must also decode
   to no more than the 0x2F000 picture block the loader trace found, and a raw palette entry
   after a plan picture is the fan's bytes. The jpn/cutobj_local.bin entries PLAN_CUTOBJ (the Autumn cloud of
   the Zodiac Hall plan) keep the fan's table field and decoded size, are stored in no more bytes than the
   fan's, and differ from the fan's decoded entry only inside the 4bpp tile data.
q. the nurse's cap. tools/props_bust.py redraws the tile data of com/bustup.bin 252, 253, 254, 255 and 264
   (OAM sprite banks, palettes 251 and 263) and of com/idcom.bin 951 and 953 (portrait icons, palettes
   950 and 952), written in place. com/bustup.bin is as long as the fan's, its whole table is the fan's and
   every other entry is the fan's bytes. com/idcom.bin may have been laid out again by the item icons (check j):
   there 951 and 953 keep the fan's table field and a slot of the fan's size, and check j, which counts them among
   the entries it lets differ, proves the layout and that every other entry is the fan's bytes. Each entry is an LZ11 stream whose declared size is the table's, decodes to the fan's size and
   fits in the bytes the fan's entry held, only its RGCN tile data differs from the fan's, and no tile
   byte the fan drew becomes index 0 (the transparent key). Neither container's loader was traced for
   these entries, so the stored size stays at or under the fan's.
s. background signs. The pictures tools/props.py redraws (SIGN_ENTRIES: com/mapbg.bin, com/logicbg.bin,
   com/upcut.bin, jpn/upcut_local.bin) are written in place: each file is as long as the fan's, its whole table is the
   fan's, every other entry (the palettes included) is the fan's bytes, each picture is an LZ11 stream
   that decodes to the fan's size, whose stream fits in the bytes the fan's entry held, and only the
   pixel data of its RGCN differs from the fan's. These containers are not idlocal or idcom (whose
   loaders decode into an exact-size heap buffer through a freed temporary); their loaders were not
   traced, so the stored size stays at or under the fan's. jpn/upcut_local.bin is rebuilt by
   tools/cg_art.py first, so there only the sign entries are compared: table field the fan's, slot of
   the fan's size, the stream decoding inside it, and only pixel data changed.
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
IDLOCAL_STORED_BOUNDED = (172,)      # title strips stored as real LZ11: no larger than the literal-only form
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
BIGG_IDLOCAL = (328, 331, 334, 337, 340, 343)
BIGG_UPCUT = (208, 244, 246, 264, 278, 280, 282)
BIGG_CUTOBJ = 26
MARKER_CUTOBJ = (2, 4, 6, 8, 10, 16, 20, 22, 24, 26)      # entries whose marker letters marker_letters.py redraws
PATCH_CUTOBJ = 18                                      # the city map's highlight patches (tools/city_patches.py)
# map pieces and floor plans re-lettered in Capcom's wording (tools/plan_labels.py, check p)
PLAN_IDLOCAL = (282, 285, 291, 294, 297, 300, 303, 306, 309, 312, 315, 318, 321, 324, 327, 349)      # 309 is only redrawn with plan_labels.LARGER
PLAN_UPCUT = (36, 40, 48, 52, 78, 80, 82, 102, 114, 116)   # the plan pictures of jpn/upcut_local.bin (RGCN entries; the palette is entry + 1)
PLAN_LARGER = (282, 285, 303, 309)      # idlocal entries allowed up to the literal-only form of their decoded size (plan_labels.LARGER)
PLAN_CUTOBJ = (12,)      # jpn/cutobj_local.bin entries plan_labels re-letters (the Autumn cloud of the Zodiac Hall plan): tile data only, stored <= fan
PLAN_UP_LARGER = (36, 48, 78)      # the same for jpn/upcut_local.bin (plan_labels.UP_LARGER; fixed 0x2F000 block, decoded size only)
UPCUT_BLOCK = 0x2F000      # the fixed picture block the cut table's column 1 entries of upcut_local are decoded into
OPENING_GFX, OPENING_PAL = 13, 14
OPENING_FREE = (0,)            # the splash title tiles, rewritten by title_text.py
ICON_ENTRIES = {281: 280, 573: 572, 575: 574}      # icon entry -> its palette entry
# the nurse's cap (tools/props_bust.py): container -> {entry: palette entry}
NURSE_ENTRIES = {
    'com/bustup.bin': {252: 251, 253: 251, 254: 251, 255: 251, 264: 263},
    'com/idcom.bin': {951: 950, 953: 952},
}
# background pictures tools/props.py redraws: container -> {picture entry: palette entry}
SIGN_ENTRIES = {
    'com/mapbg.bin': {10: 11, 20: 21, 22: 23, 30: 31, 54: 55, 56: 57, 60: 61},
    'com/logicbg.bin': {14: 15, 34: 35},
    'com/upcut.bin': {128: 129, 388: 389, 392: 393, 400: 401, 406: 407, 408: 409},
    'jpn/upcut_local.bin': {42: 43, 206: 207, 234: 235},
}
# containers the port rebuilds before the signs step (tools/cg_art.py rewrites jpn/upcut_local.bin): only
# the sign entries are compared with the fan's, each in a slot of exactly the fan's size
SIGN_REBUILT = ('jpn/upcut_local.bin',)
# every cutobj_local entry some step changes; checks h, l, o and p require every other entry to be the fan's bytes
CUTOBJ_CHANGED = tuple(sorted(set((ROOM_CUTOBJ, BIGG_CUTOBJ, PATCH_CUTOBJ) + MARKER_CUTOBJ + PLAN_CUTOBJ)))
OPENING_GFX, OPENING_PAL = 13, 14
OPENING_FREE = (0,)            # the splash title tiles, rewritten by title_text.py
ICON_ENTRIES = {281: 280, 327: 326, 485: 484, 403: 402, 405: 404, 451: 450, 453: 452, 479: 478, 481: 480, 487: 486, 489: 488, 539: 538, 541: 540, 547: 546, 549: 548, 555: 554, 557: 556, 573: 572, 575: 574, 735: 734, 737: 736,
                483: 482, 519: 518, 563: 562}      # icon entry -> its palette entry
# com/idcom.bin icons that may be stored larger than the fan's (the container is then laid out again, tools/idcom_icons.py
# relayout): column +8 icons of the arm9 record table, read into a block sized from idcom entry 129 (a static trace of the loaders), so
# their DECODED size may not exceed 2,320 bytes; the decoded size must be the fan's (every fixed buffer sees only that)
IDCOM_GROW = {483: 2320, 519: 2320, 563: 2320}
LOGIC_ICON_ENTRIES = {82: 83, 92: 93, 192: 193}      # com/logic_keyword.bin icon entry -> its palette entry (tools/item_pics.py)
MENU_TILES, MENU_OTHERS = 357, (356, 358)      # jpn/idlocal.bin: the partner card's tiles, and its cells and palette
ITEM_UPCUT = (54, 58, 66, 84, 86, 96, 104, 106, 134, 136, 200, 216, 224, 226, 274, 276)      # jpn/upcut_local.bin pictures tools/item_pics.py re-letters; the palette is entry + 1
# upcut_local pictures drawn by cg_names.py (the keycard log tables): stored literal-only, larger than the fan's stream, which
# the loader allows as long as the decoded size is the fan's; checked by check m like the others, minus the stored-size rule
ITEM_UPCUT_BIG = (210, 242)
UPCUT_FIXED_CAP = 0x2F000      # the picture buffer the cut table's column 1 pictures are streamed into

PLATE_FIRST, PLATE_LAST = 27, 86
# nameplates whose real LZ11 stream cannot fit the fan's slot (dense ink compresses worse than the
# fan's drawing): entry -> the most stored bytes it may take. The slots are 192-256 bytes; these five
# exceed theirs by 4 to 8 bytes (50 Carcerato 232 of 224, 51 Laguarde 228 of 224, 55 Shaun 200 of
# 192, 63 Excelsius 228 of 224, 66 Ringer 200 of 192). The 1.11.1 plates were all stored literal-only
# at 708 bytes and ran, so every one of these is far inside the proven form.
PLATE_STORED_OVER = {50: 232, 51: 228, 55: 200, 63: 228, 66: 200}

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
        if i in IDLOCAL_STORED_BOUNDED:
            if not ps & 0x80000000:
                raise BufCheckError('idlocal entry %d is expected to be an LZ11 stream' % i)
            literal = psize + (psize + 7) // 8 + 4
            if len(stored) > literal:
                raise BufCheckError('idlocal entry %d is stored in %d bytes, over the %d of its literal-only form'
                                    % (i, len(stored), literal))
            got = len(_decode(stored, 'idlocal entry %d' % i))
            if got != psize:
                raise BufCheckError('idlocal entry %d decodes to %d bytes inside its stored bytes, table says %d'
                                    % (i, got, psize))
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
                if i not in CUTOBJ_CHANGED and built[pe[i][0]:pe[i][1]] != fan[fe[i][0]:fe[i][1]]:
                    raise BufCheckError('cutobj_local entry %d is not the fan\'s bytes' % i)
    return out


def check_bigg(built_idl, fan_idl, built_up, fan_up, built_co, fan_co):
    """Check k. -> {('idlocal', 328): (decoded, stored, fan stored), ...}."""
    out = {}
    for name, built, fan, entries in (('idlocal', built_idl, fan_idl, BIGG_IDLOCAL),
                                      ('upcut_local', built_up, fan_up, BIGG_UPCUT),
                                      ('cutobj_local', built_co, fan_co, (BIGG_CUTOBJ, PATCH_CUTOBJ))):
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
                if i not in CUTOBJ_CHANGED and built[pe[i][0]:pe[i][1]] != fan[fe[i][0]:fe[i][1]]:
                    raise BufCheckError('cutobj_local entry %d is not the fan\'s bytes' % i)
    return out


def check_markers(built_co, fan_co):
    """Check l. -> {('cutobj_local', 2): (decoded, stored, fan stored), ...}."""
    import room_names as rn
    pt, ft = _table(built_co), _table(fan_co)
    if len(pt) != len(ft):
        raise BufCheckError('cutobj_local has %d entries, the fan has %d' % (len(pt), len(ft)))
    pe, fe = _extents(pt, len(built_co)), _extents(ft, len(fan_co))
    out = {}
    for i in MARKER_CUTOBJ:
        if i >= len(pt):
            raise BufCheckError('cutobj_local has no entry %d' % i)
        if pt[i][1] != ft[i][1]:
            raise BufCheckError('cutobj_local entry %d: table field %#x, the fan\'s %#x' % (i, pt[i][1], ft[i][1]))
        size = pt[i][1] & 0x7FFFFFFF
        if not pt[i][1] & 0x80000000:
            raise BufCheckError('cutobj_local entry %d is expected to be an LZ11 stream' % i)
        stored = built_co[pe[i][0]:pe[i][1]]
        fan_stored = fe[i][1] - fe[i][0]
        if _stream_size(stored) != size:
            raise BufCheckError('cutobj_local entry %d: stream declares %d bytes, table says %d' % (i, _stream_size(stored), size))
        dec = _decode(stored, 'cutobj_local entry %d' % i)
        if len(dec) != size:
            raise BufCheckError('cutobj_local entry %d decodes to %d bytes, table says %d' % (i, len(dec), size))
        if len(stored) > fan_stored:
            raise BufCheckError('cutobj_local entry %d is stored in %d bytes, over the fan\'s %d' % (i, len(stored), fan_stored))
        if i not in (ROOM_CUTOBJ, BIGG_CUTOBJ):
            fdec = _decode(fan_co[fe[i][0]:fe[i][1]], 'fan cutobj_local entry %d' % i)
            o = struct.unpack_from('<3I', fdec, 0)
            b = rn.Bundle(fdec[o[0]:o[1]], fdec[o[2]:])
            lo, hi = o[2] + b.tile_off, o[2] + b.tile_off + b.tile_len
            if dec[:lo] != fdec[:lo] or dec[hi:] != fdec[hi:]:
                raise BufCheckError('cutobj_local entry %d differs from the fan\'s outside its tile data' % i)
        out[('cutobj_local', i)] = (size, len(stored), fan_stored)
    for i in range(len(pt)):
        if i not in CUTOBJ_CHANGED and built_co[pe[i][0]:pe[i][1]] != fan_co[fe[i][0]:fe[i][1]]:
            raise BufCheckError('cutobj_local entry %d is not the fan\'s bytes' % i)
    return out


def check_plans(built_idl, fan_idl, built_up=None, fan_up=None):
    """Check p. The entries PLAN_IDLOCAL of idlocal and PLAN_UPCUT of upcut_local (tools/plan_labels.py)
    keep the fan's decoded size and table field, are real LZ11 streams that decode to that size, and are
    stored in no more bytes than the fan's entry (entries in PLAN_LARGER and PLAN_UP_LARGER: the slot, not the
    decodable prefix, up to the literal-only form of the decoded size plus 3 alignment bytes); the palette entry after each upcut_local plan is the fan's bytes.
    -> {('idlocal', 349): (decoded, stored, fan stored), ...}."""
    out = {}
    for name, built, fan, entries in (('idlocal', built_idl, fan_idl, PLAN_IDLOCAL),
                                      ('upcut_local', built_up, fan_up, PLAN_UPCUT)):
        if built is None:
            continue
        pt, ft = _table(built), _table(fan)
        if len(pt) != len(ft):
            raise BufCheckError('%s has %d entries, the fan has %d' % (name, len(pt), len(ft)))
        pe, fe = _extents(pt, len(built)), _extents(ft, len(fan))
        for i in entries:
            what = '%s entry %d' % (name, i)
            if i >= len(pt):
                raise BufCheckError('%s has no entry %d' % (name, i))
            if pt[i][1] != ft[i][1]:
                raise BufCheckError("%s: table field %#x, the fan's %#x" % (what, pt[i][1], ft[i][1]))
            size = pt[i][1] & 0x7FFFFFFF
            if not pt[i][1] & 0x80000000:
                raise BufCheckError('%s is expected to be an LZ11 stream' % what)
            stored = built[pe[i][0]:pe[i][1]]
            fan_stored = fe[i][1] - fe[i][0]
            if _stream_size(stored) != size:
                raise BufCheckError('%s: stream declares %d bytes, table says %d' % (what, _stream_size(stored), size))
            got = len(_decode(stored, what))
            if got != size:
                raise BufCheckError('%s decodes to %d bytes, table says %d' % (what, got, size))
            if name == 'upcut_local' and size > UPCUT_BLOCK:
                raise BufCheckError('%s decodes to %d bytes, over the %#x picture block' % (what, size, UPCUT_BLOCK))
            used = len(stored)                      # the slot: what the loader reads into its temp buffer (idlocal)
            if i in (PLAN_LARGER if name == 'idlocal' else PLAN_UP_LARGER):
                bound = size + (size + 7) // 8 + 4 + 3      # the literal-only form, as for idlocal entry 172, and up to 3 alignment bytes
            else:
                bound = fan_stored
            if used > bound:
                raise BufCheckError("%s is stored in %d bytes, over its bound %d (the fan's entry holds %d)"
                                    % (what, used, bound, fan_stored))
            if name == 'upcut_local':
                b_pal, f_pal = built[pe[i + 1][0]:pe[i + 1][1]], fan[fe[i + 1][0]:fe[i + 1][1]]
                if not pt[i + 1][1] & 0x80000000:           # a raw palette: its table size is its length, what follows is the container's 4 byte padding
                    n_pal = pt[i + 1][1] & 0x7FFFFFFF
                    ok_pal = (pt[i + 1][1] == ft[i + 1][1] and b_pal[:n_pal] == f_pal[:n_pal]
                              and not any(b_pal[n_pal:]) and not any(f_pal[n_pal:]))
                else:
                    ok_pal = b_pal == f_pal
                if not ok_pal:
                    raise BufCheckError("%s: the palette entry %d is not the fan's bytes" % (what, i + 1))
            out[(name, i)] = (size, used, fan_stored)
    return out


def check_plan_sprites(built_co, fan_co):
    """Check p (sprites). The entries PLAN_CUTOBJ of jpn/cutobj_local.bin keep the fan's table field and decoded
    size, are real LZ11 streams, are stored in no more bytes than the fan's, and differ from the fan's decoded entry
    only inside the 4bpp tile data; every cutobj_local entry outside CUTOBJ_CHANGED is the fan's bytes.
    -> {('cutobj_local', 12): (decoded, stored, fan stored)}."""
    import room_names as rn
    pt, ft = _table(built_co), _table(fan_co)
    if len(pt) != len(ft):
        raise BufCheckError('cutobj_local has %d entries, the fan has %d' % (len(pt), len(ft)))
    pe, fe = _extents(pt, len(built_co)), _extents(ft, len(fan_co))
    out = {}
    for i in PLAN_CUTOBJ:
        what = 'cutobj_local entry %d' % i
        if i >= len(pt):
            raise BufCheckError('cutobj_local has no entry %d' % i)
        if pt[i][1] != ft[i][1]:
            raise BufCheckError("%s: table field %#x, the fan's %#x" % (what, pt[i][1], ft[i][1]))
        size = pt[i][1] & 0x7FFFFFFF
        if not pt[i][1] & 0x80000000:
            raise BufCheckError('%s is expected to be an LZ11 stream' % what)
        stored = built_co[pe[i][0]:pe[i][1]]
        fan_stored = fe[i][1] - fe[i][0]
        if _stream_size(stored) != size:
            raise BufCheckError('%s: stream declares %d bytes, table says %d' % (what, _stream_size(stored), size))
        dec = _decode(stored, what)
        if len(dec) != size:
            raise BufCheckError('%s decodes to %d bytes, table says %d' % (what, len(dec), size))
        if len(stored) > fan_stored:
            raise BufCheckError("%s is stored in %d bytes, over the fan's %d" % (what, len(stored), fan_stored))
        fdec = _decode(fan_co[fe[i][0]:fe[i][1]], 'fan ' + what)
        o = struct.unpack_from('<3I', fdec, 0)
        b = rn.Bundle(fdec[o[0]:o[1]], fdec[o[2]:])
        lo, hi = o[2] + b.tile_off, o[2] + b.tile_off + b.tile_len
        if dec[:lo] != fdec[:lo] or dec[hi:] != fdec[hi:]:
            raise BufCheckError("%s differs from the fan's outside its tile data" % what)
        out[('cutobj_local', i)] = (size, len(stored), fan_stored)
    for i in range(len(pt)):
        if i not in CUTOBJ_CHANGED and built_co[pe[i][0]:pe[i][1]] != fan_co[fe[i][0]:fe[i][1]]:
            raise BufCheckError("cutobj_local entry %d is not the fan's bytes" % i)
    return out


def check_opening_card(built, fan):
    """Check i on the built and the fan's jpn/opening_local.bin bytes.
    -> (decoded size, stored size, fan's stored size) of entry 13."""
    pt, ft = _table(built), _table(fan)
    if len(pt) != len(ft):
        raise BufCheckError('opening_local has %d entries, the fan has %d' % (len(pt), len(ft)))
    if OPENING_PAL >= len(pt):
        raise BufCheckError('opening_local has no entry %d' % OPENING_PAL)
    pe, fe = _extents(pt, len(built)), _extents(ft, len(fan))

    def blob(d, t, e, i):
        raw = d[e[i][0]:e[i][1]]
        if t[i][1] & 0x80000000:
            return _decode(raw, 'opening_local entry %d' % i)
        return raw[:t[i][1] & 0x7FFFFFFF]

    for i in range(len(pt)):
        if pt[i][1] != ft[i][1]:
            raise BufCheckError('opening_local entry %d: table field %#x, the fan\'s %#x' % (i, pt[i][1], ft[i][1]))
        if i in OPENING_FREE + (OPENING_GFX, OPENING_PAL) or not ft[i][0]:
            continue
        if blob(built, pt, pe, i) != blob(fan, ft, fe, i):
            raise BufCheckError('opening_local entry %d is not the fan\'s data' % i)
    size = pt[OPENING_GFX][1] & 0x7FFFFFFF
    if not pt[OPENING_GFX][1] & 0x80000000:
        raise BufCheckError('opening_local entry %d is expected to be an LZ11 stream' % OPENING_GFX)
    stored = built[pe[OPENING_GFX][0]:pe[OPENING_GFX][1]]
    fan_stored = fe[OPENING_GFX][1] - fe[OPENING_GFX][0]
    if _stream_size(stored) != size:
        raise BufCheckError('opening_local entry %d: stream declares %d bytes, table says %d'
                            % (OPENING_GFX, _stream_size(stored), size))
    g = _decode(stored, 'opening_local entry %d' % OPENING_GFX)
    if len(g) != size:
        raise BufCheckError('opening_local entry %d decodes to %d bytes, table says %d' % (OPENING_GFX, len(g), size))
    if g[:4] != b'RGCN' or struct.unpack_from('<I', g, 8)[0] != size:
        raise BufCheckError('opening_local entry %d is not an RGCN of its own size' % OPENING_GFX)
    if len(stored) > fan_stored:
        raise BufCheckError('opening_local entry %d is stored in %d bytes, over the fan\'s %d'
                            % (OPENING_GFX, len(stored), fan_stored))
    p = blob(built, pt, pe, OPENING_PAL)
    if pt[OPENING_PAL][1] & 0x80000000 or p[:4] != b'RLCN' or len(p) != (ft[OPENING_PAL][1] & 0x7FFFFFFF):
        raise BufCheckError('opening_local entry %d is not an uncompressed RLCN of the fan\'s size' % OPENING_PAL)
    return size, len(stored), fan_stored


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


def _stream_len(st, size, what):
    """Bytes of `st` an LZ11 stream actually uses to decode `size` bytes (smallest prefix that decodes)."""
    lo, hi = 4, len(st)
    try:
        ok = len(lz11.decompress(st)) == size
    except (IndexError, ValueError):
        ok = False
    if not ok:
        raise BufCheckError('%s: the LZ11 stream does not decode to %d bytes inside its %d stored bytes'
                            % (what, size, len(st)))
    while lo < hi:
        mid = (lo + hi) // 2
        try:
            good = len(lz11.decompress(st[:mid])) == size
        except (IndexError, ValueError):
            good = False
        if good:
            hi = mid
        else:
            lo = mid + 1
    return lo


def _tile_span(dec, what):
    """(start, end) of the RGCN tile data inside a decoded icon entry (a sprite bundle of three offsets)
    or a bare RGCN picture (jpn/upcut_local.bin)."""
    if len(dec) < 0x20:
        raise BufCheckError('%s is %d bytes, too short for an icon' % (what, len(dec)))
    g = 0 if dec[:4] == b'RGCN' else struct.unpack_from('<3I', dec, 0)[2]
    if dec[g:g + 4] != b'RGCN':
        raise BufCheckError('%s has no RGCN part at %#x' % (what, g))
    body = g + 16 + 8
    dsize, doff = struct.unpack_from('<II', dec, body + 16)
    return body + doff, body + doff + dsize


def check_idcom_icons(built, fan, entries=None, name='idcom.bin'):
    """Check j on the built and the fan's com/idcom.bin bytes (or, with `entries` and name, another container
    whose icons are written in place the same way: com/logic_keyword.bin).
    -> {icon entry: (decoded size, stream bytes used, fan's stored bytes)}."""
    entries = ICON_ENTRIES if entries is None else entries
    import numpy as np
    import choice_strips as cs
    t = _table(fan)
    ext = _extents(t, len(fan))
    relaid = len(built) != len(fan)
    if relaid:
        # com/idcom.bin laid out again because an icon is stored larger (IDCOM_GROW): the table keeps its slot count, its
        # sizes and its terminator, the data starts right after it, offsets ascend, and every entry that is not an icon
        # is the fan's bytes, moved
        if name != 'idcom.bin':
            raise BufCheckError('%s is %d bytes, the fan\'s %d (the icons are written in place)' % (name, len(built), len(fan)))
        bt = _table(built)
        if len(bt) != len(t):
            raise BufCheckError('%s has %d table slots, the fan\'s %d' % (name, len(bt), len(t)))
        if struct.unpack_from('<I', built, 0)[0] != 8 * len(bt):
            raise BufCheckError('%s: the first offset is not the table length' % name)
        if bt[-1] != (len(built), 0):
            raise BufCheckError('%s: the last slot is %r, expected (file length %d, 0)' % (name, bt[-1], len(built)))
        for ge, cap in sorted(IDCOM_GROW.items()):
            # the cap of the block the column +8 icons are read into, tested on the built table alone (not through the
            # comparison with the fan's size field below, which would make it unreachable)
            if bt[ge][1] & 0x7FFFFFFF > cap:
                raise BufCheckError('%s entry %d: the table says %d decoded bytes, over the %d the column +8 icon block holds'
                                    % (name, ge, bt[ge][1] & 0x7FFFFFFF, cap))
        if [s_ for _o, s_ in bt] != [s_ for _o, s_ in t]:
            raise BufCheckError('%s: a table size field differs from the fan\'s' % name)
        offs = [o for o, _s in bt if o]
        if len(set(offs)) != len({o for o, _s in t if o}):
            raise BufCheckError('%s: the offsets are not the fan\'s set of distinct places' % name)
        if sorted(range(len(bt)), key=lambda i: (t[i][0], i)) != sorted(range(len(bt)), key=lambda i: (bt[i][0], i)):
            raise BufCheckError('%s: the entries are not in the fan\'s order' % name)
        for i in range(len(bt)):
            if t[i][0] and (bt[i][0] - t[i][0]) % 4:
                raise BufCheckError('%s entry %d: the offset moved by %d bytes, not a multiple of four (its alignment would change)'
                                    % (name, i, bt[i][0] - t[i][0]))
        bext = _extents(bt, len(built))
    else:
        if built[:struct.unpack_from('<I', fan, 0)[0]] != fan[:struct.unpack_from('<I', fan, 0)[0]]:
            raise BufCheckError('%s table differs from the fan\'s' % name)
        bext = ext
    touched = set(entries) | set(entries.values())
    if name == 'idcom.bin':
        touched |= set(NURSE_ENTRIES['com/idcom.bin'])          # the nurse's portrait icons (check q)
    for i in range(len(t)):
        a, b = ext[i]
        ba, bb = bext[i]
        if i not in touched and built[ba:bb] != fan[a:b]:
            raise BufCheckError('%s entry %d is not the fan\'s bytes' % (name, i))
    out = {}
    for e, pe in sorted(entries.items()):
        what = '%s entry %d' % (name, e)
        a, b = ext[e]
        ba, bb = bext[e]
        if not t[e][1] & 0x80000000:
            raise BufCheckError('%s is expected to be an LZ11 stream' % what)
        size = t[e][1] & 0x7FFFFFFF
        st, fst = built[ba:bb], fan[a:b]
        if _stream_size(st) != size:
            raise BufCheckError('%s: stream declares %d bytes, table says %d' % (what, _stream_size(st), size))
        used = _stream_len(st, size, what)
        dec = lz11.decompress(st)
        fdec = lz11.decompress(fst)
        if len(dec) != len(fdec):
            raise BufCheckError('%s decodes to %d bytes, the fan\'s to %d' % (what, len(dec), len(fdec)))
        if used > len(fst):
            if not (relaid and name == 'idcom.bin' and e in IDCOM_GROW):
                raise BufCheckError('%s is stored in %d bytes, over the fan\'s %d' % (what, used, len(fst)))
            if len(dec) > IDCOM_GROW[e]:
                raise BufCheckError('%s decodes to %d bytes, over the %d the column +8 icon block holds'
                                    % (what, len(dec), IDCOM_GROW[e]))
        s0, s1 = _tile_span(dec, what)
        if (s0, s1) != _tile_span(fdec, what):
            raise BufCheckError('%s: the tile data moved' % what)
        if dec[:s0] != fdec[:s0] or dec[s1:] != fdec[s1:]:
            raise BufCheckError('%s differs from the fan\'s outside its tile data' % what)
        if (np.array(cs.grid(dec), np.uint8) == 0).any():
            raise BufCheckError('%s draws index 0, the transparent key' % what)
        pa, pb = ext[pe]
        qa, qb = bext[pe]
        pw, pf = built[qa:qb], fan[pa:pb]
        if len(pw) != 90 or pw[:4] != b'RLCN':
            raise BufCheckError('%s palette entry %d is not the fan\'s 90-byte RLCN' % (name, pe))
        ttlp = pf.find(b'TTLP')
        c0 = ttlp + 8 + 16
        if pw[:c0 + 2] != pf[:c0 + 2] or pw[c0 + 32:] != pf[c0 + 32:]:
            raise BufCheckError('%s palette entry %d differs from the fan\'s outside colours 1-15' % (name, pe))
        out[e] = (len(dec), used, len(fst))
    return out


def check_plates(built, fan):
    """Check k on the built and the fan's jpn/idlocal.bin bytes.
    -> {entry: (decoded size, stored extent, fan's extent)} for the redrawn plates."""
    from plates import PLATES
    from nitro import ncgr
    pt, ft = _table(built), _table(fan)
    if len(pt) != len(ft):
        raise BufCheckError('idlocal has %d entries, the fan has %d' % (len(pt), len(ft)))
    pe, fe = _extents(pt, len(built)), _extents(ft, len(fan))
    out = {}
    for i in range(PLATE_FIRST, PLATE_LAST + 1):
        what = 'nameplate %d' % i
        stored, fstored = built[pe[i][0]:pe[i][1]], fan[fe[i][0]:fe[i][1]]
        if i not in PLATES:
            if stored != fstored:
                raise BufCheckError("%s is not the fan's bytes (only plates.PLATES may change)" % what)
            continue
        if pt[i][1] != ft[i][1]:
            raise BufCheckError("%s: table field %#x, the fan's %#x" % (what, pt[i][1], ft[i][1]))
        size = pt[i][1] & 0x7FFFFFFF
        if not pt[i][1] & 0x80000000:
            raise BufCheckError('%s is expected to be an LZ11 stream' % what)
        if _stream_size(stored) != size:
            raise BufCheckError('%s: stream declares %d bytes, table says %d' % (what, _stream_size(stored), size))
        _stream_len(stored, size, what)
        dec, fdec = lz11.decompress(stored), lz11.decompress(fstored)
        if len(dec) != len(fdec):
            raise BufCheckError("%s decodes to %d bytes, the fan's to %d" % (what, len(dec), len(fdec)))
        tiles = ncgr(fdec)[0]
        pos = fdec.find(tiles)
        if pos <= 0 or dec[:pos] != fdec[:pos] or dec[pos + len(tiles):] != fdec[pos + len(tiles):]:
            raise BufCheckError("%s differs from the fan's outside its tile data" % what)
        extent, fextent = pe[i][1] - pe[i][0], fe[i][1] - fe[i][0]
        limit = PLATE_STORED_OVER.get(i, fextent)
        if limit < fextent or limit > _lz11_literal_bound(size):
            raise BufCheckError("%s: PLATE_STORED_OVER allows %d, outside the fan's %d .. literal-only %d"
                                % (what, limit, fextent, _lz11_literal_bound(size)))
        if extent > limit:
            raise BufCheckError("%s is stored in %d bytes, over its %d (the fan's slot is %d)" % (what, extent, limit, fextent))
        out[i] = (len(dec), extent, fextent)
    if set(out) != set(PLATES):
        raise BufCheckError('nameplates checked %s, expected %s' % (sorted(out), sorted(PLATES)))
    return out


def check_item_pics(built_up, fan_up):
    """Check m. The item pictures tools/item_pics.py re-letters in jpn/upcut_local.bin (ITEM_UPCUT, each with its
    palette in the next entry). Each must keep the fan's table field (decoded size, compressed flag), be a real
    LZ11 stream that declares and decodes to exactly that size, be stored in no more bytes than the fan's entry
    (ITEM_UPCUT_BIG, the keycard log pictures, are exempt from that one rule),
    keep the fan's palette entry byte for byte, and differ from the fan's picture only inside its tile data.
    -> {entry: (decoded size, stream bytes used, fan's stored bytes)}."""
    pt, ft = _table(built_up), _table(fan_up)
    if len(pt) != len(ft):
        raise BufCheckError('upcut_local has %d entries, the fan has %d' % (len(pt), len(ft)))
    pe, fe = _extents(pt, len(built_up)), _extents(ft, len(fan_up))
    out = {}
    for e in ITEM_UPCUT + ITEM_UPCUT_BIG:
        what = 'upcut_local entry %d' % e
        if pt[e][1] & 0x7FFFFFFF > UPCUT_FIXED_CAP:
            raise BufCheckError('%s: the table says %d decoded bytes, over the %d picture buffer'
                                % (what, pt[e][1] & 0x7FFFFFFF, UPCUT_FIXED_CAP))
        if pt[e][1] != ft[e][1]:
            raise BufCheckError('%s: table field %#x, the fan\'s %#x' % (what, pt[e][1], ft[e][1]))
        size = pt[e][1] & 0x7FFFFFFF
        if not pt[e][1] & 0x80000000:
            raise BufCheckError('%s is expected to be an LZ11 stream' % what)
        stored = built_up[pe[e][0]:pe[e][1]]
        fstored = fan_up[fe[e][0]:fe[e][1]]
        if _stream_size(stored) != size:
            raise BufCheckError('%s: stream declares %d bytes, table says %d' % (what, _stream_size(stored), size))
        used = _stream_len(stored, size, what)
        dec, fdec = lz11.decompress(stored), lz11.decompress(fstored)
        if len(dec) != len(fdec):
            raise BufCheckError('%s decodes to %d bytes, the fan\'s to %d' % (what, len(dec), len(fdec)))
        if used > len(fstored) and e not in ITEM_UPCUT_BIG:
            raise BufCheckError('%s is stored in %d bytes, over the fan\'s %d' % (what, used, len(fstored)))
        s0, s1 = _tile_span(dec, what)
        if (s0, s1) != _tile_span(fdec, what):
            raise BufCheckError('%s: the tile data moved' % what)
        if dec[:s0] != fdec[:s0] or dec[s1:] != fdec[s1:]:
            raise BufCheckError('%s differs from the fan\'s outside its tile data' % what)
        if pt[e + 1][1] != ft[e + 1][1]:
            raise BufCheckError('upcut_local entry %d: table field %#x, the fan\'s %#x' % (e + 1, pt[e + 1][1], ft[e + 1][1]))
        pal = built_up[pe[e + 1][0]:pe[e + 1][1]]
        fpal = fan_up[fe[e + 1][0]:fe[e + 1][1]]
        if pt[e + 1][1] & 0x80000000:
            pal, fpal = lz11.decompress(pal), lz11.decompress(fpal)
        else:
            pal, fpal = pal[:pt[e + 1][1]], fpal[:ft[e + 1][1]]
        if pal != fpal:
            raise BufCheckError('upcut_local palette entry %d is not the fan\'s bytes' % (e + 1))
        out[e] = (size, used, len(fstored))
    return out


def check_menu_button(built_idl, fan_idl):
    """Check n. The partner card's button text (tools/menu_button.py): jpn/idlocal.bin entry 357 (the card's tiles) keeps the
    fan's table field, is a real LZ11 stream that declares and decodes to that size, is stored in no more bytes than the fan's
    entry and differs from it only in its tile data; the cells (356) and the palette (358) are the fan's bytes.
    -> (decoded size, stream bytes used, fan's stored bytes)."""
    pt, ft = _table(built_idl), _table(fan_idl)
    if len(pt) != len(ft):
        raise BufCheckError('idlocal has %d entries, the fan has %d' % (len(pt), len(ft)))
    pe, fe = _extents(pt, len(built_idl)), _extents(ft, len(fan_idl))
    e = MENU_TILES
    if pt[e][1] != ft[e][1]:
        raise BufCheckError('idlocal entry %d: table field %#x, the fan\'s %#x' % (e, pt[e][1], ft[e][1]))
    size = pt[e][1] & 0x7FFFFFFF
    if not pt[e][1] & 0x80000000:
        raise BufCheckError('idlocal entry %d is expected to be an LZ11 stream' % e)
    stored, fstored = built_idl[pe[e][0]:pe[e][1]], fan_idl[fe[e][0]:fe[e][1]]
    if _stream_size(stored) != size:
        raise BufCheckError('idlocal entry %d: stream declares %d bytes, table says %d' % (e, _stream_size(stored), size))
    used = _stream_len(stored, size, 'idlocal entry %d' % e)
    dec, fdec = lz11.decompress(stored), lz11.decompress(fstored)
    if len(dec) != len(fdec):
        raise BufCheckError('idlocal entry %d decodes to %d bytes, the fan\'s to %d' % (e, len(dec), len(fdec)))
    if used > len(fstored):
        raise BufCheckError('idlocal entry %d is stored in %d bytes, over the fan\'s %d' % (e, used, len(fstored)))
    s0, s1 = _tile_span(dec, 'idlocal entry %d' % e)
    if (s0, s1) != _tile_span(fdec, 'fan idlocal entry %d' % e):
        raise BufCheckError('idlocal entry %d: the tile data moved' % e)
    if dec[:s0] != fdec[:s0] or dec[s1:] != fdec[s1:]:
        raise BufCheckError('idlocal entry %d differs from the fan\'s outside its tile data' % e)
    for o in MENU_OTHERS:
        if pt[o][1] != ft[o][1]:
            raise BufCheckError('idlocal entry %d: table field %#x, the fan\'s %#x' % (o, pt[o][1], ft[o][1]))
        a, b = built_idl[pe[o][0]:pe[o][1]], fan_idl[fe[o][0]:fe[o][1]]
        if pt[o][1] & 0x80000000:
            a, b = lz11.decompress(a), lz11.decompress(b)
        else:
            a, b = a[:pt[o][1]], b[:ft[o][1]]
        if a != b:
            raise BufCheckError('idlocal entry %d is not the fan\'s bytes' % o)
    return size, used, len(fstored)


def check_nurse(cont, built, fan):
    """Check q on one container. -> {entry: (decoded size, stream bytes used, fan's stored bytes)}."""
    entries = NURSE_ENTRIES[cont]
    t = _table(fan)
    ext = _extents(t, len(fan))
    if cont == 'com/idcom.bin':
        # the item icons may lay this file out again (check j proves that layout, and that every entry apart from
        # the icons it lists and these two is the fan's bytes): read the nurse's entries through the built table
        bt = _table(built)
        if len(bt) != len(t):
            raise BufCheckError('%s has %d table slots, the fan\'s %d' % (cont, len(bt), len(t)))
        bext = _extents(bt, len(built))
        for e in sorted(entries):
            if bt[e][1] != t[e][1]:
                raise BufCheckError('%s entry %d: table field %#x, the fan\'s %#x' % (cont, e, bt[e][1], t[e][1]))
            if bext[e][1] - bext[e][0] != ext[e][1] - ext[e][0]:
                raise BufCheckError('%s entry %d slot is %d bytes, the fan\'s %d'
                                    % (cont, e, bext[e][1] - bext[e][0], ext[e][1] - ext[e][0]))
    else:
        if len(built) != len(fan):
            raise BufCheckError('%s is %d bytes, the fan\'s %d (the nurse\'s cap is written in place)'
                                % (cont, len(built), len(fan)))
        tlen = struct.unpack_from('<I', fan, 0)[0]
        if built[:tlen] != fan[:tlen]:
            raise BufCheckError('%s table differs from the fan\'s' % cont)
        bext = ext
        for i in range(len(t)):
            a, b = ext[i]
            if i not in entries and built[a:b] != fan[a:b]:
                raise BufCheckError('%s entry %d is not the fan\'s bytes' % (cont, i))
    out = {}
    for e in sorted(entries):
        what = '%s entry %d' % (cont, e)
        a, b = ext[e]
        if not t[e][1] & 0x80000000:
            raise BufCheckError('%s is expected to be an LZ11 stream' % what)
        size = t[e][1] & 0x7FFFFFFF
        st, fst = built[bext[e][0]:bext[e][1]], fan[a:b]
        if _stream_size(st) != size:
            raise BufCheckError('%s: stream declares %d bytes, table says %d' % (what, _stream_size(st), size))
        used = _stream_len(st, size, what)
        dec, fdec = _decode(st, what), _decode(fst, what + ' (fan)')
        if len(dec) != len(fdec):
            raise BufCheckError('%s decodes to %d bytes, the fan\'s to %d' % (what, len(dec), len(fdec)))
        # (no 'used > len(fst)' test: the stream is read from a slot of exactly the fan's size, in place
        # or checked above, so used <= len(st) == len(fst) always; the real bound is that the stream
        # decodes to the table's size inside that slot, which _stream_len raises on)
        s0, s1 = _tile_span(dec, what)
        if (s0, s1) != _tile_span(fdec, what + ' (fan)'):
            raise BufCheckError('%s: the tile data moved' % what)
        if dec[:s0] != fdec[:s0] or dec[s1:] != fdec[s1:]:
            raise BufCheckError('%s differs from the fan\'s outside its tile data' % what)
        if cont == 'com/idcom.bin':
            # 4 bpp: a nibble the fan drew must not become 0
            for k in range(s0, s1):
                for sh in (0, 4):
                    if (fdec[k] >> sh) & 15 and not (dec[k] >> sh) & 15:
                        raise BufCheckError('%s: a drawn pixel became index 0 (the transparent key)' % what)
        else:
            for k in range(s0, s1):
                if fdec[k] and not dec[k]:
                    raise BufCheckError('%s: a drawn pixel became index 0 (the transparent key)' % what)
        out[e] = (len(dec), used, len(fst))
    return out


def _rgcn_pixels(dec, what):
    """(start, end) of the pixel data of a raw RGCN picture."""
    if dec[:4] != b'RGCN' or dec[16:20] != b'RAHC':
        raise BufCheckError('%s is not an RGCN picture' % what)
    body = 24
    dsize, doff = struct.unpack_from('<II', dec, body + 16)
    if body + doff + dsize > len(dec):
        raise BufCheckError('%s: RGCN data runs past the entry' % what)
    return body + doff, body + doff + dsize


def check_signs(cont, built, fan):
    """Check s on one container. -> {entry: (decoded size, stream bytes used, fan's stored bytes)}."""
    entries = SIGN_ENTRIES[cont]
    t = _table(fan)
    ext = _extents(t, len(fan))
    if cont in SIGN_REBUILT:
        bt = _table(built)
        bext = _extents(bt, len(built))
        if len(bt) != len(t):
            raise BufCheckError('%s has %d entries, the fan\'s %d' % (cont, len(bt), len(t)))
        for e in sorted(entries):
            if bt[e][1] != t[e][1]:
                raise BufCheckError('%s entry %d table field %#x, the fan\'s %#x' % (cont, e, bt[e][1], t[e][1]))
            if bext[e][1] - bext[e][0] != ext[e][1] - ext[e][0]:
                raise BufCheckError('%s entry %d slot is %d bytes, the fan\'s %d'
                                    % (cont, e, bext[e][1] - bext[e][0], ext[e][1] - ext[e][0]))
    else:
        bext = ext
        if len(built) != len(fan):
            raise BufCheckError('%s is %d bytes, the fan\'s %d (the pictures are written in place)'
                                % (cont, len(built), len(fan)))
        tlen = struct.unpack_from('<I', fan, 0)[0]
        if built[:tlen] != fan[:tlen]:
            raise BufCheckError('%s table differs from the fan\'s' % cont)
        for i in range(len(t)):
            a, b = ext[i]
            if i not in entries and built[a:b] != fan[a:b]:
                raise BufCheckError('%s entry %d is not the fan\'s bytes' % (cont, i))
    out = {}
    for e in sorted(entries):
        what = '%s entry %d' % (cont, e)
        a, b = ext[e]
        if not t[e][1] & 0x80000000:
            raise BufCheckError('%s is expected to be an LZ11 stream' % what)
        size = t[e][1] & 0x7FFFFFFF
        st, fst = built[bext[e][0]:bext[e][1]], fan[a:b]
        if _stream_size(st) != size:
            raise BufCheckError('%s: stream declares %d bytes, table says %d' % (what, _stream_size(st), size))
        used = _stream_len(st, size, what)
        dec, fdec = _decode(st, what), _decode(fst, what + ' (fan)')
        if len(dec) != len(fdec):
            raise BufCheckError('%s decodes to %d bytes, the fan\'s to %d' % (what, len(dec), len(fdec)))
        # (no 'used > len(fst)' test: the stream is read from a slot of exactly the fan's size, in place
        # or checked above, so used <= len(st) == len(fst) always; the real bound is that the stream
        # decodes to the table's size inside that slot, which _stream_len raises on)
        s0, s1 = _rgcn_pixels(dec, what)
        if (s0, s1) != _rgcn_pixels(fdec, what + ' (fan)'):
            raise BufCheckError('%s: the pixel data moved' % what)
        if dec[:s0] != fdec[:s0] or dec[s1:] != fdec[s1:]:
            raise BufCheckError('%s differs from the fan\'s outside its pixel data' % what)
        out[e] = (len(dec), used, len(fst))
    return out


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
    with open(os.path.join(dumpdir, 'ds_fan', 'jpn', 'opening_local.bin'), 'rb') as f:
        fan_opening = f.read()
    i_size, i_stored, i_fan = check_opening_card(rom_file(rom, 'jpn/opening_local.bin'), fan_opening)
    with open(os.path.join(dumpdir, 'ds_fan', 'com', 'idcom.bin'), 'rb') as f:
        fan_idcom = f.read()
    j_icons = check_idcom_icons(rom_file(rom, 'com/idcom.bin'), fan_idcom)
    js = ', '.join('%d decodes to %d like the fan, stream %d of the fan\'s %d' % ((k,) + v) for k, v in sorted(j_icons.items()))
    k_plates = check_plates(rom_file(rom, 'jpn/idlocal.bin'), fan)
    k_over = sorted(i for i, v in k_plates.items() if v[1] > v[2])
    ks = ("%d redrawn nameplates decode to the fan's size and differ only in tile data, %d stored inside the fan's slot, "
          "%d over it (%s), the other plate slots are the fan's bytes"
          % (len(k_plates), len(k_plates) - len(k_over), len(k_over),
             ', '.join('%d: %d of %d' % (i, k_plates[i][1], k_plates[i][2]) for i in k_over) or 'none'))
    with open(os.path.join(dumpdir, 'ds_fan', 'jpn', 'upcut_local.bin'), 'rb') as f:
        fan_up = f.read()
    k_ent = check_bigg(rom_file(rom, 'jpn/idlocal.bin'), fan, rom_file(rom, 'jpn/upcut_local.bin'), fan_up,
                       rom_file(rom, 'jpn/cutobj_local.bin'), fan_co)
    obs = ', '.join('%s %d decodes %d, stored %d of the fan\'s %d' % ((k[0], k[1]) + v) for k, v in sorted(k_ent.items()))
    l_ent = check_markers(rom_file(rom, 'jpn/cutobj_local.bin'), fan_co)
    cutchg = '(%s)' % ' '.join(str(e) for e in CUTOBJ_CHANGED)
    ls = ', '.join('entry %d decodes %d, stored %d of the fan\'s %d' % ((k[1],) + v) for k, v in sorted(l_ent.items()))
    with open(os.path.join(dumpdir, 'ds_fan', 'com', 'logic_keyword.bin'), 'rb') as f:
        fan_lk = f.read()
    m_up = check_item_pics(rom_file(rom, 'jpn/upcut_local.bin'), fan_up)
    n_btn = check_menu_button(rom_file(rom, 'jpn/idlocal.bin'), fan)
    m_lk = check_idcom_icons(rom_file(rom, 'com/logic_keyword.bin'), fan_lk, LOGIC_ICON_ENTRIES, 'logic_keyword.bin')
    ms = ', '.join('upcut_local %d decodes to %d like the fan, stream %d of the fan\'s %d' % ((k,) + v) for k, v in sorted(m_up.items()))
    p_ent = check_plans(rom_file(rom, 'jpn/idlocal.bin'), fan, rom_file(rom, 'jpn/upcut_local.bin'), fan_up)
    p_ent.update(check_plan_sprites(rom_file(rom, 'jpn/cutobj_local.bin'), fan_co))
    ps_ = ', '.join("%s %d decodes %d, stored %d of the fan's %d" % ((k[0], k[1]) + v) for k, v in sorted(p_ent.items()))
    ms += '; logic_keyword.bin in place: ' + ', '.join('%d decodes to %d, stream %d of the fan\'s %d' % ((k,) + v) for k, v in sorted(m_lk.items()))
    nparts = []
    for cont in sorted(NURSE_ENTRIES):
        with open(os.path.join(dumpdir, 'ds_fan', *cont.split('/')), 'rb') as f:
            fan_c = f.read()
        for k, v in sorted(check_nurse(cont, rom_file(rom, cont), fan_c).items()):
            nparts.append('%s %d decodes to %d like the fan, stream %d of the fan\'s %d' % ((cont, k) + v))
    sparts = []
    for cont in sorted(SIGN_ENTRIES):
        with open(os.path.join(dumpdir, 'ds_fan', *cont.split('/')), 'rb') as f:
            fan_c = f.read()
        for k, v in sorted(check_signs(cont, rom_file(rom, cont), fan_c).items()):
            sparts.append('%s %d decodes to %d like the fan, stream %d of the fan\'s %d' % ((cont, k) + v))
    return ('%s; (f) logic cards: %d checked, every OBJ inside the RGCN bytes, cards with OBJs past the '
            'declared data (rewritten, no fan tail): %s, %d punctuation-matched name cards rewritten; (g) modelitemlocal entry %d decodes to %d bytes like '
            "the fan's, stored %d of the fan's %d, the other entries are the fan's bytes; "
            "(h) room names: %s, the cutobj_local entries outside %s are the fan's bytes; "
            "(i) opening_local entry %d decodes to %d bytes like the fan's, stored %d of the fan's %d, "
            "every table field the fan's; "
            "(j) idcom.bin icons written in place, or the file laid out again when an icon is stored larger (table slots and "
            "sizes, order, alignment and every other entry the fan's), icons: %s; "
            "(k) nameplates: %s; "
            "(l) marker letters (cutobj_local), tile data only in the entries no other step changes: %s; "
            "(m) item pictures, same decoded size, stored no larger (the two keycard log pictures excepted), palette the fan's: %s; "
            "(n) menu button: idlocal %d decodes to %d like the fan, stream %d of the fan's %d; "
            "(o) Bigg Building: %s, the cutobj_local entries outside %s are the fan's bytes; "
            "(p) map pieces and plans in Capcom's wording: %s; "
            "(q) the nurse's cap written in place (com/idcom.bin read through its own table), every other entry the fan's: %s; "
            "(s) background signs written in place, tables and every other entry the fan's: %s"
            % (line, n, ps, n_named, MODEL_ENTRY, g_size, g_stored, g_fan, hs, cutchg,
               OPENING_GFX, i_size, i_stored, i_fan, js, ks, ls, ms, MENU_TILES, n_btn[0], n_btn[1], n_btn[2],
               obs, cutchg, ps_, ', '.join(nparts), ', '.join(sparts)))


if __name__ == '__main__':
    print(run(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else 'dump'))
