# -*- coding: utf-8 -*-
"""Capcom's names on the security plan inside the bag model (texture bag_01).

When the plans come out of the bag in the trash-can search, the game shows a 3D
model, and the paper's picture is a texture, not a close-up: jpn/modelitemlocal.bin
entry 1 (BTX0), texture `bag_01`, 256x256, 256 colours (format 4), palette
`bag_01_pl`. The paper is the plan picture of jpn/upcut_local.bin entry 8
squashed into about 188x126 texels at (4,0), so it carries the fan's
"Rooke / Knightley" legend and handwriting, which close-up 8 no longer shows
(tools/cg_art.py draws Capcom's Rook / Knight there from
tools/cg_art_final/008.png).

This module puts the same new names into the texture, and nothing else:

  1. mask: where the fan's picture 8 and the shipped picture
     tools/cg_art_final/008.png differ (the legend names and the handwriting),
     thresholded and grown a little, mapped through the registration
     tools/bag_tex_reg.json (a per-axis scale and offset from the picture's
     pixels to the texture's texels, fitted once offline by
     tools/bag_tex_register.py).
  2. inside the mask only, the shipped picture is area-averaged through the same
     transform, shifted by the texture's own tone there (the texture is about 22
     levels darker than the picture it came from and shaded unevenly; the offset is
     measured outside the mask and blurred across it), and snapped to the texture's
     EXISTING palette (nearest colour in CIELAB, no dithering). Every texel outside the mask keeps the fan's index,
     and the palette bytes are not touched, so the paper, the clip and the frame
     are as they were.
  3. the BTX0 keeps its decompressed size, and the entry is stored as a real LZ11
     stream (tools/lz11.py) no larger than the fan's stored entry, so that no
     buffer the game sized for the fan's entry can be outgrown (the file-system
     layer sizes its buffers from the archive table; how this model loader uses
     the decoded bytes was not traced). tools/bufcheck.py checks both on the
     built ROM.

patch() guards on the sha256 of the fan's decoded BTX0 and of the fan's decoded
picture 8, and leaves the file alone (with the reason logged) if either differs,
so the routine never ships unproven.

    texture(btx, name) / palette(btx, name) / with_texture(btx, name, idx)
    python tools/bag_tex.py FAN_modelitemlocal.bin DUMPDIR OUT.bin
"""
import sys, os, struct, json, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REG_JSON = os.path.join(HERE, 'bag_tex_reg.json')
CONTAINER = 'jpn/modelitemlocal.bin'
ENTRY = 1
TEXTURE = 'bag_01'
PALETTE = 'bag_01_pl'
PIC_W, PIC_H = 256, 192
FAN_BTX_SHA256 = '567f08ef5f948c06db13b16a7eb08397aced634fd214a6547de0a833f8aefdbf'      # the fan's decoded entry 1
FAN_PICTURE_SHA256 = '371f112bd91cdad164a8449db7ca211686e46ce52710b0c89edadabf1d3a794d'   # the fan's picture 8, RGB bytes
FMT_256 = 4                     # 8 bits per texel, palette of up to 256 colours
MASK_THRESHOLD = 10             # summed |R,G,B| difference that counts as changed (the two pictures are
                                # identical outside the names: 496 pixels differ at 0, 489 at 20)
MASK_GROW = 2                   # picture pixels the changed area is grown by
TONE_SIGMA = 6.0                # texels; the blur that spreads the texture's tone over the redrawn patch


class BagTexError(ValueError):
    pass


# ---------------------------------------------------------------- BTX0 / TEX0

