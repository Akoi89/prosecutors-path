# -*- coding: utf-8 -*-
"""Capcom's English evidence icons (com/idcom.bin): the business card and the victim's letter
(entries 281, 573 and 575, swapped whole) and the icons whose wording differs from Capcom's in one
place only (redrawn locally, see LOCAL SWAP below).

The Court Record's evidence icons are small 4bpp sprites in com/idcom.bin, each with
its own 16-colour RLCN in the entry before it. Three of them show a card with a
name on it that the fan's art draws as a fan name and the Collection spells
differently:

  281  64x64   the business card: the fan's "Raymond Shields", Capcom's Eddie Fender
               (Collection texture itm01_017_00_l_eng; the Japanese twin
               itm01_017_00_l reads Shigaraki Tateyuki, the fan's Raymond Shields)
  573  64x64   the victim's letter, with the fan's "Jill Crane"; Capcom's card reads
               Ms. Rosie Ringer (itm03_00f_00_l_eng; Japanese twin itm03_00f_00_l,
               Kagome Tsubasa-sama, the fan's Jill Crane)
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

LOCAL SWAP. Where the fan's icon is good art with one wrong label (a bottle, a book cover, a card), the
icon keeps every pixel of the fan's drawing except inside a box named in its ICONS entry
(local=dict(box=(x0, y0, x1, y1), ...), in icon pixels). Inside the box, the pixels the English texture
changes from its Japanese twin (the lettering; or the whole box with rect=True) are redrawn from the English
texture, mapped, area-averaged and lightly sharpened exactly as above, then snapped to the nearest colour the
fan's own palette already holds, so the palette entry stays the fan's bytes. Options: restrict (only colours the
fan's pixels in the box already use), levels (stretch the redrawn pixels' luminance to the range the fan's
pixels in the box span; Capcom draws thinner strokes than the fan's 1-pixel ones), sharp (own sharpening).
Like a whole swap it must be stored within the fan's extent, and raises if it is not (no pixel is altered to win
bytes).

WORDS. Where the picture is good and the wrong thing is a word (a bottle's label), the word is set in pixel
lettering in the fan's own face (tools/icon_labels.py) on the label's ground; the icon's ICONS entry says
where (words=[dict(text, x, y, ink, clip, erase, fill)]).

Container policy: everything is written IN PLACE. The container's table, every other
entry and every offset stay byte for byte the fan's; an icon's entry keeps its
decoded size and is stored as a real LZ11 stream (tools/lz11.py) that must fit in
the bytes the fan's entry held (padded with zeros), so no buffer the game sized
from the fan's table can be outgrown. tools/bufcheck.py (check j) verifies all of
that on the built ROM.

patch() guards on the sha256 of the fan's decoded icon and palette entries and raises if any
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
    487: dict(pal=486, size=64, eng='itm02_026_00_l_eng', jp='itm02_026_00_l', bg=(123, 123, 115), words=[{'text': 'Ubiquium', 'x': 23, 'y': 32, 'ink': 2, 'clip': (22, 45), 'erase': (22, 32, 45, 39), 'fill': ('row', 31)}],
              sha='2322a90892653b0e7bee9876113fdd016e684894c8c0a530a779fe445684940a',
              pal_sha='fa68daa4e201e92427b0d4cda0a3f1f67f0efe338d708732c5e58e0e725c42a1'),
    489: dict(pal=488, size=64, eng='itm02_027_00_l_eng', jp='itm02_027_00_l', bg=(123, 123, 115), words=[{'text': 'Asphyxion', 'x': 23, 'y': 32, 'ink': 2, 'clip': (22, 45), 'erase': (22, 32, 45, 39), 'fill': ('row', 31)}],
              sha='e7efb41a302e4d557ce3d3b4808068f923ef911e44bca7c1a2b426f0afd7a0cf',
              pal_sha='1b07bec3f8b6fad98dc193ed6fd2e9664ebafad529bde1bb7906717f54de3542'),
    485: dict(pal=484, size=64, eng='itm02_025_00_l_eng', jp='itm02_025_00_l', bg=(123, 123, 123),
              words=[{'text': '', 'x': 0, 'y': 0, 'ink': 0, 'clip': (0, 0), 'erase': (20, 32, 43, 37), 'fill': ('flat', 8)},
                     {'text': 'ULTRA', 'x': 22, 'y': 38, 'ink': 7, 'clip': (20, 43), 'erase': (20, 38, 43, 42), 'fill': ('flat', 8), 'face': 'toxin'}],
              small={'src': (107, 157, 201, 173), 'dst': (21, 33, 42, 37), 'ramp': (8, 9, 10, 11, 12, 13, 14, 15), 'ground': 36, 'pct': 90, 'gamma': 1.4},
              sha='f5c0bb6b07343df479685eca71af89977a9115a1b42fa06eabbd8cef93190508',
              pal_sha='a675b41e02ee927d1382434434f6705c1386c32315a6f887e31ff04a3f915aa0'),
    735: dict(pal=734, size=64, eng='itm04_026_00_l_eng', jp='itm04_026_00_l', bg=(123, 123, 123), words=[{'text': '', 'x': 0, 'y': 0, 'ink': 0, 'clip': (0, 0), 'erase': (21, 30, 42, 35), 'fill': ('flat', 2)}, {'text': '3 Zs', 'x': 23, 'y': 37, 'ink': 11, 'clip': (22, 41), 'erase': (22, 36, 41, 44), 'fill': ('row', 43)}],
              sha='d08064e03b5ed372a267edc71b2524dfcc9c55514443130f7310ff8c1e646318',
              pal_sha='b13f3c601d01252c4d245cab63c65f13bbc1aff43ff9dc103d453821b9e1ea76'),
    737: dict(pal=736, size=40, eng='itm04_026_00_l_eng', jp='itm04_026_00_l', bg=(123, 123, 123), local={'box': (12, 19, 28, 30), 'rect': True, 'restrict': True, 'levels': True},
              sha='7038541026eda4d163eaf746db3297e716c192a051c28f51eaa77536c15bc081',
              pal_sha='b13f3c601d01252c4d245cab63c65f13bbc1aff43ff9dc103d453821b9e1ea76'),
    539: dict(pal=538, size=64, eng='itm03_004_00_l_eng', jp='itm03_004_00_l', bg=(123, 123, 123), local={'box': (3, 14, 62, 50), 'levels': True, 'restrict': True},
              sha='0a8561259d63defed7f0629553fc83da7a0bbf1b0e80e52a2eef683334f74cce',
              pal_sha='4c83a81640d9094de8ddad46e4b7989a2876997ca2b75ff203abfcadfd0dac18'),
    541: dict(pal=540, size=40, eng='itm03_004_00_l_eng', jp='itm03_004_00_l', bg=(123, 123, 123), local={'box': (1, 8, 40, 32), 'levels': True, 'restrict': True},
              sha='e6dd29165edfbefdbdc6c9feb275deaf6e79d2e26a6bfede34a2e4cc02600833',
              pal_sha='4c83a81640d9094de8ddad46e4b7989a2876997ca2b75ff203abfcadfd0dac18'),
    547: dict(pal=546, size=64, eng='itm03_006_00_l_eng', jp='itm03_006_00_l', bg=(123, 123, 123), local={'box': (5, 1, 41, 30), 'rect': True},
              sha='57fc8dd7e7b5b679ceb52018edb6883aeabb8e9914867ca999674a185c2bd7e7',
              pal_sha='02b29fedf8eb84a932cc4cd9d6a78ca53cc89296dc093c2c9121e316f334134f'),
    549: dict(pal=548, size=40, eng='itm03_006_00_l_eng', jp='itm03_006_00_l', bg=(123, 123, 123), local={'box': (2, 0, 26, 19), 'rect': True},
              sha='4c0275b0b86802fd0139397b052b024605f55c6112ae61a3a16251a63142e6e0',
              pal_sha='dfede80f58914937aee96340abb91d9e7615e4395779d0cdf889b3c81d74ca50'),
    451: dict(pal=450, size=64, eng='itm02_01b_00_l_eng', jp='itm02_01b_00_l', bg=(123, 123, 123), local={'box': (20, 33, 54, 47)},
              sha='86c83924a57140983dd7eb56205368cdcde6a691e3c6a406baf24b94ada4273a',
              pal_sha='5753c5cabbd96530d4080d5adbf28754c3d5febbb6d763d0a46e2387da1d3898'),
    453: dict(pal=452, size=40, eng='itm02_01b_00_l_eng', jp='itm02_01b_00_l', bg=(123, 123, 123), local={'box': (12, 21, 34, 31)},
              sha='aa0c00f010aaddf10d5ab92a2c0ca5807003e485b949c390a36e2210861e3fbf',
              pal_sha='3a6e76382a4841170d0df2a392f7b84da155081f76080a63b561e3e613fe1f67'),
    403: dict(pal=402, size=64, eng='itm02_00f_00_l_eng', jp='itm02_00f_00_l', bg=(123, 123, 123),
              title={'box': (22, 5, 49, 18), 'tbox': (24, 6, 49, 15), 'tex_box': (115, 30, 270, 78), 'ground': 1, 'skip': (13, 14),
                     'ramp': (10, 7, 8, 8, 8), 'th': (0.2, 0.4, 0.6, 0.8, 0.95), 'gamma': 0.8, 'pct': 98,
                     'bold': 1,
                     'words': [{'src': (116, 36, 176, 56), 'dst': (26, 5, 46, 11)}, {'src': (186, 41, 222, 58), 'dst': (30, 12, 42, 17)}],
                     'sharp': {'radius': 1.2, 'percent': 250, 'threshold': 0}},
              sha='4e9827476cc6e100a97351df8b7dac9af40bc170c302fbbfd4779cd358b72dee',
              pal_sha='4a945fb775839644977cb5131aa7caae7210578720f490ae23e57d43ab887df2'),
    405: dict(pal=404, size=40, eng='itm02_00f_00_l_eng', jp='itm02_00f_00_l', bg=(123, 123, 123),
              title={'box': (15, 3, 33, 12), 'tbox': (15, 3, 33, 12), 'tex_box': (108, 30, 250, 78), 'ground': 1, 'skip': (13, 15, 6),
                     'ramp': (6, 12, 14), 'th': (0.25, 0.5, 0.8), 'gamma': 0.6, 'pct': 98,
                     'sharp': {'radius': 1.0, 'percent': 200, 'threshold': 0},
                     'words': [{'src': (116, 36, 176, 56), 'dst': (16, 3, 32, 8)}, {'src': (186, 41, 222, 58), 'dst': (19, 8, 29, 12)}]},
              sha='a035009d6138f2d8b7824b59d8f6b3f84645a379b4bb8bae36093767c9a133ea',
              pal_sha='2378fc39f9f8fdff1b8706606a1b2c8a905ac63d19fb052450472757b36fc192'),
    555: dict(pal=554, size=64, eng='itm03_009_00_l_eng', jp='itm03_009_00_l', bg=(123, 123, 123), words=[{'text': 'KEYCARD', 'x': 9, 'y': 28, 'ink': 15, 'clip': (6, 60), 'erase': (6, 25, 60, 46), 'fill': ('near', (14, 15)), 'gap': 3, 'slope': 0.15}],
              sha='f1c8825e48264309fe096ccad456e54332036660ce88d6a666ee50546040926a',
              pal_sha='8b52d2136c024650b707ce604bbde3dc8002b211c1203d0cd06ea57554d28de2'),
    557: dict(pal=556, size=40, eng='itm03_009_00_l_eng', jp='itm03_009_00_l', bg=(123, 123, 123), sibling={'of': 555, 'box': (3, 13, 39, 30)},
              sha='8eae3790b1c6501e5b309a56047ce976a66e47fee93993c7ba53ec307263d3dc',
              pal_sha='0245837d0c03b7d1c5552a9a9ea439758847a4d2f0f83b2d23febf085626d783'),
    479: dict(pal=478, size=64, eng='itm02_023_00_l_eng', jp='itm02_023_00_l', bg=(123, 123, 123), local={'box': (8, 4, 48, 26), 'levels': True, 'restrict': True, 'sharp': None},
              sha='9b517b38c00b5a7678a52105c83ae41233ef675d7ad5599d4397f54e73b8242d',
              pal_sha='159b0427257a56dd5704aa6784105d38b6ba107d0c2f1ca04f2d1d8cfc30b493'),
    481: dict(pal=480, size=40, eng='itm02_023_00_l_eng', jp='itm02_023_00_l', bg=(123, 123, 123), local={'box': (4, 2, 31, 17), 'levels': True, 'restrict': True, 'sharp': None},
              sha='8962103ab27d75c96a919eb2dbee8154f28ccdd6a84bc1de8c5a8e48e70bc680',
              pal_sha='257b9d06d2dcf6a58a01154028c40e79cb807294d5058cedec50758c4e14d3f1'),
    # entries stored larger than the fan's (the container is laid out again, see relayout()); decoded size stays 2,320
    563: dict(pal=562, size=64, eng='itm03_00c_00_l_eng', jp='itm03_00c_00_l', bg=(123, 123, 123), grow=True,
              local={'box': (22, 15, 54, 30), 'levels': True, 'restrict': True},
              sha='7556358a5aa52dc6cd8f8abd37bc53913978fa5da98a1424036d124d9785492a',
              pal_sha='4027efd2ca439a247fcd8d6d6fa79c1189a0e2e8768b44efef81bdc2a45f0a12'),
    519: dict(pal=518, size=64, eng='itm02_039_00_l_eng', jp='itm02_039_00_l', bg=(123, 123, 123), grow=True,
              local={'box': (3, 13, 43, 25), 'rect': True, 'levels': True, 'restrict': True, 'sharp': {'radius': 1.0, 'percent': 220, 'threshold': 0}},
              sha='8b8ae96d37cbb9492a59e025dc673ebf655a2baa02496315e4d50eff634c0568',
              pal_sha='1596fc0865490e5213e56d9548d7d10327e6e34810e1ab41d1e2c88fedc1bfbe'),
    483: dict(pal=482, size=64, eng='itm02_024_00_l_eng', jp='itm02_024_00_l', bg=(123, 123, 123), grow=True,
              local={'box': (4, 17, 48, 30), 'levels': True, 'restrict': True},
              sha='f7fdfc4c449badcc743a67343b62f50dad26f7971b067b95c1bb77c86c61ddde',
              pal_sha='d9532fddb72f3d0379b271f9f7fd072035c0d1571926f7c1c915d71bcaf538b4'),
}
# English textures other modules draw from (tools/item_pics.py: Capcom's "30 lb" lettering)
EXTRA_TEXTURES = ('itm01_029_00_l_eng',)
TEXTURES = sorted({v[k] for v in ICONS.values() for k in ('eng', 'jp')} | set(EXTRA_TEXTURES))


class IconError(ValueError):
    pass


# ---------------------------------------------------------------- the Collection's textures

def cache_dir(dumpdir):
    return os.path.join(dumpdir, *CACHE)


def required(dumpdir):
    """The harvested English textures apply_to_rom() needs (the Japanese twins are
    extracted too, for the offline registration, but the build does not read them)."""
    names = {v['eng'] for v in ICONS.values()} | set(EXTRA_TEXTURES)
    names |= {v['jp'] for v in ICONS.values() if v.get('local') and not v['local'].get('rect')}
    return [os.path.join(cache_dir(dumpdir), n + '.png') for n in sorted(names)]


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


# sha256 of the RGB pixel bytes of every Collection texture the icons read, as the extraction saves them: a Collection build
# whose art differs would change the icons silently, so a texture that does not hash to this raises (like the fan's entries do)
TEXTURE_SHA = {
    'itm01_017_00_l': '866ca1d475163aa7dc77ce361609e0c9230642251b964bdd763b138c13db2dee',
    'itm01_017_00_l_eng': '3d1df56247b7dff456edb1683904e579c2e51ea92759cd9fca83fc428a1d8ceb',
    'itm01_029_00_l_eng': '201d07115e38a370985d4fa7d2b82402a8e92c756c21f48ae90f1840f998abf3',
    'itm02_00f_00_l': 'b55d7e0e2cbded06c057f763f4014255cb87b381a84060e9a22b5a41a201ec88',
    'itm02_00f_00_l_eng': 'b6c6ce6ea184a8b25b87eeb9b5e1177dcffbd5470a584fb36007b2cb4b4d6c6f',
    'itm02_01b_00_l': '7185e8bade1d8511940eac73b4ad8691d44ec028242a5ca3ac8a7233e1f06319',
    'itm02_01b_00_l_eng': 'ee56ade52bc56d9cfbd120c30a86b01bb9ae3a03158e41ef9ec3d7ce45e9346d',
    'itm02_023_00_l': '586d89e50aabd50fd8e077d273adb6c9197813997aa1ab7fe46eac0c5a0b1d23',
    'itm02_023_00_l_eng': 'a0ff18181e5caaa1bfe0ad2e9a3a0014514396f233964a9460648a98a79aa292',
    'itm02_024_00_l': '7a7ef3a38529b3b7ea965c026dd4a970e5956610f4c1d3b2e0c6bc68f79864c1',
    'itm02_024_00_l_eng': '63c864e2a9489aa197e735064bd59ca9b19537f606571908745fdaa46a010dd6',
    'itm02_025_00_l': 'c30ba1cc305ed0ed1ec8fa30d040313a310a6de1764149b9824329e328e36dc9',
    'itm02_025_00_l_eng': 'f2799765a8ae473f5ee0b2e9d8baa7aaea3a5c9754fc64e211c2344de8a24172',
    'itm02_026_00_l': 'd79024426de676818601a1e3ad8cad6074613c07b17a2b375845387e691ff6d3',
    'itm02_026_00_l_eng': 'a9567c255da04e4a5dd8bbd004f2376d4c1d7e149d2e54671fcaf411efa9ff74',
    'itm02_027_00_l': 'c0196209b4d0b825ef2075c1b435ec123bfd99324039aa76bc8042c96373abea',
    'itm02_027_00_l_eng': 'f5ad9273cec91484179fee923378e6bb22d5e0f7b8aa781f6dd96622a29d079d',
    'itm02_039_00_l': '6e1afadb3bdd14d493238c9f70670da5fd13b4bbde623815818925cff7fe1415',
    'itm02_039_00_l_eng': '77f398dcbbb34b868b33eee3d3ddb2c4f9ce97c634980cfa8d33de5d0126f14d',
    'itm03_004_00_l': '7900113593c490ea63ec3ec77c58638d33a9550124e2440e0d13d00aba41cc64',
    'itm03_004_00_l_eng': '74954b8a9adcb67014c304d443e197209bf420663ab30aa3e86ab7fbd657341d',
    'itm03_006_00_l': '94e48d2dddb5237a06d889adb666f6ab719549461e663d33849167816e653b38',
    'itm03_006_00_l_eng': '8e0cdb4861f460f3e7d84f5969ba6ef164c381b5635f364346504425996355a2',
    'itm03_009_00_l': '6d87b131fb5060941b8214d61e7531a57f36260388343757884a49528dd708ec',
    'itm03_009_00_l_eng': '00f3544a96423b6a49108ae77b57b5e832f5d585e16937f5628372ef8ac18aa5',
    'itm03_00c_00_l': '77d31851f657f11d12f812899838c894253ba7e4d83ebf92b988472788553019',
    'itm03_00c_00_l_eng': '6bbd13b4d8d281a94b6a70407f537627f2c582d631e485d68bfc3d4ea8b1901e',
    'itm03_00f_00_l': '22a6626c47c45b2134b975ab71881960597f4292f7cdfa5a2b7ae68d9b3fb467',
    'itm03_00f_00_l_eng': '4d2f389832b9f39cc0e7b782ed7b45b81d9dd4a0f1c296a287bd2cdf342427b0',
    'itm04_026_00_l': '8a660aa468b66ae5afac1e5835a1cfdfa51d357d676d9e10a5737654c0842de7',
    'itm04_026_00_l_eng': '8d46f5c051ced888e0e56f729fc9443e06fbc46d339aa65261b531d1c182bce0',
}


def texture_matches(name, im):
    """(True when the PIL RGB image hashes to the Collection texture this module was made against, its sha256)."""
    have = hashlib.sha256(np.asarray(im).tobytes()).hexdigest()
    return TEXTURE_SHA.get(name) == have, have


def load_texture(dumpdir, name):
    p = os.path.join(cache_dir(dumpdir), name + '.png')
    if not os.path.isfile(p):
        raise IconError('texture %s is missing (%s); run the build once without --skip-extract' % (name, p))
    im = Image.open(p).convert('RGB')
    if im.size != (TEX_SIZE, TEX_SIZE):
        raise IconError('texture %s is %dx%d, expected %dx%d' % ((name,) + im.size + (TEX_SIZE, TEX_SIZE)))
    good, have = texture_matches(name, im)
    if not good:
        raise IconError('texture %s (sha256 %s) is not the Collection build these icons were made against' % (name, have[:12]))
    return np.asarray(im, np.float64)


# ---------------------------------------------------------------- resampling and quantising

def tone(a, bg=None):
    """Map the textures' flat grey TEX_BG to the icon's background (FAN_BG unless the fan's icon has
    another, per channel), black and white fixed, piecewise linear."""
    a = np.asarray(a, np.float64)
    b = np.full(3, float(FAN_BG)) if bg is None else np.asarray(bg, np.float64)
    lo = a * (b / TEX_BG)
    hi = b + (a - TEX_BG) * ((255.0 - b) / (255.0 - TEX_BG))
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


def quantise(rgb, ncol=15, weights=(3.0, 4.0, 2.0), iters=30, bgc=None):
    """Quantise an (h, w, 3) uint8 picture to `ncol` 5-bit colours, no dithering, the
    background grey FAN_BG one of them. -> (grid of indices into the colour list, list
    of (r5, g5, b5), background index)."""
    h, w, _ = rgb.shape
    px = rgb.reshape(-1, 3).astype(np.float64)
    wt = np.array(weights)
    bg5 = snap5((FAN_BG,) * 3 if bgc is None else tuple(bgc))
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


def compose_picture(tex, reg, size, sharpen=True, bgc=None, ncol=15):
    """Texture -> (grid of palette slots (size, size) uint8, 16 palette colours as 5-bit tuples)."""
    small = resample(tone(tex, bgc), reg, size)
    im = Image.fromarray(np.clip(np.rint(small), 0, 255).astype(np.uint8), 'RGB')
    if sharpen:
        im = im.filter(ImageFilter.UnsharpMask(**SHARPEN))
    rgb = np.asarray(im)
    grid, cols5, bg_i = quantise(rgb, ncol=ncol, bgc=bgc)
    return layout(grid, cols5, bg_i)


def _dilate(m, it):
    """4-connected binary dilation, `it` times (numpy only: the build does not bundle scipy)."""
    m = np.asarray(m, bool)
    for _ in range(it):
        n = m.copy()
        n[1:, :] |= m[:-1, :]
        n[:-1, :] |= m[1:, :]
        n[:, 1:] |= m[:, :-1]
        n[:, :-1] |= m[:, 1:]
        m = n
    return m


def _erode(m, it):
    return ~_dilate(~np.asarray(m, bool), it)


def diff_mask(jp, en, thr=45, close=2, grow=3):
    """Where Capcom's English texture differs from its Japanese twin (the lettering), closed and grown a
    little, in the texture's own 300x300 grid."""
    d = np.abs(np.asarray(jp, np.float64) - np.asarray(en, np.float64)).sum(2) > thr
    return _dilate(_erode(_dilate(d, close), close), grow)


