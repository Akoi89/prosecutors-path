# -*- coding: utf-8 -*-
"""Item and evidence pictures that still carry the fan translation's wording where Capcom's own
English differs.

Every edit here is a small re-lettering of a picture the fan drew (or the retail art), done in place:
the picture's own palette, tiles and layout stay the fan's, only the pixels of the old wording and of
the new wording change. Where Capcom's own Collection texture shows the new wording, the letter
shapes are Capcom's (area-averaged down from its HD lettering); nothing is typed by hand.

Container policy (the Case 4 buffer rule): a changed entry keeps the fan's DECODED size, is stored as
a real LZ11 stream (tools/lz11.py) in no more bytes than the fan's entry held, and the palette entry
beside it is not touched. tools/bufcheck.py check m verifies that on the built ROM.

Each picture is guarded by the sha256 of the fan's decoded graphics entry and palette entry; a
different file raises (under --any-rom it is logged and the picture is left alone).

    class 1  weights: the marking "15Kg / 33lb" on the weight block becomes Capcom's "30 lb"
             jpn/upcut_local.bin 54, 58, 86 (the block, photos) and 84 (the pulley diagram: Capcom's
             block carries no marking there, so the old one is wiped), com/idcom.bin 327 (icon),
             com/logic_keyword.bin 82 and 92 (Logic keyword icons; entry 76's sneakers-and-rope icon
             shows only a few unreadable pixels of the block and is left alone)
"""
import sys, os, struct, hashlib, glob, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
REG_JSON = os.path.join(HERE, 'item_pics_reg.json')
GROUND = 128                                   # the textures' flat grey ground
BUNDLE_PREFIX = 'gk2_upcutlocal_assets_all'    # not the classic or trial bundle
CACHE = ('title', 'items')                     # under the dump folder
UPCUT = 'jpn/upcut_local.bin'
IDCOM = 'com/idcom.bin'
LOGICKW = 'com/logic_keyword.bin'


class ItemError(ValueError):
    pass


# ---------------------------------------------------------------- Capcom's lettering

WEIGHT_TEXTURE = 'itm01_029_00_l_eng'          # the weight icon, "30 lb" on the plaque (300x300, upright)
WEIGHT_WINDOW = (152, 166, 240, 199)           # x0, y0, x1, y1 around the plaque text in that texture


# ---------------------------------------------------------------- the Collection's close-up textures

def cache_dir(dumpdir):
    return os.path.join(dumpdir, *CACHE)


def swap_textures():
    """Every upcut_local texture the swaps read: the English one (drawn from) and the Japanese twin (only the
    offline registration needs it, but it is extracted with the rest)."""
    return sorted({v[k] for v in list(UPCUT_SWAPS.values()) + list(UPCUT_LOCALS.values()) + list(BANNERS.values()) for k in ('texture', 'jp')})


def required(dumpdir):
    """Files apply_to_rom() needs beyond the weight icon texture; build.py checks these under --skip-extract."""
    return [os.path.join(cache_dir(dumpdir), v['texture'] + '.png') for v in list(UPCUT_SWAPS.values()) + list(UPCUT_LOCALS.values()) + list(BANNERS.values())]


def extract(bdir, dumpdir):
    """Save the close-up textures as RGB PNGs (transparency composited over the ground grey) under dump/title/items/.
    Raises SystemExit if the bundle or a texture is missing, as the other extractors do."""
    names = swap_textures()
    if not names:
        return None
    hits = [p for p in glob.glob(os.path.join(bdir, '*.bundle'))
            if os.path.basename(p).lower().startswith(BUNDLE_PREFIX)
            and '_classic' not in os.path.basename(p).lower() and '_trial' not in os.path.basename(p).lower()]
    if not hits:
        raise SystemExit('item pictures: no bundle starting with %r in %s' % (BUNDLE_PREFIX, bdir))
    import UnityPy
    env = UnityPy.load(hits[0])
    found = {}
    for obj in env.objects:
        if obj.type.name != 'Texture2D':
            continue
        d = obj.read()
        if d.m_Name in names:
            found[d.m_Name] = d.image.copy()
    missing = [n for n in names if n not in found]
    if missing:
        raise SystemExit('item pictures: texture(s) %s not found in %s' % (', '.join(missing), os.path.basename(hits[0])))
    out = cache_dir(dumpdir)
    os.makedirs(out, exist_ok=True)
    for name, im in found.items():
        rgba = im.convert('RGBA')
        if rgba.size[0] != 1920:
            raise SystemExit('item pictures: texture %s is %dx%d, expected 1920 wide' % ((name,) + rgba.size))
        bg = Image.new('RGBA', rgba.size, (GROUND, GROUND, GROUND, 255))
        bg.alpha_composite(rgba)
        bg.convert('RGB').save(os.path.join(out, name + '.png'))
    return out


# sha256 of the RGB pixel bytes of every Collection close-up texture read here, as the extraction saves them; one that does not
# hash to this is a different Collection build and raises, like the fan's own entries do
TEXTURE_SHA = {
    'cut01_027': '233ca5e958e91a4be8af7990862585e2eadc2b325ba720884b2f8cdcf7508d67',
    'cut01_027_eng': 'c124612ba4936ce7218d1cc5ddfc571e027c4cbeed5a4156cd78c8a0c026f5c4',
    'cut02_001': '57efb3f0864030890d068ce77b0e95cde76ee5b9a8f45da98939576227ca6cd9',
    'cut02_001_eng': 'f11498829597b416b982f773632ae9e30bcf7b51fb1bb1a4f8175fc1f3b97dfb',
    'cut02_005': '910987d8cffc28d7873741443599f13f7b40537f16ee451a96d99faab7e5382f',
    'cut02_005_eng': '4872c1c2608e7dc871b3423d2609687c79f5709c6fdf712474f458651816f869',
    'cut02_006': '79b2bd4562d75eedccd736618e931cc78795edefd1cb7c1775dccff3e1bbbc5c',
    'cut02_006_eng': '3fbee7d68577a9904ad95d29be81e91ab788bf731e854cea3a8e538c83102a39',
    'cut02_031': '959baf615c8d9b443d40526fda6bc0de6633a034bcf45071cb5eb46e8fdaa6c8',
    'cut02_031_eng': 'b6fcffd8b2846272a8fdac66b7c936299b3e01e01758d925fa1e9528aef1241d',
    'cut02_032': '5c79b72fc7d6e3f3eec98b4883064b7ad40057abaf97cb45b22b66801ee78589',
    'cut02_032_eng': '5202a7ec39eeb840a40a239ef283d6d724907af26fbd1c2c90d3de872e8c0ced',
    'cut03_001': 'ccf2c30c508d976ba157f983175cc302acacb010a436a7bfa9cd851327b5bb4a',
    'cut03_001_eng': 'bf2d46bee6264ba327f3ea9f3d6cb8539ff4d698c41e19a1250947a7333eb883',
    'cut03_00e': '2962e528c1c1460943c6eb2cde45f5cd3dea5e0cd1b909d9502311d246c5a10a',
    'cut03_00e_eng': 'd534ad668b12d0ce7e7840b7b7a13cfacd3d61c771cf6f422471e116b5f34687',
    'cut03_017': '8464726f50ed9536f3d264d764d8e63b2ad97dfd282f2a2ec090f2dbb530eff5',
    'cut03_017_eng': 'b4602acb102ed7f17e25d569e12e9a2b843d190caaed2ae15a9209474533d391',
    'cut03_018': '5faa5d5e53df0907667d1eaf900872e2aadebaed354d8c625ca08f3459fe4373',
    'cut03_018_eng': '9906d077ac73f8f9aa46366bb5d68018606b4dc4c92edd7d7234700470251809',
    'cut04_035': '4dfd2d3ccb0802d01720646c6da0e64b123459780b5d9f1f36f042a7e3e7bae0',
    'cut04_035_eng': '2b6d25ae8360970c10f90e73b6bfdaa5504f790d0616c6b7a3ac2399ca2daa14',
}