def _dict(d, off):
    """Entries and names of a 3D info dictionary at `off`:
    [(name, entry bytes)]. Layout: u8 0, u8 count, u16 size; u16 8, u16 size of
    the tree part (count + 1 nodes of 4 bytes behind an 8-byte head);
    u16 entry size, u16 size; count entries; count names of 16 bytes."""
    if off + 4 > len(d):
        raise BagTexError('dictionary at %#x is outside the data' % off)
    cnt = d[off + 1]
    tree = struct.unpack_from('<H', d, off + 6)[0]
    if tree != 8 + (cnt + 1) * 4:
        raise BagTexError('dictionary at %#x has an unexpected tree size %#x for %d entries' % (off, tree, cnt))
    p = off + tree
    entsz = struct.unpack_from('<H', d, p)[0]
    p += 4
    end = p + cnt * entsz + cnt * 16
    if entsz < 4 or end > len(d):
        raise BagTexError('dictionary at %#x does not fit in the data' % off)
    out = []
    for i in range(cnt):
        e = bytes(d[p + i * entsz:p + (i + 1) * entsz])
        n = p + cnt * entsz + i * 16
        out.append((bytes(d[n:n + 16]).split(b'\0')[0].decode('latin1'), e))
    return out


def parse(btx):
    """Locate the texture and palette records of a BTX0.
    -> {'tex0': offset of the TEX0 block, 'textures': {name: info}, 'palettes': {name: (offset, size)}}.
    A texture's info holds its absolute data offset, size, width, height,
    format and the colour-0-transparent flag."""
    if btx[:4] != b'BTX0':
        raise BagTexError('not a BTX0 (starts %r)' % (bytes(btx[:4]),))
    size = struct.unpack_from('<I', btx, 8)[0]
    nblk = struct.unpack_from('<H', btx, 14)[0]
    if size != len(btx):
        raise BagTexError('BTX0 declares %d bytes, has %d' % (size, len(btx)))
    base = None
    for k in range(nblk):
        o = struct.unpack_from('<I', btx, 16 + 4 * k)[0]
        if btx[o:o + 4] == b'TEX0':
            base = o
    if base is None:
        raise BagTexError('BTX0 holds no TEX0 block')
    texinfo = struct.unpack_from('<H', btx, base + 0x0E)[0]
    texdata = struct.unpack_from('<I', btx, base + 0x14)[0]
    palsize = struct.unpack_from('<I', btx, base + 0x30)[0] << 3     # stored in units of 8 bytes
    palinfo = struct.unpack_from('<I', btx, base + 0x34)[0]
    paldata = struct.unpack_from('<I', btx, base + 0x38)[0]
    textures = {}
    for name, e in _dict(btx, base + texinfo):
        off, par = struct.unpack_from('<HH', e, 0)
        w, h, fmt = 8 << ((par >> 4) & 7), 8 << ((par >> 7) & 7), (par >> 10) & 7
        bits = {1: 8, 2: 2, 3: 4, 4: 8, 5: 2, 6: 8, 7: 16}.get(fmt)
        if bits is None:
            raise BagTexError('texture %s has format %d' % (name, fmt))
        textures[name] = dict(off=base + texdata + (off << 3), size=w * h * bits // 8, w=w, h=h, fmt=fmt,
                              c0t=bool(par & 0x2000))
    pals = {}
    ents = _dict(btx, base + palinfo)
    offs = sorted(struct.unpack_from('<H', e, 0)[0] << 3 for _n, e in ents)
    for name, e in ents:
        o = struct.unpack_from('<H', e, 0)[0] << 3
        nxt = [q for q in offs if q > o]
        pals[name] = (base + paldata + o, (nxt[0] if nxt else palsize) - o)
    return dict(tex0=base, textures=textures, palettes=pals)


def _tex(btx, name):
    info = parse(btx)['textures'].get(name)
    if info is None:
        raise BagTexError('no texture %s in this BTX0' % name)
    if info['fmt'] != FMT_256:
        raise BagTexError('texture %s is format %d, only the 256-colour format is handled' % (name, info['fmt']))
    return info


def texture(btx, name):
    """Palette indices of a format-4 texture -> uint8 array (height, width)."""
    t = _tex(btx, name)
    return np.frombuffer(bytes(btx[t['off']:t['off'] + t['size']]), np.uint8).reshape(t['h'], t['w']).copy()


def palette(btx, name):
    """The texture's palette -> (raw bytes, list of (r, g, b) at 8 bits)."""
    p = parse(btx)['palettes'].get(name)
    if p is None:
        raise BagTexError('no palette %s in this BTX0' % name)
    raw = bytes(btx[p[0]:p[0] + p[1]])
    cols = []
    for i in range(0, len(raw) - 1, 2):
        v = struct.unpack_from('<H', raw, i)[0]
        r, g, b = (v & 31) << 3, ((v >> 5) & 31) << 3, ((v >> 10) & 31) << 3
        cols.append((r | r >> 5, g | g >> 5, b | b >> 5))
    return raw, cols


