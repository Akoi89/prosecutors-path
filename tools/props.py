# -*- coding: utf-8 -*-
"""Signs and props painted into the backgrounds, redrawn with Capcom's wording from the Collection's
own pictures (com/mapbg.bin, com/logicbg.bin, com/upcut.bin, jpn/upcut_local.bin).

The fan translation lettered these signs with its own wording ("EAT FREE, LIVE FREE IN PRISON",
"SPECIAL CELL", ...) where the Collection's English pictures say something else ("Your Life, Your
Choice", "MAXIMUM SECURITY", ...). Each DS picture is the same art as a Collection texture drawn 5.625
times larger, so at build time, from the user's own Collection install (extract() keeps a window
round each sign, every language, under dump/title/props/):

  1. the sign without lettering: the colour the languages that show no lettering there agree on
     (props_core.background), scaled to DS size and turned into the DS picture's own palette indices
     by the colour vote of props_core.vote, on the pixels of the sign that carried the fan's lettering
     (and one pixel round them);
  2. Capcom's lettering, in one of two ways:
       'native'  Capcom's English picture as it is, scaled with the picture (whole sign faces whose
                 design differs, banners whose lettering is large enough at DS size);
       'relaid'  Capcom's own words cut out of its English picture at the word gaps and set in lines at
                 the height of the fan's lettering (the fan's letters are scaled-down type too; Capcom's
                 line at the picture's own scale is smaller than the fan's), centred where the fan's
                 lines were, carried onto a sign seen at an angle by a perspective map;
     composited in the colour of the fan's lettering and snapped to the palette entries the fan's
     sign already uses.
The registration of every window is proved on every build (props_core.register_check).

Container policy: written IN PLACE. The table and every other entry stay the fan's bytes; a changed
entry keeps its decoded size and its RGCN header (only pixels change) and is stored as a real LZ11
stream that must fit in the bytes the fan's entry held (padded with zeros); the palette entry is not
touched. tools/bufcheck.py check (s) verifies that on the built ROM. patch() guards on the sha256 of
the fan's decoded entries and palettes.

    python tools/props.py FAN_DIR DUMPDIR OUTDIR     (offline: FAN_DIR holds com/, jpn/ of the fan ROM)
"""
import sys, os, glob, hashlib, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image
import props_core as pc
from props_core import PropsError

S = 5.625                       # Capcom pixels per DS pixel
LANGS = ('', '_eng', '_fre', '_ger', '_kor', '_sim', '_tra')
CACHE = ('title', 'props')
CTX = 12                        # DS pixels of context kept round a window at extraction
BUNDLES = {                     # texture family -> bundle file prefix (not the _trial or _classic one)
    'mapbg': 'gk2_mapbg_assets_all',
    'upcut': 'gk2_upcut_assets_all',
    'upcutlocal': 'gk2_upcutlocal_assets_all',
}

# A canvas is a Collection picture as the DS sees it: parts = [(texture base, x of the part in Capcom
# pixels)] (a panorama is two halves side by side); size in Capcom pixels; crop_x = Capcom pixels left of
# the DS picture (a 16:9 cut-in whose DS picture is its central 4:3).
CANVASES = {
    'map04': dict(family='mapbg', parts=[('map04', 0)], size=(3600, 1080), crop_x=0),
    'mapVS04': dict(family='upcut', parts=[('mapVS04_0', 0), ('mapVS04_1', 2340)], size=(4680, 1080), crop_x=0),
    'map08_00': dict(family='mapbg', parts=[('map08_00', 0)], size=(2160, 1080), crop_x=0),
    'map08_01': dict(family='mapbg', parts=[('map08_01', 0)], size=(2160, 1080), crop_x=0),
    'mapVS08': dict(family='upcut', parts=[('mapVS08_0', 0), ('mapVS08_1', 2340)], size=(4680, 1080), crop_x=0),
    'map09_03': dict(family='mapbg', parts=[('map09_03', 0)], size=(3600, 1440), crop_x=0),
    'cut01_009': dict(family='upcutlocal', parts=[('cut01_009', 0)], size=(1920, 1080), crop_x=240),
    'map11_00': dict(family='mapbg', parts=[('map11_00', 0)], size=(3060, 1620), crop_x=0),
    'map11_01': dict(family='mapbg', parts=[('map11_01', 0)], size=(3060, 1620), crop_x=0),
    'map13': dict(family='mapbg', parts=[('map13', 0)], size=(2880, 1800), crop_x=0),
    'mapVS11': dict(family='upcut', parts=[('mapVS11_0', 0), ('mapVS11_1', 2340)], size=(4680, 1080), crop_x=0),
    'mapVS14': dict(family='upcut', parts=[('mapVS14_0', 0), ('mapVS14_1', 2340)], size=(4680, 1080), crop_x=0),
    'mapVS0d': dict(family='upcut', parts=[('mapVS0d_0', 0), ('mapVS0d_1', 2340)], size=(4680, 1080), crop_x=0),
    'cut02_008': dict(family='upcut', parts=[('cut02_008', 0)], size=(2880, 1080), crop_x=0),
    'cut03_005': dict(family='upcutlocal', parts=[('cut03_005', 0)], size=(1920, 1080), crop_x=240),
    'cut03_020': dict(family='upcutlocal', parts=[('cut03_020', 0)], size=(1920, 1080), crop_x=240),
}

# Capcom's lettering to relay: canvas, the sign face (Capcom pixels, canvas coordinates), the x range
# of each word (canvas coordinates) and the cap line and baseline rows.
LETTERING = {
    'motto': dict(canvas='map04', box=(872, 96, 1243, 169), words=[(878, 949), (961, 1028), (1040, 1111), (1124, 1219)],
                  cap=(116, 139.5)),
    # MAXIMUM / SECURITY: white capitals in two lines on the dark door plate
    'maxsec': dict(canvas='map08_00', box=(1796, 498, 1898, 546), ink='light', median=True,
                   words=[(1807, 1885, 507, 521), (1806, 1887, 525, 540)], cap=(507, 518.5)),
}

# The pictures. pal: palette entry; window: DS rectangle (x0, y0, x1, y1) worked on; off: the picture's
# DS offset on its canvas; face: DS polygon the new lettering and the fill may touch; mode as above;
# relaid: lettering key, scale (Capcom pixels per DS pixel of the lettering), lines = [(word indices,
# DS cap row, DS centre x)] in the frontal lettering space, H = optional 3x3 map from the lettering's
# canvas (Capcom pixels) to this canvas (Capcom pixels); thr: DS colour difference above which a pixel
# of the face is taken as the fan's lettering; max_err: registration bound. Optional: gamma (< 1 makes
# relaid ink bolder, for a 16-colour picture whose mid shades would thin the strokes), ink ('dark' or
# 'light' lettering on the canvas), median (also take any pixel where a language differs from the others
# as lettering), halo, lone (colour distance beyond which a pixel takes the nearest palette colour
# instead of a voted example), cal_exclude (DS polygons left out of the registration proof), row_fill
# ((x0, x1): a plate flat along each row; each filled pixel takes its row's commonest colour over those
# columns), face_palette (only the face's own pixels are examples and its own colours the fallback, for a
# sign with colours of its own over a busy picture), fill='nearest' (every changed pixel takes the nearest of
# those colours to Capcom's fitted colour, no vote: a smooth cloth gradient the vote turns into flat patches).
PICTURES = []


def picture(**kw):
    kw.setdefault('off', (0, 0))
    kw.setdefault('thr', 30.0)
    kw.setdefault('max_err', 12.0)
    kw.setdefault('H', None)
    PICTURES.append(kw)
    return kw


# ---------------------------------------------------------------- class A: the prison motto sign
picture(name='motto_mapbg10', cont='com/mapbg.bin', entry=10, pal=11, canvas='map04',
        window=(136, 4, 240, 44), face=[(155, 16), (220, 16), (220, 29), (155, 29)],
        mode='relaid', lettering='motto', scale=4.0, lines=[((0, 1), 16.6, 188), ((2, 3), 23.4, 188)])
# the Logic backdrop of the same corridor: the canvas from x 176, sixteen cyan shades, light lettering on a
# dark face, cut by the left edge of the screen; the lines stand where they stand on the sign above
picture(name='motto_logicbg14', cont='com/logicbg.bin', entry=14, pal=15, canvas='map04', off=(176, 0),
        window=(0, 4, 64, 44), face=[(0, 16), (44, 16), (44, 29), (0, 29)], max_err=18.0, gamma=0.6,
        mode='relaid', lettering='motto', scale=4.0, lines=[((0, 1), 16.6, 188 - 176), ((2, 3), 23.4, 188 - 176)])
# the corridor panorama: the sign seen from below, close; Capcom's own line is large enough here to be
# taken as it is (one line, cut by the top edge as Capcom's picture cuts it)
picture(name='motto_upcut388', cont='com/upcut.bin', entry=388, pal=389, canvas='mapVS04',
        window=(100, 0, 252, 26), face=[(111, 0), (247, 0), (244, 11), (123, 22)], mode='native', max_err=22.0)

# ---------------------------------------------------------------- class B: the Maximum Security door plate
# The plate's face is 23 x 12 pixels: SECURITY cannot stand at the fan's 5-row letter height in it (eight
# capitals of the fan's 3-pixel face and their gaps are 31 pixels). Capcom's own plate is small print at DS
# size; its two lines are set as large as the plate takes (larger than Capcom's, about 2 rows), the design
# Capcom gives the plate. The location caption names the room Maximum Security.
# The fan widened the retail plate by two pixels each side (face x 316-338, the retail's 318-336): the fill
# keeps the fan's plate, flat along each row (row_fill), so Capcom's narrower plate edge draws no stripe.
picture(name='maxsec_mapbg20', cont='com/mapbg.bin', entry=20, pal=21, canvas='map08_00',
        window=(300, 76, 352, 112), face=[(317, 87), (338, 87), (338, 98), (317, 98)], ink='light', median=True,
        face_examples=True, mode='relaid', lettering='maxsec', scale=3.6,
        lines=[((0,), 88.6, 327.5), ((1,), 93.6, 327.5)], ink_min=0.3, row_fill=(320, 335))