def compose_local(grid, pal_rgb, en, jp, reg, size, local, bgc=None):
    """The fan's icon with only its old wording replaced by Capcom's: inside `local['box']` (x0, y0, x1, y1 in icon
    pixels), the pixels the English texture changes from its Japanese twin (or the whole box when local['rect'])
    are redrawn from the English texture, area-averaged into the icon grid and snapped to the nearest colour the
    fan's own 16-colour palette already holds. Every other pixel, the palette and the layout stay the fan's.
    -> (new grid, mask of redrawn pixels)."""
    x0, y0, x1, y1 = local['box']
    box = np.zeros((size, size), bool)
    box[y0:y1, x0:x1] = True
    if local.get('rect'):
        mask = box
    else:
        m = diff_mask(jp, en, local.get('thr', 45))
        cov = resample(m[..., None].repeat(3, 2).astype(np.float64) * 255.0, reg, size)[..., 0] / 255.0
        mask = _dilate(cov > 0.15, local.get('dil', 1)) & box
    small = resample(tone(en, bgc), reg, size)
    im = Image.fromarray(np.clip(np.rint(small), 0, 255).astype(np.uint8), 'RGB')
    sharp = local.get('sharp', SHARPEN)
    if sharp:
        im = im.filter(ImageFilter.UnsharpMask(**sharp))
    rgb = np.asarray(im).astype(np.float64)
    pal = np.asarray(pal_rgb, np.float64)
    out = np.array(grid, np.uint8)
    wt = np.array((3.0, 4.0, 2.0))
    ys, xs = np.where(mask)
    if local.get('levels') and len(ys):
        # Capcom's lettering is drawn thinner than the 1-pixel strokes the fan's icons use, so its area-averaged
        # strokes come out grey: stretch the luminance of the redrawn pixels to the range the fan's own pixels in
        # the box span (their 3rd to 97th percentile), keeping hue
        lw = np.array((0.299, 0.587, 0.114))
        Ls = rgb[ys, xs] @ lw
        Lt = (pal[np.asarray(grid)[y0:y1, x0:x1]] @ lw).ravel()
        s_lo, s_hi = np.percentile(Ls, local.get('s_pct', (3, 97)))
        t_lo, t_hi = np.percentile(Lt, (3, 97))
        if s_hi - s_lo > 1:
            Ln = np.clip(t_lo + (Ls - s_lo) / (s_hi - s_lo) * (t_hi - t_lo), 0, 255)
            rgb = rgb.copy()
            rgb[ys, xs] = np.clip(rgb[ys, xs] + (Ln - Ls)[:, None], 0, 255)
    allowed = None
    if local.get('restrict') and len(ys):
        # only colours the fan's own pixels in the box already use (a label's black, white and red, not
        # the bottle's browns that a blurred edge would otherwise snap to)
        allowed = set(int(v) for v in np.unique(np.asarray(grid)[y0:y1, x0:x1])) - {0}
    for y, x in zip(ys, xs):
        d = (((pal - rgb[y, x]) * wt) ** 2).sum(1)
        d[0] = 1e18                     # the transparent key is never drawn
        if allowed is not None:
            for k in range(len(d)):
                if k not in allowed:
                    d[k] = 1e18
        out[y, x] = int(d.argmin())
    return out, mask


