# -*- coding: utf-8 -*-
"""Mind Chess banner (jpn/idlocal.bin entry 25): redraw the fan's "Logic Chess"
name-row and "Complete" end-row art as "Mind Chess" / "Checkmate", using
Capcom's own English Logic Chess title letters harvested from the player's
Collection install at build time. Nothing Capcom-owned ships with this tool.

Container: entry 25 is a self-contained sprite bundle (RECN cells + RNAN
animation + RGCN tiles, palette shared with idlocal entry 24), 45 NCER cells
= 11 single-object shapes x 4 palette banks + one blank filler. Cells 0-10
are the palette-bank-0 ("red") set: 0/1/2 used to hold "Lo"/"gi"/"c", 3/4/5
"Ch"/"es"/"s", 6 a blank piece (placed by two sequences, drawn empty), 7/8 "Be"/"gin", 9 "Co", and cell 10
carries TWO OAM objects at once, tile fields 160 and 176, which used to hold
the two pieces of "mplete". The same tile ids are shared across all 4
palette banks, so each tile only needs its pixels drawn once.

RNAN: every one of entry 25's 18 named animation sequences uses element type
1 (cell index + rotation + scale + a per-frame x/y). Each visible piece is
placed at its OWN animation-supplied screen position (px, py) EVERY frame,
plus that cell's own OAM x/y offset, plus a +32/+32 shift on any OAM entry
that has the double-size affine flag set (all of entry 25's do). This was
confirmed by writing a compositor that reads the animation's real resting
(px, py) per cell together with the OAM data; on the fan's data it assembles
"Begin / Logic Chess" and "Logic Chess / Complete" with every piece in place
(checked against the data by an independent parser, not against a capture).
An earlier attempt that assumed OAM x alone (with a fixed spacing guessed
from the tile field number) placed the pieces wrong - "Mind" overlapping
itself, "Checkmate" reading "Check mate" - because it ignored the animation's
per-frame position entirely. The animation itself is NOT edited anywhere in
this module: only OAM x (never y, never the RNAN frame data) and tile pixels
change, per cell.

Design (all measured against entry 25's own real screen positions - a
verified renderer, not a mock, produced every number below):
  - The fan's shipped "Logic" ink spans screen x -108 to -9 (100px); "Chess"
    (cells 3/4/5, untouched pixels) spans 0 to 107 (108px); the two words
    sit only 9px apart. "Complete" (cell 9 + cell 10's two objects) spans
    -77 to 75 (153px) - NOT a clean 192px fill; there is no hard budget.
  - "Mind" (Capcom letters M/i/n/d, sheared to the fan's own italic lean) is
    about 109px of real ink, split M / in / d into cells 0/1/2 the way the
    fan split "Logic" into Lo/gi/c. Letters are spaced by ink, not by their
    (wider, because sheared) crop boxes: OPTICAL_GAP is the fan's own
    tightest row-wise approach between adjacent letter groups in "Chess"
    (measured off the renderer, about -3 to -5px, i.e. already overlapping),
    applied the same way between M/i/n/d. Its baseline is placed to land on
    the same real screen row as "Chess" (both cap-height glyphs, matched by
    measuring the fan's own baseline row off the renderer, not assumed).
    "Checkmate" (Check+mate joined at CHECKMATE_GAP, closing the visual gap
    those two pre-rendered word images otherwise leave between "k" and "m";
    condensed to 192px, about 85.7% of their 224px joined width) is split
    into three 64px slices across cell 9 and cell 10's two objects, the way
    the fan split "Complete" into Co/mplete.
  - Each redrawn cell's OAM x is set so that group's real screen position
    equals the layout below (LAYOUT selects which); "Chess" keeps its own
    pixels and is only shifted by a constant OAM x delta, same for all
    three of its cells (preserves the fan's own internal Ch/es/s kerning).
  - Two layouts are implemented, picked by the LAYOUT constant below:
    (A) "Mind Chess" centred on the same centre as the fan's "Logic Chess"
        (about x=0), WORD_GAP between the two words' ink.
    (B) "Mind" left edge at Logic's own old left edge (-108), "Chess" moved
        right by the same WORD_GAP (B runs past the screen edge and is not
        used). WORD_GAP=10 is close to the fan's own "Logic"/"Chess" gap
        (8 to 9 blank columns between the words' ink).

Harvesting matches title_assets.py's own extract/apply split: extract() runs
once against the player's Collection install and caches cropped PNGs under
dump/title/mindchess/, raising if the bundle or the needed sprites are not
found (same convention as the other title extractors) so a real extract
never silently produces a game missing this art. apply()/patch() only ever
read that cache. required() lists the cached images, so build.py stops a
--skip-extract build on an older dump that lacks them ("run once without
--skip-extract"); only a direct call to patch()/apply_to_rom() without the
cache logs the reason and returns entry 25 unchanged.

No rig capture of this redraw has been made; every number here comes from
the tile/animation data and the renderer above, not from a screenshot.
"""
import os, sys, glob, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image
from choice_strips import Idlocal, rebuild, rom_file
from nitro import _sections as nitro_sections