def load_texture(dumpdir, name):
    p = os.path.join(cache_dir(dumpdir), name + '.png')
    if not os.path.isfile(p):
        raise ItemError('texture %s is missing (%s); run the build once without --skip-extract' % (name, p))
    im = Image.open(p).convert('RGB')
    have = hashlib.sha256(np.asarray(im).tobytes()).hexdigest()
    if TEXTURE_SHA.get(name) != have:
        raise ItemError('texture %s (sha256 %s) is not the Collection build these pictures were made against' % (name, have[:12]))
    return np.asarray(im, np.float64)


def load_reg():
    with open(REG_JSON, 'r', encoding='utf-8') as f:
        return json.load(f)


def resample(tex, reg, w, h):
    """Area-average (box filter) the rectangle of the texture that the picture covers into w x h.
    reg = [sx, sy, ox, oy]: texel = o + s * picture pixel. -> float array (h, w, 3)."""
    if len(reg) == 9:
        return resample_h(tex, reg, w, h)
    sx, sy, ox, oy = reg
    box = (ox, oy, ox + sx * w, oy + sy * h)
    if box[0] < 0 or box[1] < 0 or box[2] > tex.shape[1] or box[3] > tex.shape[0]:
        raise ItemError('registration %r reaches outside the %dx%d texture' % (list(reg), tex.shape[1], tex.shape[0]))
    out = np.zeros((h, w, 3))
    for c in range(3):
        im = Image.fromarray(tex[..., c].astype(np.float32), mode='F')
        out[..., c] = np.asarray(im.resize((w, h), Image.BOX, box=box))
    return out


HOMOGRAPHY_PRE = 4


