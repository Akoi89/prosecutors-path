# -*- coding: utf-8 -*-
"""Capcom's English cake-show logo on the episode opening card (jpn/opening_local.bin 11-14).

One episode opens on a TV-show logo card. In the fan patch it reads
"KATHERINE HALL AND JEFF MASTER'S / Piece of Cake! / 3pm Decoration Special",
with the fan's names. Capcom's Collection ships the same card in English
(bundle gk2_openinglocal_assets_all_*, texture opObj02_032_256_eng, reading
"Samson & Judy's / Bake 'n' Bop! / Your 3 PM Cakestravaganza") beside its
Japanese twin (opObj02_032_256) and the DS cell bank they were laid out from
(MonoBehaviour opObj02_032_256: the same 13 cells, parts and animations as the
DS entries 12 and 11).

The card is a sprite bundle: entry 12 RECN (cell 0 the 256x192 logo in 16 OBJs,
cells 1-12 the overlay sprites: two hand pairs, two face pairs, four
sparkles), 11 RNAN, 13 RGCN (8bpp, linear), 14 RLCN (256 colours, stored
uncompressed). The overlays are placed by the game on top of the logo (seen in
the episode's opening code); the first frame of each hand and face pair is a
copy of the logo underneath, the second the moved pose.

What this module does, at build time, from the player's own Collection:

  1. sheet: the English and Japanese atlases area-averaged onto the DS cell
     sheet. The atlas is the DS sheet at 1080/192 = 5.625 texels per pixel
     (its cell list uses DS pixel units), so no fitted transform is needed: the
     Japanese twin at that scale covers the Japanese DS card's silhouette at
     IoU 0.9915 (a free fit reaches 0.9928).
  2. mask, in logo pixels: where the English art differs from the Japanese twin
     (the new lettering and banner), plus where the fan's card differs from the
     Japanese twin by more than art noise (the fan's own lettering and the note it
     moved), small specks dropped, both grown a little. Inside the mask the
     logo takes Capcom's English art; outside it every pixel keeps the fan's
     palette index (characters, cake, cream, whisk as drawn).
  3. overlays: in the hand and face cells, a pixel that sits on the mask takes
     the new logo's index where the fan's frame copied the logo there, and
     Capcom's English sprite (the same cell in the same atlas) where the fan's
     frame drew its own pose. The sparkles do not touch the lettering and are
     not changed.
  4. palette: every index the unchanged pixels use keeps its colour; the free
     slots get new colours (k-means in CIELAB over the redrawn pixels, BGR555),
     no dithering. Unused free slots keep the fan's colour.
  5. container: entry 13 keeps the fan's decoded size and is stored as a real
     LZ11 stream (tools/lz11.py); entry 14 keeps its size and stays
     uncompressed; every other entry keeps the bytes it had. The game reads
     these entries through its sprite bundle loader, which allocates the
     decoded size from the archive table and decompresses through a temporary
     copy of the stored entry, so the stored size only sets that transient
     buffer. tools/bufcheck.py check (h) holds the decoded sizes and caps the
     stored size.

patch() guards on the sha256 of the fan's decoded entries 11-14 and on the
Capcom cell list matching the fan's cells, and raises if either differs (under
--any-rom it logs the reason and leaves the file alone).

    extract(bdir, dumpdir) / required(dumpdir) / patch(container, dumpdir) / apply_to_rom(rom, dumpdir)
    python tools/opening_card.py FAN_opening_local.bin DUMPDIR OUT.bin
"""
import sys, os, struct, json, glob, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np