picture(name='maxsec_mapbg22', cont='com/mapbg.bin', entry=22, pal=23, canvas='map08_01',
        window=(300, 76, 352, 112), face=[(317, 87), (338, 87), (338, 98), (317, 98)], ink='light', median=True,
        face_examples=True, mode='relaid', lettering='maxsec', scale=3.6,
        lines=[((0,), 88.6, 327.5), ((1,), 93.6, 327.5)], ink_min=0.3, row_fill=(320, 335))
# the cell-block panorama: the same plate seen close, cut by the right edge; Capcom's MAXI.. / SECU.. is
# about 5 rows high there and is taken as drawn
picture(name='maxsec_upcut392', cont='com/upcut.bin', entry=392, pal=393, canvas='mapVS08',
        window=(780, 64, 832, 124), face=[(802, 78), (832, 78), (832, 112), (802, 112)], ink='light', median=True,
        mode='native')


# ---------------------------------------------------------------- class C: the circus banner
# The retail art's own English ANIMAL SHOW (the fan left it); Capcom's picture prints CIRCUS SHOW, in
# letters large enough at DS size to be taken as Capcom drew them
picture(name='circus_mapbg30', cont='com/mapbg.bin', entry=30, pal=31, canvas='map09_03',
        window=(300, 72, 424, 152), face=[(304, 76), (420, 76), (420, 148), (304, 148)], mode='native', median=True)
# the Logic backdrop of the stage: the canvas from x 272, sixteen cyan shades
# (taken from the redrawn mapbg 30 through the backdrop's own colour mapping: the sixteen shades follow
# the room picture pixel for pixel, 76 percent of pixels by one index mapping, the rest dithering)
picture(name='circus_logicbg34', cont='com/logicbg.bin', entry=34, pal=35, canvas='map09_03', off=(272, 0),
        window=(28, 72, 152, 152), face=[(32, 76), (148, 76), (148, 148), (32, 148)], mode='derived',
        source='circus_mapbg30')
# the grey flashback of the show (jpn/upcut_local, a 16:9 cut-in): the banner behind the elephant and the tiger
picture(name='circus_upcutlocal42', cont='jpn/upcut_local.bin', entry=42, pal=43, canvas='cut01_009',
        window=(0, 0, 256, 140), face=[(0, 0), (136, 0), (136, 94), (0, 94)], mode='native', median=True, max_err=55.0)


# ---------------------------------------------------------------- class D: the cotton candy stand
# The fan's banner HEAVEN'S TEAR / Heavenly Cotton Candy where Capcom's banner reads Cotton Candy / Parting
# Clouds. Only the banner is taken from Capcom's picture: the stand's boards (the fan's Cotton Candy and $9,
# Capcom's cloud flavours) and its jar, cloud and side panel stay the fan's. The banner keeps its own
# colours (face_palette) and its smooth gradient (fill='nearest'); the face follows the banner's edges, where
# the fan's banner and Capcom's agree. The plaza pictures register with a larger error than the others
# (Capcom redrew the shop window beside the stand), still well clear of every one-pixel shift.
picture(name='cotton_mapbg54', cont='com/mapbg.bin', entry=54, pal=55, canvas='map11_00',
        window=(396, 84, 492, 186), face=[(456, 90), (470, 90), (482, 95), (470, 168), (458, 168), (446, 164)],
        mode='native', median=True, face_palette=True, fill='nearest', max_err=20.0)
picture(name='cotton_mapbg56', cont='com/mapbg.bin', entry=56, pal=57, canvas='map11_01',
        window=(396, 84, 492, 186), face=[(456, 90), (470, 90), (482, 95), (470, 168), (458, 168), (446, 164)],
        mode='native', median=True, face_palette=True, fill='nearest', max_err=14.0)
# map13: a vertical banner at each edge of the plaza, cut by the screen edge
picture(name='cotton_mapbg60_left', cont='com/mapbg.bin', entry=60, pal=61, canvas='map13',
        window=(0, 36, 24, 112), face=[(0, 48), (11, 48), (11, 111), (0, 111)],
        mode='native', median=True, face_palette=True, fill='nearest')
picture(name='cotton_mapbg60_right', cont='com/mapbg.bin', entry=60, pal=61, canvas='map13',
        window=(488, 36, 512, 112), face=[(500, 48), (511, 48), (511, 111), (500, 111)],
        mode='native', median=True, face_palette=True, fill='nearest')
# the plaza panorama: the banner close up beside the angel's cloud
picture(name='cotton_upcut406', cont='com/upcut.bin', entry=406, pal=407, canvas='mapVS11',
        window=(630, 0, 832, 192), face=[(765, 8), (832, 8), (832, 30), (812, 95), (803, 140), (800, 192), (742, 192),
                                         (744, 150), (752, 100), (760, 50)],
        mode='native', median=True, face_palette=True, fill='nearest', max_err=17.0)
# the grey rain cut-in and the night cut-in (jpn/upcut_local): the banner at the right edge of the screen
picture(name='cotton_upcutlocal206', cont='jpn/upcut_local.bin', entry=206, pal=207, canvas='cut03_005',
        window=(180, 0, 256, 192), face=[(233, 0), (256, 0), (256, 192), (233, 192)],
        mode='native', median=True, face_palette=True, fill='nearest')
picture(name='cotton_upcutlocal234', cont='jpn/upcut_local.bin', entry=234, pal=235, canvas='cut03_020',
        window=(196, 40, 256, 160), face=[(246, 58), (256, 58), (256, 112), (246, 112)],
        mode='native', median=True, face_palette=True, fill='nearest')


# ---------------------------------------------------------------- class E: the permit on the site fence
# The fan's BUILDING PERMIT notice (red header, GR Works / Prime Mall / 83 m2 / 2020) where Capcom's fence
# carries a Filming Permit (Production Co.: Global Studios ...): the whole sign differs, so the sign is
# taken as Capcom drew it, on the fan's fence (registered: Capcom's sign stands within a pixel of the
# fan's; the spotlight's head that covers its right edge is the same in both)
picture(name='permit_upcut408', cont='com/upcut.bin', entry=408, pal=409, canvas='mapVS14',
        window=(700, 110, 790, 192), face=[(722, 126), (772, 126), (772, 192), (722, 192)],
        mode='native', median=True)


# ---------------------------------------------------------------- class F: the ship model's plaque
# The fan's plaque reads The Voyage of the Good Ship / Red Rum; Capcom's reads Voyage of The Red Rover and
# four lines of small print. The plaque is taken as Capcom drew it: in the museum panorama (cut by the
# bottom edge) and in the close-up of the model, both in the plaque's own colours (the vote put the ship's
# greys into the plate and olive smudges into the close-up's title)
picture(name='plaque_upcut400', cont='com/upcut.bin', entry=400, pal=401, canvas='mapVS0d',
        window=(460, 150, 580, 192), face=[(470, 160), (570, 160), (570, 192), (470, 192)],
        mode='native', median=True, face_palette=True, fill='nearest')
picture(name='plaque_upcut128', cont='com/upcut.bin', entry=128, pal=129, canvas='cut02_008',
        window=(330, 110, 440, 192), face=[(340, 120), (432, 120), (432, 186), (340, 186)],
        mode='native', median=True, face_palette=True, fill='nearest')


