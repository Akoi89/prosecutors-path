# -*- coding: utf-8 -*-
"""Pull the official English GK2 logo out of the user's own Collection and lay it
out as the DS title screen picture.

The logo is the Sprite `GK2_Logo_R_eng` (1062x498) in the Collection bundle whose
name starts with `localization-assets-english(en)_`. Nothing ships with the tool:
the image is read from the user's install at build time, exactly like the script.

    python tools/extract_logo.py BUNDLE_DIR FAN_TITLE_SCREEN_1x.png OUT_256x192.png

FAN_TITLE_SCREEN_1x.png is a true-colour render of the fan title_local.bin (see
render_title.py) and is used only for its copyright band, which is kept verbatim.
Feed OUT to title_logo.py.
"""
import sys, os, glob
from PIL import Image

W, H = 256, 192
BUNDLE_PREFIX = 'localization-assets-english(en)_'
ASSET = 'GK2_Logo_R_eng'
BAND_TOP = 178          # first row of the copyright line on the fan screen
TOP_MARGIN = 4
SIDE_MARGIN = 4


def extract_logo(bundle_dir):
    import UnityPy
    hits = [p for p in glob.glob(os.path.join(bundle_dir, '*.bundle'))
            if os.path.basename(p).startswith(BUNDLE_PREFIX)]
    if not hits:
        raise SystemExit('no bundle starting with %r in %s' % (BUNDLE_PREFIX, bundle_dir))
    env = UnityPy.load(hits[0])
    for o in env.objects:
        if o.type.name == 'Sprite':
            d = o.read()
            if d.m_Name == ASSET:
                return d.image.convert('RGBA')
    raise SystemExit('%s not found in %s' % (ASSET, os.path.basename(hits[0])))


def compose(logo, fan_screen):
    """Black 256x192, the logo scaled to fit above the copyright band, band kept."""
    fan = Image.open(fan_screen).convert('RGB')
    assert fan.size == (W, H), 'fan screen is %s' % (fan.size,)
    avail_h = (BAND_TOP - 6) - TOP_MARGIN
    scale = min((W - 2 * SIDE_MARGIN) / float(logo.width), avail_h / float(logo.height))
    lw, lh = int(round(logo.width * scale)), int(round(logo.height * scale))
    small = logo.resize((lw, lh), Image.LANCZOS)
    out = Image.new('RGB', (W, H), (0, 0, 0))
    out.paste(fan.crop((0, BAND_TOP - 2, W, H)), (0, BAND_TOP - 2))
    ox, oy = (W - lw) // 2, TOP_MARGIN + (avail_h - lh) // 2
    out.paste(small, (ox, oy), small)
    return out, (ox, oy, lw, lh, scale)


if __name__ == '__main__':
    bdir, fan_png, out_png = sys.argv[1:4]
    logo = extract_logo(bdir)
    img, (ox, oy, lw, lh, scale) = compose(logo, fan_png)
    img.save(out_png)
    print('logo %dx%d -> placed at (%d,%d) as %dx%d (scale %.3f); wrote %s'
          % (logo.width, logo.height, ox, oy, lw, lh, scale, out_png))