CONTAINER = 'jpn/opening_local.bin'
E_ANIM, E_CELLS, E_GFX, E_PAL = 11, 12, 13, 14
FAN_SHA256 = {
    11: '066c4ed7f88710e4d17f98ff528fac16c72e310c2bc36bcd9c1c7254e62b89d2',
    12: 'c37500d301ca36c79a78d4d447795f8ee67b7fb0e0355c8dffa1dc1a92d344da',
    13: 'c3f8aea17b3428addbc4dc8b1b965a4461d053d60a54acb3cf9576e846125dd9',
    14: '721861b873ff17a45f7ee66f2365f75b5ec2cc95f0d22209276f229901a7c53b',
}
BUNDLE_PREFIX = 'gk2_openinglocal_assets_all_'
TEX_ENG, TEX_JPN, CELL_LIST = 'opObj02_032_256_eng', 'opObj02_032_256', 'opObj02_032_256'
CACHE_DIRNAME = 'opening'
SCALE = 5.625                    # atlas texels per DS pixel (1080 / 192)
SHEET_W, SHEET_H = 352, 192      # the DS cell sheet the parts come from (logo 256x192, overlays right of it)
CARD_W, CARD_H = 256, 192
CARD_ORIGIN = (-128, -96)        # cell 0's top-left in OAM coordinates; the logo rests at screen (128, 96)
# overlay objects the episode's opening code places over the logo: (first cell, second cell, x, y)
# in screen pixels; the first cell of each pair copies the logo underneath
OVERLAYS = ((1, 2, 80, 40), (3, 4, 184, 40), (5, 6, 64, 40), (7, 8, 192, 32))
ALPHA_ON = 0.5                   # area-averaged coverage at which a pixel is drawn
DIFF_ENG = 32                    # premultiplied channel difference (0..255) that counts as English lettering
DIFF_COVER = 0.02                # share of a pixel's footprint that must be lettering
DIFF_FAN = 60                    # summed |R,G,B| fan card vs Japanese twin that counts as the fan's own drawing
SPECK = 30                       # components of the fan mask smaller than this many px are art noise
GROW_ENG, GROW_FAN = 1, 2
KMEANS_ROUNDS = 10


class OpeningCardError(ValueError):
    pass


# ---------------------------------------------------------------- container

def _table(d):
    n = struct.unpack_from('<I', d, 0)[0] // 8
    slots = [struct.unpack_from('<II', d, i * 8) for i in range(n)]
    order = sorted((o, i) for i, (o, s) in enumerate(slots) if o)
    ext = {}
    for k, (o, i) in enumerate(order):
        ext[i] = (o, order[k + 1][0] if k + 1 < len(order) else len(d))
    return slots, ext


def entry(d, i):
    """-> (decoded bytes, stored bytes, compressed flag) of entry i."""
    import lz11
    slots, ext = _table(d)
    if i >= len(slots) or i not in ext:
        raise OpeningCardError('%s has no entry %d' % (CONTAINER, i))
    o, s = slots[i]
    stored = d[ext[i][0]:ext[i][1]]
    comp = bool(s & 0x80000000)
    dec = lz11.decompress(stored) if comp else stored[:s & 0x7FFFFFFF]
    if len(dec) != s & 0x7FFFFFFF:
        raise OpeningCardError('%s entry %d decodes to %d bytes, its table says %d'
                               % (CONTAINER, i, len(dec), s & 0x7FFFFFFF))
    return bytes(dec), bytes(stored), comp


def rebuild(d, repl, lz=()):
    """Container with entries in `repl` replaced: those in `lz` stored as a real
    LZ11 stream, the rest uncompressed; every other entry keeps its stored
    bytes and flag. Entries are 4-byte aligned as tools/title_text.py lays them out."""
    import lz11
    slots, ext = _table(d)
    n = len(slots)
    table = bytearray(n * 8)
    body = bytearray()
    for i, (o, s) in enumerate(slots):
        if not o:
            struct.pack_into('<II', table, i * 8, 0, s)
            continue
        if i in repl:
            raw = bytes(repl[i])
            stored, field = (lz11.compress(raw), len(raw) | 0x80000000) if i in lz else (raw, len(raw))
        else:
            stored, field = d[ext[i][0]:ext[i][1]], s
        while (n * 8 + len(body)) % 4:
            body += b'\x00'
        struct.pack_into('<II', table, i * 8, n * 8 + len(body), field)
        body += stored
    return bytes(table) + bytes(body)


