# -*- coding: utf-8 -*-
"""Capcom's English evidence icons for the business card and the victim's letter
(com/idcom.bin entries 281, 573 and 575).

The Court Record's evidence icons are small 4bpp sprites in com/idcom.bin, each with
its own 16-colour RLCN in the entry before it. Three of them show a card with a
name on it that the fan's art draws as a fan name and the Collection spells
differently:

  281  64x64   the business card: the fan's "Raymond Shields", Capcom's Eddie Fender
               (Collection texture itm01_017_00_l_eng; the Japanese twin
               itm01_017_00_l reads 信楽 盾之)
  573  64x64   the victim's letter, with the fan's "Jill Crane"; Capcom's card reads
               Ms. Rosie Ringer (itm03_00f_00_l_eng; Japanese twin itm03_00f_00_l,
               篭目 つばさ様)
  575  40x40   the small twin of 573 (four OBJs of one cell)

The fan's icons are downscales of the same art the Collection ships as 300x300
textures, so the picture is swapped whole, not re-lettered (the fan's 1-2 pixel
strokes cannot be harvested and "Rosie Ringer" is longer than "Jill Crane" in
the same space):

  1. the Collection's English texture (extracted at build time from the player's own
     install into dump/title/idcom/, un-flipped, flat grey background)
  2. mapped onto the fan icon's framing with the registration in
     tools/idcom_icons_reg.json (a separate scale and offset per axis, texel =
     offset + scale * icon pixel, fitted offline by tools/idcom_icons_register.py
     against the JAPANESE twin texture), area-averaged (box filter) into the icon
     grid
  3. tone-mapped so the texture's flat grey background (128) is exactly the grey
     the fan's icon uses (123, the 5-bit value 15), lightly sharpened, and
     quantised WITHOUT dithering to 15 colours + the key: index 0 stays the green
     key (0,255,0) and is never drawn (the fan's icons use none either), the
     background colour keeps slot 4 like the fan's, and every colour is a
     5-bit-per-channel value, which is all the DS can show
  4. written back into the fan's entry with its layout untouched (the cell and OBJ
     data, the tile bank size, the palette's 16 slots), the palette entry's other
     bytes are the fan's

Container policy: everything is written IN PLACE. The container's table, every other
entry and every offset stay byte for byte the fan's; an icon's entry keeps its
decoded size and is stored as a real LZ11 stream (tools/lz11.py) that must fit in
the bytes the fan's entry held (padded with zeros), so no buffer the game sized
from the fan's table can be outgrown. tools/bufcheck.py (check h) verifies all of
that on the built ROM.

patch() guards on the sha256 of the fan's six decoded entries and raises if any
differs (under --any-rom it logs and leaves the file alone), so the routine never
ships unproven.

    python tools/idcom_icons.py FAN_idcom.bin DUMPDIR OUT.bin
"""
import sys, os, struct, json, hashlib, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
REG_JSON = os.path.join(HERE, 'idcom_icons_reg.json')
CONTAINER = 'com/idcom.bin'
BUNDLE_PREFIX = 'gk2_idcom_assets_all'          # not the _trial_ bundle
CACHE = ('title', 'idcom')                      # under the dump folder
TEX_SIZE = 300
TEX_BG = 128                                    # the textures' flat background grey
FAN_BG = 123                                    # the fan icons' background (5-bit 15) in the palette
BG_SLOT = 4                                     # where the fan keeps it
KEY = (0, 255, 0)
SHARPEN = dict(radius=0.6, percent=60, threshold=2)     # light unsharp mask on the downscaled 8-bit image
PAD = 64