# sha256 of the fan's decoded picture and palette entries: patch() redraws nothing else
FAN_SHA = {
    ('com/mapbg.bin', 10): ('2c58701c83ae549aad3a67f9176e3711b3ee5b83306dc6d48ccf2251329e3be6',
        '9526c9f0695d7c9590a43974c05c79ca2e2b88226ec9eeaf77d08de9db4f23b6'),
    ('com/logicbg.bin', 14): ('774a0070503132e9ed797c206f795af6dd61bae742a50c9f50e57ed88693ccc8',
        'f1ba8a08f48bf4ed347c1e30848bebabe2126c97762df39c7448b0a1d7f88dd7'),
    ('com/upcut.bin', 388): ('939a0f32d01a87a2b03841a640552f6dbdcb6533963449535a894ddc886d5d9b',
        '16ccfb7e690dcdedeeda69470f37728feb6b626bb9d9f6844706f0412f191b5a'),
    ('com/mapbg.bin', 20): ('bc0864af49f07c8081ad317299de89e5f6287cb6320bff17221e640211047c0a',
        '332425dc89195f57317d88614938bddb48316f7ff4760395de634bcd759b18bb'),
    ('com/mapbg.bin', 22): ('65e603c3a4c7144b1ad2c4c0303023442b2b9caf772537764a9e6edfb16d2f6e',
        '6949d07cda3597897fb0a62da36f2f5cdc85d3f846e41bed963a73c7be7a3fc6'),
    ('com/upcut.bin', 392): ('c69af1cad82361855de0d69010d05157890245442375376a0be65f26701b0c10',
        '92b385f59ee1699663d25a8e60acc48e2577d344ceb1efb9da3db216aa7bb027'),
    ('com/mapbg.bin', 30): ('a957485681b3192645b3d7021e95eb3e3b809c3e9e926fa0cbb5b3901ea7eb67',
        '739200e508816b479ee720b745766fcf821257223ee9c09ebef77636e380349e'),
    ('com/logicbg.bin', 34): ('a2f3575746bc59071b7d1fbdb048de283a29aeab18c0b9fddbd0fc313ee8ab4c',
        'ae75fae18f3564681dbaa2c3e50030bcff0932d8fb9902e492553f1f7ad8d74d'),
    ('jpn/upcut_local.bin', 42): ('9c4b4b44f546ecdc0fb0a5489378692330e7661fd074bafdc3f2680446643735',
        'fd28ad5e0785db49a0f94d39d7fbcc7e5cf03401d3e283e22cbfc0bbb3b6a360'),
    ('com/mapbg.bin', 54): ('a54c5320ac66d23ccc0cd73e96d8a3148e3b34cb5e19acd5f7ecd7bd65f91139',
        'c565c0274838ad5f1aaa32d005dca91f62c0bdfcaaaa145bc367efbe6a1b9af1'),
    ('com/mapbg.bin', 56): ('e3e93615e35c4a41ed068b696350a6d8351dc0c74b69893eebe3024c46f97a3e',
        '87f7b5091eb4fc8301d122d6a5e08a433c814dfdb166231bd1f7e30acc146f72'),
    ('com/mapbg.bin', 60): ('ac13b5285397672cfd20781279daa057fb37d19894e4399d35f5ddcbaec57349',
        '1d222b59a5960659ac8126a5ca63e5c2959fa77d04d387000f5a76959f0f9d9c'),
    ('com/upcut.bin', 406): ('a36218b3bf5ef72d82fe9a219d64c163cf9e7d2f2de8216741aa3903b204d736',
        '79ff1cac2ccd2de491b316aca1917ea38f6bc5ef3904c4d0d39b9ec7a23f69ee'),
    ('jpn/upcut_local.bin', 206): ('c96b9e960c0f83c3a00042f5a9017a8b454bb21a8b85ad25cb3d0cd9550f908b',
        '88e0c617a30f53519414a7c41ea67cc364cccffffc9a8267340f1089d38c6ff3'),
    ('jpn/upcut_local.bin', 234): ('5a99e4871dc2a2c76c0de55bdc31dbcb09685784f1a49cfae56558f84cc896e0',
        '27135b900d4a6f74984cb6e35232fda4db176df3e6e91b235d22e0fe4bd4e1ff'),
    ('com/upcut.bin', 408): ('e3fd83fa2903410deb71ad856bd2194fd609d5c609cfcd79f99890e4af666425',
        'd2a924c6add67934504d91e3dff377106d5fee297b5409199cb55a9e4483c48e'),
    ('com/upcut.bin', 400): ('7db544e48130bb8d03dc977e981fb8ec44a8cd0fbee833a478a918a6282cbf9b',
        '37d3051ccbb0501a488411bc3447d1ab2b17c5bc5fe5c0096d864c6e291d1f9c'),
    ('com/upcut.bin', 128): ('d9d3df3bcc02a41aa0af1b294590648e9a2b2d20cc346b8b2dff5b1572b125db',
        '14008cf5f17f494eaa9e79e144cc5be288443eaa7584ee264ca1c1a6b261aef5'),
}