# ---------------------------------------------------------------- the DS card

def unit(mapping):
    return 32 << (mapping & 3)


def cell_canvas(objs, data, mapping, origin, size):
    """Palette indices of a cell on a canvas whose top-left is OAM `origin`
    (-1 = no OBJ pixel, 0 = transparent) -> int array (h, w)."""
    w, h = size
    a = np.full((h, w), -1, np.int32)
    for o in reversed(objs):
        base = o['tile'] * unit(mapping)
        blk = np.frombuffer(bytes(data[base:base + o['w'] * o['h']]), np.uint8).reshape(o['h'], o['w']).astype(np.int32)
        if o['hflip']:
            blk = blk[:, ::-1]
        if o['vflip']:
            blk = blk[::-1]
        x, y = o['x'] - origin[0], o['y'] - origin[1]
        if x < 0 or y < 0 or x + o['w'] > w or y + o['h'] > h:
            raise OpeningCardError('an OBJ of the cell lies outside its %dx%d canvas' % (w, h))
        a[y:y + o['h'], x:x + o['w']] = blk
    return a


def write_cell(data, objs, mapping, origin, idx):
    """Write a (h, w) index canvas back into the OBJs' linear 8bpp tiles."""
    for o in objs:
        if o['hflip'] or o['vflip']:
            raise OpeningCardError('flipped OBJs are not handled')
        base = o['tile'] * unit(mapping)
        x, y = o['x'] - origin[0], o['y'] - origin[1]
        blk = idx[y:y + o['h'], x:x + o['w']]
        if (blk < 0).any() or (blk > 255).any():
            raise OpeningCardError('index out of range inside an OBJ')
        data[base:base + o['w'] * o['h']] = blk.astype(np.uint8).tobytes()


def cell_box(objs):
    x0 = min(o['x'] for o in objs); y0 = min(o['y'] for o in objs)
    return (x0, y0), (max(o['x'] + o['w'] for o in objs) - x0, max(o['y'] + o['h'] for o in objs) - y0)


def gfx_split(gfx):
    """-> (offset of the tile data inside the RGCN, tile bytes)."""
    from nitro import _sections
    p, size, body = _sections(gfx)[b'RAHC']
    dsize, doff = struct.unpack_from('<II', body, 16)
    return p + 8 + doff, bytearray(body[doff:doff + dsize])


def pal_split(palb):
    """-> (offset of the colour data inside the RLCN, colour count)."""
    from nitro import _sections
    p, size, body = _sections(palb)[b'TTLP']
    dsize = struct.unpack_from('<I', body, 8)[0]
    return p + 8 + 16, dsize // 2


# ---------------------------------------------------------------- Capcom's art

def cache_dir(dumpdir):
    return os.path.join(dumpdir, 'title', CACHE_DIRNAME)


def required(dumpdir):
    c = cache_dir(dumpdir)
    return [os.path.join(c, TEX_ENG + '.png'), os.path.join(c, TEX_JPN + '.png'), os.path.join(c, CELL_LIST + '_cells.json')]