def compose_title(grid, en, reg, size, t):
    """A thin pale title on a cover (the Zodiac brochure): the old title's block is returned to the cover's ground, then
    Capcom's own lettering is area-averaged into the icon grid and drawn in pale colours of the fan's palette.
    t: box (x0, y0, x1, y1) cleared to the index `ground` (pixels whose fan index is in `skip`, the cover's edge and
    the sprite's background, are left alone); tbox where lettering may be drawn (inside box); tex_box the texel box of
    the title in the English texture (nothing outside it counts as lettering); words, optionally, re-lays the title in
    lines: [{'src': texel box of a word, 'dst': its box in the icon}], each area-averaged separately; ramp / th the palette indices and the
    normalised-coverage thresholds that pick one (a pixel below th[0] keeps the ground); gamma, pct (the coverage that
    counts as full), sharp (an unsharp mask on the coverage) as the label's own lettering needs. -> (grid, mask)."""
    x0, y0, x1, y1 = t['box']
    out = np.array(grid, np.uint8)
    skip = set(t.get('skip', ()))
    lum = np.asarray(en, np.float64) @ np.array((0.299, 0.587, 0.114))
    wh = np.clip((lum - t.get('floor', 90)) / (255.0 - t.get('floor', 90)), 0, 1) * 255.0
    if t.get('bold'):
        # thin strokes taken a few texels bolder before the averaging, as the fan's one-pixel strokes are
        wh = np.asarray(Image.fromarray(wh.astype(np.uint8)).filter(ImageFilter.MaxFilter(2 * int(t['bold']) + 1)), np.float64)
    m = np.zeros_like(wh)
    a, b, c, d = t['tex_box']
    m[b:d, a:c] = 1
    if t.get('words'):
        # the title re-laid in lines: each word's own texel box is area-averaged into its own box of the icon
        cov = np.zeros((size, size))
        for w in t['words']:
            wx0, wy0, wx1, wy1 = w['dst']
            im = Image.fromarray(wh.astype(np.float32), mode='F')
            cov[wy0:wy1, wx0:wx1] = np.asarray(im.resize((wx1 - wx0, wy1 - wy0), Image.BOX, box=tuple(w['src'])), np.float64) / 255.0
    else:
        cov = resample(np.repeat((wh * m)[..., None], 3, 2), reg, size)[..., 0] / 255.0
    if t.get('sharp'):
        im = Image.fromarray((np.clip(cov, 0, 1) * 255).astype(np.uint8))
        cov = np.asarray(im.filter(ImageFilter.UnsharpMask(**t['sharp'])), np.float64) / 255.0
    mask = np.zeros(out.shape, bool)
    for y in range(y0, y1):
        for x in range(x0, x1):
            if int(grid[y, x]) not in skip:
                out[y, x] = t['ground']
                mask[y, x] = True
    tx0, ty0, tx1, ty1 = t['tbox']
    if not (x0 <= tx0 and tx1 <= x1 and y0 <= ty0 and ty1 <= y1):
        raise IconError('title letters box %r reaches outside the cleared box %r' % (t['tbox'], t['box']))
    if len(t['ramp']) != len(t['th']):
        raise IconError('title ramp and thresholds differ in length')
    hi = np.percentile(cov[ty0:ty1, tx0:tx1], t.get('pct', 99))
    if hi <= 0:
        raise IconError('no lettering found in the English texture inside %r' % (t['tex_box'],))
    cn = np.clip(cov / hi, 0, 1) ** t.get('gamma', 1.0)
    for y in range(ty0, ty1):
        for x in range(tx0, tx1):
            if int(grid[y, x]) in skip:
                continue
            k = 0
            for i, th in enumerate(t['th']):
                if cn[y, x] >= th:
                    k = i + 1
            if k:
                out[y, x] = t['ramp'][k - 1]
    return out, mask


