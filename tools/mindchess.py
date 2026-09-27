# -*- coding: utf-8 -*-
"""Mind Chess banner (jpn/idlocal.bin entry 25): redraw the fan's "Logic Chess"
name-row and "Complete" end-row art as "Mind Chess" / "Checkmate", using
Capcom's own English Logic Chess title letters harvested from the player's
Collection install at build time. Nothing Capcom-owned ships with this tool.

Three fixes over the previous pass, found by comparing a tester's capture of
the shipped banner against the fan's own untouched lettering:
  1. Soft edges. I was thresholding every letter to just 2 colours (fill,
     outline), while the fan's own glyphs use an 11-step anti-alias ramp
     between them. I read that ramp from the ROM itself (see PALETTE_ENTRY
     below - it is idlocal entry 26, not entry 24; I checked entry 24 first
     since an earlier pass's docstring pointed there, found it holds a
     red/pink ramp that never appears on screen, then found the exact
     measured ramp, colour for colour, at entry 26 bank 0 indices 1-11) and
     map every opaque source pixel to the nearest ramp step by where it
     falls between fill and outline. The outer edge stays hard (alpha<128 is
     fully transparent, no partial-alpha ramp there, matching the fan's own
     glyphs). "Checkmate" was also being resampled twice (marked/thresholded
     at one scale, then resized again to its final width); both words now go
     through exactly one resize, from Capcom's native art to final size,
     with the ramp classification happening once at the very end.
  2. "Checkmate" was never sheared, so it stood upright next to the fan's own
     italic "Chess" - now it gets the same _shear() as "Mind", anchored the
     same way.
  3. The old fixed 64px/128px slice of the condensed word cut cell 9 from
     cell 10 mid-letter (through the "e" of "Check"), which is fine at rest
     but visibly splits for the first few frames of the end-banner zoom-in
     because the two cells scale about separate anchors. I now search the
     classified word for a column near the fixed 64px field boundary where
     no row has fill or ramp ink darker than the midpoint, and condense the
     word's width (not its height) so that column lines up exactly on the
     boundary, then re-centre the whole word by shifting all three end-field
     OAM x by the same amount (the canvas content, and so the seam's local
     column, is untouched). This is not perfectly clean: the gap between "e"
     and "c" is only 1px wide on some rows, so the cut (reported by patch(),
     not silently overwritten) still puts the "e"'s own rightmost
     outline pixel in cell 10 on those rows - no straight cut avoids that.
     What it does avoid, which the old fixed cut did not, is ANY dark fill
     pixel crossing the boundary: the "e"'s body stays entirely in cell 9.
     See checkmate_chunks() for the numbers and which letter gap it lands on.

Container: entry 25 is a self-contained sprite bundle (RECN cells + RNAN
animation + RGCN tiles; the palette bank its OAMs actually use is idlocal
entry 26, not entry 24 - see PALETTE_ENTRY below), 45 NCER cells
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
    "Checkmate" (Check+mate sheared the same way as "Mind", THEN joined at a
    gap tightened 1px at a time - starting from CHECKMATE_JOIN0 - until a
    flood fill finds no enclosed hole left in the outline between "k" and
    "m"; condensed to about END_WIDTH=192px, less when the seam fit below
    needs the margin, then re-centred) is cut across cell 9 and cell 10's two
    objects at whichever column near the fixed 64px field boundary has no
    FILL or ramp pixel darker than the midpoint at that exact column (the
    "e"/"c" gap is only 1px wide on some rows, so the "e"'s own outline still
    crosses on those rows - see checkmate_chunks), the way the fan split
    "Complete" into Co/mplete.
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

No rig capture of this pass's redraw has been made; the layout numbers above
still come from the tile/animation data and the renderer, not a screenshot.
The ramp fix was prompted by a tester's screenshot of the shipped banner
(fill and outline colours measured off it), then confirmed independently by
reading PALETTE_ENTRY straight out of the ROM (see _read_ramp) - the two
matched exactly, colour for colour.
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
ALPHA_MIN = 26           # ~0.1 of 255: gates near-invisible source noise out of
                          # the crop box BEFORE any spacing math runs, same gate
                          # the old threshold step used, kept so "Mind"'s letter
                          # spacing (measured off these same crop boxes) does not
                          # shift by being a pixel looser than before
ALPHA_HARD = 128         # outer-edge cutoff: alpha below this is fully transparent
                          # (index 0) in the FINAL written tile, no partial-alpha
                          # ramp step there - matches the fan's own glyphs, which
                          # have a hard outer edge

FILL_IDX, OUTLINE_IDX = 1, 11   # ramp bounds: index 1 is pure fill, 11 pure outline
RAMP_LEN = OUTLINE_IDX - FILL_IDX + 1   # 11 steps, indices 1-11 inclusive
PALETTE_ENTRY = 26       # idlocal entry whose bank-0 indices 1-11 hold the fan's
                          # 11-step fill->outline anti-alias ramp. NOT entry 24:
                          # entry 24 has the same 45-cell/4-bank shape and was
                          # assumed to be "the" shared palette by an earlier pass,
                          # but its bank 0 decodes to a red/pink ramp that never
                          # appears on screen. Entry 26 bank 0 indices 1-11 match
                          # the fan's own measured on-screen ramp exactly, colour
                          # for colour; entry 26 bank 4 is identical to entry 24
                          # bank 0 (the same red/pink set, kept as a spare bank),
                          # which is presumably how the mix-up happened.

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
                          # this (see CHECKMATE_JOIN0 for how the join itself is
                          # chosen); not a hard fill, just a width that reads clearly
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


def _resample(im, scale=SCALE):
    """Capcom's native glyph -> the same art at fan cap-height scale, ONE
    LANCZOS resize. Colour is left alone (no thresholding here - that used
    to happen in this same step, collapsing the source's own anti-aliasing
    to 2 hard colours; classification to the fan's 11-step ramp now happens
    once, at write time, on this continuous-tone result, in _ramp_grid).
    Only near-invisible alpha (<ALPHA_MIN) is zeroed, same gate the old
    thresholding step used, so _crop()'s bbox - and everything measured off
    it, including "Mind"'s own letter spacing - is exactly as tight as
    before."""
    w, h = max(1, round(im.width * scale)), max(1, round(im.height * scale))
    small = im.resize((w, h), Image.LANCZOS)
    out = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    sp, op = small.load(), out.load()
    for y in range(h):
        for x in range(w):
            r, g, b, a = sp[x, y]
            if a >= ALPHA_MIN:
                op[x, y] = (r, g, b, a)
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
    """-> ([M, in, d] continuous-tone RGBA images, [offsets], mind_width) or
    None. `offsets` are each group's real ink-start relative to M's own
    ink-start (0); mind_width is the whole word's real ink width. Letters are
    spaced by OPTICAL_GAP (see above), not by concatenating their crop boxes.
    Each letter is resampled exactly once (_resample); classification to the
    fan's ramp happens later, at write time, on the assembled result."""
    letters = {}
    for c in ('M', 'i', 'n', 'd'):
        src = _load(dumpdir, 'letter_%s' % c)
        if src is None:
            return None
        letters[c] = _crop(_resample(_shear(src)))
    M, i, n, d = letters['M'], letters['i'], letters['n'], letters['d']
    off_i = _optical_offset(M, i)
    off_n = off_i + _optical_offset(i, n)
    off_d = off_n + _optical_offset(n, d)
    in_canvas = Image.new('RGBA', (off_n - off_i + n.width, max(i.height, n.height)), (0, 0, 0, 0))
    in_canvas.alpha_composite(i, (0, in_canvas.height - i.height))
    in_canvas.alpha_composite(n, (off_n - off_i, in_canvas.height - n.height))
    return [M, in_canvas, d], [0, off_i, off_d], off_d + d.width