def extract(bdir, dumpdir):
    """Save the English and Japanese atlases (the part holding the DS sheet,
    turned upright) and the cell list of opObj02_032_256 into
    dump/title/opening/. Raises SystemExit if the bundle or an asset is missing."""
    hits = [p for p in glob.glob(os.path.join(bdir, '*.bundle')) if os.path.basename(p).lower().startswith(BUNDLE_PREFIX)]
    if not hits:
        raise SystemExit('opening card: no bundle starting with %r in %s' % (BUNDLE_PREFIX, bdir))
    import UnityPy
    from PIL import Image
    env = UnityPy.load(hits[0])
    tex, cells = {}, None
    for obj in env.objects:
        if obj.type.name == 'Texture2D':
            d = obj.read()
            if d.m_Name in (TEX_ENG, TEX_JPN):
                tex[d.m_Name] = d.image
        elif obj.type.name == 'MonoBehaviour':
            try:
                tt = obj.read_typetree()
            except Exception:
                continue
            if tt.get('m_Name') == CELL_LIST and 'SpriteList' in tt:
                cells = tt
    missing = [n for n in (TEX_ENG, TEX_JPN) if n not in tex] + ([] if cells else [CELL_LIST + ' cell list'])
    if missing:
        raise SystemExit('opening card: %s missing from %s' % (', '.join(missing), os.path.basename(hits[0])))
    out = cache_dir(dumpdir)
    os.makedirs(out, exist_ok=True)
    box = (0, 0, int(round(SHEET_W * SCALE)), int(round(SHEET_H * SCALE)))
    for name, im in tex.items():
        im.convert('RGBA').transpose(Image.FLIP_TOP_BOTTOM).crop(box).save(os.path.join(out, name + '.png'))
    keep = dict(SpriteList=[dict(Parts=[{k: p[k] for k in ('DestX', 'DestY', 'SrcX', 'SrcY', 'Width', 'Height', 'Flag')}
                                        for p in s['Parts']]) for s in cells['SpriteList']],
                AnimList=[[(k['Frame'], k['Index']) for k in a['KeyFrames']] for a in cells.get('AnimList', [])])
    with open(os.path.join(out, CELL_LIST + '_cells.json'), 'w') as f:
        json.dump(keep, f, indent=0)
    return out


def coverage(n_dst, n_src, scale, offset=0.0):
    """Area-average matrix (n_dst, n_src): destination cell u covers source
    [(u - offset) / scale, (u + 1 - offset) / scale]."""
    u0 = (np.arange(n_dst) - offset) / scale
    u1 = (np.arange(n_dst) + 1 - offset) / scale
    x = np.arange(n_src)
    lo = np.maximum(u0[:, None], x[None, :])
    hi = np.minimum(u1[:, None], x[None, :] + 1)
    return np.clip(hi - lo, 0, None) / (u1 - u0)[:, None]


def to_sheet(img):
    """(H, W[, C]) float atlas -> area average on the DS sheet (SHEET_H, SHEET_W[, C])."""
    my = coverage(SHEET_H, img.shape[0], 1 / SCALE)
    mx = coverage(SHEET_W, img.shape[1], 1 / SCALE)
    if img.ndim == 2:
        return (my @ img) @ mx.T
    return np.stack([(my @ img[:, :, c]) @ mx.T for c in range(img.shape[2])], axis=2)


def load_atlas(dumpdir, name):
    from PIL import Image
    a = np.asarray(Image.open(os.path.join(cache_dir(dumpdir), name + '.png')).convert('RGBA'), np.float64)
    if a.shape[:2] != (int(round(SHEET_H * SCALE)), int(round(SHEET_W * SCALE))):
        raise OpeningCardError('%s is %dx%d, expected the %dx%d sheet crop' % (name, a.shape[1], a.shape[0],
                               int(round(SHEET_W * SCALE)), int(round(SHEET_H * SCALE))))
    return a


def premul(a):
    al = a[..., 3:4] / 255.0
    return np.concatenate([a[..., :3] * al, a[..., 3:4]], axis=2)


def sheet_rgba(a):
    """Atlas RGBA (0..255) -> (rgb (H, W, 3), alpha 0..1) on the DS sheet, premultiplied averaging."""
    s = to_sheet(premul(a))
    al = s[..., 3] / 255.0
    return s[..., :3] / np.maximum(al, 1e-6)[..., None], al


def check_cells(cells_json, cells):
    """Capcom's cell list must be the fan's cells part for part (dest and size;
    src of the logo parts equal to their place on the card)."""
    sl = cells_json['SpriteList']
    for k in range(13):
        mine = sorted((o['x'], o['y'], o['w'], o['h']) for o in cells[k]) if k < len(cells) else []
        theirs = sorted((int(p['DestX']), int(p['DestY']), int(p['Width']), int(p['Height'])) for p in sl[k]['Parts']) \
            if k < len(sl) else []
        if mine != theirs:
            return 'Capcom cell %d does not match the fan\'s (%d parts vs %d)' % (k, len(theirs), len(mine))
    for p in sl[0]['Parts']:
        if (p['SrcX'], p['SrcY']) != (p['DestX'] - CARD_ORIGIN[0], p['DestY'] - CARD_ORIGIN[1]) or p['Flag']:
            return 'Capcom logo part at (%g,%g) does not come from its own place on the sheet' % (p['DestX'], p['DestY'])
    return None