BUNDLE_PREFIX = 'gk2_logicchess_trial_assets_all_'
ATLAS_NAME = 'logicchess_title_eng'
CACHE_DIRNAME = 'mindchess'

LETTER_SPRITE = {'M': 0, 'i': 1, 'n': 2, 'd': 3}
WORD_SPRITE = {'check': 11, 'mate': 12}

SCALE = 0.229            # Capcom cap-height -> fan cap-height
SHEAR = 0.16             # fan's own italic lean, measured off "Be"
ALPHA_MIN = 26           # ~0.1 of 255, same gate the choice-strip lettering uses
LUM_THRESH = 128

FILL_IDX, OUTLINE_IDX = 1, 11

# ---- real screen positions, off entry 25's own animation + OAM data -------
# tile field -> resting screen x of that field's cell/object (see docstring;
# start-row and end-row differ by at most 1px for the name-row cells, which
# is folded in here rather than kept as two near-identical tables).
TX = {0: -81, 16: -54, 32: -26, 48: 0, 64: 24, 80: 48, 144: -40, 160: 26, 176: 26}
DBL_ADJ = 32              # every one of entry 25's OAM objects sets the double-size
                          # affine flag, which adds this to the real screen position
                          # on top of (cell px) + (OAM x); confirmed on all fields
                          # via the renderer, not assumed
BASELINE_ROW = 51         # local row (0-63) inside a name-row tile where a cap-height
                          # glyph's baseline must sit to land on the SAME real screen
                          # row as "Chess" (measured 50, unmoved) once placed through
                          # (tile field's ty=31, OAM y=-64, DBL_ADJ); an earlier build
                          # bottom-flush-pasted each group at local row 63, 12-13px too
                          # low, which read as "Mind" sitting lower than "Chess"
NAME_FIELDS = (0, 16, 32)
CHESS_FIELDS = (48, 64, 80)
END_FIELDS = (144, 160, 176)

CHESS_SPAN = (0, 107)     # fan's own "Ch".."s" ink span, measured, pixels untouched
CHESS_WIDTH = CHESS_SPAN[1] - CHESS_SPAN[0] + 1
LOGIC_SPAN = (-108, -9)   # fan's own "Lo".."c" ink span, measured (layout B only)
END_WIDTH = 192           # "Checkmate" condense target: joined width condenses to
                          # this (see CHECKMATE_GAP for the joined width and ratio);
                          # not a hard fill, just a width that reads clearly
CHECKMATE_START = -96     # centres "Checkmate" on "Complete"'s own old centre (~0)
WORD_GAP = 10             # ink-to-ink gap between "Mind" and "Chess", both layouts;
                          # close to the fan's own "Logic"/"Chess" gap (8 to 9 blank
                          # columns between the words' ink)

# name-row layout: pick 'A' or 'B' and rebuild; both are fully computed at
# build time from the ACTUAL harvested letter widths (not a fixed guess), so
# this is the only line that needs to change to switch.
#   'A': "Mind Chess" centred on the same centre as the fan's "Logic Chess"
#   'B': "Mind" left edge at Logic's own old left edge (LOGIC_SPAN[0])
LAYOUT = 'A'