# sha256 of each Collection crop's decoded pixels ("(h, w, 3):" + RGB bytes): a crop from another release
# of the Collection, another language's texture or a shifted window is refused (the build goes on without
# the signs only under --any-rom)
CROP_SHA = {
    'cut01_009_172_-68_1748_855.png': '5f947f6e08a7ede7c8185f79e485329a27ad025dd6dc2774ad16bd37550c0416',
    'cut01_009_172_-68_1748_855_eng.png': 'ec6c5b56d3b9c91385c82feb2ae72c762df9c227995478d01400dc103d7ce6b2',
    'cut01_009_172_-68_1748_855_fre.png': 'd54ca03e3f503c17e91d18b0eb4f3d719c87808388133c31b5d76f71873661d3',
    'cut01_009_172_-68_1748_855_ger.png': '417ffd70dd7955cfc74438b5558693d6a1ad891f02f4360a52639fe255a17144',
    'cut01_009_172_-68_1748_855_kor.png': '5f947f6e08a7ede7c8185f79e485329a27ad025dd6dc2774ad16bd37550c0416',
    'cut01_009_172_-68_1748_855_sim.png': '5f947f6e08a7ede7c8185f79e485329a27ad025dd6dc2774ad16bd37550c0416',
    'cut01_009_172_-68_1748_855_tra.png': '5f947f6e08a7ede7c8185f79e485329a27ad025dd6dc2774ad16bd37550c0416',
    'cut02_008_1788_551_2543_1148.png': 'b56996fecece4c357ee108ccafc2fcb12e647ae4ac7e63e189bab82362ef022b',
    'cut02_008_1788_551_2543_1148_eng.png': 'b992654bdab0f2c22f5abec33597d55bd9f61ac2db07d9bed9682af63b9144a5',
    'cut02_008_1788_551_2543_1148_fre.png': 'b6e414d267ebd9157677664fa4e3c2271194d3d16f601937fc5c7f5aefffd5cc',
    'cut02_008_1788_551_2543_1148_ger.png': '3fb469b9c67d11abb99e7e3a90524a6a6fcd160b505f8685c6d48e322d5ff496',
    'cut02_008_1788_551_2543_1148_kor.png': 'b22bbb3814ebca422ef7d0512876bfb0f412af7c503deb35ed9cabadf80d79e8',
    'cut02_008_1788_551_2543_1148_sim.png': '64711a822f5659a66589e9b5dd2f37f2c70c22ece294ff123c0c06530fa53848',
    'cut02_008_1788_551_2543_1148_tra.png': '4bb02e0f47c611a492ba61eaf73f761199e5137672f264f01626065a0f16a882',
    'cut03_005_1185_-68_1748_1148.png': '474068e20e691d782f48f846e9fd33d64f00372068c8f6d833294dcaa30a7994',
    'cut03_005_1185_-68_1748_1148_eng.png': '66699ea7dc4d8727aa2069726889dfc8d0ee726229ab77fad16241c4adae887c',
    'cut03_005_1185_-68_1748_1148_fre.png': 'b0e9d830a09afacf1317a1249c913a28cdcde1efcd5536664aab96c8ce7e1a2d',
    'cut03_005_1185_-68_1748_1148_ger.png': 'a83db2f1a02f6f38d57283f160c17af639b4b001ea24e476924cdba6791b0187',
    'cut03_005_1185_-68_1748_1148_kor.png': 'ad96b4767b4d3c8a39e6c7f52fca13b7e9e72a22793a71942d58e2174674f9e2',
    'cut03_005_1185_-68_1748_1148_sim.png': '6ff715a1c472eaa673dcbb36cb9f1009220bba39238e811e1fa5f7bab82dc220',
    'cut03_005_1185_-68_1748_1148_tra.png': '1dcc49d34579a7cd7b1f121f779f29a76277e3deafe2f19584c13d412e18e550',
    'cut03_020_1275_157_1748_968.png': '06460d388401e3b88ddf56dd0e7586e876a51d491de519e50213e36b4f5ccc70',
    'cut03_020_1275_157_1748_968_eng.png': '5ac6e41225a2974eb7b98361be6236a5f405c3e5034c8d6c0b3dc20accc7f778',
    'cut03_020_1275_157_1748_968_fre.png': '8c99b017a29a680bd6c69eca97bccbeac33c692bdec3c414559ceb6a1173f587',
    'cut03_020_1275_157_1748_968_ger.png': '8d5099fc74659f235fbdd2618d77f922687bf80ba5cc941eaf822530c9d2ca6d',
    'cut03_020_1275_157_1748_968_kor.png': '3ef11a5cfd6afd87a8979e1cdbc956a7e349bf70cb73e58d90153ddc25b1435a',
    'cut03_020_1275_157_1748_968_sim.png': '93fe7829677f8972c00ee7d968fc58fc3c1a62304062714cbb72cb9583ff2fa0',
    'cut03_020_1275_157_1748_968_tra.png': 'd952df337505301ea26d0e804f6c637c13914e57012b0c10e91cad2862b8a292',
    'map04_697_-45_1418_315.png': '99eb16e9bf6d3ac4a4bebe4e5cc35ac0dac3b3c7920b65f06a610f16f0af6a29',
    'map04_697_-45_1418_315_eng.png': '39909061f5e7f469e701ad9d93a95acc3130de391bee4d2ffc94fec2f5950161',
    'map04_697_-45_1418_315_fre.png': '9005aefddcb3f242339457ada2dc553e5034fefcd772171cff09b6880ae08a3e',
    'map04_697_-45_1418_315_ger.png': '8d2f17fbe7edb9e7d8ae47cc3d80a807f216aa4b16a522b917cf2e505863f7ce',
    'map04_697_-45_1418_315_kor.png': 'cfd5e67212f41a5d2d73e2941fcb0ae7511531dac6cbebce54909e3736edc37e',
    'map04_697_-45_1418_315_sim.png': '5faaf0e85d6de5e83e8756eabca10ba5c489659ec08810ec76ca9a43690e4362',
    'map04_697_-45_1418_315_tra.png': '5faaf0e85d6de5e83e8756eabca10ba5c489659ec08810ec76ca9a43690e4362',
    'map04_840_64_1275_201.png': 'cc504fe9a371da9998b1146b2e46c1d7fd699a5657f220e45538d6c3b67d0763',
    'map04_840_64_1275_201_eng.png': '5374deadb8618824075318121a2f5c6056d5db798b22ad4105785ddff38c8893',
    'map04_840_64_1275_201_fre.png': '5dd1be397825b2a7965877b6d96b646f8f7452bc74ad3a736edc6dd781e5d472',
    'map04_840_64_1275_201_ger.png': 'f06789138c55d9a07a2718d518ab387970aa7779c06fc224dcace7e2fc268031',
    'map04_840_64_1275_201_kor.png': 'fd22272a806edfae47edfcb827f0aead9faa68f98b54536df9d828b8e1766f8a',
    'map04_840_64_1275_201_sim.png': 'b37b50a91768b9e8a114115cee0447b007ea6bdf1f4fb8dbb5d2e5bfc3439919',
    'map04_840_64_1275_201_tra.png': 'b37b50a91768b9e8a114115cee0447b007ea6bdf1f4fb8dbb5d2e5bfc3439919',
    'map04_922_-45_1418_315.png': '4430222878ef1ff057fe03ca552a92c0463f9eed2e752d4c8be45352f137d9f9',
    'map04_922_-45_1418_315_eng.png': '44fe820684e43c33788eba3ca7595bf2618caef26d680dc886222d8b5a681665',
    'map04_922_-45_1418_315_fre.png': 'b820e4d72e9b6a77716184ab3b2ac155177c61c511d3ef1a39b23ebf69ec0a21',
    'map04_922_-45_1418_315_ger.png': '6949afa1c223e8e38d98a1de641bf8c6142bfbc507b6012c17577710ff3fdc51',
    'map04_922_-45_1418_315_kor.png': '0eb372ef0661fabf10b6d7c2a81d16d0655364ddf7afb7af6a305b857d929f9b',
    'map04_922_-45_1418_315_sim.png': '031e93e8775de117e0327bc04876b42e388e1756baecd49ae3fb20d04a3cec9a',
    'map04_922_-45_1418_315_tra.png': '031e93e8775de117e0327bc04876b42e388e1756baecd49ae3fb20d04a3cec9a',
    'map08_00_1620_360_2048_698.png': '289ae4f3093e249061ea61c5c7ff8347aa90fcb94a2e30c6d336e3e5ebfb46aa',
    'map08_00_1620_360_2048_698_eng.png': 'd6bef92b6da16fc2614fb5b93cf1a5e3dc84ebe31abe905a6ca5064898bcef19',
    'map08_00_1620_360_2048_698_fre.png': '03237f69e425e605087041101b5e67aa0ba0de8a39115accd8830cf977fea77a',
    'map08_00_1620_360_2048_698_ger.png': 'f05fe5369dbf95213625e91a3217eeb21eb1ff0f48e208f7e86385cbb55d54e8',
    'map08_00_1620_360_2048_698_kor.png': '22eb3db38d45d7a687f5af18fa011335cfcd14286b7cb0bee94c1cd919b703f0',
    'map08_00_1620_360_2048_698_sim.png': 'e4e8beb88301fe564d020240388a8389083b721b2684970533370759042ff64c',
    'map08_00_1620_360_2048_698_tra.png': '3f18e810607a98c3b6de845acdbd19717387c4d31de03758142d19b4ca0e255b',
    'map08_00_1764_466_1930_578.png': '5610a6e5975301aca037e9a8431c3f7ca0047f8785fbcf09b053d930964c2651',
    'map08_00_1764_466_1930_578_eng.png': 'd39daaeeca039b343322bd012068144e505505dc71c94003894bcb8c3cb2773e',
    'map08_00_1764_466_1930_578_fre.png': 'd08f8ff9073e5cb25921a3d782d93399b4b950d5f482c8bdbe492b1365d544ff',
    'map08_00_1764_466_1930_578_ger.png': '851ea64387d9ad44737fecc0652f0c393075db0f102889a4b3ab4a1303a26147',
    'map08_00_1764_466_1930_578_kor.png': '620e6b426c934427dde06eddf9d64b2187d98dc3d12a55bda25e3c57f3329345',
    'map08_00_1764_466_1930_578_sim.png': 'f8cae63ce3288d70ad6a994c335d426a62438f6792f7aa60bcf1e39416cceda4',
    'map08_00_1764_466_1930_578_tra.png': 'a95e22a11d93ceb2a527b9e69b351cb4a02c698da2c2a116174ba981098c7508',
    'map08_01_1620_360_2048_698.png': '7b177742688a00995702b7c664c5041bdb3db9164f0ab77705e9ec3fa8d45785',
    'map08_01_1620_360_2048_698_eng.png': '2336b69372282de413d53e6bd0e0af7f0d9792efc4523cc6710886a54446f201',
    'map08_01_1620_360_2048_698_fre.png': '71b7ef4bb789c45dcb314b9639fd64ce7c5fda37316370f7928e2015de67f060',
    'map08_01_1620_360_2048_698_ger.png': '5a6f99ada57200646a92fe492749ccddf1a6567b13e144e2893ad528ab4a3633',
    'map08_01_1620_360_2048_698_kor.png': '34683630afa6315711ed071ac30a57e9d5c139ecd56996d6167b15bd70dcebcf',
    'map08_01_1620_360_2048_698_sim.png': 'daa5ee245d8b2864726a61f9cb22c66869a462badfba43b8e4e3a8a9d4387646',
    'map08_01_1620_360_2048_698_tra.png': '7f4e4a224782e1d502016a3d4a117c405e93dfb59e79fb1df489a834c0da911a',
    'map09_03_1620_337_2453_923.png': '67c5f0d19407e01631755be9060a64a3e8c01c1fed281b710adc3c6e66a52413',
    'map09_03_1620_337_2453_923_eng.png': '74f124dc67954cb8a161d55e5a9286aa36c48085e3aa4ee0264c59c6f09411cb',
    'map09_03_1620_337_2453_923_fre.png': '65066ff23fdacd55ca5fc0163215fc27adf7cd9e3c0cee6d3ec02b8d9acff466',
    'map09_03_1620_337_2453_923_ger.png': 'c97f41c7af4bc7cfcaa3adab9ed3997cf8a06747fb1f4a91cd69f97e35cf192c',
    'map09_03_1620_337_2453_923_kor.png': '67c5f0d19407e01631755be9060a64a3e8c01c1fed281b710adc3c6e66a52413',
    'map09_03_1620_337_2453_923_sim.png': '67c5f0d19407e01631755be9060a64a3e8c01c1fed281b710adc3c6e66a52413',
    'map09_03_1620_337_2453_923_tra.png': '67c5f0d19407e01631755be9060a64a3e8c01c1fed281b710adc3c6e66a52413',
    'map11_00_2160_405_2835_1114.png': '0f71c1fffcead4223841f8e424f51f505301c9a5725d6fc8b5c8f1e8c4cf9bf1',
    'map11_00_2160_405_2835_1114_eng.png': '54163368ff93cbb9c6a8dd3e607e8e69d550544d7514f316aa4972c752490c82',
    'map11_00_2160_405_2835_1114_fre.png': '4f0cfa15bf88079bc58f84d4998dd8d3eb1cf22ad29315df6b834697c38e1732',
    'map11_00_2160_405_2835_1114_ger.png': '418ca1f91be9dd38b9647649db379f00aefd0d919d8b14928aabcf05f5c3ebd0',
    'map11_00_2160_405_2835_1114_kor.png': '1daddf78cc33c244fdff8b9b5157294a6d9098751e84bc1d3634e7cbbd3a38de',
    'map11_00_2160_405_2835_1114_sim.png': 'de8853d9852753175e854a786b47c8c367785d41200e85ef16942d79f759516f',
    'map11_00_2160_405_2835_1114_tra.png': '8983d159e7ce69632bb404dfc85f09510047f3632c34baf7df126408aea0e2f7',
    'map11_01_2160_405_2835_1114.png': 'cca12deccd12b36110b07ff66181d7f6394fdc3dad4760e7e4b861ca9f6cbc1f',
    'map11_01_2160_405_2835_1114_eng.png': '5ee867e58af8fd583b53f90c17994f082eedec879c5c4c8878ed515bc724778a',
    'map11_01_2160_405_2835_1114_fre.png': '5a74f74a11cb9922fe0af1db801bfce41216e5f5c28008b8c0029c5db3c8298c',
    'map11_01_2160_405_2835_1114_ger.png': '01eb0937db2335d7716a990a285484a494d7320a9c1f2b8d4c4eb7f186755675',
    'map11_01_2160_405_2835_1114_kor.png': '16c460c31d7a9728dbccc001e639820dc04f80f92f46185f0a8ed0b7862b6f44',
    'map11_01_2160_405_2835_1114_sim.png': '673c4e46ecbbd1979ec95ec75dadc38eb5fcfcdf1b8819ccc52a2aa4b3bc6dde',
    'map11_01_2160_405_2835_1114_tra.png': 'eb6df73d6cacc497ae5711354f505b5af57f745a6ba8306819fe8c2ad1bb9d0b',
    'map13_-68_135_203_698.png': '4a93caac8ea6b90b760291e0f3d2bb99abe28b4cfb90b327571d824b8306c219',
    'map13_-68_135_203_698_eng.png': '595f4e0413c41a3bebf83e553741e7b89ee2f8326baa6aab2722dd87922fb7ac',
    'map13_-68_135_203_698_fre.png': 'cbce6006f8a5e4be31707e0723ac88c099de49854268cdc5249325f171ab6e51',
    'map13_-68_135_203_698_ger.png': '0cec70cc5644acd0d9b69a35be3103ea2612f920df7a34c85d9412a27d5c1ac5',
    'map13_-68_135_203_698_kor.png': '299e09b334886c5b36fba9ac35d5891c6e5366aecde36b1194576c0c2a9f982c',
    'map13_-68_135_203_698_sim.png': 'b8c037679549a849284ece4ba7a07332671f4f68058423aa5d1e74727cdd7734',
    'map13_-68_135_203_698_tra.png': 'abfc0581b27b223b9fd3599f7f898dd9d4b91bb16656ce3ca7a5932d3d9d5d72',
    'map13_2677_135_2948_698.png': '79bdba2957017b8888c00145cea089ff316360ce40c47908d31e7a21fb4fe35d',
    'map13_2677_135_2948_698_eng.png': '752cd7e8544dda36203dd88d48e892cf034a193a6d7f965c566f98a44ba72bf1',
    'map13_2677_135_2948_698_fre.png': '8bc844866d77dcaf4559e0cc796bbab6876e782c0a4ce13851b57f9c660a9aa7',
    'map13_2677_135_2948_698_ger.png': '1f5d7ee5ee926500f1cf1205448940d095eff53bc3a9cca5ec6b3d5c0cea9ab3',
    'map13_2677_135_2948_698_kor.png': 'a771f3d996f953c6b84d7a42fbdf6b0a8086d282cfa4b0a26f07a2ea71b701d5',
    'map13_2677_135_2948_698_sim.png': '7295af3f782a26cd54d5b73583c5914c3d23f9e4443d03025bf9b2b35a1e21fb',
    'map13_2677_135_2948_698_tra.png': '317b0a085fe93854f8cc4bb6bdd58bd34303031b06838ba31bf923c9948377cc',
    'mapVS04_495_-68_1485_214.png': '4b953d459a01f08ce499cca9249eea53612a48183aed3ca5f20e3ece636c2e32',
    'mapVS04_495_-68_1485_214_eng.png': '14ef28b03dbc909eff0b75e5e6282bab6718005b24a48315a399bc2eedf7d39e',
    'mapVS04_495_-68_1485_214_fre.png': 'b16be7c1f5f9a54dbb2d65ab80148e93a0340232e30032ec18732ad2a68e986e',
    'mapVS04_495_-68_1485_214_ger.png': '751a941b048eaf49758cac54e6067825e83bd000520fa3e65af74578625e166b',
    'mapVS04_495_-68_1485_214_kor.png': 'bd7f9ac08b4d5c5ed4d888a392ce6dbd1f7e38231e8037c12a6eea915af24e5e',
    'mapVS04_495_-68_1485_214_sim.png': '42dba13f093ef81af3aa66dd24e727bfdb46b69ddc9afbfa8dde31b86935e0e0',
    'mapVS04_495_-68_1485_214_tra.png': '4b953d459a01f08ce499cca9249eea53612a48183aed3ca5f20e3ece636c2e32',
    'mapVS08_4320_292_4748_765.png': '2efd917c12290e31972ef96a81d8d11800a287b42f74b42d1664a86651f5fa6f',
    'mapVS08_4320_292_4748_765_eng.png': 'b30d3a06051d5dd929af596a6dd6776293bb0c3727584cdbf34d2ddac569f197',
    'mapVS08_4320_292_4748_765_fre.png': '593cf38046caa4e3cb8fdeb144d695af2bb70d3fbdf5434dc1ce63afb659a4f0',
    'mapVS08_4320_292_4748_765_ger.png': 'f764b053d8a0cc981e1d8aae96055d6fb574a45aeeedc4dfa892816a482e1ce6',
    'mapVS08_4320_292_4748_765_kor.png': '8cd24be9f71db7774c30b5a3f530d10f81880ae384e1d50c93f1975dec68fa8d',
    'mapVS08_4320_292_4748_765_sim.png': 'ce375f94bacb76a3c5656297653a17648a439e70383ac6a638185b930ed75293',
    'mapVS08_4320_292_4748_765_tra.png': '203c3c99080253580618ab66ef581b4dc326c2156a89fc6c94e99e2100cc4a16',
    'mapVS0d_2520_776_3330_1148.png': '9a4ae5bd51cf00009097e0da3f583ffd78dee78cff9e698f10273acda1eefac6',
    'mapVS0d_2520_776_3330_1148_eng.png': 'f807d14787e24506621361d539db1cd0ce57628f36599b1c2e7909efcbe3f745',
    'mapVS0d_2520_776_3330_1148_fre.png': '1f4503c6850dad286684e71754d2a3f4f46e80bfeb1c9d404733041bebf6d04e',
    'mapVS0d_2520_776_3330_1148_ger.png': 'dca51e2d7508a9a6a0067df8f3a1632940c9786a78e94451eb457b1e93a8cde1',
    'mapVS0d_2520_776_3330_1148_kor.png': '53be835f9708bc27ff402936f27ba33775e5df111266c1ef0c521de285f2e0fa',
    'mapVS0d_2520_776_3330_1148_sim.png': 'd48dc3b7d8534bb0a54a8287fb6983a76006d607a0b1ce1d839c252b5f1d8ba2',
    'mapVS0d_2520_776_3330_1148_tra.png': 'dcf3218cedb70faee8a2167214c16c7afe97b7851dff73bf27a36dfc444090a2',
    'mapVS11_3476_-68_4748_1148.png': '7b093c2eccddbe5d5fedda44b0e83864685fb80a2ac5117820487951749b3407',
    'mapVS11_3476_-68_4748_1148_eng.png': '4a758a1bd3abc25ff48c7bc19c88900cc3ebe3d855d9c9ffd93063a678ae6e74',
    'mapVS11_3476_-68_4748_1148_fre.png': '64a412a687025c3e31aa27659e4996ac3ae494487ebca03205e859ea5d06eab4',
    'mapVS11_3476_-68_4748_1148_ger.png': 'cc0316e9df64140603b997401c4133a6d94e011038b50777caac1425a98c30c5',
    'mapVS11_3476_-68_4748_1148_kor.png': 'b7abbce689ae3a182b0c3bcb964fee6ddabe0ac26ab10e3b98add4be307147d9',
    'mapVS11_3476_-68_4748_1148_sim.png': '750926c80129ee045475a9f8577183114e3d7a5b7fcd2b10a5573eec32980c37',
    'mapVS11_3476_-68_4748_1148_tra.png': '6f292067790413e49b89d3bb2aa53470ad0b5be13861e0752a9612b72d7a38dd',
    'mapVS14_3870_551_4512_1148.png': 'd4619b03ac24932cc5d2d4ab71bd7b4966d39fb7564c49e9936d76e0c4eb3baf',
    'mapVS14_3870_551_4512_1148_eng.png': '72e0b1c867af3ad82a32b9504452e8edcb791cfbac2477e652bc724ebd449622',
    'mapVS14_3870_551_4512_1148_fre.png': 'c6ae071ae3b328da512ca6c1b389ec374fba5f4219d580c590a6b38801c97bcd',
    'mapVS14_3870_551_4512_1148_ger.png': 'c4452368873cf05d60405b62b893778a9e8ec889f09bda28b0aaff0cc52cfde2',
    'mapVS14_3870_551_4512_1148_kor.png': 'e008974fc2f51454c9f3f28a14dd5e526b9e81f619b3ef05b3dff6c0ce6e9961',
    'mapVS14_3870_551_4512_1148_sim.png': '58698665eb795a84d8fb1f39abc43b82e6c4ab7ca3a2e7d200b5e49b85d5a38e',
    'mapVS14_3870_551_4512_1148_tra.png': 'd8671dcd20f2a9ecfa9e632f10f404faefcefd4d63a64cadaff2c065f3cef90a',
}