# icon entry -> (palette entry, size, English texture, Japanese twin, sha256 of the fan's decoded icon entry,
#                sha256 of the fan's palette entry)
ICONS = {
    281: dict(pal=280, size=64, eng='itm01_017_00_l_eng', jp='itm01_017_00_l',
              sha='2be8838c776200bce5fe595552b2c59e13b9239e818915d75985ef41aea2a6f1',
              pal_sha='d9532fddb72f3d0379b271f9f7fd072035c0d1571926f7c1c915d71bcaf538b4'),
    573: dict(pal=572, size=64, eng='itm03_00f_00_l_eng', jp='itm03_00f_00_l',
              sha='ec8f048a8fdab433afc8cf6af3bcdec974fc39ab062d7e0c8a4bea16a512ee19',
              pal_sha='42b1421cdfbb2a7d073849e13bb38eb050f7378df86d5225a12f643228d520f5'),
    575: dict(pal=574, size=40, eng='itm03_00f_00_l_eng', jp='itm03_00f_00_l',
              sha='288b0e780e6d7091edeccb961b5fa0f2093582aeb2b7d2b6582c179bff172100',
              pal_sha='3a98cb59b87c7554fdd7740461829ff118ff5f405aaa79fb9c00d3ff19c1a33a'),
}
TEXTURES = sorted({v[k] for v in ICONS.values() for k in ('eng', 'jp')})


class IconError(ValueError):
    pass


# ---------------------------------------------------------------- the Collection's textures

def cache_dir(dumpdir):
    return os.path.join(dumpdir, *CACHE)


def required(dumpdir):
    """The harvested English textures apply_to_rom() needs (the Japanese twins are
    extracted too, for the offline registration, but the build does not read them)."""
    return [os.path.join(cache_dir(dumpdir), n + '.png') for n in sorted({v['eng'] for v in ICONS.values()})]


def extract(bdir, dumpdir):
    """Pull the four item textures out of the Collection's idcom bundle into
    dump/title/idcom/ as RGB PNGs, un-flipped (Unity stores them upside down),
    composited over the flat background grey if a texture has any transparency.
    Raises SystemExit if the bundle or a texture is missing, as the other extractors do."""
    hits = [p for p in glob.glob(os.path.join(bdir, '*.bundle'))
            if os.path.basename(p).lower().startswith(BUNDLE_PREFIX)]
    if not hits:
        raise SystemExit('idcom icons: no bundle starting with %r in %s' % (BUNDLE_PREFIX, bdir))
    import UnityPy
    env = UnityPy.load(hits[0])
    found = {}
    for obj in env.objects:
        if obj.type.name != 'Texture2D':
            continue
        d = obj.read()
        if d.m_Name in TEXTURES:
            found[d.m_Name] = d.image.copy()
    missing = [n for n in TEXTURES if n not in found]
    if missing:
        raise SystemExit('idcom icons: texture(s) %s not found in %s' % (', '.join(missing), os.path.basename(hits[0])))
    out = cache_dir(dumpdir)
    os.makedirs(out, exist_ok=True)
    for name, im in found.items():
        rgba = im.convert('RGBA')
        if rgba.size != (TEX_SIZE, TEX_SIZE):
            raise SystemExit('idcom icons: texture %s is %dx%d, expected %dx%d' % ((name,) + rgba.size + (TEX_SIZE, TEX_SIZE)))
        bg = Image.new('RGBA', rgba.size, (TEX_BG, TEX_BG, TEX_BG, 255))
        bg.alpha_composite(rgba)
        bg.convert('RGB').transpose(Image.FLIP_TOP_BOTTOM).save(os.path.join(out, name + '.png'))
    return out


def load_texture(dumpdir, name):
    p = os.path.join(cache_dir(dumpdir), name + '.png')
    if not os.path.isfile(p):
        raise IconError('texture %s is missing (%s); run the build once without --skip-extract' % (name, p))
    im = Image.open(p).convert('RGB')
    if im.size != (TEX_SIZE, TEX_SIZE):
        raise IconError('texture %s is %dx%d, expected %dx%d' % ((name,) + im.size + (TEX_SIZE, TEX_SIZE)))
    return np.asarray(im, np.float64)


# ---------------------------------------------------------------- resampling and quantising

def tone(a):
    """Map the textures' flat grey TEX_BG to FAN_BG, black and white fixed, piecewise linear."""
    a = np.asarray(a, np.float64)
    lo = a * (FAN_BG / TEX_BG)
    hi = FAN_BG + (a - TEX_BG) * ((255.0 - FAN_BG) / (255.0 - TEX_BG))
    return np.where(a <= TEX_BG, lo, hi)