def compose_small(grid, pal_rgb, en, small):
    """Small print: one word of Capcom's lettering, area-averaged from its own texel box into `small['dst']`
    (x0, y0, x1, y1 in icon pixels), as the fan's small print on these labels is a texture, not a readable word.
    `small['src']` is the word's texel box (x0, y0, x1, y1) in the 300x300 English texture; the box keeps its own
    aspect (the destination is sized for it). The averaged luminance is stretched so that the label's black is the
    ground index `bg` and the 98th percentile of the word the lightest of the ramp, then every pixel takes the
    nearest grey of `ramp` (palette indices). Nothing else of the icon changes. -> (new grid, mask)."""
    sx0, sy0, sx1, sy1 = small['src']
    x0, y0, x1, y1 = small['dst']
    w, h = x1 - x0, y1 - y0
    lum = np.asarray(en, np.float64) @ np.array((0.299, 0.587, 0.114))
    im = Image.fromarray(lum.astype(np.float32), mode='F')
    avg = np.asarray(im.resize((w, h), Image.BOX, box=(sx0, sy0, sx1, sy1)), np.float64)
    pal = np.asarray(pal_rgb, np.float64)
    ramp = list(small['ramp'])
    rl = pal[ramp] @ np.array((0.299, 0.587, 0.114))
    ground = float(small['ground'])                  # the texture's label black, measured
    hi = np.percentile(avg, small.get('pct', 98))
    out = np.array(grid, np.uint8)
    mask = np.zeros(out.shape, bool)
    for y in range(h):
        for x in range(w):
            t = np.clip((avg[y, x] - ground) / max(hi - ground, 1.0), 0.0, 1.0)
            t = t ** small.get('gamma', 1.0)
            target = rl[0] + t * (rl[-1] - rl[0])
            out[y0 + y, x0 + x] = ramp[int(np.abs(rl - target).argmin())]
            mask[y0 + y, x0 + x] = True
    return out, mask