def pixel_sha(a):
    a = np.ascontiguousarray(a)
    return hashlib.sha256(('%s:' % (a.shape,)).encode() + a.tobytes()).hexdigest()


def check_crop(name, a):
    want = CROP_SHA.get(name)
    if want is None:
        raise PropsError('%s: no recorded hash for this Collection crop' % name)
    if pixel_sha(a) != want:
        raise PropsError('%s is not the Collection picture the signs were fitted to (pixel hash differs)' % name)
    return a


def cache_dir(dumpdir):
    return os.path.join(dumpdir, *CACHE)


# ---------------------------------------------------------------- windows on the canvases

def hd_window(p, ctx=CTX):
    """Capcom pixel box (canvas coordinates, ints) of picture p's window plus ctx DS pixels."""
    x0, y0, x1, y1 = p['window']
    ox, oy = p['off']
    cv = CANVASES[p['canvas']]
    return (int(np.floor((x0 - ctx + ox) * S)) + cv['crop_x'], int(np.floor((y0 - ctx + oy) * S)),
            int(np.ceil((x1 + ctx + ox) * S)) + cv['crop_x'], int(np.ceil((y1 + ctx + oy) * S)))


def crops_wanted():
    """{(canvas, box)} every crop the build reads: each picture's window and each lettering box."""
    out = {}
    for p in PICTURES:
        if p['mode'] != 'derived':
            out[(p['canvas'], hd_window(p))] = p['name']
    for k, l in LETTERING.items():
        x0, y0, x1, y1 = l['box']
        out[(l['canvas'], (x0 - 32, y0 - 32, x1 + 32, y1 + 32))] = 'lettering_' + k
    return out


def crop_name(canvas, box, lang):
    return '%s_%d_%d_%d_%d%s.png' % ((canvas,) + tuple(box) + (lang,))


def required(dumpdir):
    d = cache_dir(dumpdir)
    return sorted(os.path.join(d, crop_name(cv, box, l)) for (cv, box) in crops_wanted() for l in LANGS)


def _canvas_crop(textures, canvas, box, lang):
    """Cut box out of the canvas built from textures {name: PIL image}; a language a part does not have
    takes the Japanese part (only the half with lettering is localised)."""
    cv = CANVASES[canvas]
    W, H = cv['size']
    x0, y0, x1, y1 = box
    out = Image.new('RGB', (x1 - x0, y1 - y0))
    full = Image.new('RGB', (W, H))
    xs = [px for _b, px in cv['parts']] + [W]
    for k, (base, px) in enumerate(cv['parts']):
        im = textures.get(base + lang) or textures.get(base)
        if im is None:
            raise SystemExit('props: texture %s missing' % base)
        im = im.convert('RGB')
        size = (xs[k + 1] - px, H)
        if im.size != size:
            # some halves (and some languages of a half) ship at 1664x768: scaled to the canvas
            im = im.resize(size, Image.LANCZOS)
        full.paste(im, (px, 0))
    # edge pixels repeat outside the canvas
    a = np.asarray(full)
    ys = np.clip(np.arange(y0, y1), 0, H - 1)
    xs = np.clip(np.arange(x0, x1), 0, W - 1)
    return Image.fromarray(a[ys][:, xs])