def resample(tex, reg, size):
    """Area-average (box filter) the texture into size x size. reg = [sx, sy, ox, oy]:
    texel = o + s * icon pixel. -> float array (size, size, 3). The texture is padded
    with its own edge (flat background) so a footprint may reach a little outside."""
    sx, sy, ox, oy = reg
    box = (ox + PAD, oy + PAD, ox + PAD + sx * size, oy + PAD + sy * size)
    if box[0] < 0 or box[1] < 0 or box[2] > TEX_SIZE + 2 * PAD or box[3] > TEX_SIZE + 2 * PAD:
        raise IconError('registration %r reaches outside the texture' % (list(reg),))
    padded = np.pad(tex, ((PAD, PAD), (PAD, PAD), (0, 0)), mode='edge')
    out = np.zeros((size, size, 3))
    for c in range(3):
        im = Image.fromarray(padded[..., c].astype(np.float32), mode='F')
        out[..., c] = np.asarray(im.resize((size, size), Image.BOX, box=box))
    return out


def _disp(v):
    """The 8-bit colour a 5-bit channel value shows as (what nitro.nclr reads back)."""
    v = np.asarray(v, np.int64)
    return (v << 3) | (v >> 2)


DISP = _disp(np.arange(32))


def snap5(c):
    """Nearest 5-bit-per-channel colour to float RGB c -> (r5, g5, b5)."""
    return tuple(int(np.abs(DISP - float(x)).argmin()) for x in c)


def show(c5):
    return tuple(int(DISP[v]) for v in c5)