def src_of(cells_json, k):
    """{(dest x, dest y): (src x, src y)} for Capcom cell k."""
    return {(int(p['DestX']), int(p['DestY'])): (int(p['SrcX']), int(p['SrcY'])) for p in cells_json['SpriteList'][k]['Parts']}


# ---------------------------------------------------------------- masks and colour

def grow(m, n):
    out = m.copy()
    h, w = m.shape
    for dy in range(-n, n + 1):
        for dx in range(-n, n + 1):
            out[max(0, dy):h + min(0, dy), max(0, dx):w + min(0, dx)] |= \
                m[max(0, -dy):h + min(0, -dy), max(0, -dx):w + min(0, -dx)]
    return out


def drop_specks(m, minpx):
    """m without its 8-connected components of fewer than minpx pixels."""
    seen = np.zeros(m.shape, bool)
    out = np.zeros(m.shape, bool)
    h, w = m.shape
    for y, x in np.argwhere(m):
        if seen[y, x]:
            continue
        st, comp = [(y, x)], []
        seen[y, x] = True
        while st:
            cy, cx = st.pop()
            comp.append((cy, cx))
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    ny, nx = cy + dy, cx + dx
                    if 0 <= ny < h and 0 <= nx < w and m[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        st.append((ny, nx))
        if len(comp) >= minpx:
            ys, xs = zip(*comp)
            out[list(ys), list(xs)] = True
    return out


def to_lab(rgb):
    c = np.asarray(rgb, np.float64) / 255.0
    c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    m = np.array([[0.4124564, 0.3575761, 0.1804375],
                  [0.2126729, 0.7151522, 0.0721750],
                  [0.0193339, 0.1191920, 0.9503041]])
    xyz = c @ m.T / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 216 / 24389, np.cbrt(xyz), (24389 / 27 * xyz + 16) / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], axis=-1)


def to555(rgb):
    """Round to BGR555 and expand back the way tools/nitro.nclr reads it."""
    q = np.clip(np.round(np.asarray(rgb, np.float64) * 31 / 255), 0, 31).astype(np.int64)
    return (q << 3) | (q >> 2)


def nearest(lab_px, lab_pal):
    """Index into lab_pal of the colour nearest each pixel, and the distance."""
    out = np.empty(len(lab_px), np.int64)
    dist = np.empty(len(lab_px))
    for s in range(0, len(lab_px), 4096):
        d = ((lab_px[s:s + 4096, None, :] - lab_pal[None, :, :]) ** 2).sum(axis=2)
        out[s:s + 4096] = d.argmin(axis=1)
        dist[s:s + 4096] = np.sqrt(d.min(axis=1))
    return out, dist