def extract(bdir, dumpdir):
    """Save the windows round each sign, every language, from the Collection's bundles as RGB PNGs under
    dump/title/props/. Raises SystemExit if a bundle or a texture is missing."""
    import UnityPy
    want = crops_wanted()
    names = {}
    for canvas, _box in want:
        cv = CANVASES[canvas]
        for base, _x in cv['parts']:
            names.setdefault(cv['family'], set()).update(base + l for l in LANGS)
    textures = {}
    for fam, nm in sorted(names.items()):
        pre = BUNDLES[fam]
        hits = [p for p in glob.glob(os.path.join(bdir, '*.bundle'))
                if os.path.basename(p).lower().startswith(pre)]
        if not hits:
            raise SystemExit('props: no bundle starting with %r in %s' % (pre, bdir))
        env = UnityPy.load(hits[0])
        for obj in env.objects:
            if obj.type.name != 'Texture2D':
                continue
            d = obj.read()
            if d.m_Name in nm:
                textures[d.m_Name] = d.image.copy()
    out = cache_dir(dumpdir)
    os.makedirs(out, exist_ok=True)
    for canvas, box in want:
        cv = CANVASES[canvas]
        for base, _x in cv['parts']:
            if base not in textures:
                raise SystemExit('props: texture %s not found in the %s bundle' % (base, cv['family']))
            if base + '_eng' not in textures and canvas_needs_eng(canvas, base):
                raise SystemExit('props: texture %s_eng not found' % base)
        for l in LANGS:
            _canvas_crop(textures, canvas, box, l).save(os.path.join(out, crop_name(canvas, box, l)))
    return out


def canvas_needs_eng(canvas, base):
    """A part needs its English texture if any window on it reaches into that part."""
    cv = CANVASES[canvas]
    xs = [px for b, px in cv['parts']]
    i = [b for b, px in cv['parts']].index(base)
    lo = xs[i]
    hi = xs[i + 1] if i + 1 < len(xs) else cv['size'][0]
    for (c, box) in crops_wanted():
        if c == canvas and box[0] < hi and box[2] > lo:
            return True
    return False


_TEX = {}


def _texroot_crop(root, canvas, box, lang):
    """Offline experiments only (environment PROPS_TEXROOT = a folder of whole extracted textures,
    <root>/gk2_<family>/<name>.png): the crop cut from the whole texture instead of the cache."""
    cv = CANVASES[canvas]
    tx = {}
    for base, _x in cv['parts']:
        for n in (base + lang, base):
            p = os.path.join(root, 'gk2_' + cv['family'], n + '.png')
            if n not in _TEX and os.path.isfile(p):
                _TEX[n] = Image.open(p).convert('RGB')
            if n in _TEX:
                tx[n] = _TEX[n]
    return _canvas_crop(tx, canvas, box, lang)


def load_stack(dumpdir, canvas, box):
    """(7, h, w, 3) uint8 of the crop in every language (LANGS order)."""
    root = os.environ.get('PROPS_TEXROOT')
    if root:
        return np.stack([check_crop(crop_name(canvas, box, l), np.asarray(_texroot_crop(root, canvas, box, l)))
                         for l in LANGS])
    out = []
    for l in LANGS:
        p = os.path.join(cache_dir(dumpdir), crop_name(canvas, box, l))
        if not os.path.isfile(p):
            raise PropsError('%s is missing; run the build once without --skip-extract' % p)
        out.append(check_crop(crop_name(canvas, box, l), np.asarray(Image.open(p).convert('RGB'))))
    shapes = {a.shape for a in out}
    if len(shapes) != 1:
        raise PropsError('crops of %s %r differ in size' % (canvas, box))
    return np.stack(out)


# ---------------------------------------------------------------- container and pixels

def table(d):
    n = struct.unpack_from('<I', d, 0)[0] // 8
    return [struct.unpack_from('<II', d, i * 8) for i in range(n)]


def extents(t, total):
    live = sorted({o for o, _s in t if o})
    out = {}
    for i, (o, _s) in enumerate(t):
        nxt = [q for q in live if q > o]
        out[i] = (o, nxt[0] if nxt else total)
    return out


def entry_decoded(container, i):
    import lz11
    t = table(container)
    a, b = extents(t, len(container))[i]
    st = bytes(container[a:b])
    s = t[i][1]
    if s & 0x80000000:
        out = lz11.decompress(st)
        if len(out) != (s & 0x7FFFFFFF):
            raise PropsError('entry %d decodes to %d bytes, its table says %d' % (i, len(out), s & 0x7FFFFFFF))
        return out, len(st), True
    return st[:s], len(st), False


def _rgcn(dec):
    """-> (offset of the pixel data, bpp, tiles across, tiles down, data size)."""
    if dec[:4] != b'RGCN':
        raise PropsError('entry is not an RGCN picture')
    p = 16
    if dec[p:p + 4] != b'RAHC':
        raise PropsError('RGCN without RAHC first')
    body = p + 8
    th, tw, fmt = struct.unpack_from('<HHI', dec, body)
    bpp = 8 if fmt == 4 else 4
    dsize, doff = struct.unpack_from('<II', dec, body + 16)
    return body + doff, bpp, tw, th, dsize


def read_grid(dec):
    o, bpp, tw, th, dsize = _rgcn(dec)
    per = 64 if bpp == 8 else 32
    if dsize < tw * th * per:
        raise PropsError('RGCN holds %d bytes, %dx%d tiles need %d' % (dsize, tw, th, tw * th * per))
    raw = np.frombuffer(dec[o:o + tw * th * per], np.uint8)
    if bpp == 4:
        raw = np.stack([raw & 15, raw >> 4], 1).reshape(-1)
    t = raw.reshape(th, tw, 8, 8)
    return t.transpose(0, 2, 1, 3).reshape(th * 8, tw * 8).copy(), bpp


def write_grid(dec, g):
    o, bpp, tw, th, dsize = _rgcn(dec)
    per = 64 if bpp == 8 else 32
    g = np.asarray(g, np.uint8)
    if g.shape != (th * 8, tw * 8):
        raise PropsError('grid %r does not match %dx%d tiles' % (g.shape, tw, th))
    if bpp == 4 and g.max() > 15:
        raise PropsError('index above 15 in a 4bpp picture')
    t = g.reshape(th, 8, tw, 8).transpose(0, 2, 1, 3).reshape(-1)
    if bpp == 4:
        t = (t[0::2] | (t[1::2] << 4)).astype(np.uint8)
    out = bytearray(dec)
    out[o:o + tw * th * per] = t.tobytes()
    return bytes(out)


# ---------------------------------------------------------------- the lettering

def lettering_alpha(dumpdir, key):
    """Capcom's English lettering of LETTERING[key] as ink coverage (0..1) over its crop, the crop's box."""
    L = LETTERING[key]
    x0, y0, x1, y1 = L['box']
    box = (x0 - 32, y0 - 32, x1 + 32, y1 + 32)
    V = load_stack(dumpdir, L['canvas'], box)
    let = pc.lettering_masks(V, L.get('ink', 'dark'), L.get('median', False))
    bg, _stage = pc.background(V, let, halo=4)
    Lb = bg.astype(np.float64).mean(-1)
    Le = V[LANGS.index('_eng')].astype(np.float64).mean(-1)
    face = np.zeros(Lb.shape, bool)
    face[32:32 + (y1 - y0), 32:32 + (x1 - x0)] = True
    if L.get('ink', 'dark') == 'dark':
        lo = np.percentile(Le[face], 1)
        a = np.clip((Lb - Le - 6) / np.maximum(Lb - lo - 6, 1), 0, 1) * face
    else:
        hi = np.percentile(Le[face], 99)
        a = np.clip((Le - Lb - 6) / np.maximum(hi - Lb - 6, 1), 0, 1) * face
    a = np.clip((a - 0.08) / 0.5, 0, 1)          # even out ink a glass glare lightens
    # the words must be where the table says: ink inside each range, none in the gaps
    # (a word given as (x0, x1, y0, y1) is a box of its own line: y0 its cap line, y1 below its baseline;
    # the box must hold ink and its edges must be clear of it)
    col = (a > 0.3).any(0)
    # the English picture must differ from the Japanese one in every word (a Japanese plate whose own
    # characters stand where the English words stand would otherwise pass as English lettering)
    Lj = V[LANGS.index('')].astype(np.float64).mean(-1)
    for i, w in enumerate(L['words']):
        wa, wb = w[:2]
        ya, yb = (w[2], w[3]) if len(w) == 4 else (y0, y1)
        sl = (slice(ya - box[1], yb - box[1]), slice(wa - box[0], wb - box[0]))
        if (np.abs(Le[sl] - Lj[sl]) > 24).mean() < 0.04:
            raise PropsError('lettering %s: word %d %r is the same in the English and Japanese pictures' % (key, i, w))
    for i, w in enumerate(L['words']):
        wa, wb = w[:2]
        if len(w) == 4:
            sub = a[w[2] - box[1]:w[3] - box[1], wa - box[0]:wb - box[0]] > 0.3
            if not sub.any():
                raise PropsError('lettering %s: no ink in word %d %r' % (key, i, w))
            if sub[:, 0].any() or sub[:, -1].any():
                raise PropsError('lettering %s: word %d %r is cut by its box' % (key, i, w))
        elif not col[wa - box[0]:wb - box[0]].any():
            raise PropsError('lettering %s: no ink in word %d (%d-%d)' % (key, i, wa, wb))
    plain = [w for w in L['words'] if len(w) == 2]
    for (pa, pb), (qa, qb) in zip(plain[:-1], plain[1:]):
        if col[pb - box[0] + 1:qa - box[0] - 1].any():
            raise PropsError('lettering %s: ink between words at %d-%d' % (key, pb, qa))
    return a, box