# ---- harvesting (extract-time, needs the Collection install) --------------
def cache_dir(dumpdir):
    return os.path.join(dumpdir, 'title', CACHE_DIRNAME)


def required(dumpdir):
    """The harvested letter images apply_to_rom() needs."""
    names = ['letter_%s' % c for c in LETTER_SPRITE] + ['word_%s' % w for w in WORD_SPRITE]
    return [os.path.join(cache_dir(dumpdir), n + '.png') for n in names]


def extract(bdir, dumpdir):
    """Pull M/i/n/d and Check/mate out of the Collection's Logic Chess bundle
    into dump/title/mindchess/. Raises SystemExit if the bundle or any needed
    sprite is missing, same convention as the other title-asset extractors -
    a real extract should never silently ship without this banner."""
    hits = [p for p in glob.glob(os.path.join(bdir, '*.bundle'))
            if os.path.basename(p).lower().startswith(BUNDLE_PREFIX)]
    if not hits:
        raise SystemExit('mindchess: no bundle starting with %r in %s' % (BUNDLE_PREFIX, bdir))
    import UnityPy
    env = UnityPy.load(hits[0])
    found = {}
    for obj in env.objects:
        if obj.type.name != 'Sprite':
            continue
        d = obj.read()
        name = getattr(d, 'm_Name', None)
        if not name or not name.startswith('LogicChess_Title_R_'):
            continue
        try:
            atlas = d.m_SpriteAtlas.read().m_Name
        except Exception:
            continue
        if atlas and atlas.lower() == ATLAS_NAME:
            found[name] = d
    need = {'letter_%s' % c: 'LogicChess_Title_R_%02d' % i for c, i in LETTER_SPRITE.items()}
    need.update({'word_%s' % w: 'LogicChess_Title_R_%02d' % i for w, i in WORD_SPRITE.items()})
    missing = [srcname for srcname in need.values() if srcname not in found]
    if missing:
        raise SystemExit('mindchess: sprites missing from %s: %s'
                          % (os.path.basename(hits[0]), missing))
    out = cache_dir(dumpdir)
    os.makedirs(out, exist_ok=True)
    for outname, srcname in need.items():
        im = found[srcname].image.convert('RGBA')
        bbox = im.getbbox()
        if bbox:
            im = im.crop(bbox)
        im.save(os.path.join(out, outname + '.png'))
    return out


# ---- glyph pipeline (apply-time, cache only, no bdir needed) ---------------
def _load(dumpdir, name):
    p = os.path.join(cache_dir(dumpdir), name + '.png')
    if not os.path.exists(p):
        return None
    return Image.open(p).convert('RGBA')


def _crop(im):
    bbox = im.getbbox()
    return im.crop(bbox) if bbox else im


def _shear(im, k=SHEAR):
    """Top-right/bottom-left lean, matching the fan's own italic glyphs (measured
    on the fan's "L" stem in the screen render: top x=11 at row14, bottom x=5 at
    row48, dx/dy about -0.16). An earlier version of this function anchored the
    TOP and shifted the bottom right instead - backwards - which was not obvious
    on "M" (its own diagonal legs happened to partly cancel the error) but was
    confirmed wrong with a plain vertical test line before this fix. Bottom is
    now the anchor; the top shifts right by k*h."""
    w, h = im.size
    pad = int(h * k) + 2
    out = Image.new('RGBA', (w + pad, h), (0, 0, 0, 0))
    out.paste(im, (0, 0))
    return out.transform((w + pad, h), Image.AFFINE,
                          (1, k, -k * h, 0, 1, 0), resample=Image.BICUBIC)


def _mark(im, scale=SCALE):
    """Capcom blue-fill/white-outline glyph -> a two-marker-colour RGBA image
    (black=fill, white=outline), alpha kept, by a binary luminance threshold."""
    w, h = max(1, round(im.width * scale)), max(1, round(im.height * scale))
    small = im.resize((w, h), Image.LANCZOS)
    out = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    sp, op = small.load(), out.load()
    for y in range(h):
        for x in range(w):
            r, g, b, a = sp[x, y]
            if a < ALPHA_MIN:
                continue
            lum = 0.299 * r + 0.587 * g + 0.114 * b
            op[x, y] = ((255, 255, 255) if lum >= LUM_THRESH else (0, 0, 0)) + (a,)
    return out