CHECKMATE_JOIN0 = round(-10 / SCALE)  # starting native-scale join gap: a straight
                      # port of the old small-scale kerning ("Check"/"mate" are two
                      # pre-rendered word images, each already tight to its own ink
                      # at the edges; a gap of 0-1 still reads as two words because
                      # "k"'s and "m"'s own tapering strokes leave a low-density
                      # optical gap even with no blank column between them; -10 was
                      # chosen, before this pass, by rendering -10/-15/-20 and
                      # picking the tightest that keeps "k" legible), converted to
                      # native pixels by dividing by SCALE. On its own this leaves a
                      # real hole in the outline between "k" and "m" partway up once
                      # both words are sheared (found in review, confirmed with a
                      # flood fill: an enclosed transparent region the staged build
                      # does not have). Cause: shearing shifts each letter's own
                      # silhouette right by an amount that grows with height above
                      # the baseline, and "k"'s tall ascender shifts further than
                      # "m"'s short x-height body, so a gap that closes the words at
                      # the baseline can still be open partway up. checkmate_chunks
                      # closes this by increasing the overlap 1px at a time,
                      # checking with the same flood fill each step, until no
                      # enclosed hole remains near the join - not a fixed guess.
CHECKMATE_JOIN_MARGIN = 12  # how far (in final 192px-wide columns) either side of
                      # the computed check/mate join a hole must be to count as
                      # "the k/m hole", vs. e.g. the notch inside Capcom's own "C"