def _word(a, lbox, w, cap_top):
    """Coverage strip of one word over the whole crop height, its cap line on row cap_top - lbox[1]."""
    wa, wb = w[:2]
    if len(w) == 2:
        return a[:, wa - lbox[0]:wb - lbox[0]]
    piece = np.zeros((a.shape[0], wb - wa))
    r0 = int(cap_top - lbox[1])
    h = w[3] - w[2]
    piece[r0:r0 + h] = a[w[2] - lbox[1]:w[3] - lbox[1], wa - lbox[0]:wb - lbox[0]]
    return piece


def relaid_alpha(dumpdir, p, shape_hd, box_hd):
    """Ink coverage on picture p's canvas crop box_hd (Capcom pixels) with the words set as p['lines']."""
    a, lbox = lettering_alpha(dumpdir, p['lettering'])
    L = LETTERING[p['lettering']]
    cap_top, base = L['cap']
    s = float(p['scale'])
    k = S / s                                   # enlargement of the lettering on the canvas
    gap = L.get('gap', 14)
    out = np.zeros(shape_hd)
    ox, oy = p['off']
    for words, cap_row, xc in p['lines']:
        strips = []
        for j, wi in enumerate(words):
            if j:
                strips.append(np.zeros((a.shape[0], gap)))
            strips.append(_word(a, lbox, L['words'][wi], cap_top))
        strip = np.hstack(strips)
        w = strip.shape[1]
        nw, nh = int(round(w * k)), int(round(strip.shape[0] * k))
        big = np.asarray(Image.fromarray(strip.astype(np.float32), mode='F').resize((nw, nh), Image.BICUBIC), np.float64)
        big = np.clip(big, 0, 1)
        # cap line of the strip lands on DS row cap_row; centred on DS x xc (frontal lettering space)
        top = (cap_row + oy) * S - (cap_top - lbox[1]) * k
        left = (xc + ox) * S - nw / 2.0
        fx, fy = int(round(left)), int(round(top))
        if p['H'] is None:
            X0, Y0 = fx - box_hd[0], fy - box_hd[1]
            ys0, xs0 = max(0, Y0), max(0, X0)
            ys1, xs1 = min(shape_hd[0], Y0 + nh), min(shape_hd[1], X0 + nw)
            out[ys0:ys1, xs0:xs1] = np.maximum(out[ys0:ys1, xs0:xs1], big[ys0 - Y0:ys1 - Y0, xs0 - X0:xs1 - X0])
        else:
            out = np.maximum(out, _warp(big, fx, fy, p['H'], shape_hd, box_hd))
    return out


def _warp(img, fx, fy, H, shape_hd, box_hd):
    """Paste img (top-left at canvas fx, fy of the lettering's canvas) through the perspective map H
    (lettering canvas -> picture canvas) into the picture crop box_hd."""
    Hm = np.array(H, np.float64).reshape(3, 3)
    T = np.array([[1, 0, fx], [0, 1, fy], [0, 0, 1]], np.float64)
    C = np.array([[1, 0, -box_hd[0]], [0, 1, -box_hd[1]], [0, 0, 1]], np.float64)
    M = C @ Hm @ T                              # img pixel -> crop pixel
    Minv = np.linalg.inv(M)
    Minv = Minv / Minv[2, 2]
    coeffs = tuple(Minv.reshape(-1)[:8])
    im = Image.fromarray(img.astype(np.float32), mode='F')
    w = im.transform((shape_hd[1], shape_hd[0]), Image.PERSPECTIVE, coeffs, Image.BICUBIC)
    return np.clip(np.asarray(w, np.float64), 0, 1)


# ---------------------------------------------------------------- one picture

def _source_grid(src, dumpdir, originals):
    """The fan's grid and palette of picture src, from originals[cont] (the container before this build
    step changed it) or the fan's file in the dump. Raises unless it is the fan's picture."""
    from nitro import nclr
    data = (originals or {}).get(src['cont'])
    if data is None:
        with open(os.path.join(dumpdir, 'ds_fan', *src['cont'].split('/')), 'rb') as f:
            data = f.read()
    dec = entry_decoded(data, src['entry'])[0]
    pdec = entry_decoded(data, src['pal'])[0]
    want = FAN_SHA.get((src['cont'], src['entry']))
    if want is None or hashlib.sha256(dec).hexdigest() != want[0] or hashlib.sha256(pdec).hexdigest() != want[1]:
        raise PropsError('%s entry %d (source of a derived picture) is not the fan\'s' % (src['cont'], src['entry']))
    return read_grid(dec)[0], nclr(pdec)


def derived(p, g, pal, dumpdir, info=None, originals=None):
    """A picture that is a recoloured crop of another (a Logic backdrop of a room): the source picture is
    redrawn, and every pixel the redraw changed inside p's face takes the index this picture uses for that
    source index elsewhere (majority over the pixels the redraw left alone). p['off'] = (dx, dy): this
    picture's pixel (x, y) is the source's (x + dx, y + dy)."""
    src = [q for q in PICTURES if q['name'] == p['source']][0]
    gs, pal_s = _source_grid(src, dumpdir, originals)
    sinfo = {}
    ns = redraw(src, gs, pal_s, dumpdir, sinfo, originals)
    dx, dy = int(p['off'][0]), int(p['off'][1])
    H, W = g.shape
    S_ = gs[dy:dy + H, dx:dx + W]
    N_ = ns[dy:dy + H, dx:dx + W]
    if S_.shape != g.shape:
        raise PropsError('%s: the source picture does not cover this one at offset %r' % (p['name'], p['off']))
    face = pc.polygon_mask(g.shape, p['face'])
    ch = (N_ != S_) & face
    keep = ~pc.dilate(N_ != S_, 1)
    # the mapping must hold: the fan's own picture is the recoloured source on the pixels left alone
    m = {}
    a, b = S_[keep].ravel(), g[keep].ravel()
    pairs = np.zeros((256, 256), np.int64)
    np.add.at(pairs, (a, b), 1)
    agree = pairs.max(1).sum() / max(1, keep.sum())
    if agree < p.get('min_agree', 0.7):
        raise PropsError('%s: only %.2f of the pixels follow one mapping from the source' % (p['name'], agree))
    seen = pairs.sum(1) > 0
    Ps = np.array(list(pal_s) + [(0, 0, 0)] * (256 - len(pal_s)), np.float64)
    out = g.copy()
    for y, x in zip(*np.nonzero(ch)):
        v = int(N_[y, x])
        if not seen[v]:
            # an index the source never shows here: the seen source index of the nearest colour
            cand = np.nonzero(seen)[0]
            v = int(cand[((Ps[cand] - Ps[v]) ** 2).sum(1).argmin()])
        out[y, x] = int(pairs[v].argmax())
    if info is not None:
        info.update(core=sinfo['core'][dy:dy + H, dx:dx + W] & face, targets=ch, lone=0, reg=dict(err=round(1 - agree, 3), shifts={}), filled=int(ch.sum()),
                    lettered=0, hidden_hd=0, grown_hd=0, changed=int((out != g).sum()), agree=round(float(agree), 3))
    return out