def with_texture(btx, name, idx):
    """A copy of the BTX0 with the texture's indices replaced; same size."""
    t = _tex(btx, name)
    idx = np.asarray(idx)
    if idx.shape != (t['h'], t['w']) or idx.dtype != np.uint8:
        raise BagTexError('texture %s needs %dx%d uint8 indices, got %s %s'
                          % (name, t['w'], t['h'], idx.shape, idx.dtype))
    out = bytearray(btx)
    out[t['off']:t['off'] + t['size']] = idx.tobytes()
    if len(out) != len(btx):
        raise BagTexError('BTX0 changed size %d -> %d' % (len(btx), len(out)))
    return bytes(out)


# ---------------------------------------------------------------- resampling

def coverage(n_dst, n_src, scale, offset):
    """Matrix (n_dst, n_src): row u holds the share of destination cell
    [u, u+1] that each source cell [x, x+1] covers, where destination = offset +
    scale * source (an area-average filter). Rows whose footprint leaves the
    source are zero and flagged False in the second result."""
    u0 = (np.arange(n_dst) - offset) / scale
    u1 = (np.arange(n_dst) + 1 - offset) / scale
    x = np.arange(n_src)
    lo = np.maximum(u0[:, None], x[None, :])
    hi = np.minimum(u1[:, None], x[None, :] + 1)
    m = np.clip(hi - lo, 0, None) / (u1 - u0)[:, None]
    inside = (u0 >= 0) & (u1 <= n_src)
    m[~inside] = 0
    return m, inside


def resample(img, reg, size):
    """Area-average `img` (h, w[, c], float) into a (size, size) texel grid by
    the registration [sx, sy, ox, oy]. -> (array, valid rows mask, valid cols mask)."""
    sx, sy, ox, oy = reg
    mx, vx = coverage(size, img.shape[1], sx, ox)
    my, vy = coverage(size, img.shape[0], sy, oy)
    if img.ndim == 2:
        return my @ img @ mx.T, vy, vx
    out = np.stack([my @ img[:, :, c] @ mx.T for c in range(img.shape[2])], axis=2)
    return out, vy, vx


# ---------------------------------------------------------------- the change

def load_reg(path=REG_JSON):
    with open(path) as f:
        reg = json.load(f)['reg']
    if len(reg) != 4:
        raise BagTexError('%s: expected [sx, sy, ox, oy]' % path)
    return [float(v) for v in reg]


def grow(mask, n):
    """Mask grown by n pixels in every direction (a square window)."""
    out = mask.copy()
    h, w = mask.shape
    for dy in range(-n, n + 1):
        for dx in range(-n, n + 1):
            out[max(0, dy):h + min(0, dy), max(0, dx):w + min(0, dx)] |= \
                mask[max(0, -dy):h + min(0, -dy), max(0, -dx):w + min(0, -dx)]
    return out


def changed_mask(fan, new, threshold=MASK_THRESHOLD, n=MASK_GROW):
    """Where two (192, 256, 3) pictures differ: summed channel difference over
    `threshold`, grown by `n` pixels."""
    d = np.abs(new.astype(np.int32) - fan.astype(np.int32)).sum(axis=2)
    return grow(d > threshold, n)


def texel_mask(mask, reg, size):
    """The texels any part of whose footprint lies on a masked picture pixel."""
    cov, vy, vx = resample(mask.astype(np.float64), reg, size)
    m = cov > 1e-9
    bad = m & ~(vy[:, None] & vx[None, :])
    if bad.any():
        y, x = np.argwhere(bad)[0]
        raise BagTexError('mask texel (%d,%d) reaches outside the picture; the registration or mask is off' % (x, y))
    return m