CHECKMATE_JOIN_MAX_STEPS = 60  # give up after this many 1px tightening steps


def _enclosed_regions(grid, w, h):
    """-> [(size, (x0,y0,x1,y1)), ...] for every index-0 (transparent) 4-connected
    component that is NOT reachable from the canvas edge - a real hole enclosed
    by fill/ramp/outline pixels, not the word's own outer background. Used to
    close the "k"/"m" join below, and again on the final shipped-width grid to
    confirm the seam fit did not open a new one."""
    from collections import deque
    outer = [[False] * w for _ in range(h)]
    dq = deque()
    for x in range(w):
        for y in (0, h - 1):
            if grid[y][x] == 0 and not outer[y][x]:
                outer[y][x] = True
                dq.append((x, y))
    for y in range(h):
        for x in (0, w - 1):
            if grid[y][x] == 0 and not outer[y][x]:
                outer[y][x] = True
                dq.append((x, y))
    while dq:
        x, y = dq.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < w and 0 <= ny < h and grid[ny][nx] == 0 and not outer[ny][nx]:
                outer[ny][nx] = True
                dq.append((nx, ny))
    seen = [[False] * w for _ in range(h)]
    regions = []
    for y in range(h):
        for x in range(w):
            if grid[y][x] == 0 and not outer[y][x] and not seen[y][x]:
                comp = []
                dq2 = deque([(x, y)])
                seen[y][x] = True
                while dq2:
                    cx, cy = dq2.popleft()
                    comp.append((cx, cy))
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        nx, ny = cx + dx, cy + dy
                        if 0 <= nx < w and 0 <= ny < h and grid[ny][nx] == 0 and not outer[ny][nx] and not seen[ny][nx]:
                            seen[ny][nx] = True
                            dq2.append((nx, ny))
                xs = [p[0] for p in comp]
                ys = [p[1] for p in comp]
                regions.append((len(comp), (min(xs), min(ys), max(xs), max(ys))))
    return regions


SEAM_FIELD_BOUNDARY = 64   # local column where field 144 (cell 9) ends and the
                            # cell-10 pair (160/176) begins - fixed by tile geometry,
                            # cannot move
SEAM_SEARCH = 40            # how far either side of SEAM_FIELD_BOUNDARY to look
                            # for a column where every row is safe (see below)


def _blend_index(rgb, ramp):
    """-> nearest ramp index (1-11) for an opaque pixel's own RGB, by its
    projected position on the fill->outline line (ramp[0]->ramp[-1]), the
    same 11 colours read off the ROM by _read_ramp(). Clamped to the ramp's
    own ends, so a pixel bluer than pure fill still lands on index 1, not off
    the end of the ramp."""
    fill, outline = ramp[0], ramp[-1]
    d = [o - f for f, o in zip(fill, outline)]
    denom = sum(v * v for v in d) or 1
    t = sum((c - f) * v for c, f, v in zip(rgb, fill, d)) / denom
    t = 0.0 if t < 0 else (1.0 if t > 1 else t)
    return FILL_IDX + int(round(t * (RAMP_LEN - 1)))


def _ramp_grid(im, w, h, ramp):
    """Continuous-tone RGBA -> palette-index grid, 0 = transparent. The outer
    edge is hard (alpha < ALPHA_HARD -> 0); every opaque pixel is classified
    to the nearest of the 11 ramp steps by _blend_index, which is what puts
    the fan's own anti-aliasing back into these two redrawn words instead of
    the old flat fill/outline threshold."""
    grid = [[0] * w for _ in range(h)]
    if im is None:
        return grid
    px = im.load()
    for y in range(min(h, im.height)):
        for x in range(min(w, im.width)):
            r, g, b, a = px[x, y]
            if a < ALPHA_HARD:
                continue
            grid[y][x] = _blend_index((r, g, b), ramp)
    return grid