def compose_sibling(grid, pal_rgb, sib_grid, sib_pal, reg_sib, reg, size, box, bgc=None):
    """The small twin of an icon the fan drew (or this module redrew) for its bigger sibling: inside `box`
    (x0, y0, x1, y1 of the small icon) the sibling's picture is area-averaged into the small icon's grid
    through the two registrations (both map icon pixels to the same texture) and snapped to the colours the small
    icon's palette holds, as the fan's small twins are made. -> (new grid, mask)."""
    sib = np.asarray(sib_pal, np.float64)[np.asarray(sib_grid)]
    ssz = sib.shape[0]
    sx, sy, ox, oy = reg_sib
    tx, ty, tox, toy = reg
    # small icon pixel range [0, size] -> texel [tox, tox + size * tx] -> sibling pixels
    box_src = ((tox - ox) / sx, (toy - oy) / sy, (tox + size * tx - ox) / sx, (toy + size * ty - oy) / sy)
    pad = 16
    padded = np.pad(sib, ((pad, pad), (pad, pad), (0, 0)), mode='edge')
    small = np.zeros((size, size, 3))
    bx = (box_src[0] + pad, box_src[1] + pad, box_src[2] + pad, box_src[3] + pad)
    for c in range(3):
        im = Image.fromarray(padded[..., c].astype(np.float32), mode='F')
        small[..., c] = np.asarray(im.resize((size, size), Image.BOX, box=bx))
    x0, y0, x1, y1 = box
    out = np.array(grid, np.uint8)
    pal = np.asarray(pal_rgb, np.float64)
    wt = np.array((3.0, 4.0, 2.0))
    mask = np.zeros((size, size), bool)
    for y in range(y0, y1):
        for x in range(x0, x1):
            d = (((pal - small[y, x]) * wt) ** 2).sum(1)
            d[0] = 1e18
            out[y, x] = int(d.argmin())
            mask[y, x] = True
    return out, mask


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