def to_lab(rgb):
    """sRGB (..., 3), 0..255 -> CIELAB (D65)."""
    c = np.asarray(rgb, np.float64) / 255.0
    c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    m = np.array([[0.4124564, 0.3575761, 0.1804375],
                  [0.2126729, 0.7151522, 0.0721750],
                  [0.0193339, 0.1191920, 0.9503041]])
    xyz = c @ m.T / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 216 / 24389, np.cbrt(xyz), (24389 / 27 * xyz + 16) / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], axis=-1)


def nearest(rgb, pal):
    """Index of the palette colour nearest each pixel of rgb (h, w, 3) in CIELAB."""
    lab, plab = to_lab(rgb), to_lab(np.array(pal, np.float64))
    d = ((lab[:, :, None, :] - plab[None, None, :, :]) ** 2).sum(axis=3)
    return d.argmin(axis=2).astype(np.uint8), np.sqrt(d.min(axis=2))


def blur(a, sigma):
    """Gaussian blur of a (h, w) array, zero outside the array, as two matrix products."""
    def kernel(n):
        i = np.arange(n)
        k = np.exp(-((i[:, None] - i[None, :]) ** 2) / (2.0 * sigma * sigma))
        k[np.abs(i[:, None] - i[None, :]) > 3 * sigma] = 0
        return k
    return kernel(a.shape[0]) @ a @ kernel(a.shape[1]).T


def tone_offset(tex_rgb, fan_res, weight, need, sigma=TONE_SIGMA):
    """Smooth per-channel offset (texture minus the fan's picture resampled to
    texels), measured where `weight` is 1 and filled in over the rest by a
    normalised Gaussian blur; every texel of `need` must have some weight near it. The model texture is a little darker and shaded
    differently from the picture it was made from, so a patch of the picture
    pasted in as it is would show as a pale box."""
    wt = weight.astype(np.float64)
    den = blur(wt, sigma)
    if (den[need] < 1e-3).any():
        raise BagTexError('no texture around part of the mask to take the tone from')
    err = tex_rgb - fan_res
    return np.stack([blur(err[:, :, c] * wt, sigma) for c in range(3)], axis=2) / np.maximum(den, 1e-9)[:, :, None]


def compose(btx, fan, new, reg=None, tone=TONE_SIGMA):
    """The BTX0 with the changed texels of bag_01 redrawn from `new` (a
    (192, 256, 3) picture), `fan` being the picture the fan's texture was made
    from; `tone` 0 pastes the new picture's own colours. -> (new BTX0 bytes, info dict)."""
    reg = reg or load_reg()
    idx = texture(btx, TEXTURE)
    _raw, pal = palette(btx, PALETTE)
    size = idx.shape[0]
    tm = texel_mask(changed_mask(fan, new), reg, size)
    res, vy, vx = resample(new.astype(np.float64), reg, size)
    if tone:
        fres, _vy, _vx = resample(fan.astype(np.float64), reg, size)
        rgb = np.array(pal, np.float64)[idx]
        ok = np.zeros((size, size), bool)
        ok[2:-2, 2:-2] = (vy[:, None] & vx[None, :])[2:-2, 2:-2]
        res = res + tone_offset(rgb, fres, ok & ~grow(tm, 4), tm, tone)
    snapped, dist = nearest(np.clip(res, 0, 255), pal)
    out = idx.copy()
    out[tm] = snapped[tm]
    return with_texture(btx, TEXTURE, out), dict(texels=int(tm.sum()), moved=int((out != idx).sum()),
                                                 mean_de=float(dist[tm].mean()), max_de=float(dist[tm].max()),
                                                 mask=tm)


# ---------------------------------------------------------------- container

def _slot(d, i):
    """(stored bytes, decoded size, compressed flag) of entry i of an 8-byte-table archive."""
    n = struct.unpack_from('<I', d, 0)[0] // 8
    if not 0 <= i < n:
        raise BagTexError('container has %d entries, no entry %d' % (n, i))
    o, s = struct.unpack_from('<II', d, i * 8)
    nxt = min([struct.unpack_from('<I', d, k * 8)[0] for k in range(n)
               if struct.unpack_from('<I', d, k * 8)[0] > o] + [len(d)])
    return bytes(d[o:nxt]), s & 0x7FFFFFFF, bool(s & 0x80000000)