def choose_colours(targets, fixed, n_free, rounds=KMEANS_ROUNDS):
    """New colours for the free palette slots: k-means in CIELAB over the target
    pixels (n, 3 RGB) with the `fixed` colours (m, 3 RGB) held in place,
    seeded by a median cut of the pixels the fixed colours match worst, each
    centre rounded to BGR555. Deterministic. -> (k, 3) int RGB, k <= n_free."""
    from PIL import Image
    tl = to_lab(targets)
    fl = to_lab(np.asarray(fixed, np.float64)) if len(fixed) else np.zeros((0, 3))
    if n_free <= 0:
        return np.zeros((0, 3), np.int64)
    if len(fl):
        _i, d = nearest(tl, fl)
        seed = targets[d > 2.0]
    else:
        seed = targets
    if len(seed) == 0:
        return np.zeros((0, 3), np.int64)
    im = Image.fromarray(np.clip(np.round(seed), 0, 255).astype(np.uint8).reshape(-1, 1, 3))
    q = im.quantize(colors=min(n_free, 256), method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    used = sorted(set(np.asarray(q).ravel().tolist()))
    p = q.getpalette()
    cent = np.unique(to555(np.array([p[3 * i:3 * i + 3] for i in used], np.float64)), axis=0)
    for _r in range(rounds):
        allc = np.concatenate([np.asarray(fixed, np.float64).reshape(-1, 3), cent.astype(np.float64)])
        a, d = nearest(tl, to_lab(allc))
        new = []
        for k in range(len(cent)):
            sel = a == len(fixed) + k
            if sel.any():
                new.append(to555(targets[sel].mean(axis=0)))
        worst = np.argsort(-d, kind='stable')
        for w in worst:                         # refill emptied centres with the worst-served pixels
            if len(new) >= len(cent):
                break
            new.append(to555(targets[w]))
        cent = np.unique(np.array(new, np.int64), axis=0)
    return cent[:n_free]


# ---------------------------------------------------------------- compose

def compose(gfx, palb, cells, mapping, eng, jpn, cells_json):
    """New (RGCN, RLCN) bytes and an info dict (masks, canvases for renders)."""
    from nitro import nclr
    doff, data = gfx_split(gfx)
    poff, ncol = pal_split(palb)
    pal = np.array(nclr(palb), np.float64)
    if ncol != 256 or len(pal) != 256:
        raise OpeningCardError('palette has %d colours, expected 256' % ncol)
    new_data = bytearray(data)

    erg, eal = sheet_rgba(eng)
    jrg, jal = sheet_rgba(jpn)

    # logo canvas, card mask
    fan = cell_canvas(cells[0], data, mapping, CARD_ORIGIN, (CARD_W, CARD_H))
    obj = fan >= 0
    ink = fan > 0
    hd = np.abs(premul(eng) - premul(jpn)).max(axis=2) > DIFF_ENG
    m_eng = to_sheet(hd.astype(np.float64))[:CARD_H, :CARD_W] > DIFF_COVER
    fan_rgb = pal[np.maximum(fan, 0)]
    j_on = jal[:CARD_H, :CARD_W] > ALPHA_ON
    d_fan = np.where(ink & j_on, np.abs(fan_rgb - jrg[:CARD_H, :CARD_W]).sum(axis=2), 0)
    d_fan = np.where(ink != j_on, 999, d_fan)
    m_fan = drop_specks(d_fan > DIFF_FAN, SPECK)
    mask = (grow(m_eng, GROW_ENG) | grow(m_fan, GROW_FAN)) & obj
    e_on = eal[:CARD_H, :CARD_W] > ALPHA_ON
    lost = int((grow(m_eng, GROW_ENG) & e_on & ~obj).sum())     # English art outside every OBJ (cannot be drawn)

    # what each redrawn pixel should show: ('rgb', colour) or transparent, or 'card' (copy the new logo)
    card_t = np.full((CARD_H, CARD_W), -1, np.int64)            # -1 keep, -2 transparent, >= 0 target row
    targets = []
    ys, xs = np.nonzero(mask)
    for y, x in zip(ys, xs):
        if e_on[y, x]:
            card_t[y, x] = len(targets)
            targets.append(erg[y, x])
        else:
            card_t[y, x] = -2

    over = {}
    for a, b, px, py in OVERLAYS:
        for k in (a, b):
            (cx, cy), (cw, ch) = cell_box(cells[k])
            can = cell_canvas(cells[k], data, mapping, (cx, cy), (cw, ch))
            srcs = src_of(cells_json, k)
            t = np.full((ch, cw), -1, np.int64)
            cap = np.full((ch, cw, 3), np.nan)
            cap_on = np.zeros((ch, cw), bool)
            for o in cells[k]:
                sx, sy = srcs[(o['x'], o['y'])]
                X, Y = o['x'] - cx, o['y'] - cy
                cap[Y:Y + o['h'], X:X + o['w']] = erg[sy:sy + o['h'], sx:sx + o['w']]
                cap_on[Y:Y + o['h'], X:X + o['w']] = eal[sy:sy + o['h'], sx:sx + o['w']] > ALPHA_ON
            for y in range(ch):
                for x in range(cw):
                    if can[y, x] <= 0:
                        continue                      # no OBJ pixel, or transparent: the logo shows through
                    X, Y = px + cx + x, py + cy + y   # screen = logo canvas coordinates
                    if not (0 <= X < CARD_W and 0 <= Y < CARD_H) or not mask[Y, X]:
                        continue
                    if can[y, x] == fan[Y, X]:
                        t[y, x] = -3                  # copy of the logo: take the new logo's index
                    elif cap_on[y, x]:
                        t[y, x] = len(targets)
                        targets.append(cap[y, x])
                    else:
                        t[y, x] = -2
            over[k] = dict(origin=(cx, cy), size=(cw, ch), fan=can, t=t, pos=(px, py))

    # palette: indices still used by kept pixels stay
    keep = set(fan[obj & (card_t == -1)].ravel().tolist())
    for k in range(1, len(cells)):
        if not cells[k]:
            continue
        (cx, cy), (cw, ch) = cell_box(cells[k])
        can = cell_canvas(cells[k], data, mapping, (cx, cy), (cw, ch))
        kept = can >= 0
        if k in over:
            kept &= over[k]['t'] == -1
        keep |= set(can[kept].ravel().tolist())
    keep.discard(-1)
    keep.add(0)
    fixed_idx = sorted(i for i in keep if i != 0)
    free = [i for i in range(1, 256) if i not in keep]
    targets = np.array(targets, np.float64)
    newc = choose_colours(targets, pal[fixed_idx], len(free))
    slots = free[:len(newc)]
    new_pal = pal.copy()
    for s, c in zip(slots, newc):
        new_pal[s] = c
    cand = fixed_idx + slots
    pick, dist = nearest(to_lab(targets), to_lab(new_pal[cand]))
    tidx = np.array(cand, np.int64)[pick]

    out = fan.copy()
    sel = card_t >= 0
    out[sel] = tidx[card_t[sel]]
    out[card_t == -2] = 0
    write_cell(new_data, cells[0], mapping, CARD_ORIGIN, np.where(obj, out, 0))
    for k, ov in over.items():
        can, t = ov['fan'], ov['t']
        px, py = ov['pos']
        cx, cy = ov['origin']
        res = can.copy()
        for y, x in zip(*np.nonzero(t != -1)):
            v = t[y, x]
            if v >= 0:
                res[y, x] = tidx[v]
            elif v == -2:
                res[y, x] = 0
            else:
                res[y, x] = out[py + cy + y, px + cx + x]
        write_cell(new_data, cells[k], mapping, ov['origin'], np.maximum(res, 0))
        ov['new'] = res

    g = bytearray(gfx)
    g[doff:doff + len(new_data)] = new_data
    p = bytearray(palb)
    for s in slots:
        r, gg, b = (int(v) >> 3 for v in new_pal[s])
        struct.pack_into('<H', p, poff + 2 * s, r | gg << 5 | b << 10)
    if len(g) != len(gfx) or len(p) != len(palb):
        raise OpeningCardError('a part changed size')
    info = dict(mask=mask, m_eng=m_eng, m_fan=m_fan, fan=fan, new=np.where(obj, out, -1), over=over,
                kept=len(fixed_idx), new_colours=len(slots), free=len(free), redrawn=int(len(targets)),
                lost=lost, mean_de=float(dist.mean()) if len(dist) else 0.0,
                max_de=float(dist.max()) if len(dist) else 0.0, pal=new_pal)
    return bytes(g), bytes(p), info


# ---------------------------------------------------------------- patch

def patch(container, dumpdir, log=None, any_rom=False):
    """-> (new container bytes, changed, info). Raises OpeningCardError on a
    foreign or stale input unless any_rom (then logs and leaves it alone)."""
    from ncer import ncer
    log = log or (lambda s: None)

    def skip(why):
        if not any_rom:
            raise OpeningCardError('%s (pass --any-rom to build without the opening card)' % why)
        log('opening card: NOT redrawn, --any-rom given (%s)' % why)
        return container, False, None

    try:
        ents = {i: entry(container, i) for i in FAN_SHA256}
    except (OpeningCardError, IndexError, ValueError) as e:
        return skip('%s does not read as the fan\'s (%s)' % (CONTAINER, e))
    for i, want in FAN_SHA256.items():
        have = hashlib.sha256(ents[i][0]).hexdigest()
        if have != want:
            return skip('%s entry %d sha256 %s is not the fan\'s' % (CONTAINER, i, have[:12]))
    if ents[E_GFX][2] is not True or ents[E_PAL][2] is not False:
        return skip('%s entries %d/%d are not stored as the fan stores them' % (CONTAINER, E_GFX, E_PAL))
    with open(os.path.join(cache_dir(dumpdir), CELL_LIST + '_cells.json')) as f:
        cj = json.load(f)
    cells, mapping = ncer(ents[E_CELLS][0])
    why = check_cells(cj, cells)
    if why:
        raise OpeningCardError(why)
    eng, jpn = load_atlas(dumpdir, TEX_ENG), load_atlas(dumpdir, TEX_JPN)
    gfx, palb, info = compose(ents[E_GFX][0], ents[E_PAL][0], cells, mapping, eng, jpn, cj)
    out = rebuild(container, {E_GFX: gfx, E_PAL: palb}, lz=(E_GFX,))
    g2, gs, gc = entry(out, E_GFX)
    p2, ps, pc = entry(out, E_PAL)
    if g2 != gfx or p2 != palb or not gc or pc:
        raise OpeningCardError('%s entries %d/%d do not round-trip' % (CONTAINER, E_GFX, E_PAL))
    for i in range(len(_table(out)[0])):
        if i in (E_GFX, E_PAL):
            continue
        if not _table(container)[0][i][0]:
            continue
        was, now = entry(container, i), entry(out, i)
        if (now[0], now[2]) != (was[0], was[2]) or now[1][:len(was[1])] != was[1] or any(now[1][len(was[1]):]):
            raise OpeningCardError('%s entry %d changed' % (CONTAINER, i))
    fan_stored = len(ents[E_GFX][1])
    info.update(stored=len(gs), fan_stored=fan_stored, decoded=len(g2), fan_decoded=len(ents[E_GFX][0]))
    log('opening card: Capcom\'s English cake-show logo (%s entries %d/%d): %d px redrawn (mask %d logo px), '
        '%d palette colours kept, %d new of %d free, colour error mean %.1f max %.1f (CIELAB), %d English px outside the OBJs; '
        'tiles decoded %d bytes (fan %d), stored %d (fan %d), palette %d bytes uncompressed'
        % (CONTAINER, E_GFX, E_PAL, info['redrawn'], int(info['mask'].sum()), info['kept'], info['new_colours'],
           info['free'], info['mean_de'], info['max_de'], info['lost'], len(g2), len(ents[E_GFX][0]),
           len(gs), fan_stored, len(p2)))
    return out, True, info


def apply_to_rom(rom, dumpdir, log=None, any_rom=False):
    import title_logo
    from choice_strips import rom_file
    cur = rom_file(rom, CONTAINER)
    new, changed, _info = patch(cur, dumpdir, log, any_rom)
    if not changed:
        return rom, False
    return title_logo.splice(rom, CONTAINER, new), True


if __name__ == '__main__':
    if len(sys.argv) != 4:
        raise SystemExit('usage: opening_card.py FAN_opening_local.bin DUMPDIR OUT.bin')
    src, dump, dst = sys.argv[1:4]
    new, changed, _i = patch(open(src, 'rb').read(), dump, print)
    open(dst, 'wb').write(new)
    print('wrote', dst, '(changed)' if changed else '(unchanged)')