GROW_CAP = 2320          # decoded bytes a column +8 icon may have: the block sized from idcom entry 129 (a static trace of the loaders)


def relayout(container, grown):
    """The container laid out again with the entries in `grown` ({entry: LZ11 stream}) stored larger. Every extent keeps its
    bytes and its place in the file's order; a grown stream is padded so that its extent is a whole number of fours longer
    than the one it replaces; every later offset moves by the growth so far (a multiple of four, so no entry's alignment
    changes, whatever the old extent's length was); the table keeps its slot count, its sizes
    and its terminator slot (the new file length, size 0). com/idcom.bin is read only through its offset table
    (a static trace of the loaders), so nothing else needs to know."""
    t = table(container)
    n = len(t)
    ext = extents(t, len(container))
    hdr = n * 8
    first = min(o for o, _s in t if o)
    if first != hdr:
        raise IconError('the table is %d bytes but the first entry starts at %d' % (hdr, first))
    by_off = {}
    for i, (o, _s) in enumerate(t):
        if o:
            by_off.setdefault(o, []).append(i)
    for e in grown:
        if len(by_off[t[e][0]]) != 1:
            raise IconError('entry %d shares its bytes with another slot, it cannot be moved on its own' % e)
    body = bytearray()
    new_off = {}
    for o in sorted(by_off):
        slots = by_off[o]
        end = ext[slots[0]][1]
        piece = bytes(container[o:end])
        if len(slots) == 1 and slots[0] in grown:
            piece = bytes(grown[slots[0]])
            piece += bytes((end - o - len(piece)) % 4)       # same length mod 4 as the extent it replaces
        new_off[o] = hdr + len(body)
        body += piece
    out = bytearray(hdr)
    for i, (o, s_) in enumerate(t):
        struct.pack_into('<II', out, i * 8, new_off[o] if o else 0, s_)
    return bytes(out) + bytes(body)