def redraw(p, g, pal, dumpdir, info=None, originals=None):
    """g: the fan's index grid of the picture, pal its colours. -> new grid."""
    if p['mode'] == 'derived':
        return derived(p, g, pal, dumpdir, info, originals)
    box = hd_window(p)
    V = load_stack(dumpdir, p['canvas'], box)
    x0, y0, x1, y1 = p['window']
    size = (x1 - x0 + 2 * CTX, y1 - y0 + 2 * CTX)
    ox, oy = p['off']
    cv = CANVASES[p['canvas']]
    # the crop starts at floor((x0 - CTX + ox) * S); the exact DS grid starts at (x0 - CTX + ox) * S
    exact = ((x0 - CTX + ox) * S + cv['crop_x'] - box[0], (y0 - CTX + oy) * S - box[1])
    hd_box = (exact[0], exact[1], exact[0] + size[0] * S, exact[1] + size[1] * S)
    let = pc.lettering_masks(V, p.get('ink', 'dark'), p.get('median', False))
    bg, stage = pc.background(V, let, halo=p.get('halo', 4))
    D_bg = pc.downscale(bg, hd_box, size)
    D_eng = pc.downscale(V[LANGS.index('_eng')], hd_box, size)
    P = np.array(list(pal) + [(255, 0, 255)] * (256 - len(pal)), np.float64)
    # DS window with context; pixels outside the picture are left out of every test
    H, W = g.shape
    gy0, gx0 = y0 - CTX, x0 - CTX
    inside = np.zeros((size[1], size[0]), bool)
    ys, xs = np.mgrid[gy0:gy0 + size[1], gx0:gx0 + size[0]]
    inside = (ys >= 0) & (ys < H) & (xs >= 0) & (xs < W)
    gw = np.zeros((size[1], size[0]), np.int64)
    gw[inside] = g[ys[inside], xs[inside]]
    ds = P[gw]
    face = pc.polygon_mask(g.shape, p['face'])
    fw = np.zeros_like(inside)
    fw[inside] = face[ys[inside], xs[inside]]
    # calibration: the whole window round the sign (less two pixels round the face)
    ring = inside & ~pc.dilate(fw, 2)
    for poly in p.get('cal_exclude', ()):
        ex = pc.polygon_mask(g.shape, poly)
        ring[inside] &= ~ex[ys[inside], xs[inside]]
    # (a 'native' picture is proved with Capcom's English picture, whose lettering stands where the DS
    # lettering that stays stands; a 'relaid' one with the picture without lettering)
    reg = pc.register_check(D_eng if p['mode'] == 'native' else D_bg, ds, ring, p['max_err'], what=p['name'])
    fitted_bg, _e = pc.fit_linear(D_bg, ds, ring)
    fitted_eng, _e = pc.fit_linear(D_eng, ds, ring)
    if p['mode'] == 'native':
        ref = fitted_eng
        Dsrc = D_eng
    else:
        ref = fitted_bg
        Dsrc = D_bg
    diff = np.abs(ref - ds).max(-1)
    targets = pc.dilate((diff > p['thr']) & fw, 1) & fw
    # examples: pixels of the window (outside the targets) whose colour agrees with Capcom's
    tol = p.get('agree', p['thr'] * 0.5)
    agree = (np.abs(fitted_bg - ds).max(-1) < tol) & inside & ~targets
    if p.get('face_examples'):
        # a sign whose face is covered in lettering: the face pixels between the fan's letters (not the
        # one-pixel ring round them) are examples too, or the face colour has no example at all
        agree |= (np.abs(fitted_bg - ds).max(-1) < tol) & inside & fw & ~((diff > p['thr']) & fw)
    if p.get('face_palette'):
        # a sign with colours of its own (a cloth banner over a busy stand): only the sign's own pixels
        # are examples, and a colour with no close example takes one of the sign's own colours, so the
        # stand's colours (the teal of a screen, the yellow of a lamp) do not turn up on the cloth
        agree &= fw
    nearest = p.get('fill') == 'nearest'
    if p.get('fill') not in (None, 'nearest'):
        raise PropsError('%s: unknown fill %r' % (p['name'], p['fill']))
    new = gw.copy() if nearest else pc.vote(Dsrc, gw, targets, agree)
    # a Capcom colour with no close example near the sign (lettering the fan's picture has nowhere else)
    # takes the nearest palette colour of its fitted value, among the colours the window already uses
    # (with fill='nearest', every changed pixel does)
    fsrc = fitted_eng if p['mode'] == 'native' else fitted_bg
    ex = Dsrc[agree]
    used = sorted(set(gw[fw if p.get('face_palette') else inside].tolist()))
    lone = 0
    for y, x in zip(*np.nonzero(targets)):
        if nearest or ((ex - Dsrc[y, x]) ** 2).sum(1).min() > p.get('lone', 30.0) ** 2:
            new[y, x] = int(pc.nearest_index(fsrc[y, x][None], P, used)[0])
            lone += 1
    if p.get('row_fill'):
        # a plate whose face is flat along each row, drawn wider than Capcom's plate (the fan's door
        # plate): Capcom's plate edge stands at other columns than the fan's, so each filled pixel takes the
        # commonest colour of its row over the plate's inner columns instead (no stripe inside the plate)
        xa, xb = p['row_fill']
        cols = slice(xa - gx0, xb - gx0 + 1)
        for r in np.nonzero((targets & fw).any(1))[0]:
            vals = new[r, cols][fw[r, cols]]
            if not len(vals):
                raise PropsError('%s: row %d has no inner face column' % (p['name'], r + gy0))
            v, c = np.unique(vals, return_counts=True)
            new[r, targets[r] & fw[r]] = int(v[c.argmax()])
    n_fill = int(targets.sum())
    n_let = 0
    if p['mode'] == 'relaid':
        A_hd = relaid_alpha(dumpdir, p, bg.shape[:2], box)
        A = np.clip(pc.downscale(A_hd, hd_box, size), 0, 1) ** p.get('gamma', 1.0) * fw
        # the fan's lettering colour: of the colours on the face, the one furthest from the face colour
        Lface = np.median(P[gw[fw & ~targets]].mean(-1)) if (fw & ~targets).any() else np.median(P[gw[fw]].mean(-1))
        # (the commonest of the colours in the strongest fifth of its contrast, so a stray darker
        # shade of the frame does not win)
        tl = gw[fw & targets]
        Lt = P[tl].mean(-1)
        sign = -1.0 if np.median(Lt) < Lface else 1.0      # dark lettering on a light face, or the reverse
        far = (Lt - Lface) * sign
        strong = tl[far >= 0.8 * far.max()]
        vals, cnts = np.unique(strong, return_counts=True)
        ink = int(vals[cnts.argmax()])
        comp = P[new] * (1 - A[..., None]) + P[ink] * A[..., None]
        m = A > p.get('ink_min', 0.06)
        # a lettered pixel takes the nearest of the colours the fan's own lettering used, or keeps the
        # face colour under it if that is nearer
        text_cols = sorted(set(gw[fw & (diff > p['thr'])].tolist()) | {ink})
        cand = pc.nearest_index(comp[m], P, text_cols)
        wgt = np.array([3.0, 4.0, 2.0])
        d_text = (((P[cand] - comp[m]) * wgt) ** 2).sum(-1)
        d_face = (((P[new[m]] - comp[m]) * wgt) ** 2).sum(-1)
        new[m] = np.where(d_text < d_face, cand, new[m])
        n_let = int(m.sum())
    out = g.copy()
    out[ys[inside], xs[inside]] = new[inside]
    # the fan's lettering, in picture coordinates (for tools/props_detect.py): face pixels whose colour
    # is not Capcom's (the picture without lettering, or Capcom's English picture for 'native')
    core = np.zeros(g.shape, bool)
    core[ys[inside], xs[inside]] = ((diff > p['thr']) & fw)[inside]
    if info is not None:
        info.update(core=core, targets=targets, lone=lone, reg=reg, filled=n_fill, lettered=n_let, hidden_hd=int((stage > 0).sum()),
                    grown_hd=int((stage == 2).sum()), changed=int((out != g).sum()))
    return out


# ---------------------------------------------------------------- containers

def patch_container(cont, data, dumpdir, log=None, infos=None, originals=None):
    """-> new bytes of one container with every PICTURES entry of it redrawn, written in place."""
    import lz11
    from nitro import nclr
    log = log or (lambda s: None)
    t = table(data)
    ext = extents(t, len(data))
    out = bytearray(data)
    entries = []
    for q in PICTURES:
        if q['cont'] == cont and q['entry'] not in entries:
            entries.append(q['entry'])
    for e in entries:
        group = [q for q in PICTURES if q['cont'] == cont and q['entry'] == e]
        p = group[0]
        dec, stored, comp = entry_decoded(data, e)
        pdec, _ps, _pc = entry_decoded(data, p['pal'])
        want = FAN_SHA.get((cont, e))
        if want is None:
            raise PropsError('%s entry %d has no fan checksum in FAN_SHA' % (cont, e))
        if hashlib.sha256(dec).hexdigest() != want[0]:
            raise PropsError('%s entry %d is not the fan\'s picture' % (cont, e))
        if hashlib.sha256(pdec).hexdigest() != want[1]:
            raise PropsError('%s entry %d is not the fan\'s palette' % (cont, p['pal']))
        if not comp:
            raise PropsError('%s entry %d is expected to be an LZ11 stream' % (cont, e))
        g, bpp = read_grid(dec)
        pal = nclr(pdec)
        # several signs in one picture are redrawn one after the other, each on the fan's pixels of its
        # own window (their windows do not overlap)
        g2 = g.copy()
        info = dict(changed=0, reg=dict(err=0.0))
        names = []
        for q in group:
            qi = {}
            gq = redraw(q, g, pal, dumpdir, qi, originals)
            m = gq != g
            if (g2[m] != g[m]).any():
                raise PropsError('%s: two signs change the same pixels' % q['name'])
            g2[m] = gq[m]
            info['changed'] += int(m.sum())
            info['reg']['err'] = max(info['reg']['err'], qi['reg']['err'])
            names.append(q['name'])
            if infos is not None:
                infos[q['name']] = qi
        new = write_grid(dec, g2)
        if len(new) != len(dec):
            raise PropsError('entry changed size')
        st = lz11.compress(new)
        if lz11.decompress(st) != new:
            raise PropsError('%s entry %d does not round-trip through LZ11' % (cont, e))
        a, b = ext[e]
        if len(st) > b - a:
            raise PropsError('%s entry %d would be stored in %d bytes, the fan\'s is %d; it must not be larger'
                             % (cont, e, len(st), b - a))
        out[a:b] = st + b'\0' * (b - a - len(st))
        info.update(stored=len(st), fan_stored=b - a, decoded=len(new))
        log('sign %s (%s %d): %d pixels changed, registration error %.2f, stored %d of the fan\'s %d'
            % (' + '.join(names), cont, e, info['changed'], info['reg']['err'], len(st), b - a))
    if len(out) != len(data):
        raise PropsError('container changed size')
    return bytes(out)


def containers():
    return sorted({p['cont'] for p in PICTURES})


def apply_to_rom(rom, dumpdir, log=None, any_rom=False):
    import title_logo
    from choice_strips import rom_file
    log = log or (lambda s: None)
    originals = {cont: rom_file(rom, cont) for cont in containers()}
    for cont in containers():
        cur = originals[cont]
        try:
            new = patch_container(cont, cur, dumpdir, log, originals=originals)
        except PropsError as ex:
            if not any_rom:
                raise
            log('signs in %s: NOT redrawn, --any-rom given (%s)' % (cont, ex))
            continue
        rom = title_logo.splice(rom, cont, new)
    return rom, True


if __name__ == '__main__':
    if len(sys.argv) != 4:
        raise SystemExit('usage: props.py FAN_DIR DUMPDIR OUTDIR')
    src, dump, outdir = sys.argv[1:4]
    for cont in containers():
        data = open(os.path.join(src, cont), 'rb').read()
        new = patch_container(cont, data, dump, print)
        os.makedirs(os.path.dirname(os.path.join(outdir, cont)), exist_ok=True)
        open(os.path.join(outdir, cont), 'wb').write(new)