def _read_ramp(idl):
    """-> the fan's 11-step fill->outline ramp, [idx1..idx11], read from
    PALETTE_ENTRY bank 0 of the ROM being built (not a fixed guess)."""
    pal = idl.palette(PALETTE_ENTRY)[0:16]
    return pal[FILL_IDX:OUTLINE_IDX + 1]


def _seam_safe(grid, h, col):
    """-> True if no row of `grid` has a fill/ramp pixel darker than the
    midpoint (index 1-6) AT THIS EXACT COLUMN - only outline (7-11) or
    transparent (0) pixels are allowed to sit on the cell 9 / cell 10
    boundary. This is a one-column test, not a check that the two letters'
    ink is fully separated either side of it: on the shipped word, the gap
    between "e" and "c" is only 1px wide on some rows, so the safe column
    itself is clear but the very next column over (inside cell 9) still
    carries "e"'s own dark fill, and "e"'s rightmost outline pixel ends up
    in cell 10 on those rows. What this DOES guarantee is that no dark fill
    pixel is ever split by the cut - see checkmate_chunks for the measured
    rows."""
    return all(not (FILL_IDX <= grid[y][col] <= 6) for y in range(h))


def _find_seam(grid, h, near=SEAM_FIELD_BOUNDARY, radius=SEAM_SEARCH):
    """-> nearest column to `near` (within +-radius) that is seam-safe at
    EVERY row, by _seam_safe, or None if the search finds nothing."""
    w = len(grid[0])
    for d in range(radius + 1):
        for col in (near - d, near + d):
            if 0 <= col < w and _seam_safe(grid, h, col):
                return col
    return None