def patch(container, textures, reg, log=None, any_rom=False):
    """-> (new container bytes, changed, info). `textures` maps texture name to the
    300x300 RGB float array, `reg` maps entry number (str) to [sx, sy, ox, oy]."""
    import lz11
    from nitro import nclr
    log = log or (lambda s: None)

    def skip(why):
        if not any_rom:
            raise IconError('%s (pass --any-rom to build without the icons)' % why)
        log('evidence icons: NOT redrawn, --any-rom given (%s)' % why)
        return container, False, {}

    t = table(container)
    ext = extents(t, len(container))
    parts = {}
    for e, spec in ICONS.items():
        for i, want in ((e, spec['sha']), (spec['pal'], spec['pal_sha'])):
            try:
                dec, _n = entry_decoded(container, i)
            except (IndexError, ValueError, struct.error) as ex:
                return skip("%s does not read as the fan's (%s)" % (CONTAINER, ex))
            have = hashlib.sha256(dec).hexdigest()
            if have != want:
                return skip('%s entry %d sha256 %s is not the fan\'s' % (CONTAINER, i, have[:12]))
            parts[i] = dec
    if any(v.get('words') for v in ICONS.values()):
        # the label face is cut out of the fan's own "Norm" and "Fatal" icons (tools/icon_labels.py)
        import icon_labels
        try:
            icon_labels.harvest({k: _grid(entry_decoded(container, k)[0]) for k in icon_labels.HARVEST})
        except (ValueError, IndexError, struct.error) as ex:
            return skip('the label face cannot be cut out of the fan\'s icons (%s)' % ex)
    out = bytearray(container)
    info = {}
    done = {}
    grown = {}
    for e, spec in sorted(ICONS.items(), key=lambda kv: bool(kv[1].get('sibling'))):
        size = spec['size']
        a, b = ext[e]
        new_pal = None
        if spec.get('sibling'):
            sb = spec['sibling']
            fan_grid = _grid(parts[e])
            grid, _mask = compose_sibling(fan_grid, nclr(parts[spec['pal']]), done[sb['of']], nclr(parts[ICONS[sb['of']]['pal']]),
                                          reg[str(sb['of'])]['reg'], reg[str(e)]['reg'], size, sb['box'], spec.get('bg'))
            how = 'the picture of %d scaled into the small twin inside %r' % (sb['of'], sb['box'])
        elif spec.get('words'):
            # Capcom's words set as pixel lettering in the fan's face, on the label ground (tools/icon_labels.py);
            # a `small` box (small print of Capcom's own word) is placed after the words' erase, over the ground
            import icon_labels
            fan_grid = _grid(parts[e])
            grid, _chg = icon_labels.set_words(fan_grid, spec['words'])
            how = 'words %s' % ', '.join(repr(w['text']) for w in spec['words'] if w['text'])
            if spec.get('small'):
                grid, _mask = compose_small(grid, nclr(parts[spec['pal']]), textures[spec['eng']], spec['small'])
                how += " and Capcom's small print %r" % (spec['small']['src'],)
        elif spec.get('title'):
            fan_grid = _grid(parts[e])
            grid, _mask = compose_title(fan_grid, textures[spec['eng']], reg[str(e)]['reg'], size, spec['title'])
            how = "Capcom's %s title redrawn inside %r only" % (spec['eng'], spec['title']['box'])
        elif spec.get('local'):
            # only the old wording is redrawn, in the fan's own palette; the palette entry stays the fan's bytes
            fan_grid = _grid(parts[e])
            grid, _mask = compose_local(fan_grid, nclr(parts[spec['pal']]), textures[spec['eng']], textures.get(spec['jp']),
                                        reg[str(e)]['reg'], size, spec['local'], spec.get('bg'))
            how = "Capcom's %s redrawn inside %r only" % (spec['eng'], spec['local']['box'])
        else:
            grid, pal5 = compose_picture(textures[spec['eng']], reg[str(e)]['reg'], size, bgc=spec.get('bg'))
            new_pal = palette_bytes(parts[spec['pal']], pal5)
            how = "Capcom's %s at %dx%d" % (spec['eng'], size, size)
        done[e] = grid
        new_entry = _with_grid(parts[e], grid)
        stream = lz11.compress(new_entry)
        if lz11.decompress(stream) != new_entry:
            raise IconError('entry %d does not round-trip through LZ11' % e)
        if len(stream) > b - a:
            if not spec.get('grow'):
                raise IconError('entry %d would be stored in %d bytes, the fan\'s is %d; it must not be larger'
                                % (e, len(stream), b - a))
            if len(new_entry) > GROW_CAP:
                raise IconError('entry %d decodes to %d bytes, over the %d the column +8 icon block holds'
                                % (e, len(new_entry), GROW_CAP))
            grown[e] = stream
        else:
            out[a:b] = stream + b'\0' * (b - a - len(stream))
        if new_pal is not None:
            pa, pb = ext[spec['pal']]
            if len(new_pal) != pb - pa:
                raise IconError('palette entry %d changed size' % spec['pal'])
            out[pa:pb] = new_pal
        changed = int((grid != _grid(parts[e])).sum())
        info[e] = dict(stored=len(stream), fan_stored=b - a, decoded=len(new_entry), changed=changed)
        log('evidence icon %d (%s): %s, %d px changed, decoded %d bytes (fan %d), stored %d (fan %d)'
            % (e, CONTAINER, how, changed, len(new_entry), len(parts[e]), len(stream), b - a))
    if len(out) != len(container):
        raise IconError('container changed size')
    if grown:
        return relayout(bytes(out), grown), True, info
    return bytes(out), True, info