def resample_h(tex, hm, w, h):
    """A picture of w x h pixels sampled from the texture through a homography hm (nine numbers, row major): texel
    = H (x, y, 1) for a picture pixel (x, y), both with the pixel centre at the integer (the OpenCV convention the offline
    registration uses). The texture is first area-averaged down by HOMOGRAPHY_PRE, then sampled bicubically (PIL), so
    the result is an area average to within a pixel. -> float array (h, w, 3)."""
    H = np.array(hm, np.float64).reshape(3, 3)
    F = float(HOMOGRAPHY_PRE)
    th, tw = tex.shape[:2]
    if th % HOMOGRAPHY_PRE or tw % HOMOGRAPHY_PRE:
        raise ItemError('texture size %dx%d is not a multiple of %d' % (tw, th, HOMOGRAPHY_PRE))
    tr = lambda a, b: np.array([[1, 0, a], [0, 1, b], [0, 0, 1.0]])
    pad = 8                                          # edge pixels repeated, so a sample just outside the texture is not black
    M = tr(pad, pad) @ np.diag([1.0 / F, 1.0 / F, 1.0]) @ tr(0.5, 0.5) @ H @ tr(-0.5, -0.5)
    M = M / M[2, 2]
    out = np.zeros((h, w, 3))
    for c in range(3):
        small = Image.fromarray(tex[..., c].astype(np.float32), mode='F').resize((tw // HOMOGRAPHY_PRE, th // HOMOGRAPHY_PRE), Image.BOX)
        padded = Image.fromarray(np.pad(np.asarray(small), pad, mode='edge'), mode='F')
        out[..., c] = np.asarray(padded.transform((w, h), Image.PERSPECTIVE, tuple(M.flatten()[:8]), Image.BICUBIC))
    return out


def swap_diff(grid, pal, en, jp, reg, box, grow=1, rect=False):
    """Redraw only the lettering: the pixels where the English texture differs from its Japanese twin, inside box, grown by
    `grow` pixels, take the nearest colour of the picture's own palette from the English texture. -> new grid."""
    h, w = grid.shape
    d = (np.abs(np.asarray(en, np.float64) - np.asarray(jp, np.float64)).sum(2) > 40).astype(np.float64) * 255.0
    cov = resample(np.repeat(d[..., None], 3, 2), reg, w, h)[..., 0] / 255.0
    mask = cov > 0.1
    for _ in range(grow):
        n = mask.copy()
        n[1:, :] |= mask[:-1, :]; n[:-1, :] |= mask[1:, :]; n[:, 1:] |= mask[:, :-1]; n[:, :-1] |= mask[:, 1:]
        mask = n
    x0, y0, x1, y1 = box
    inbox = np.zeros_like(mask)
    inbox[y0:y1, x0:x1] = True
    mask = inbox if rect else (mask & inbox)
    small = resample(en, reg, w, h)
    pal = np.asarray(pal, np.float64)
    new = grid.copy()
    for y, x in zip(*np.nonzero(mask)):
        dd = (((pal - small[y, x]) * np.array((3.0, 4.0, 2.0))) ** 2).sum(1)
        new[y, x] = int(dd.argmin())
    return new


def swap_whole(grid, pal, tex, reg, paper=None):
    """The picture redrawn from Capcom's texture: area-averaged into the grid and snapped to the nearest colour
    the picture's own palette holds. Where the texture is its flat ground the picture keeps its own ground
    index (the palette holds several near-equal greys; the ground must not flicker between them).
    -> new index grid."""
    h, w = grid.shape
    small = resample(tex, reg, w, h)
    pal = np.asarray(pal, np.float64)
    d = (((small[:, :, None, :] - pal[None, None]) * np.array((3.0, 4.0, 2.0))) ** 2).sum(3)
    new = d.argmin(2).astype(np.uint8)
    if paper:
        # a paper on a vignetted ground: only the paper (and three pixels around it, where its shadow starts) is redrawn from
        # Capcom's texture; the ground stays the fan's own pixels (the same Collection ground the fan's picture was made from)
        lw = np.array((0.299, 0.587, 0.114))
        m = (small @ lw > paper) | (pal[grid] @ lw > paper)
        for y in range(m.shape[0]):                 # a paper is one span per row, whatever is written or drawn on it
            xs = np.nonzero(m[y])[0]
            if len(xs):
                m[y, xs.min():xs.max() + 1] = True
        for _ in range(3):
            n = m.copy()
            n[1:, :] |= m[:-1, :]; n[:-1, :] |= m[1:, :]; n[:, 1:] |= m[:, :-1]; n[:, :-1] |= m[:, 1:]
            m = n
        return np.where(m, new, grid).astype(np.uint8)
    ground = np.abs(small - float(GROUND)).sum(2) < 3.0
    gl = np.abs(pal[grid] - float(GROUND)).sum(2) < 12.0          # the fan's own ground pixels
    if gl.any():
        vals, cnt = np.unique(grid[gl], return_counts=True)
        new[ground] = vals[cnt.argmax()]
    return new




def weight_mask(tex):
    """Capcom's "30 lb" as a soft mask (rows, cols) 0..1 from the weight icon's HD texture: the letters are the
    lighter shapes on the dark plaque, so the red channel separates them. Raises if it does not look like
    "30 lb" (width/height about 3.1, mass inside the window)."""
    x0, y0, x1, y1 = WEIGHT_WINDOW
    r = np.asarray(tex, np.float64)[y0:y1, x0:x1, 0]
    m = np.clip((r - 165.0) / 40.0, 0, 1)
    ys, xs = np.where(m > 0.5)
    if len(ys) < 500:
        raise ItemError('the weight plaque lettering is not where it was measured (%d letter pixels)' % len(ys))
    m = m[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    ratio = m.shape[1] / m.shape[0]
    if not 2.6 <= ratio <= 3.6:
        raise ItemError('the weight plaque lettering has aspect %.2f, expected about 3.1' % ratio)
    return m


def crisp(m, w, h):
    """Area-average the soft mask into w x h and pull it to the strokes a pixel picture draws:
    1 where the letter covers most of the pixel, 0.55 for half-covered ones, else 0."""
    im = Image.fromarray((m * 255).astype(np.uint8), 'L').resize((w, h), Image.BOX)
    a = np.asarray(im).astype(np.float64) / 255.0
    return np.where(a > 0.5, 1.0, np.where(a > 0.3, 0.55, 0.0))


# ---------------------------------------------------------------- pictures

def pic_grid(gfx):
    """RGCN (8bpp, 256 wide) -> index grid (rows, 256)."""
    from nitro import ncgr
    data, bpp, cnt, _tw, _th = ncgr(gfx)
    if bpp != 8:
        raise ItemError('expected an 8bpp picture')
    rows = (cnt + 31) // 32
    g = np.zeros((rows * 8, 256), np.uint8)
    for t in range(cnt):
        bx, by = (t % 32) * 8, (t // 32) * 8
        g[by:by + 8, bx:bx + 8] = np.frombuffer(data[t * 64:(t + 1) * 64], np.uint8).reshape(8, 8)
    return g


def pic_write(gfx, grid):
    """The RGCN with the tile data replaced by `grid` (same length, same layout)."""
    from nitro import _sections
    p, size, body = _sections(gfx)[b'RAHC']
    dsize = struct.unpack_from('<I', body, 16)[0]
    doff = struct.unpack_from('<I', body, 20)[0]
    cnt = dsize // 64
    if grid.shape != ((cnt + 31) // 32 * 8, 256):
        raise ItemError('picture is %r, the fan\'s is %d tiles' % (grid.shape, cnt))
    tiles = bytearray(dsize)
    for t in range(cnt):
        bx, by = (t % 32) * 8, (t // 32) * 8
        tiles[t * 64:(t + 1) * 64] = grid[by:by + 8, bx:bx + 8].tobytes()
    out = bytearray(gfx)
    start = p + 8 + doff
    out[start:start + dsize] = tiles
    if not np.array_equal(pic_grid(bytes(out)), grid):
        raise ItemError('picture does not read back as written')
    return bytes(out)


def _lum(a):
    return np.asarray(a, np.float64) @ np.array([0.299, 0.587, 0.114])


def _nearest(pal, rgb, skip0=False):
    d = (((pal - np.asarray(rgb, np.float64)[None]) * np.array((3.0, 4.0, 2.0))) ** 2).sum(1)
    if skip0:
        d[0] = 1e18
    return int(d.argmin())


def stripe_face(rgb, row, x0, x1):
    """A scanlined face has one tone per row: the mean of the brighter 40 percent of the row's pixels
    (the ink is darker than the face)."""
    seg = rgb[row, x0:x1]
    L = _lum(seg)
    return seg[L >= np.percentile(L, 60)].mean(0)


def reletter_photo(grid, pal, spec, cov):
    """Wipe the old marking from the block's face and draw the new one. `grid` is the picture's index grid,
    `pal` its (256, 3) palette. -> (new grid, set of changed (x, y))."""
    fx0, fy0, fx1, fy1 = spec['face']
    ox0, oy0, ox1, oy1 = spec['old']
    rgb = pal[grid].astype(np.float64)
    new = rgb.copy()
    if spec['mode'] == 'stripe':
        for y in range(oy0, oy1):
            col = stripe_face(rgb, y, fx0, fx1)
            new[y, ox0:ox1] = col
    elif spec['mode'] in ('flat', 'blank'):
        blk = rgb[fy0:fy1, fx0:fx1].reshape(-1, 3).astype(int)
        vals, cnt = np.unique(blk, axis=0, return_counts=True)
        new[oy0:oy1, ox0:ox1] = vals[cnt.argmax()]
    else:
        raise ItemError('unknown mode %r' % spec['mode'])
    if spec['mode'] != 'blank':
        x, y, w, h = spec['box']
        if not (ox0 <= x and x + w <= ox1 and oy0 <= y and y + h <= oy1):
            raise ItemError('new lettering box %r is not inside the wiped box %r' % (spec['box'], spec['old']))
        a = cov(w, h)
        k = spec['k']
        for j in range(h):
            for i in range(w):
                new[y + j, x + i] = new[y + j, x + i] * (1 - a[j, i] * (1 - k))
    out = grid.copy()
    changed = set()
    for yy in range(oy0, oy1):
        for xx in range(ox0, ox1):
            n = _nearest(pal, new[yy, xx])
            if n != grid[yy, xx]:
                changed.add((xx, yy))
            out[yy, xx] = n
    return out, changed


def reletter_icon(grid, pal, spec, cov):
    """The same for a 4bpp icon with a flat face: face, ink and half-tone are palette slots."""
    fx0, fy0, fx1, fy1 = spec['face']
    ox0, oy0, ox1, oy1 = spec['old']
    out = grid.copy()
    out[oy0:oy1, ox0:ox1] = spec['face_idx']
    x, y, w, h = spec['box']
    if not (ox0 <= x and x + w <= ox1 and oy0 <= y and y + h <= oy1):
        raise ItemError('new lettering box %r is not inside the wiped box %r' % (spec['box'], spec['old']))
    a = cov(w, h)
    for j in range(h):
        for i in range(w):
            if a[j, i] == 1.0:
                out[y + j, x + i] = spec['ink']
            elif a[j, i] > 0:
                out[y + j, x + i] = spec['half']
    changed = {(xx, yy) for yy in range(oy0, oy1) for xx in range(ox0, ox1) if out[yy, xx] != grid[yy, xx]}
    return out, changed


# ---------------------------------------------------------------- the pictures of each class

# upcut_local pictures: entry -> spec. `face` is the face the marking sits on (inside the outline),
# `old` the box wiped (every old ink pixel is inside it), `box` the new lettering (inside `old`),
# `k` how dark the ink is against the face. sha / pal_sha guard the fan's decoded graphics and
# palette entries.
UPCUT_PICS = {
    54: dict(mode='stripe', face=(218, 321, 240, 338), old=(218, 324, 240, 338), box=(218, 328, 22, 7), k=0.5,
             sha='59fa1bf6be0d4652dbabdbb61cc3eb96c3c0d3c78a42c1eb406098003dd9f820',
             pal_sha='d63bea8d2f711ac881f562540b9f90904edfd9f773eaf231f0aa33aa5c717e7f', cls='weights'),
    58: dict(mode='stripe', face=(218, 323, 240, 339), old=(218, 325, 240, 339), box=(218, 329, 22, 7), k=0.5,
             sha='55b36edbff4d1524c093519ccce019a3fda97998abb5c8beb22140a71b101661',
             pal_sha='a818421c708b49e67dcb82c649bb868bb887431875ff1f7292bd90e2a4cb16b3', cls='weights'),
    86: dict(mode='flat', face=(218, 322, 240, 339), old=(218, 323, 240, 338), box=(218, 328, 22, 7), k=0.5,
             sha='a5c8c3e3bcc8b107d5d4cdc3213276518b7053f9bf11e1c8400d24c3d879641e',
             pal_sha='024733359654f3e7a9009df3893cfc021274e92dfc6b0be051eae2e2b0acbf1c', cls='weights'),
    84: dict(mode='blank', face=(199, 105, 218, 119), old=(200, 107, 218, 118),
             sha='d54dffddb998be0eef70fa6d27bd11aba5917f618f18bc43b0ea819fc1b8b8ae',
             pal_sha='a7c7f698a6991a497e5e14bc034a2a0abf9e8b5ba52efc9a18da5d1ec4a8ce0b', cls='weights'),
}

# upcut_local pictures redrawn whole from Capcom's texture (the scene is Capcom's too: a ticket on a grey ground):
# entry -> spec. `old` is the box every changed pixel must lie in; the registration is in item_pics_reg.json.
UPCUT_SWAPS = {
    200: dict(texture='cut03_001_eng', jp='cut03_001', old=(56, 10, 204, 176), cls='bigg',
              sha='f30ac0c7d0a7c5f48b0debb4d7ed0d63d559b846fbd0c746ec2c94639ba0aa87',
              pal_sha='591896d4cfcd1db130c4a91022807d9ca26b9da9faf50370d721666b0aed1132'),
    66: dict(texture='cut01_027_eng', jp='cut01_027', old=(0, 0, 256, 192), cls='chess', paper=175,
             sha='d5a5b5db0c85fae3280f7aeea271583fcdba5964f17bf09c5bb270c798766c61',
             pal_sha='9bf64872b189d0a84e94bcad05fff056be401ed631c6d95a7dd7dc63dcd41968'),
    276: dict(texture='cut04_035_eng', jp='cut04_035', old=(0, 0, 256, 192), cls='chess', paper=175, homography=(5.5, 408.0, 24.0),
              sha='d88ff112ed2c7cf5c73ae7624de0318b0a5760b560051480a9a9ffae22fff6d9',
              pal_sha='60aad8348d3ef3c4b2c5a84b17d708efad647d3d1cabffe21664381f452bfb37'),
}

# upcut_local pictures where Capcom kept the scene and changed only the lettering (the DS picture is the middle 1440 x 1080
# of Capcom's 1920 x 1080 texture, scaled by 5.625): the pixels the English texture changes from its Japanese twin, inside
# `box` and grown by one pixel, are redrawn from the English texture (the rest of the picture stays the fan's).
CROP_REG = (5.625, 5.625, 240.0, 0.0)
# The three brass plaques of the Angel's Cookbook close-ups (104 and 106): the fan's plaques (the retail art, wider than
# Capcom's) and Capcom's own plaques ("A Diary of Despair", "The Light of Life", "Angel Beset by Thorns") occupy the
# rects below, in picture pixels (x0, y0, x1, y1, end exclusive; the first of each pair is the fan's, the second
# Capcom's). The union, grown by `grow`, is redrawn from Capcom's registered texture; the next `feather` pixels blend
# into the fan's picture so there is no seam. Nothing else of the picture changes.
PLAQUES = (
    dict(rects=((59, 176, 111, 191), (73, 176, 108, 191)), grow=1, feather=2,                # A Diary of Despair
         draw=dict(box=(71, 175, 109, 192), lines=('A Diary', 'of Despair'))),
    dict(rects=((160, 176, 215, 191), (166, 176, 197, 191)), grow=1, feather=2,              # The Light of Life
         draw=dict(box=(164, 175, 199, 192), lines=('The Light', 'of Life'))),
    dict(rects=((52, 121, 84, 131), (45, 121, 94, 131)), grow=1, feather=2,                  # Angel Beset by Thorns
         draw=dict(box=(29, 121, 110, 131), bevel=1, lines=('Angel Beset by Thorns',))),
)
# The plaques are painted, not averaged: Capcom's lettering is a hairline about three and a half pixels tall, which an
# area average turns into a smear. The plaque is redrawn as Capcom's plaque (a light bevel along the top, a smooth brown
# face that is lighter on the left, a darker edge, a shade along the bottom; the colours are fitted to Capcom's own
# plaque with its lettering masked out and snapped to the picture's palette) and its words are set in tools/plaque_face.py
# (one pixel strokes, light on the face), each line centred.
PLAQUE_INK = (239.0, 231.0, 208.0)
PLAQUE_PITCH = 6


def patch_bounds(patches, w=256, h=192):
    """Every box (x0, y0, x1, y1) outside which a patch list leaves the picture untouched."""
    out = []
    for p in patches:
        g = p['grow'] + p['feather']
        for r in p['rects'] + ((p['draw']['box'],) if p.get('draw') else ()):
            out.append((max(r[0] - g, 0), max(r[1] - g, 0), min(r[2] + g, w), min(r[3] + g, h)))
    return out


def swap_patches(grid, pal, en, patches, reg=CROP_REG):
    """Redraw the plaques from Capcom's texture (area-averaged through `reg`, snapped to the picture's own palette), blended
    into the fan's pixels over `feather` pixels at the edge. -> new grid."""
    h, w = grid.shape
    small = resample(en, reg, w, h)
    pal = np.asarray(pal, np.float64)
    fan = pal[grid]
    alpha = np.zeros((h, w))
    yy, xx = np.mgrid[0:h, 0:w]
    for p in patches:
        for r in p['rects']:
            x0, y0, x1, y1 = r[0] - p['grow'], r[1] - p['grow'], r[2] + p['grow'], r[3] + p['grow']
            dx = np.maximum(np.maximum(x0 - xx, xx - (x1 - 1)), 0)
            dy = np.maximum(np.maximum(y0 - yy, yy - (y1 - 1)), 0)
            d = np.maximum(dx, dy)
            a = np.where(d == 0, 1.0, np.maximum(0.0, 1.0 - d / (p['feather'] + 1.0)))
            alpha = np.maximum(alpha, a)
    new = grid.copy()
    wt = np.array((3.0, 4.0, 2.0))
    for y, x in zip(*np.nonzero(alpha > 0)):
        rgb = alpha[y, x] * small[y, x] + (1 - alpha[y, x]) * fan[y, x]
        new[y, x] = int((((pal - rgb) * wt) ** 2).sum(1).argmin())
    return new

def _snap_pal(pal, rgb):
    """Index of the palette entry nearest rgb (index 0, the transparent key, never)."""
    d = (((pal - np.asarray(rgb, np.float64)) * np.array((3.0, 4.0, 2.0))) ** 2).sum(1)
    d[0] = 1e18
    return int(d.argmin())


def _fit_line(ts, vals):
    """Least-squares line through (t, rgb) points -> function t -> rgb (clamped to the data's range)."""
    ts = np.asarray(ts, np.float64)
    vals = np.asarray(vals, np.float64)
    out = []
    for c in range(3):
        a, b = np.polyfit(ts, vals[:, c], 1) if len(ts) > 1 else (0.0, float(vals[0, c]))
        out.append((a, b))
    lo, hi = vals.min(0), vals.max(0)
    return lambda t: np.clip([out[c][0] * t + out[c][1] for c in range(3)], lo, hi)


def plaque_text(d):
    """The pixels of a plaque's words (set of (x, y)): each line of the face centred in the face's inner columns, the block
    centred in the face rows, PLAQUE_PITCH rows between lines. Raises if a line does not fit."""
    import plaque_face as F
    bx0, by0, bx1, by1 = d['box']
    fy0 = by0 + d.get('bevel', 2)
    fy1 = by1 - 1
    lines = d['lines']
    block = (len(lines) - 1) * PLAQUE_PITCH + F.CAP + F.DESC
    top = fy0 + ((fy1 - fy0) - block + 1) // 2
    ix0, ix1 = bx0 + 2, bx1 - 1
    out = set()
    for li, text in enumerate(lines):
        bm, tw = F.layout(text)
        if tw > ix1 - ix0 - 2:
            raise ItemError('plaque line %r is %d px, the plaque holds %d' % (text, tw, ix1 - ix0 - 2))
        x0 = ix0 + (ix1 - ix0 - tw) // 2
        y0 = top + li * PLAQUE_PITCH
        for (gx, rows, gt) in bm:
            for r, row in enumerate(rows):
                for c, chh in enumerate(row):
                    if chh == '#':
                        out.add((x0 + gx + c, y0 + gt + r))
    return out


def draw_plaques(grid, pal, en, patches, reg=CROP_REG):
    """Paint every plaque of `patches` that has a `draw` spec: Capcom's plaque (colours fitted to its texture) at the spec's
    box, with the words set in the small face, centred. -> new grid."""
    h, w = grid.shape
    small = resample(en, reg, w, h)
    lum = small @ np.array((0.299, 0.587, 0.114))
    pal = np.asarray(pal, np.float64)
    new = grid.copy()
    ink = _snap_pal(pal, PLAQUE_INK)
    for p in patches:
        d = p.get('draw')
        if not d:
            continue
        cx0, cy0, cx1, cy1 = p['rects'][1]
        bx0, by0, bx1, by1 = d['box']
        bev = d.get('bevel', 2)
        ys_face = range(cy0 + bev, cy1 - 1)
        def colmed(x, rows, masked=True):
            col = small[list(rows), x]
            if masked:
                l = lum[list(rows), x]
                m = l < 125.0
                if m.sum() >= 2:
                    col = col[m]
            return np.median(col, 0)
        xs = list(range(cx0 + 2, cx1 - 1))
        tcap = lambda x: (x - cx0) / float(cx1 - 1 - cx0)
        face = _fit_line([tcap(x) for x in xs], [colmed(x, ys_face) for x in xs])
        bevels = []
        for k in range(bev):
            xs_b = list(range(cx0 + 2, cx1 - 2))
            bevels.append(_fit_line([tcap(x) for x in xs_b], [small[cy0 + k, x] for x in xs_b]))
        left = [colmed(cx0, ys_face), colmed(cx0 + 1, ys_face)]
        right = colmed(cx1 - 1, ys_face)
        bw = bx1 - bx0
        t_of = lambda x: (x - (bx0 + 2)) / float(max(bw - 4, 1))
        fy0, fy1 = by0 + bev, by1 - 1                 # face rows fy0 .. fy1 - 1; row by1 - 1 is the bottom edge
        for y in range(by0, by1):
            for x in range(bx0, bx1):
                t = min(max(t_of(x), 0.0), 1.0)
                if x < bx0 + 2:
                    c = left[x - bx0]
                elif x == bx1 - 1:
                    c = right
                else:
                    c = face(t)
                if y < by0 + bev:
                    c = left[0] if x == bx0 else bevels[y - by0](t) if x < bx1 - 1 else right
                elif y == by1 - 1:
                    c = np.asarray(c) * 0.74
                new[y, x] = _snap_pal(pal, c)
        for (x, y) in plaque_text(d):
            new[y, x] = ink
    return new


# upcut_local pictures whose speech bubble is re-lettered (a bubble, yellow, black lettering): entry -> spec.
# `yellow` is the bubble's palette index, `ink` the lettering's (the picture's black), `rows` the rows where the old
# lettering is wiped and `right` the right-hand limit of the bubble body by rows (the first column that is no longer
# bubble); the left edge is the first yellow pixel of the row. `lines` are set in tools/plaque_face.py (bold: every
# stroke doubled to the right), each line centred on (cx + k * dx, cy + k * pitch) and stepped up `slope` rows per
# column, as the bubble leans; `margin` pixels of yellow must surround every letter.
BUBBLES = {
    274: dict(yellow=61, ink=None, rows=(12, 57), right=((12, 40, 102), (40, 49, 96), (49, 53, 88), (53, 57, 78)),
              lines=('The one!', 'The only!', 'The Berry', 'Big Circus', 'is back!'), bold=False,
              cx=75.0, cy=22.0, pitch=7.0, dx=0.0, slope=0.2, margin=1, cls='berry',
              sha='27a6851cb094cc131a8d7b15dd9038dc60bcedee9dc026867d3a758bee8c01a6',
              pal_sha='bc6ce226a3c9dedaa38877d71710e0389b6a520c178b0a879617bb9115f83bf6'),
}


def _bubble_geometry(grid, pal, spec):
    """-> (wipe mask, yellow mask) of the bubble body from the fan's picture."""
    pal = np.asarray(pal, np.float64)
    h, w = grid.shape
    rgb = pal[grid]
    yel = (rgb[..., 0] > 200) & (rgb[..., 1] > 200) & (rgb[..., 2] < 90)
    wipe = np.zeros((h, w), bool)
    for y in range(*spec['rows']):
        xs = np.where(yel[y, :140])[0]
        if not len(xs):
            continue
        xr = next(r for a, b, r in spec['right'] if a <= y < b)
        wipe[y, xs.min():min(xr, xs.max() + 1)] = True
    return wipe, yel


def bubble_text(spec):
    """Pixels (set of (x, y)) of the bubble's lines."""
    import plaque_face as F
    out = set()
    for k, text in enumerate(spec['lines']):
        bm, tw = F.layout(text)
        bold = spec.get('bold')
        w = tw + (len(bm) if bold else 0)           # bold: every glyph one pixel wider
        cx, cy = spec['cx'] + k * spec['dx'], spec['cy'] + k * spec['pitch']
        x_start = int(round(cx - w / 2.0))
        for gi, (gx, rows, gt) in enumerate(bm):
            ox = gx + (gi if bold else 0)
            dy = -int(round(spec['slope'] * (ox + 1.5 - w / 2.0)))
            for r, row in enumerate(rows):
                for c, chh in enumerate(row):
                    if chh != '#':
                        continue
                    for b in ((0, 1) if bold else (0,)):
                        out.add((x_start + ox + c + b, int(round(cy)) - 2 + gt + r + dy))
    return out


def paint_bubble(grid, pal, spec):
    pal_a = np.asarray(pal, np.float64)
    wipe, yel = _bubble_geometry(grid, pal, spec)
    new = grid.copy()
    new[wipe] = spec['yellow']
    ink = spec['ink']
    if ink is None:
        ink = int(((pal_a[1:] ** 2).sum(1)).argmin()) + 1
    for (x, y) in bubble_text(spec):
        if not wipe[y, x]:
            raise ItemError('bubble letter pixel (%d, %d) falls outside the bubble body' % (x, y))
        new[y, x] = ink
    return new, ink


# upcut_local pictures whose banner is replaced: entry -> spec. The picture keeps the fan's scene (the DS crop is the middle
# 1440 x 1080 of Capcom's texture, CROP_REG, and the buildings are the same art). `restore` (the fan's red banner, its outline
# and shadow) is redrawn from Capcom's texture, which shows the building clean there. `bar` rows (y0, y1) are Capcom's
# banner painted across the full width of the picture as flat rows (a navy stripe, a maroon body, an olive and a navy stripe;
# each row's colour is the median of Capcom's own row with its lettering left out, snapped to the picture's palette):
# Capcom's bar is translucent over the scene and carries its lettering, which no averaging keeps legible at this size, so
# its headline is set over the body in tools/plaque_face.py capitals, one line, centred, on the rows Capcom's lettering uses.
BANNERS = {
    216: dict(texture='cut03_00e_eng', jp='cut03_00e', restore=(112, 6, 256, 64), bar=(30, 51),
              text='SEVENTEEN-YEAR-OLD SOUGHT IN CONNECTION WITH LAWYER SLAYING', cls='news',
              sha='ef9167a028ce61234287cb9d68bc4bb79b9455a26fa85476b37185e47c5bbbc9',
              pal_sha='eafc3d92a2e0e2bd183da26d34e959c8ebd97438c4583eab4474d71e7b324c04'),
}


def banner_regions(spec, w=256, h=192):
    """Mask of the pixels the banner changes: the restored box and the bar rows."""
    m = np.zeros((h, w), bool)
    x0, y0, x1, y1 = spec['restore']
    m[y0:y1, x0:x1] = True
    m[spec['bar'][0]:spec['bar'][1], :] = True
    return m


def _bar_rows(small, spec):
    """-> ({row: rgb}, (first, last) row of Capcom's lettering) from Capcom's resampled picture."""
    lw = np.array((0.299, 0.587, 0.114))
    y0, y1 = spec['bar']
    seg = small[y0:y1, 5:170]
    lum = seg @ lw
    white = (seg.min(2) > 150.0) & (lum > 170.0)
    rows = np.nonzero(white.any(1))[0]
    out = {}
    for i in range(y1 - y0):
        px = seg[i][~white[i]]
        out[y0 + i] = np.median(px, 0)
    # the body rows that carry the lettering take the body colour of the rows without it
    clean = [y for y in range(y0, y1) if not white[y - y0].any() and abs(out[y][0] - 126.0) < 12 and out[y][1] < 70]
    body = np.median([out[y] for y in clean], 0)
    for y in range(y0, y1):
        if white[y - y0].any() or (abs(out[y][0] - 126.0) < 14 and out[y][1] < 100 and y in range(y0 + 3, y1 - 3)):
            out[y] = body
    return out, (int(rows.min()) + y0, int(rows.max()) + y0)


def banner_text(spec, rows, w=256):
    """The headline's pixels (set of (x, y)): one line of capitals centred on the picture and on `rows` (Capcom's lettering rows)."""
    import plaque_face as F
    bm, tw = F.layout(spec['text'])
    x0 = (w - tw) // 2
    y0 = int(round((rows[0] + rows[1]) / 2.0 - (F.CAP - 1) / 2.0))
    out = set()
    for (gx, grows, gt) in bm:
        for r, row in enumerate(grows):
            for c, ch in enumerate(row):
                if ch == '#':
                    out.add((x0 + gx + c, y0 + gt + r))
    return out


def paint_banner(grid, pal, tex, spec):
    pal_a = np.asarray(pal, np.float64)
    h, w = grid.shape
    small = resample(tex, CROP_REG, w, h)
    bar, rows = _bar_rows(small, spec)
    new = grid.copy()
    wt = np.array((3.0, 4.0, 2.0))
    x0, y0, x1, y1 = spec['restore']
    for y in range(y0, y1):
        for x in range(x0, x1):
            d = (((pal_a - small[y, x]) * wt) ** 2).sum(1)
            d[0] = 1e18
            new[y, x] = int(d.argmin())
    for y, rgb in bar.items():
        new[y, :] = _snap_pal(pal_a, rgb)
    ink = _snap_pal(pal_a, (245.0, 245.0, 245.0))
    for (x, y) in banner_text(spec, rows, w):
        new[y, x] = ink
    return new, ink


UPCUT_LOCALS = {
    224: dict(texture='cut03_017_eng', jp='cut03_017', box=(79, 136, 194, 180), rect=True, cls='notebook',
              sha='b5fc75e610ae4c240cc8bd9a32347ee6589de5d274a520e1997947c5b845beaa', pal_sha='a847ac39898a5a871016d36b3605981fbdf1cf80f490a72dcd64b8302bbab046'),
    226: dict(texture='cut03_018_eng', jp='cut03_018', box=(112, 115, 187, 180), cls='notebook',
              sha='45909f88cbe2c7d846d1843344c83001e29191fc5d80c3c6ef89bcc403676364', pal_sha='7478c35c714758313f33c1266300567fabab15a54b1aad3271cc6d2290367773'),
    104: dict(texture='cut02_005_eng', jp='cut02_005', box=(40, 80, 96, 98), rect=True, cls='cookbook', patches=PLAQUES,
              sha='a53bdd0dcbe84bbac2b6e0952a8c0d49ed28b2f041cc6c62a58ef376f6c541e1',
              pal_sha='da93db39b35c07d866d7461973b71499b6eeef48d6dd63cc23508140fadae5f3'),
    106: dict(texture='cut02_006_eng', jp='cut02_006', box=(40, 80, 96, 98), rect=True, cls='cookbook', patches=PLAQUES,
              sha='60af061f4de91039ebc71bec244acb7e7740dbd726470edde754e77ff9896fe1',
              pal_sha='aab1f2270b975119ec03773424283998bcb6d836d828ce6a8ec8f1bab0866d10'),
    96: dict(texture='cut02_001_eng', jp='cut02_001', box=(57, 0, 202, 61), rect=True, cls='tvsign',
              sha='c964de9a16cf649f54036f890ae4ddd621ea36ef2bde72aaf3f82f8dfc361886',
              pal_sha='5bd647f925daa559652bf65c3bc5a0e499a33399bacf8e3683209f4a75ed7c10'),
    134: dict(texture='cut02_031_eng', jp='cut02_031', box=(58, 0, 200, 61), rect=True, cls='tvsign',
              sha='f3e0e442d5750c53c820036109b60851a4a107d9db6e7b449a50dc35627322d2',
              pal_sha='c529f14d9b5ab4b675ff18abbf384c2e802f31f595b0acfc1001a43298437935'),
    136: dict(texture='cut02_032_eng', jp='cut02_032', box=(57, 0, 201, 67), rect=True, cls='tvsign',
              sha='6151414327389924d82b505970026e68401c25e7119d1ae8f6f7cb4b37cfcac1',
              pal_sha='a3f5618cab19ab25ea9c338b4c7f22cb827c8cd0c285313bf71cc259111acdc5'),
}

# 4bpp icons with a flat face: (container, entry) -> spec (the palette entry is `pal`).
ICON_PICS = {
    (IDCOM, 327): dict(pal=326, face=(27, 31, 55, 51), face_idx=6, old=(29, 34, 54, 51), box=(30, 38, 24, 7),
                       ink=2, half=3, cls='weights',
                       sha='b130252958eef02a90ca192490d286903ac364b8a2ea2a6a241cd33bcf2df4eb',
                       pal_sha='7354edb45f537c817acbd465af15fa116c1e7661b4dbfe7f8aa953ba7ac4b812'),
    (LOGICKW, 82): dict(pal=83, face=(17, 19, 35, 32), face_idx=6, old=(18, 20, 34, 32), box=(18, 24, 16, 6),
                        ink=2, half=3, cls='weights',
                        sha='324c44e1ebb1ecb16512b12b2cd48fbb1a9b3398d44a400c535d972af741723e',
                        pal_sha='f5910cb6d96b024f4aecdb6443cce486e811c51ac0c1b65d6895e1fe6030a1bf'),
    (LOGICKW, 92): dict(pal=93, face=(17, 19, 35, 32), face_idx=6, old=(18, 20, 34, 32), box=(18, 24, 16, 6),
                        ink=2, half=3, cls='weights',
                        sha='324c44e1ebb1ecb16512b12b2cd48fbb1a9b3398d44a400c535d972af741723e',
                        pal_sha='f5910cb6d96b024f4aecdb6443cce486e811c51ac0c1b65d6895e1fe6030a1bf'),
}


# 4bpp icons that take their picture from a bigger twin: (container, entry) -> spec. `sibling` names the twin
# (container, entry), `reg` maps this icon's pixels into the twin's (sibling pixel = o + s * pixel, fitted by the
# overlap of the two silhouettes, IoU 0.966), `box` where this icon changes.
SIBLING_PICS = {
    (LOGICKW, 192): dict(pal=193, sibling=(IDCOM, 555), reg=(1.54, 1.52, 0.5, 1.5), box=(4, 12, 36, 30), cls='keycard',
                         sha='7dfaa3097a61f699ad663442d5a1444cdeb217f86e4b5b041bed147581d795f0',
                         pal_sha='0245837d0c03b7d1c5552a9a9ea439758847a4d2f0f83b2d23febf085626d783'),
}


def changed_entries(classes=None):
    """({upcut_local entry}, {(container, icon entry): palette entry}) for the given classes (all if None)."""
    up = {e for e, s in list(UPCUT_PICS.items()) + list(UPCUT_SWAPS.items()) if classes is None or s['cls'] in classes}
    ic = {k: s['pal'] for k, s in ICON_PICS.items() if classes is None or s['cls'] in classes}
    return up, ic


def scale_into(sib_grid, sib_pal, reg, size, pad=20):
    """The twin's picture area-averaged into a size x size grid through reg. -> float RGB (size, size, 3)."""
    sib = np.asarray(sib_pal, np.float64)[np.asarray(sib_grid)]
    sx, sy, ox, oy = reg
    padded = np.pad(sib, ((pad, pad), (pad, pad), (0, 0)), mode='edge')
    out = np.zeros((size, size, 3))
    for c in range(3):
        im = Image.fromarray(padded[..., c].astype(np.float32), mode='F')
        out[..., c] = np.asarray(im.resize((size, size), Image.BOX, box=(ox + pad, oy + pad, ox + sx * size + pad, oy + sy * size + pad)))
    return out


def _load_cov(dumpdir):
    p = os.path.join(dumpdir, 'title', 'idcom', WEIGHT_TEXTURE + '.png')
    if not os.path.isfile(p):
        raise ItemError('texture %s is missing (%s); run the build once without --skip-extract' % (WEIGHT_TEXTURE, p))
    im = Image.open(p).convert('RGB')
    import idcom_icons as I
    good, have = I.texture_matches(WEIGHT_TEXTURE, im)
    if not good:
        raise ItemError('texture %s (sha256 %s) is not the Collection build these pictures were made against' % (WEIGHT_TEXTURE, have[:12]))
    m = weight_mask(np.asarray(im))
    return lambda w, h: crisp(m, w, h)


def _content(idl, i):
    """Decoded bytes of entry i: a compressed entry decompressed, an uncompressed one cut to its table size
    (Idlocal.blob returns the slot including its alignment padding)."""
    b = idl.blob(i)
    size = idl.ents[i][1]
    return b if size & 0x80000000 else b[:size]


def _extents_of(d):
    import choice_strips as cs
    t = cs.Idlocal(d)
    order = sorted(range(t.n), key=lambda i: t.ents[i][0])
    return {i: (t.ents[i][0], t.ents[order[k + 1]][0] if k + 1 < len(order) else len(d)) for k, i in enumerate(order)}


def patch_upcut(upcut_bytes, fan_upcut_bytes, cov, classes, dumpdir):
    """-> (new upcut_local bytes, {entry: (decoded, stored, fan stored, changed pixels)})."""
    import choice_strips as cs
    from lz11 import compress, decompress
    from nitro import nclr
    idl = cs.Idlocal(upcut_bytes)
    repl, changed_px = {}, {}
    reg = None
    for e, spec in sorted(list(UPCUT_PICS.items()) + list(UPCUT_SWAPS.items()) + list(UPCUT_LOCALS.items()) + list(BUBBLES.items()) + list(BANNERS.items())):
        if spec['cls'] not in classes:
            continue
        gfx, palb = _content(idl, e), _content(idl, e + 1)
        for what, blob, want in (('graphics', gfx, spec['sha']), ('palette', palb, spec['pal_sha'])):
            if hashlib.sha256(blob).hexdigest() != want:
                raise ItemError('upcut_local entry %d (%s) is not the fan\'s picture' % (e + (what == 'palette'), what))
        pal = nclr(palb)
        pal = np.array(pal + [(255, 0, 255)] * (256 - len(pal)), np.float64)
        grid = pic_grid(gfx)
        if e in UPCUT_LOCALS:
            new = swap_diff(grid, pal, load_texture(dumpdir, spec['texture']), load_texture(dumpdir, spec['jp']), CROP_REG, spec['box'], rect=spec.get('rect', False))
            if spec.get('patches'):
                new = swap_patches(new, pal, load_texture(dumpdir, spec['texture']), spec['patches'])
                new = draw_plaques(new, pal, load_texture(dumpdir, spec['texture']), spec['patches'])
            changed = set(zip(*[a.tolist() for a in np.nonzero((new != grid).T)]))
        elif e in BANNERS:
            new, _ink = paint_banner(grid, pal, load_texture(dumpdir, spec['texture']), spec)
            changed = {(int(x), int(y)) for y, x in zip(*np.nonzero(new != grid))}
        elif e in BUBBLES:
            new, _ink = paint_bubble(grid, pal, spec)
            changed = {(int(x), int(y)) for y, x in zip(*np.nonzero(new != grid))}
        elif e in UPCUT_SWAPS:
            if reg is None:
                reg = load_reg()
            new = swap_whole(grid, pal, load_texture(dumpdir, spec['texture']), reg[str(e)]['reg'], spec.get('paper'))
            ox0, oy0, ox1, oy1 = spec['old']
            diff = new != grid
            ys, xs = np.where(diff)
            if len(ys) and (xs.min() < ox0 or xs.max() >= ox1 or ys.min() < oy0 or ys.max() >= oy1):
                raise ItemError('upcut_local entry %d: the redrawn picture changes pixels outside its declared box %r'
                                % (e, spec['old']))
            changed = set(zip(xs.tolist(), ys.tolist()))
        else:
            new, changed = reletter_photo(grid, pal, spec, cov)
        repl[e] = pic_write(gfx, new)
        changed_px[e] = len(changed)
    out = cs.rebuild(upcut_bytes, repl, lz=tuple(sorted(repl)))
    fext = _extents_of(fan_upcut_bytes)
    res = {}
    for e in sorted(repl):
        stream = compress(repl[e])
        if decompress(stream) != repl[e]:
            raise ItemError('upcut_local entry %d does not round-trip through LZ11' % e)
        fan_stored = fext[e][1] - fext[e][0]
        if len(stream) > fan_stored:
            raise ItemError('upcut_local entry %d would be stored in %d bytes, the fan\'s is %d; it must not be larger'
                            % (e, len(stream), fan_stored))
        res[e] = (len(repl[e]), len(stream), fan_stored, changed_px[e])
    back = cs.Idlocal(out)
    for i in range(idl.n):
        if i not in repl and _content(back, i) != _content(idl, i):
            raise ItemError('upcut_local entry %d changed and should not have' % i)
    return out, res


def patch_icons(container, name, cov, classes, rom=None):
    """In place, as idcom_icons does: -> (new container bytes, {entry: (decoded, stored, fan stored, changed px)})."""
    import choice_strips as cs
    import idcom_icons as I
    from lz11 import compress, decompress
    from nitro import nclr
    t = I.table(container)
    ext = I.extents(t, len(container))
    out = bytearray(container)
    res = {}
    from choice_strips import rom_file
    for (cont, e), spec in sorted(list(ICON_PICS.items()) + list(SIBLING_PICS.items())):
        if cont != name or spec['cls'] not in classes:
            continue
        ent, _n = I.entry_decoded(container, e)
        pal_e, _n = I.entry_decoded(container, spec['pal'])
        for what, blob, want in (('graphics', ent, spec['sha']), ('palette', pal_e, spec['pal_sha'])):
            if hashlib.sha256(blob).hexdigest() != want:
                raise ItemError('%s entry %d (%s) is not the fan\'s' % (name, e if what == 'graphics' else spec['pal'], what))
        grid = np.array(cs.grid(ent), np.uint8)
        if 'sibling' in spec:
            scont, sent = spec['sibling']
            sc = rom_file(rom, scont)
            sg = np.array(cs.grid(I.entry_decoded(sc, sent)[0]), np.uint8)
            spal = nclr(I.entry_decoded(sc, sent - 1)[0])
            pal = np.array(nclr(pal_e), np.float64)
            small = scale_into(sg, spal, spec['reg'], grid.shape[0])
            new = grid.copy()
            x0, y0, x1, y1 = spec['box']
            for yy in range(y0, y1):
                for xx in range(x0, x1):
                    d = (((pal - small[yy, xx]) * np.array((3.0, 4.0, 2.0))) ** 2).sum(1)
                    d[0] = 1e18
                    new[yy, xx] = int(d.argmin())
            changed = {(xx, yy) for yy in range(y0, y1) for xx in range(x0, x1) if new[yy, xx] != grid[yy, xx]}
        else:
            new, changed = reletter_icon(grid, np.array(nclr(pal_e), np.uint8), spec, cov)
        if (new == 0).any():
            raise ItemError('%s entry %d would draw index 0, the transparent key' % (name, e))
        new_entry = cs.encode(ent, [list(map(int, r)) for r in new])
        if len(new_entry) != len(ent) or not np.array_equal(np.array(cs.grid(new_entry), np.uint8), new):
            raise ItemError('%s entry %d does not read back as written' % (name, e))
        stream = compress(new_entry)
        if decompress(stream) != new_entry:
            raise ItemError('%s entry %d does not round-trip through LZ11' % (name, e))
        a, b = ext[e]
        if len(stream) > b - a:
            raise ItemError('%s entry %d would be stored in %d bytes, the fan\'s is %d; it must not be larger'
                            % (name, e, len(stream), b - a))
        out[a:b] = stream + b'\0' * (b - a - len(stream))
        res[e] = (len(new_entry), len(stream), b - a, len(changed))
    return bytes(out), res


def apply_to_rom(rom, dumpdir, log=None, any_rom=False, classes=None):
    """Run after idcom_icons and after the last step that writes upcut_local. -> (rom, changed)."""
    import title_logo
    from choice_strips import rom_file
    log = log or (lambda s: None)
    classes = classes or CLASSES
    try:
        cov = _load_cov(dumpdir)
        fan_up = open(os.path.join(dumpdir, 'ds_fan', 'jpn', 'upcut_local.bin'), 'rb').read()
        new_up, up_res = patch_upcut(rom_file(rom, UPCUT), fan_up, cov, classes, dumpdir)
        new_ic, ic_res = patch_icons(rom_file(rom, IDCOM), IDCOM, cov, classes, rom)
        new_lk, lk_res = patch_icons(rom_file(rom, LOGICKW), LOGICKW, cov, classes, rom)
    except ItemError as e:
        if not any_rom:
            raise ItemError('%s (pass --any-rom to build without the item pictures)' % e)
        log('item pictures: NOT redrawn, --any-rom given (%s)' % e)
        return rom, False
    for nm, res in ((UPCUT, up_res), (IDCOM, ic_res), (LOGICKW, lk_res)):
        for e, (dec, st, fst, px) in sorted(res.items()):
            log('item picture %s entry %d: %d px changed, decoded %d bytes, stored %d (fan %d)' % (nm, e, px, dec, st, fst))
    rom = title_logo.splice(rom, UPCUT, new_up)
    rom = title_logo.splice(rom, IDCOM, new_ic)
    rom = title_logo.splice(rom, LOGICKW, new_lk)
    return rom, True


CLASSES = ('weights', 'bigg', 'keycard', 'notebook', 'tvsign', 'cookbook', 'berry', 'chess', 'news')