def _hpaste(glyphs, gap=0):
    h = max(g.height for g in glyphs)
    w = sum(g.width for g in glyphs) + gap * (len(glyphs) - 1)
    out = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    x = 0
    for g in glyphs:
        out.alpha_composite(g, (x, h - g.height))
        x += g.width + gap
    return out


def _row_extent(im):
    """-> per-row (left, right) ink column, or None for an empty row."""
    px = im.load()
    w, h = im.size
    out = []
    for y in range(h):
        xs = [x for x in range(w) if px[x, y][3] > 128]
        out.append((min(xs), max(xs)) if xs else None)
    return out


OPTICAL_GAP = -3   # the fan's own tightest letter-to-letter approach, measured off
                    # the real screen render: the row-wise minimum gap between
                    # "Ch"'s and "es"'s ink is -5, between "es"'s and "s"'s is -2
                    # (both already slight overlaps - the fan's own lettering is
                    # kerned tight, not just touching). -3 is between them.


def _optical_offset(a, b, target=OPTICAL_GAP):
    """-> x offset to place `b` (bottom-aligned with `a`, both already cropped
    tight to their own ink) so the closest row-wise approach of b's ink to a's
    ink equals `target`. Placing by crop-box width instead (as an earlier
    version did) leaves letters visibly spread apart, because shearing widens
    a letter's bounding box on the side away from its ink without adding ink
    there - two such boxes can touch edge to edge while their actual ink
    is still several pixels apart."""
    pa, pb = _row_extent(a), _row_extent(b)
    ha, hb = len(pa), len(pb)
    da = {ha - 1 - y: pa[y] for y in range(ha) if pa[y]}
    db = {hb - 1 - y: pb[y] for y in range(hb) if pb[y]}
    best = min((db[k][0] - da[k][1] for k in da if k in db), default=None)
    return a.width if best is None else target - best


def mind_groups(dumpdir):
    """-> ([M, in, d] RGBA marker images, [offsets], mind_width) or None.
    `offsets` are each group's real ink-start relative to M's own ink-start
    (0); mind_width is the whole word's real ink width. Letters are spaced by
    OPTICAL_GAP (see above), not by concatenating their crop boxes."""
    letters = {}
    for c in ('M', 'i', 'n', 'd'):
        src = _load(dumpdir, 'letter_%s' % c)
        if src is None:
            return None
        letters[c] = _crop(_mark(_shear(src)))
    M, i, n, d = letters['M'], letters['i'], letters['n'], letters['d']
    off_i = _optical_offset(M, i)
    off_n = off_i + _optical_offset(i, n)
    off_d = off_n + _optical_offset(n, d)
    in_canvas = Image.new('RGBA', (off_n - off_i + n.width, max(i.height, n.height)), (0, 0, 0, 0))
    in_canvas.alpha_composite(i, (0, in_canvas.height - i.height))
    in_canvas.alpha_composite(n, (off_n - off_i, in_canvas.height - n.height))
    return [M, in_canvas, d], [0, off_i, off_d], off_d + d.width


CHECKMATE_GAP = -10  # "Check"/"mate" are two pre-rendered word images, each already
                      # tight to its own ink at the edges; a gap of 0-1 still read as
                      # two words ("Check mate") because "k"'s and "m"'s own tapering
                      # strokes leave a low-density optical gap even with no blank
                      # column between them. -10 (a real Capcom-scale kerning
                      # overlap, chosen by rendering -10/-15/-20 and picking the
                      # tightest one that keeps "k" legible) closes it into one word.


def checkmate_chunks(dumpdir):
    """-> [chunk0, chunk1, chunk2], 64px-wide slices of "Checkmate" condensed
    to END_WIDTH, one per end-row field (144, 160, 176), or None."""
    check = _load(dumpdir, 'word_check')
    mate = _load(dumpdir, 'word_mate')
    if check is None or mate is None:
        return None
    word = _hpaste([_mark(check), _mark(mate)], gap=CHECKMATE_GAP)
    if word.width != END_WIDTH:
        word = word.resize((END_WIDTH, word.height), Image.LANCZOS)
    canvas = Image.new('RGBA', (END_WIDTH, 64), (0, 0, 0, 0))
    canvas.alpha_composite(word, (0, 64 - word.height))
    return [canvas.crop((k * 64, 0, (k + 1) * 64, 64)) for k in range(3)]