def load_reg():
    with open(REG_JSON, 'r', encoding='utf-8') as f:
        return json.load(f)


def needed_textures():
    """The textures patch() reads: every icon's English one, and the Japanese twin of a local swap that is
    gated by where the two differ."""
    return {v['eng'] for v in ICONS.values()} | {v['jp'] for v in ICONS.values()
                                                  if v.get('local') and not v['local'].get('rect')}


def apply_to_rom(rom, dumpdir, log=None, any_rom=False):
    import title_logo
    from choice_strips import rom_file
    cur = rom_file(rom, CONTAINER)
    try:
        tex = {n: load_texture(dumpdir, n) for n in sorted(needed_textures())}
    except IconError as ex:
        if not any_rom:
            raise IconError('%s (pass --any-rom to build without the icons)' % ex)
        (log or (lambda s: None))('evidence icons: NOT redrawn, --any-rom given (%s)' % ex)
        return rom, False
    new, changed, _info = patch(cur, tex, load_reg(), log, any_rom)
    if not changed:
        return rom, False
    return title_logo.splice(rom, CONTAINER, new), True


if __name__ == '__main__':
    if len(sys.argv) != 4:
        raise SystemExit('usage: idcom_icons.py FAN_idcom.bin DUMPDIR OUT.bin')
    src, dump, out = sys.argv[1:4]
    tex = {n: load_texture(dump, n) for n in sorted(needed_textures())}
    new, changed, _i = patch(open(src, 'rb').read(), tex, load_reg(), print)
    open(out, 'wb').write(new)
    print('wrote', out, '(changed)' if changed else '(unchanged)')