def quantise(rgb, ncol=15, weights=(3.0, 4.0, 2.0), iters=30):
    """Quantise an (h, w, 3) uint8 picture to `ncol` 5-bit colours, no dithering, the
    background grey FAN_BG one of them. -> (grid of indices into the colour list, list
    of (r5, g5, b5), background index)."""
    h, w, _ = rgb.shape
    px = rgb.reshape(-1, 3).astype(np.float64)
    wt = np.array(weights)
    bg5 = snap5((FAN_BG,) * 3)
    bg = np.array(show(bg5), np.float64)
    exact_bg = (np.abs(px - bg).max(1) < 0.5)
    rest = px[~exact_bg]
    k = ncol - 1
    if len(rest) < k:
        raise IconError('only %d non-background pixels' % len(rest))
    # start: PIL's median cut over the pixels that are not background
    im = Image.fromarray(rest.reshape(1, -1, 3).astype(np.uint8), 'RGB')
    q = im.quantize(colors=k, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    pal = np.array(q.getpalette()[:3 * k], np.float64).reshape(-1, 3)
    if len(pal) < k:
        pal = np.vstack([pal, np.tile(pal[-1], (k - len(pal), 1))])
    cen = pal[:k]
    # Lloyd, with the background fixed as one more centre
    for _ in range(iters):
        allc = np.vstack([bg[None], cen])
        d = (((px[:, None, :] - allc[None]) * wt) ** 2).sum(2)
        lab = d.argmin(1)
        new = cen.copy()
        for j in range(k):
            sel = lab == j + 1
            if sel.any():
                new[j] = px[sel].mean(0)
        if np.allclose(new, cen, atol=1e-3):
            break
        cen = new
    # snap to what the DS can show, dedupe (a duplicate or a copy of the background is a wasted slot)
    cols = []
    seen = {bg5}
    for c in cen:
        c5 = snap5(c)
        if c5 in seen:
            continue
        seen.add(c5)
        cols.append(c5)
    guard = 0
    while len(cols) < k and guard < 64:
        guard += 1
        allc = np.array([show(bg5)] + [show(c) for c in cols], np.float64)
        d = (((px[:, None, :] - allc[None]) * wt) ** 2).sum(2)
        err = d.min(1)
        for i in np.argsort(-err):
            c5 = snap5(px[i])
            if c5 not in seen:
                seen.add(c5)
                cols.append(c5)
                break
        else:
            break
    allc5 = [bg5] + cols
    allc = np.array([show(c) for c in allc5], np.float64)
    d = (((px[:, None, :] - allc[None]) * wt) ** 2).sum(2)
    lab = d.argmin(1)
    return lab.reshape(h, w), allc5, 0


def layout(grid, cols5, bg_i):
    """Place the colours in the fan's slot layout: slot 0 the key (never drawn), the
    background in BG_SLOT, the rest in ascending luma around it. -> (grid of slots,
    list of 16 (r5, g5, b5) with the key as (0, 31, 0))."""
    others = [i for i in range(len(cols5)) if i != bg_i]
    others.sort(key=lambda i: (0.299 * show(cols5[i])[0] + 0.587 * show(cols5[i])[1] + 0.114 * show(cols5[i])[2], cols5[i]))
    free = [s for s in range(1, 16) if s != BG_SLOT]
    if len(others) > len(free):
        raise IconError('%d colours do not fit %d slots' % (len(others), len(free)))
    slot = {bg_i: BG_SLOT}
    for s, i in zip(free, others):
        slot[i] = s
    pal = [(0, 31, 0)] * 16
    for i, s in slot.items():
        pal[s] = cols5[i]
    # unused slots (fewer colours than slots) repeat the background rather than the key
    used = set(slot.values())
    for s in range(1, 16):
        if s not in used:
            pal[s] = cols5[bg_i]
    lut = np.zeros(len(cols5), np.uint8)
    for i, s in slot.items():
        lut[i] = s
    return lut[grid], pal


def compose_picture(tex, reg, size, sharpen=True):
    """Texture -> (grid of palette slots (size, size) uint8, 16 palette colours as 5-bit tuples)."""
    small = resample(tone(tex), reg, size)
    im = Image.fromarray(np.clip(np.rint(small), 0, 255).astype(np.uint8), 'RGB')
    if sharpen:
        im = im.filter(ImageFilter.UnsharpMask(**SHARPEN))
    rgb = np.asarray(im)
    grid, cols5, bg_i = quantise(rgb)
    return layout(grid, cols5, bg_i)


def palette_bytes(fan_pal, cols5):
    """The fan's RLCN entry with its 16 colours replaced (BGR555); every other byte the fan's."""
    if fan_pal[:4] != b'RLCN':
        raise IconError('palette entry does not start with RLCN')
    ttlp = fan_pal.find(b'TTLP')
    dsize, ncol = struct.unpack_from('<II', fan_pal, ttlp + 16)
    if dsize != 32 or ncol != 16:
        raise IconError('palette is %d bytes / %d colours, expected 32 / 16' % (dsize, ncol))
    off = ttlp + 8 + 16
    out = bytearray(fan_pal)
    for i, (r, g, b) in enumerate(cols5):
        struct.pack_into('<H', out, off + 2 * i, r | (g << 5) | (b << 10))
    out[off:off + 2] = fan_pal[off:off + 2]         # the key stays the fan's bytes
    return bytes(out)


# ---------------------------------------------------------------- container

def table(d):
    n = struct.unpack_from('<I', d, 0)[0] // 8
    return [struct.unpack_from('<II', d, i * 8) for i in range(n)]


def extents(t, total):
    """{entry: (start, end)}: each slot ends where the next one in file order begins."""
    live = sorted({o for o, _s in t if o})
    out = {}
    for i, (o, _s) in enumerate(t):
        nxt = [q for q in live if q > o]
        out[i] = (o, nxt[0] if nxt else total)
    return out


def entry_decoded(container, i):
    """-> (decoded bytes, stored extent in bytes) of entry i; a stream is LZ11-decoded."""
    import lz11
    t = table(container)
    a, b = extents(t, len(container))[i]
    st = bytes(container[a:b])
    s = t[i][1]
    if s & 0x80000000:
        out = lz11.decompress(st)
        if len(out) != (s & 0x7FFFFFFF):
            raise IconError('entry %d decodes to %d bytes, its table says %d' % (i, len(out), s & 0x7FFFFFFF))
        return out, len(st)
    return st[:s], len(st)


def _grid(entry):
    import choice_strips as cs
    return np.array(cs.grid(entry), np.uint8)


def _with_grid(entry, g):
    import choice_strips as cs
    new = cs.encode(entry, [list(map(int, r)) for r in g])
    if len(new) != len(entry):
        raise IconError('icon entry changed size %d -> %d' % (len(entry), len(new)))
    if not np.array_equal(_grid(new), g):
        raise IconError('icon entry does not read back as the picture written')
    return new


def fan_render(container, e):
    """The fan's icon as an RGB array (for renders and the registration tool)."""
    from nitro import nclr
    pal_e = ICONS[e]['pal']
    ent, _ = entry_decoded(container, e)
    pal, _ = entry_decoded(container, pal_e)
    g = _grid(ent)
    return np.array(nclr(pal), np.uint8)[g]


def patch(container, textures, reg, log=None, any_rom=False):
    """-> (new container bytes, changed, info). `textures` maps texture name to the
    300x300 RGB float array, `reg` maps entry number (str) to [sx, sy, ox, oy]."""
    import lz11
    log = log or (lambda s: None)

    def skip(why):
        if not any_rom:
            raise IconError('%s (pass --any-rom to build without the icons)' % why)
        log('evidence icons: NOT redrawn, --any-rom given (%s)' % why)
        return container, False, {}

    t = table(container)
    ext = extents(t, len(container))
    try:
        parts = {}
        for e, spec in ICONS.items():
            for i, want in ((e, spec['sha']), (spec['pal'], spec['pal_sha'])):
                dec, _n = entry_decoded(container, i)
                have = hashlib.sha256(dec).hexdigest()
                if have != want:
                    return skip('%s entry %d sha256 %s is not the fan\'s' % (CONTAINER, i, have[:12]))
                parts[i] = dec
    except (IndexError, ValueError, struct.error) as ex:
        return skip("%s does not read as the fan's (%s)" % (CONTAINER, ex))
    out = bytearray(container)
    info = {}
    for e, spec in ICONS.items():
        size = spec['size']
        grid, pal5 = compose_picture(textures[spec['eng']], reg[str(e)]['reg'], size)
        new_entry = _with_grid(parts[e], grid)
        new_pal = palette_bytes(parts[spec['pal']], pal5)
        stream = lz11.compress(new_entry)
        if lz11.decompress(stream) != new_entry:
            raise IconError('entry %d does not round-trip through LZ11' % e)
        a, b = ext[e]
        if len(stream) > b - a:
            raise IconError('entry %d would be stored in %d bytes, the fan\'s is %d; it must not be larger'
                            % (e, len(stream), b - a))
        out[a:b] = stream + b'\0' * (b - a - len(stream))
        pa, pb = ext[spec['pal']]
        if len(new_pal) != pb - pa:
            raise IconError('palette entry %d changed size' % spec['pal'])
        out[pa:pb] = new_pal
        info[e] = dict(stored=len(stream), fan_stored=b - a, decoded=len(new_entry),
                       colours=len(set(int(x) for x in grid.ravel())))
        log('evidence icon %d (%s): Capcom\'s %s at %dx%d, %d colours + key, decoded %d bytes (fan %d), stored %d (fan %d)'
            % (e, CONTAINER, spec['eng'], size, size, info[e]['colours'], len(new_entry), len(parts[e]),
               len(stream), b - a))
    if len(out) != len(container):
        raise IconError('container changed size')
    return bytes(out), True, info


def load_reg():
    with open(REG_JSON, 'r', encoding='utf-8') as f:
        return json.load(f)


def apply_to_rom(rom, dumpdir, log=None, any_rom=False):
    import title_logo
    from choice_strips import rom_file
    cur = rom_file(rom, CONTAINER)
    tex = {n: load_texture(dumpdir, n) for n in sorted({v['eng'] for v in ICONS.values()})}
    new, changed, _info = patch(cur, tex, load_reg(), log, any_rom)
    if not changed:
        return rom, False
    return title_logo.splice(rom, CONTAINER, new), True


if __name__ == '__main__':
    if len(sys.argv) != 4:
        raise SystemExit('usage: idcom_icons.py FAN_idcom.bin DUMPDIR OUT.bin')
    src, dump, out = sys.argv[1:4]
    tex = {n: load_texture(dump, n) for n in sorted({v['eng'] for v in ICONS.values()})}
    new, changed, _i = patch(open(src, 'rb').read(), tex, load_reg(), print)
    open(out, 'wb').write(new)
    print('wrote', out, '(changed)' if changed else '(unchanged)')