def checkmate_chunks(dumpdir, ramp):
    """-> (chunks, seam_found, join_gap, width_used, center_shift) or None.
    chunks = [grid0, grid1, grid2], 64x64 palette-index grids (ready for
    _write_shape) for fields 144/160/176, already cut and centred - nothing
    downstream needs to know width_used or center_shift except patch()'s log
    line and the OAM x it adds center_shift to.

    Fixes for "Checkmate" live here:
      - Sheared (_shear, same as "Mind"'s letters) and joined at Capcom's own
        native resolution, THEN resampled to final size in one LANCZOS call
        (width to the seam-fitted target below, height by SCALE alone) -
        one resample total, where the previous version thresholded each word
        to 2 colours at one scale and then resized the already-thresholded
        result a second time.
      - The join itself starts at CHECKMATE_JOIN0 and is tightened 1px at a
        time, re-classifying and re-running _enclosed_regions each step,
        until no enclosed hole remains within CHECKMATE_JOIN_MARGIN columns
        of the check/mate boundary (a review found a real hole here in the
        first pass - see CHECKMATE_JOIN0's comment for the cause).
      - The old code always cut the condensed word at local columns 64 and
        128 - fixed by tile geometry - regardless of what ink was there,
        which is why the first cut used to fall inside the "e" of "Check".
        I classify the word to the ramp at END_WIDTH and look for a column
        near 64 where the column ITSELF has no fill/ramp pixel darker than
        the midpoint (_find_seam). On this word that column is 67, not 64 -
        the field boundary is fixed, so I shrink the word's WIDTH ONLY by
        the ratio needed to bring column 67 exactly onto 64, then re-render
        and re-run the hole check on this final, narrower grid too (a shrink
        that fixes the seam could in principle open a different hole it
        wasn't checked for). A narrower word would read left-shifted inside
        the unchanged 192px budget, so I re-centre it afterwards - see
        center_shift below - by moving the whole assembly, not by moving
        content inside the canvas, which would undo the seam fit.
        Only a safe column AT OR RIGHT of 64 is handled: one to the left
        would need the word to GROW past 192px and pin to the right, clipping
        the "C" on the left instead of fixing anything, so that path raises
        instead of doing it. _find_seam finding nothing, and the 1px nudge
        loop running out, both raise too - a bad seam is not shipped quietly.
        The second cut, at 128, sits inside cell 10's own two objects (which
        share one animation anchor and were already confirmed not to
        visibly split).
      - One-sidedness (found in review, not hidden): the gap between "e" and
        "c" is only 1px wide on some rows, so a single safe column can't put
        clear air on both sides of it - "e"'s own rightmost outline pixel
        ends up in cell 10 on those rows. What the search DOES guarantee
        (checked column by column, not assumed) is that no dark FILL pixel
        is ever split - "e"'s body is entirely inside cell 9 - which the old
        fixed 64px cut did not guarantee (it ran through the fill itself).
    """
    check = _load(dumpdir, 'word_check')
    mate = _load(dumpdir, 'word_mate')
    if check is None or mate is None:
        return None
    check_s = _crop(_shear(check))
    mate_s = _crop(_shear(mate))

    def render_join(gap, width=END_WIDTH, xoff=0):
        joined = _hpaste([check_s, mate_s], gap=gap)
        target_h = max(1, round(joined.height * SCALE))
        word = joined.resize((width, target_h), Image.LANCZOS)
        canvas = Image.new('RGBA', (END_WIDTH, 64), (0, 0, 0, 0))
        canvas.alpha_composite(word, (xoff, 64 - target_h))
        return joined, canvas

    gap = CHECKMATE_JOIN0
    for _ in range(CHECKMATE_JOIN_MAX_STEPS):
        joined, canvas0 = render_join(gap)
        grid0 = _ramp_grid(canvas0, END_WIDTH, 64, ramp)
        # the check/mate boundary in final (post-resize) columns, used only to
        # tell "the k/m hole" apart from unrelated ones (e.g. Capcom's own
        # notch inside the "C") - NOT a hardcoded pixel position
        join_final_col = (check_s.width + gap / 2) * END_WIDTH / joined.width
        regions_192 = _enclosed_regions(grid0, END_WIDTH, 64)
        holes = [r for r in regions_192
                 if r[1][0] - CHECKMATE_JOIN_MARGIN <= join_final_col <= r[1][2] + CHECKMATE_JOIN_MARGIN]
        if not holes:
            break
        gap -= 1
    else:
        raise SystemExit('mindchess: could not close the "k"/"m" join after %d steps'
                          % CHECKMATE_JOIN_MAX_STEPS)
    join_gap = gap  # reported by patch() below

    grid = _ramp_grid(canvas0, END_WIDTH, 64, ramp)
    seam_found = _find_seam(grid, 64)
    if seam_found is None:
        raise SystemExit('mindchess: no seam column within +-%d of the field '
                          'boundary (%d) is free of fill/ramp ink darker than '
                          'the midpoint' % (SEAM_SEARCH, SEAM_FIELD_BOUNDARY))
    if seam_found < SEAM_FIELD_BOUNDARY:
        raise SystemExit('mindchess: safe seam column %d is LEFT of the field '
                          'boundary (%d); fitting it would grow the word past '
                          'END_WIDTH and clip the left edge instead, which is '
                          'not implemented - only a safe column at or right of '
                          'the boundary is handled' % (seam_found, SEAM_FIELD_BOUNDARY))

    width_used = END_WIDTH
    if seam_found != SEAM_FIELD_BOUNDARY:
        width_used = max(1, round(END_WIDTH * SEAM_FIELD_BOUNDARY / seam_found))
        joined2, canvas1 = render_join(gap, width_used, 0)
        grid = _ramp_grid(canvas1, END_WIDTH, 64, ramp)
        # the ratio above is exact only for a linear resize; nudge 1px at a
        # time in case rounding left the boundary column unsafe
        tries = 0
        while not _seam_safe(grid, 64, SEAM_FIELD_BOUNDARY) and tries < 8:
            width_used += 1
            joined2, canvas1 = render_join(gap, width_used, 0)
            grid = _ramp_grid(canvas1, END_WIDTH, 64, ramp)
            tries += 1
        if not _seam_safe(grid, 64, SEAM_FIELD_BOUNDARY):
            raise SystemExit('mindchess: column %d still unsafe after %d 1px '
                              'nudges from the fitted width' % (SEAM_FIELD_BOUNDARY, tries))

    # the fit above only proves the boundary COLUMN is safe; re-run the same
    # hole check used to close the k/m join on this final, shipped-width grid
    # matched by position, not just counted: each hole in the final grid must
    # overlap (within 2px) a hole of the full-width grid once that one's x
    # extent is scaled to the fitted width, so a fit that opens one hole and
    # closes another still stops the build
    regions_final = _enclosed_regions(grid, END_WIDTH, 64)
    k = width_used / END_WIDTH

    def _matched(box):
        x0, y0, x1, y1 = box
        for _, (a0, b0, a1, b1) in regions_192:
            if (x0 <= a1 * k + 2 and a0 * k - 2 <= x1
                    and y0 <= b1 + 2 and b0 - 2 <= y1):
                return True
        return False

    new_holes = [r for r in regions_final if not _matched(r[1])]
    if new_holes:
        raise SystemExit('mindchess: the %dpx seam fit opened %d enclosed '
                          'hole(s) not present at %dpx (%r vs %r)'
                          % (width_used, len(new_holes), END_WIDTH,
                             new_holes, regions_192))

    # a word narrower than END_WIDTH is left-pinned at local column 0 by the
    # fit above (so the boundary column lands correctly); re-centre the whole
    # assembly by shifting screen position, not canvas content, so the seam
    # fit above is untouched
    center_shift = round((END_WIDTH - width_used) / 2)

    chunks = [[row[k * 64:(k + 1) * 64] for row in grid] for k in range(3)]
    return chunks, seam_found, join_gap, width_used, center_shift


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
    Collection harvest cache is missing (never raises for THAT case, same as
    before). It DOES raise SystemExit, same as extract()'s missing-bundle
    case, if checkmate_chunks can't make the cell 9 / cell 10 seam safe or
    can't close the "k"/"m" join - an internal invariant failing, not a
    missing asset, but still not something to ship silently."""
    log = log or (lambda s: None)
    idl = Idlocal(idlocal_bytes)
    ramp = _read_ramp(idl)
    mg = mind_groups(dumpdir)
    ck = checkmate_chunks(dumpdir, ramp)
    if mg is None or ck is None:
        log('mindchess: harvested letters not found in dump/title/mindchess/ - entry 25 left untouched')
        return idlocal_bytes, False
    groups, offsets, mind_width = mg
    chunks, seam_found, join_gap, width_used, center_shift = ck

    if LAYOUT == 'A':
        mind_start = -((mind_width + WORD_GAP + CHESS_WIDTH) // 2)
    elif LAYOUT == 'B':
        mind_start = LOGIC_SPAN[0]
    else:
        raise ValueError('unknown LAYOUT %r' % LAYOUT)
    chess_shift = (mind_start + mind_width + WORD_GAP) - CHESS_SPAN[0]

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
        _write_shape(rgcn, tile_off, field, boundary, _ramp_grid(canvas, 64, 64, ramp))
        _apply_x(recn, by_tile, field, lambda cur, t=target: t)
    mind_end = mind_start + mind_width - 1

    # ---- Ch/es/s: pixels untouched, all three OAM x moved by the same delta
    chess_start = CHESS_SPAN[0] + chess_shift
    chess_end = CHESS_SPAN[1] + chess_shift
    moved = sum(_apply_x(recn, by_tile, f, lambda cur, s=chess_shift: cur + s)
                for f in CHESS_FIELDS)

    # ---- end row: "Checkmate" split Check/mate-style across cell 9 + cell 10.
    # center_shift moves all three fields by the same amount to re-centre a
    # word narrower than END_WIDTH (see checkmate_chunks) - it does NOT touch
    # the tile pixels or the seam's local column, only where the group as a
    # whole lands on screen.
    cum2 = CHECKMATE_START + center_shift
    for field, chunk in zip(END_FIELDS, chunks):
        target = cum2 - TX[field] - DBL_ADJ
        _write_shape(rgcn, tile_off, field, boundary, chunk)
        _apply_x(recn, by_tile, field, lambda cur, t=target: t)
        cum2 += 64

    new_b = bytes(b[:o[0]]) + bytes(recn) + bytes(b[o[1]:o[2]]) + bytes(rgcn)
    checkmate_start_shifted = CHECKMATE_START + center_shift
    log('mindchess [layout %s]: Mind %d..%d, Chess %d..%d (gap %d), %d OAM x fields moved, '
        'Checkmate %d..%d (width %d/%d, centre shift %+d), join gap %d (native, started %d), '
        'seam found at col %d (field boundary %d, %s), ramp entry %d bank 0'
        % (LAYOUT, mind_start, mind_end, chess_start, chess_end,
           chess_start - mind_end - 1, moved, checkmate_start_shifted,
           checkmate_start_shifted + width_used - 1, width_used, END_WIDTH, center_shift,
           join_gap, CHECKMATE_JOIN0, seam_found, SEAM_FIELD_BOUNDARY,
           'no width change needed' if width_used == END_WIDTH else 'word fitted to make it safe',
           PALETTE_ENTRY))
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
