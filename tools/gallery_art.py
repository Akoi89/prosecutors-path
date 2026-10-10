# -*- coding: utf-8 -*-
"""Capcom's own picture of the Zodiac Hall leaflet map for jpn/upcut_local.bin entry 114.

The DS picture is the fan's lettered version of the retail leaflet ("Zodiac Art Gallery", a small fan-shaped plan with
rotated labels Summer / Winter / Spring / Autumn Palace, EV, Fountain Patio, Sec. Room, Rec. Booth, Gardens). Capcom's
Collection draws the same leaflet again as cut02_010_eng ("Zodiac Hall: Building Map", Hours: 10 AM - 5 PM, Summer /
Winter / Spring / Autumn Wing, EL, Fountain Hall, Security Room, Reception, Entrance, Garden). The two are different
drawings (Capcom's plan fills the picture, the DS plan is smaller under a large title), and the fan's labels are lettered
along the wings at 35 and 60 degrees, where the letters Capcom's words need exist nowhere else, so the picture is
swapped whole: Capcom's picture, its central 4:3 part (columns 240 to 1679 of 1920, the same crop the DS pictures
take of the Collection's 16:9 textures), reduced to 256 x 192 with a Lanczos filter, lightly sharpened, and quantised
without dithering into the entry's own 256 colour palette (the palette entry is not touched). Only the tile data of
the picture entry changes; decoded size, tile bank size, and every other entry stay the fan's.

At build time the texture comes from the player's own Collection (extract() saves it under dump/title/gallery/);
nothing of the game is shipped.
"""
import os, glob, hashlib
import numpy as np
from PIL import Image, ImageFilter

BUNDLE_PREFIX = 'gk2_upcutlocal_assets'
TEXTURE = 'cut02_010_eng'
CACHE = ('title', 'gallery')
ENTRY = 114
TEXTURE_SHA256 = '63f960c7beffddedd0e916d14730286e5dfb07bde4e27c38e5d22a63ae82b678'      # of the decoded RGBA pixels
CROP = (240, 0, 1680, 1080)            # the Collection's 16:9 texture, the central 4:3 part
SIZE = (256, 192)
SHARPEN = dict(radius=1.2, percent=120, threshold=2)


class GalleryError(ValueError):
    pass


def cache_dir(dumpdir):
    return os.path.join(dumpdir, *CACHE)


def required(dumpdir):
    return [os.path.join(cache_dir(dumpdir), TEXTURE + '.png')]


def extract(bdir, dumpdir):
    """Save the English leaflet texture into dump/title/gallery/ (upright as UnityPy returns it). Raises SystemExit if the bundle or the
    texture is missing, as the other extractors do."""
    hits = [p for p in glob.glob(os.path.join(bdir, '*.bundle'))
            if os.path.basename(p).lower().startswith(BUNDLE_PREFIX)
            and '_trial' not in os.path.basename(p).lower() and '_classic' not in os.path.basename(p).lower()]
    if not hits:
        raise SystemExit('gallery leaflet: no bundle starting with %r in %s' % (BUNDLE_PREFIX, bdir))
    import UnityPy
    env = UnityPy.load(hits[0])
    found = None
    for obj in env.objects:
        if obj.type.name == 'Texture2D':
            d = obj.read()
            if d.m_Name == TEXTURE:
                found = d.image.convert('RGBA')              # UnityPy hands the texture over upright
                break
    if found is None:
        raise SystemExit('gallery leaflet: texture %s not found in %s' % (TEXTURE, os.path.basename(hits[0])))
    out = cache_dir(dumpdir)
    os.makedirs(out, exist_ok=True)
    found.save(os.path.join(out, TEXTURE + '.png'))
    return out


def load_texture(dumpdir):
    p = os.path.join(cache_dir(dumpdir), TEXTURE + '.png')
    if not os.path.isfile(p):
        raise GalleryError('texture %s is missing (%s); run the build once without --skip-extract' % (TEXTURE, p))
    im = Image.open(p).convert('RGBA')
    if im.size != (1920, 1080):
        raise GalleryError('texture %s is %dx%d, expected 1920x1080' % ((TEXTURE,) + im.size))
    a = np.asarray(im)
    got = hashlib.sha256(a.tobytes()).hexdigest()
    if got != TEXTURE_SHA256:
        raise GalleryError('texture %s is not the Collection picture this routine was proven on (decoded sha256 %s...)' % (TEXTURE, got[:12]))
    if int(a[..., 3].min()) < 240:
        raise GalleryError('texture %s has transparency (alpha down to %d); expected an opaque picture' % (TEXTURE, int(a[..., 3].min())))
    return im.convert('RGB')


def picture(dumpdir, pal):
    """The new 256 x 192 index grid: Capcom's picture reduced and quantised into `pal` (list of RGB triples)."""
    tex = load_texture(dumpdir)
    small = tex.crop(CROP).resize(SIZE, Image.LANCZOS).filter(ImageFilter.UnsharpMask(**SHARPEN))
    a = np.asarray(small).astype(np.int64)
    P = np.array(pal[:256], np.int64)
    if len(P) < 256:
        raise GalleryError('the picture palette has %d colours, expected 256' % len(P))
    w = np.array([2, 4, 3], np.int64)                   # a cheap perceptual weighting of the channels
    q = np.zeros(a.shape[:2], np.int32)
    for y in range(a.shape[0]):
        d = (((a[y][:, None, :] - P[None, :, :]) ** 2) * w).sum(-1)
        d[:, 0] = 1 << 40                               # index 0 is the transparent key: never drawn
        q[y] = d.argmin(-1)
    return q