def entry_btx(container):
    """-> (decoded BTX0 of ENTRY, stored size, decoded size)."""
    import lz11
    stored, size, comp = _slot(container, ENTRY)
    if not comp:
        raise BagTexError('%s entry %d is expected to be an LZ11 stream' % (CONTAINER, ENTRY))
    btx = lz11.decompress(stored)
    if len(btx) != size:
        raise BagTexError('%s entry %d decodes to %d bytes, its table says %d' % (CONTAINER, ENTRY, len(btx), size))
    return btx, len(stored), size


def patch(container, fan_picture, new_picture, log=None):
    """-> (new container bytes, changed). `fan_picture` and `new_picture` are
    (192, 256, 3) uint8 RGB. Leaves the container alone, and says why, when
    the fan's data are not what the routine was proven on; raises BagTexError
    if the result would not fit the fan's entry."""
    log = log or (lambda s: None)

    def skip(why):
        log('bag texture: not redrawn (%s)' % why)
        return container, False

    btx, fan_stored, fan_size = entry_btx(container)
    have = hashlib.sha256(btx).hexdigest()
    if have != FAN_BTX_SHA256:
        return skip('%s entry %d sha256 %s is not the fan\'s' % (CONTAINER, ENTRY, have[:12]))
    have = hashlib.sha256(np.ascontiguousarray(fan_picture).tobytes()).hexdigest()
    if have != FAN_PICTURE_SHA256:
        return skip('the fan\'s picture 8 sha256 %s is not the one the registration was fitted on' % have[:12])
    if fan_picture.shape != (PIC_H, PIC_W, 3) or new_picture.shape != (PIC_H, PIC_W, 3):
        raise BagTexError('pictures must be %dx%d RGB' % (PIC_W, PIC_H))
    new_btx, info = compose(btx, fan_picture, new_picture)
    if len(new_btx) != fan_size:
        raise BagTexError('BTX0 changed size %d -> %d' % (fan_size, len(new_btx)))
    from choice_strips import rebuild
    out = rebuild(container, {ENTRY: new_btx}, lz=(ENTRY,))
    back, stored, size = entry_btx(out)
    if back != new_btx or size != fan_size:
        raise BagTexError('%s entry %d does not round-trip through LZ11' % (CONTAINER, ENTRY))
    if stored > fan_stored:
        raise BagTexError('%s entry %d would be stored in %d bytes, the fan\'s is %d; it must not '
                          'be larger' % (CONTAINER, ENTRY, stored, fan_stored))
    log('bag texture: Capcom\'s names on the plan in the bag model (%s entry %d, %s): %d texels redrawn of %d, '
        'palette untouched, colour error in the redrawn texels mean %.1f max %.1f (CIELAB); '
        'decoded %d bytes (fan %d), stored %d (fan %d)'
        % (CONTAINER, ENTRY, TEXTURE, info['moved'], info['texels'], info['mean_de'], info['max_de'],
           size, fan_size, stored, fan_stored))
    return out, True


def fan_picture(dumpdir):
    """The fan's picture 8 (RGB array) from the fan's own jpn/upcut_local.bin."""
    import cg_art
    from txtcut import table
    E = table(open(os.path.join(dumpdir, 'ds_fan', 'jpn', 'upcut_local.bin'), 'rb').read())
    return np.asarray(cg_art.decode(E[8], E[9])[0], np.uint8)


def new_picture():
    import cg_art
    return np.asarray(cg_art.final_picture(8), np.uint8)


def apply_to_rom(rom, dumpdir, log=None):
    import title_logo
    from choice_strips import rom_file
    cur = rom_file(rom, CONTAINER)
    new, changed = patch(cur, fan_picture(dumpdir), new_picture(), log)
    if not changed:
        return rom, False
    return title_logo.splice(rom, CONTAINER, new), True


if __name__ == '__main__':
    if len(sys.argv) != 4:
        raise SystemExit('usage: bag_tex.py FAN_modelitemlocal.bin DUMPDIR OUT.bin')
    src, dump, out = sys.argv[1:4]
    new, changed = patch(open(src, 'rb').read(), fan_picture(dump), new_picture(), print)
    open(out, 'wb').write(new)
    print('wrote', out, '(changed)' if changed else '(unchanged)')