def _index_grid(im, w, h):
    """Marker RGBA -> palette-index grid, 0 = transparent."""
    grid = [[0] * w for _ in range(h)]
    if im is None:
        return grid
    px = im.load()
    for y in range(min(h, im.height)):
        for x in range(min(w, im.width)):
            r, g, b, a = px[x, y]
            if a < 128:
                continue
            grid[y][x] = OUTLINE_IDX if r >= 128 else FILL_IDX
    return grid


# ---- entry 25 container -----------------------------------------------
def _ncgr_tile_offset(rgcn_bytes):
    """-> (absolute byte offset of the tile data inside rgcn_bytes, size)."""
    pos, size, body = nitro_sections(rgcn_bytes)[b'RAHC']
    dsize = struct.unpack_from('<I', body, 16)[0]
    doff = struct.unpack_from('<I', body, 20)[0]
    return pos + 8 + doff, dsize


def _kbec(recn_bytes):
    """-> (body, base) where base is body's absolute offset inside recn_bytes."""
    assert recn_bytes[16:20] == b'KBEC', 'entry 25 RECN layout changed (expected KBEC first)'
    return recn_bytes[24:], 24


def _cells(recn_bytes):
    """-> (list of (tile, x_field_abs_offset) for EVERY oam of every cell,
    absolute offsets into recn_bytes), boundary. Done locally rather than
    with ncer.ncer() because that helper's section walk is not alignment-safe
    past the first block, and entry 25's RECN carries three blocks."""
    body, base = _kbec(recn_bytes)
    n_cells, attr = struct.unpack_from('<HH', body, 0)
    cell_off, mapping = struct.unpack_from('<II', body, 4)
    rec = 16 if (attr & 1) else 8
    oam_base = cell_off + n_cells * rec
    boundary = 1 << (mapping & 3) if (mapping & 3) else 1
    out = []
    for i in range(n_cells):
        p = cell_off + i * rec
        n_oam = struct.unpack_from('<H', body, p)[0]
        oam_off = struct.unpack_from('<I', body, p + 4)[0]
        for j in range(n_oam):
            q = oam_base + oam_off + j * 6
            a2 = struct.unpack_from('<H', body, q + 4)[0]
            tile = a2 & 0x3FF
            out.append((tile, base + q + 2))   # +2 = the OAM's attr1 (x) field
    return out, boundary


def _set_x(recn, abs_off, new_x):
    a1 = struct.unpack_from('<H', recn, abs_off)[0]
    a1 = (a1 & ~0x1FF) | (new_x & 0x1FF)
    struct.pack_into('<H', recn, abs_off, a1)


def _apply_x(recn, by_tile, field, value_fn):
    n = 0
    for xoff in by_tile.get(field, []):
        cur = struct.unpack_from('<H', recn, xoff)[0] & 0x1FF
        if cur >= 256:
            cur -= 512
        _set_x(recn, xoff, value_fn(cur))
        n += 1
    return n


def _write_shape(rgcn, tile_off, tile_field, boundary, grid, w_tiles=8, h_tiles=8):
    base = tile_field * boundary
    for ty in range(h_tiles):
        for tx in range(w_tiles):
            ti = base + ty * w_tiles + tx
            off = tile_off + ti * 32
            for yy in range(8):
                for xx in range(0, 8, 2):
                    Y, X = ty * 8 + yy, tx * 8 + xx
                    lo, hi = grid[Y][X], grid[Y][X + 1]
                    rgcn[off + yy * 4 + xx // 2] = (hi << 4) | lo


def patch(idlocal_bytes, dumpdir, log=None):
    """-> (new_idlocal_bytes, changed) or (idlocal_bytes, False) if the
    Collection harvest cache is missing - never raises."""
    log = log or (lambda s: None)
    mg = mind_groups(dumpdir)
    chunks = checkmate_chunks(dumpdir)
    if mg is None or chunks is None:
        log('mindchess: harvested letters not found in dump/title/mindchess/ - entry 25 left untouched')
        return idlocal_bytes, False
    groups, offsets, mind_width = mg

    if LAYOUT == 'A':
        mind_start = -((mind_width + WORD_GAP + CHESS_WIDTH) // 2)
    elif LAYOUT == 'B':
        mind_start = LOGIC_SPAN[0]
    else:
        raise ValueError('unknown LAYOUT %r' % LAYOUT)
    chess_shift = (mind_start + mind_width + WORD_GAP) - CHESS_SPAN[0]

    idl = Idlocal(idlocal_bytes)
    b = bytearray(idl.blob(25))
    o = struct.unpack_from('<3I', b, 0)
    recn = bytearray(b[o[0]:o[1]])
    rgcn = bytearray(b[o[2]:])
    tile_off, _ = _ncgr_tile_offset(bytes(rgcn))
    cell_list, boundary = _cells(bytes(recn))
    by_tile = {}
    for tile, xoff in cell_list:
        by_tile.setdefault(tile, []).append(xoff)

    # ---- name row: "Mind" split M/in/d into cells 0/1/2, each cell's OAM x
    # set so the pieces read continuously at the chosen layout's start, spaced
    # by real ink offsets (mind_groups), not by crop-box width.
    for field, grp, off in zip(NAME_FIELDS, groups, offsets):
        target = mind_start + off - TX[field] - DBL_ADJ
        canvas = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
        canvas.alpha_composite(grp, (0, BASELINE_ROW - grp.height + 1))
        _write_shape(rgcn, tile_off, field, boundary, _index_grid(canvas, 64, 64))
        _apply_x(recn, by_tile, field, lambda cur, t=target: t)
    mind_end = mind_start + mind_width - 1

    # ---- Ch/es/s: pixels untouched, all three OAM x moved by the same delta
    chess_start = CHESS_SPAN[0] + chess_shift
    chess_end = CHESS_SPAN[1] + chess_shift
    moved = sum(_apply_x(recn, by_tile, f, lambda cur, s=chess_shift: cur + s)
                for f in CHESS_FIELDS)

    # ---- end row: "Checkmate" split Check/mate-style across cell 9 + cell 10
    cum2 = CHECKMATE_START
    for field, chunk in zip(END_FIELDS, chunks):
        target = cum2 - TX[field] - DBL_ADJ
        _write_shape(rgcn, tile_off, field, boundary, _index_grid(chunk, 64, 64))
        _apply_x(recn, by_tile, field, lambda cur, t=target: t)
        cum2 += 64

    new_b = bytes(b[:o[0]]) + bytes(recn) + bytes(b[o[1]:o[2]]) + bytes(rgcn)
    log('mindchess [layout %s]: Mind %d..%d, Chess %d..%d (gap %d), %d OAM x fields moved, '
        'Checkmate %d..%d'
        % (LAYOUT, mind_start, mind_end, chess_start, chess_end,
           chess_start - mind_end - 1, moved, CHECKMATE_START, CHECKMATE_START + 191))
    new_idlocal = rebuild(idlocal_bytes, {25: new_b})
    return new_idlocal, True


# ---- ROM-level driver, same shape as choice_strips.apply_to_rom -----------
def apply_to_rom(rom, dumpdir, log=None):
    import title_logo
    cur = rom_file(rom, 'jpn/idlocal.bin')
    new_idlocal, changed = patch(cur, dumpdir, log)
    if not changed:
        return rom, False
    return title_logo.splice(rom, 'jpn/idlocal.bin', new_idlocal), True


if __name__ == '__main__':
    dumpdir = sys.argv[1] if len(sys.argv) > 1 else 'dump'
    if len(sys.argv) > 2 and sys.argv[2] == '--extract':
        bdir = sys.argv[3]
        print('extract ->', extract(bdir, dumpdir))
    else:
        data = open(os.path.join(dumpdir, 'ds_fan', 'jpn', 'idlocal.bin'), 'rb').read()
        new_idlocal, changed = patch(data, dumpdir, print)
        print('changed:', changed)
