# -*- coding: utf-8 -*-
"""Detector: raises if the fan's old wording is still in a picture tools/props.py or tools/props_bust.py
redrew. It never calls the redraw (props.redraw, props_bust) nor takes a mask from it. For the circus
banner it borrows from tools/props.py only the geometry and the reference picture: props.PICTURES (the
window a crop was cut for), props.hd_window and props.load_stack, which reads the Collection crop and
refuses it unless its pixels match the recorded sha256. That is safe: those give Capcom's own English
picture, fixed and hash-checked, never the ROM under test, and a crop shifted or swapped is refused before
any mask is made (round-3 refuter: 6 and 17 px shifts and the German crops raise).

The fan's lettering is located from the fan's and the retail Japanese ROM's own pictures (dump/ds_fan and
dump/ds_jp) inside a box per sign written down here: the pixels where the fan's picture differs from the
retail one (the fan's relettering) and stands out from the sign's face (more than CONTRAST from the box's
commonest colour, so a repainted face does not count as lettering). The circus banner is retail art (the
retail picture already says ANIMAL SHOW), so there the lettering is the pixels inside a tight box round
ANIMAL that stand out from the banner face (luminance, rows averaged in pairs so the scan lines of the
green variant drop out), less the pixels where Capcom's English picture (CIRCUS, from the hash-guarded
Collection crop, fitted to the fan's colours round the box) already matches the fan's ANIMAL: those cannot
tell the two words apart, and left in they let a letter of ANIMAL hide among them. For the nurse's sprites
the boxes are cap rectangles per group of cells; the lettering is the dark or red pixels held between
light band pixels (within 3, above and below or left and right) that differ from the retail sprite, counted
as the tile bytes that draw them. Her icons are scored twice: the red 1st!, and the dark Safety (which
shares most strokes with Capcom's SAFETY at the same place, so its build score is about a half).

A picture whose lettering mask has fewer than MIN_MASK pixels cannot be judged and fails. Two rules, a
sign is flagged if either trips:
- the score: the share of mask pixels the built picture still shows as the fan's (exact index; on the
  circus banner, row-paired luminance within 8) must not pass the sign's LIMITS entry, the build's own
  score (aa505492) plus half of one mask pixel. On the non-circus signs any old pixel the build changed that
  comes back raises the score by a whole pixel and flags.
- on the circus banner the row pairing can hide a single restored row or pixel (its partner row still
  differs), so a second, unpaired rule: the count of mask pixels whose index equals the fan's exactly must
  not pass EXACT, this build's own count. Any old pixel the build changed that comes back adds one.
test_props.py restores the fan's pixels over every band, every 1-, 2- and 3-row strip and every single
changed pixel of every old word and checks each one is flagged. The control
that must fail: the same check on the fan's own containers (the base ROM) flags every sign
(test_props.py runs it); the built ROM must pass.

    python tools/props_detect.py BUILT.nds [DUMPDIR]
"""
import os, sys, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import props
from nitro import nclr

# per sign: the share of the old lettering the build may keep: the build's own score (aa505492) plus half
# a mask pixel, rounded up to 1e-4. On the non-circus signs one changed old pixel back flags through this
# alone; on the circus signs the row-paired score can absorb a single row or pixel, which EXACT catches.
# A change to the redraw that moves a score needs these set again from the new build (and the plants in
# test_props.py rerun).
LIMITS = {
    'motto_mapbg10': 0.1306,
    'motto_logicbg14': 0.0848,
    'motto_upcut388': 0.0241,
    'maxsec_mapbg20': 0.0532,
    'maxsec_mapbg22': 0.1154,
    'maxsec_upcut392': 0.0306,
    'circus_mapbg30': 0.2254,
    'circus_logicbg34': 0.3276,
    'circus_upcutlocal42': 0.1544,
    'cotton_mapbg54': 0.0260,
    'cotton_mapbg56': 0.1290,
    'cotton_mapbg60': 0.0990,
    'cotton_upcut406': 0.0831,
    'cotton_upcutlocal206': 0.0360,
    'cotton_upcutlocal234': 0.0824,
    'permit_upcut408': 0.1084,
    'plaque_upcut400': 0.0040,
    'plaque_upcut128': 0.0615,
    'nurse_bustup252': 0.0334,
    'nurse_bustup253': 0.0215,
    'nurse_bustup254': 0.0247,
    'nurse_bustup255': 0.1446,
    'nurse_bustup264': 0.0711,
    'nurse_idcom951_red': 0.0074,
    'nurse_idcom951_dark': 0.3978,
    'nurse_idcom953_red': 0.0167,
    'nurse_idcom953_dark': 0.6750,
}
# below this many old-lettering pixels a sign cannot be judged (the check is <). The smallest mask is the
# 40-pixel icon's dark Safety, exactly 20 pixels, 13 of them the same as Capcom's SAFETY: its 7 changed
# pixels decide, and with the half-pixel limit any one of them coming back is flagged. The masks come from
# the fan's and the retail containers only (and for the circus, the hash-checked Capcom crop), so they
# cannot shrink between builds.
MIN_MASK = 20
# circus signs: mask pixels whose index is exactly the fan's in this build (aa505492); one more flags
EXACT = {
    'circus_mapbg30': 59,
    'circus_logicbg34': 95,
    'circus_upcutlocal42': 189,
}
CONTRAST = 40.0

# name -> (container, entry, palette entry, boxes (x0, y0, x1, y1), mode): 'retail' = differs from the retail
# picture and stands out from the face; 'face' = stands out from the face (retail art)
SIGNS = {
    'motto_mapbg10': ('com/mapbg.bin', 10, 11, [(159, 15, 214, 31)], 'retail'),
    'motto_logicbg14': ('com/logicbg.bin', 14, 15, [(0, 13, 48, 32)], 'retail'),
    'motto_upcut388': ('com/upcut.bin', 388, 389, [(108, 0, 250, 24)], 'retail'),
    'maxsec_mapbg20': ('com/mapbg.bin', 20, 21, [(317, 87, 339, 99)], 'retail'),
    'maxsec_mapbg22': ('com/mapbg.bin', 22, 23, [(317, 87, 339, 99)], 'retail'),
    'maxsec_upcut392': ('com/upcut.bin', 392, 393, [(802, 78, 832, 112)], 'retail'),
    'circus_mapbg30': ('com/mapbg.bin', 30, 31, [(314, 93, 394, 127)], 'face'),
    'circus_logicbg34': ('com/logicbg.bin', 34, 35, [(42, 93, 122, 127)], 'face'),
    'circus_upcutlocal42': ('jpn/upcut_local.bin', 42, 43, [(106, 24, 136, 94)], 'face'),
    'cotton_mapbg54': ('com/mapbg.bin', 54, 55, [(448, 90, 480, 166)], 'retail'),
    'cotton_mapbg56': ('com/mapbg.bin', 56, 57, [(448, 90, 480, 166)], 'retail'),
    'cotton_mapbg60': ('com/mapbg.bin', 60, 61, [(0, 48, 12, 110), (500, 48, 512, 110)], 'retail'),
    'cotton_upcut406': ('com/upcut.bin', 406, 407, [(745, 10, 830, 190)], 'retail'),
    'cotton_upcutlocal206': ('jpn/upcut_local.bin', 206, 207, [(234, 0, 256, 192)], 'retail'),
    'cotton_upcutlocal234': ('jpn/upcut_local.bin', 234, 235, [(246, 58, 256, 112)], 'retail'),
    'permit_upcut408': ('com/upcut.bin', 408, 409, [(722, 128, 772, 190)], 'retail'),
    'plaque_upcut400': ('com/upcut.bin', 400, 401, [(470, 165, 565, 192)], 'retail'),
    'plaque_upcut128': ('com/upcut.bin', 128, 129, [(345, 125, 430, 180)], 'retail'),
}

# the nurse's sprites: entry -> palette entry, [(cells, cap box in frame pixels from the OAM bounds)]
NURSE = {
    252: (251, [(range(0, 110), (66, 0, 154, 56))]),
    253: (251, [(range(0, 52), (68, 0, 152, 58))]),
    254: (251, [(range(0, 8), (90, 0, 176, 59))]),
    255: (251, [(range(0, 9), (122, 0, 194, 56)), ((9,), (150, 9, 209, 58)), ((10,), (158, 17, 217, 66)),
                ((11, 15), (166, 33, 225, 82)), ((12,), (182, 73, 241, 122)), ((13,), (198, 153, 256, 202))]),
    264: (263, [(range(0, 17), (24, 0, 114, 57))]),
}
# the portrait icons: entry -> (palette entry, cap box)
ICONS = {951: (950, (0, 0, 64, 26)), 953: (952, (0, 0, 40, 17))}


class DetectError(RuntimeError):
    pass


def _boxmask(shape, boxes):
    m = np.zeros(shape, bool)
    for x0, y0, x1, y1 in boxes:
        m[max(0, y0):y1, max(0, x0):x1] = True
    return m


def _stands_out(rgb, inbox):
    """pixels of the box more than CONTRAST from the box's commonest colour (the face)."""
    q = rgb[inbox].astype(np.int64)
    keys, counts = np.unique(q[:, 0] * 65536 + q[:, 1] * 256 + q[:, 2], return_counts=True)
    k = keys[counts.argmax()]
    face = np.array([k // 65536, (k // 256) % 256, k % 256], np.float64)
    return (np.abs(rgb.astype(np.float64) - face).max(-1) > CONTRAST) & inbox


def _pair_rows(a):
    b = a.copy()
    b[:-1] = (a[:-1] + a[1:]) / 2
    return b


# the circus banner is retail art: the fixed reference that says which of ANIMAL's pixels CIRCUS already
# covers is Capcom's English picture (the hash-guarded Collection crop, props.load_stack), never the ROM
# under test. face sign -> (props picture whose window and crop it uses, x offset of this picture in it)
CIRCUS_REF = {
    'circus_mapbg30': ('circus_mapbg30', 0),
    'circus_logicbg34': ('circus_mapbg30', 272),
    'circus_upcutlocal42': ('circus_upcutlocal42', 0),
}


def _capcom_rgb(name, shape, dumpdir):
    """Capcom's English picture, area-averaged onto this picture's DS grid over the reference window
    (NaN elsewhere). The geometry is the crop window's (props.PICTURES / props.hd_window)."""
    import props_core as pc
    pname, dx = CIRCUS_REF[name]
    p = [q for q in props.PICTURES if q['name'] == pname][0]
    box = props.hd_window(p)
    V = props.load_stack(dumpdir, p['canvas'], box)            # raises unless the crops' pixel hashes match
    x0, y0, x1, y1 = p['window']
    C, S = props.CTX, props.S
    ox, oy = p['off']
    cv = props.CANVASES[p['canvas']]
    size = (x1 - x0 + 2 * C, y1 - y0 + 2 * C)
    ex = ((x0 - C + ox) * S + cv['crop_x'] - box[0], (y0 - C + oy) * S - box[1])
    D = pc.downscale(V[props.LANGS.index('_eng')], (ex[0], ex[1], ex[0] + size[0] * S, ex[1] + size[1] * S), size)
    out = np.full(shape + (3,), np.nan)
    gy0, gx0 = y0 - C, x0 - C - dx
    for yy in range(size[1]):
        for xx in range(size[0]):
            Y, X = gy0 + yy, gx0 + xx
            if 0 <= Y < shape[0] and 0 <= X < shape[1]:
                out[Y, X] = D[yy, xx]
    return out


def sign_mask(name, fan_c, jp_c, dumpdir):
    cont, e, pe, boxes, mode = SIGNS[name]
    g = props.read_grid(props.entry_decoded(fan_c, e)[0])[0]
    pal = np.array(nclr(props.entry_decoded(fan_c, pe)[0]) + [(0, 0, 0)] * 256, np.float64)[:256]
    inbox = _boxmask(g.shape, boxes)
    if mode == 'face':
        import props_core as pc
        lum = _pair_rows(pal[g].mean(-1))
        m = inbox & (np.abs(lum - np.median(lum[inbox])) > 25)
        cap = _capcom_rgb(name, g.shape, dumpdir)
        valid = ~np.isnan(cap[..., 0])
        fit, _err = pc.fit_linear(np.nan_to_num(cap), pal[g], valid & ~inbox)
        # tolerance 8 is below the fit's own mean error (8.65 / 13.80 / 13.47 on the three circus pictures),
        # on purpose: a wider one drops more pixels (mapbg30: 191 / 263 / 312 dropped at 6 / 8 / 10) and
        # there is no plateau to choose. Dropping too few only keeps pixels where CIRCUS and ANIMAL agree,
        # which the build keeps and the limits absorb; a misaligned fit only drops fewer. Of the pixels
        # dropped at 8, the build changed the index of 68 / 56 / 46. One of those restored alone is NOT
        # flagged: its row-paired luminance already matches Capcom's picture there, so it shows no old
        # letter. Restoring all of them, or any whole row of the undropped mask, is flagged.
        same = valid & (np.abs(_pair_rows(fit.mean(-1)) - lum) < 8)
        return g, m & ~same
    m = _stands_out(pal[g], inbox)
    if mode == 'retail':
        r = props.read_grid(props.entry_decoded(jp_c, e)[0])[0]
        if r.shape != g.shape:
            raise DetectError('%s: the retail picture has another size' % name)
        m &= g != r
    return g, m


def kept_mask(name, g, n, new_c):
    """per pixel: the built picture n still shows the fan's g there (face signs: row-paired luminance within 8)."""
    if SIGNS[name][4] == 'face':
        pal = np.array(nclr(props.entry_decoded(new_c, SIGNS[name][2])[0]) + [(0, 0, 0)] * 256, np.float64)[:256]
        return np.abs(_pair_rows(pal[n].mean(-1)) - _pair_rows(pal[g].mean(-1))) < 8
    return n == g


_CACHE = {}


def _cached(key, fn):
    """memo for the test plants, which judge thousands of edits of the same pictures (keyed by content)."""
    if key not in _CACHE:
        _CACHE[key] = fn()
    return _CACHE[key]


def _h(b):
    import hashlib
    return hashlib.sha1(b).hexdigest()


def check_sign(name, fan_c, jp_c, new_c, dumpdir, edit=None):
    """-> (share of the fan-lettering pixels the built picture still has, mask size, exact count: mask pixels
    whose index is the fan's, or None off the circus). edit (tests): a function (fan grid, built grid) ->
    built grid, applied to the decoded built picture before scoring."""
    g, m = _cached(('mask', name, _h(fan_c), _h(jp_c), dumpdir), lambda: sign_mask(name, fan_c, jp_c, dumpdir))
    if m.sum() < MIN_MASK:
        raise DetectError('%s: only %d pixels of fan lettering found; the detector cannot judge' % (name, m.sum()))
    hn = _h(new_c)
    n = _cached(('grid', name, hn), lambda: props.read_grid(props.entry_decoded(new_c, SIGNS[name][1])[0])[0])
    if edit is not None:
        n = edit(g, n)
    if SIGNS[name][4] == 'face':
        pal = _cached(('pal', name, hn), lambda: np.array(
            nclr(props.entry_decoded(new_c, SIGNS[name][2])[0]) + [(0, 0, 0)] * 256, np.float64)[:256])
        kept = np.abs(_pair_rows(pal[n].mean(-1)) - _pair_rows(pal[g].mean(-1))) < 8
        exact = int((n == g)[m].sum())
    else:
        kept = n == g
        exact = None
    return float(kept[m].mean()), int(m.sum()), exact


def flagged(name, kept, exact):
    """either rule trips: the score over LIMITS, or (circus) the exact count over EXACT."""
    return kept > limit(name) or (name in EXACT and exact is not None and exact > EXACT[name])


def limit(name):
    if name not in LIMITS:
        raise DetectError('%s: no limit recorded' % name)
    return LIMITS[name]


def _letters_on_band(rgb, valid):
    """dark or red pixels held between light band pixels (within 3, both sides, one axis)."""
    lum = rgb.mean(-1)
    light = (lum > 175) & valid
    ink = valid & ((lum < 150) | ((rgb[..., 0] > rgb[..., 1] + 40) & (rgb[..., 0] > rgb[..., 2] + 25)))

    def between(axis):
        lo = np.zeros_like(light)
        hi = np.zeros_like(light)
        for d in (1, 2, 3):
            a = np.zeros_like(light)
            b = np.zeros_like(light)
            if axis == 0:
                a[d:] = light[:-d]
                b[:-d] = light[d:]
            else:
                a[:, d:] = light[:, :-d]
                b[:, :-d] = light[:, d:]
            lo |= a
            hi |= b
        return lo & hi
    return ink & (between(0) | between(1))


# ---- the nurse's sprites: a decoder of their own (cells -> frame pixels -> tile bytes)

def _sprite(dec):
    from ncer import ncer
    o = struct.unpack_from('<3I', dec, 0)
    cells, mapping = ncer(dec[o[0]:])
    body = o[2] + 24
    dsize, doff = struct.unpack_from('<II', dec, body + 16)
    start = body + doff
    return cells, mapping, start, dsize


def _cell_bytes(cell, mapping, start, bnd, box):
    """{(x, y): tile byte offset in the entry} drawn inside box (frame pixels) by this cell, topmost OBJ wins."""
    bx0, by0 = bnd
    x0, y0, x1, y1 = box
    owner = {}
    boundary = max(1, (32 << (mapping & 3)) // 64)
    for ob in reversed(cell):
        tw, th = ob['w'] // 8, ob['h'] // 8
        for ty in range(th):
            for tx in range(tw):
                t = ob['tile'] * boundary + ty * tw + tx
                for yy in range(8):
                    for xx in range(8):
                        sx = (tw * 8 - 1) - (tx * 8 + xx) if ob['hflip'] else tx * 8 + xx
                        sy = (th * 8 - 1) - (ty * 8 + yy) if ob['vflip'] else ty * 8 + yy
                        X, Y = ob['x'] - bx0 + sx, ob['y'] - by0 + sy
                        if x0 <= X < x1 and y0 <= Y < y1:
                            owner[(X, Y)] = start + t * 64 + yy * 8 + xx
    return owner


def nurse_mask(e, fan_e, jp_e, pal):
    """-> (tile byte offsets of the fan's cap lettering, the frame x and y of each where it is first drawn)."""
    pe, groups = NURSE[e]
    cells, mapping, start, dsize = _sprite(fan_e)
    objs = [ob for c in cells for ob in c]
    bnd = (min(ob['x'] for ob in objs), min(ob['y'] for ob in objs))
    f = np.frombuffer(fan_e, np.uint8)
    j = np.frombuffer(jp_e, np.uint8)
    xof = {}
    for cl, box in groups:
        x0, y0, x1, y1 = box
        for k in cl:
            own = _cell_bytes(cells[k], mapping, start, bnd, box)
            src = np.full((y1 - y0, x1 - x0), -1, np.int64)
            for (X, Y), o in own.items():
                if f[o]:
                    src[Y - y0, X - x0] = o
            valid = src >= 0
            rgb = pal[f[np.maximum(src, 0)]]
            m = _letters_on_band(rgb, valid)
            for yy, xx in zip(*np.nonzero(m)):
                o = int(src[yy, xx])
                if f[o] != j[o]:
                    xof.setdefault(o, (x0 + int(xx), y0 + int(yy)))
    offs = np.array(sorted(xof), np.int64)
    return (offs, np.array([xof[int(o)][0] for o in offs], np.int64),
            np.array([xof[int(o)][1] for o in offs], np.int64))


def check_nurse(e, fan_c, jp_c, new_c, edit=None):
    """edit (tests): a function (fan bytes, built bytes, mask offsets, their frame x) -> built bytes."""
    fan_e = props.entry_decoded(fan_c, e)[0]
    jp_e = props.entry_decoded(jp_c, e)[0]
    if len(jp_e) != len(fan_e):
        raise DetectError('bustup %d: the retail entry has another size' % e)
    pal = np.array(nclr(props.entry_decoded(fan_c, NURSE[e][0])[0]), np.float64)
    m, xs, _ys = _cached(('nurse', e, _h(fan_c), _h(jp_c)), lambda: nurse_mask(e, fan_e, jp_e, pal))
    if len(m) < MIN_MASK:
        raise DetectError('bustup %d: only %d tile bytes of fan lettering found; the detector cannot judge' % (e, len(m)))
    f = np.frombuffer(fan_e, np.uint8)
    n = np.frombuffer(props.entry_decoded(new_c, e)[0], np.uint8)
    if edit is not None:
        n = edit(f, n, m, xs)
    return float((n[m] == f[m]).mean()), len(m), None


def icon_mask(e, fan_c, jp_c, part):
    import choice_strips as cs
    pe, box = ICONS[e]
    g = np.array(cs.grid(props.entry_decoded(fan_c, e)[0]))
    r = np.array(cs.grid(props.entry_decoded(jp_c, e)[0]))
    pal = np.array(nclr(props.entry_decoded(fan_c, pe)[0]), np.float64)
    rgb = pal[g]
    red = (rgb[..., 0] > rgb[..., 1] + 40) & (rgb[..., 0] > rgb[..., 2] + 25)
    m = _boxmask(g.shape, [box]) & (g != r) & _letters_on_band(rgb, g > 0) & (red if part == 'red' else ~red)
    return g, m


def check_icon(e, fan_c, jp_c, new_c, part='red', edit=None):
    """part 'red': the red 1st!; 'dark': the dark Safety. edit (tests): (fan grid, built grid) -> built grid."""
    import choice_strips as cs
    g, m = _cached(('icon', e, part, _h(fan_c), _h(jp_c)), lambda: icon_mask(e, fan_c, jp_c, part))
    if m.sum() < MIN_MASK:
        raise DetectError('idcom %d %s: only %d pixels of fan lettering found; the detector cannot judge' % (e, part, m.sum()))
    n = np.array(cs.grid(props.entry_decoded(new_c, e)[0]))
    if edit is not None:
        n = edit(g, n)
    return float((n[m] == g[m]).mean()), int(m.sum()), None


def _read(dumpdir, folder, c):
    p = os.path.join(dumpdir, folder, *c.split('/'))
    if not os.path.isfile(p):
        raise DetectError('%s is missing: the detector reads the fan\'s (ds_fan) and the retail Japanese (ds_jp) '
                          'containers from the dump folder %s' % (p, dumpdir))
    with open(p, 'rb') as f:
        return f.read()


def scores(get, dumpdir):
    """get(container path) -> the container to judge. -> [(name, kept, mask size, exact count or None)]."""
    out = []
    for name in SIGNS:
        c = SIGNS[name][0]
        out.append((name,) + check_sign(name, _read(dumpdir, 'ds_fan', c), _read(dumpdir, 'ds_jp', c), get(c), dumpdir))
    bc = 'com/bustup.bin'
    for e in sorted(NURSE):
        out.append(('nurse_bustup%d' % e,) + check_nurse(e, _read(dumpdir, 'ds_fan', bc), _read(dumpdir, 'ds_jp', bc), get(bc)))
    ic = 'com/idcom.bin'
    for e in sorted(ICONS):
        for part in ('red', 'dark'):
            out.append(('nurse_idcom%d_%s' % (e, part),)
                       + check_icon(e, _read(dumpdir, 'ds_fan', ic), _read(dumpdir, 'ds_jp', ic), get(ic), part))
    return out


def run(rom_path, dumpdir):
    from bufcheck import rom_file
    rom = open(rom_path, 'rb').read()
    lines, bad = [], []
    for name, kept, n, exact in scores(lambda c: rom_file(rom, c), dumpdir):
        ex = '' if exact is None else '; %d exactly the fan\'s (limit %d)' % (exact, EXACT[name])
        lines.append('%s: %.4f of the %d fan-lettering pixels unchanged (limit %.4f)%s' % (name, kept, n, limit(name), ex))
        if flagged(name, kept, exact):
            bad.append(name)
    if bad:
        raise DetectError('old fan lettering still found in: %s\n%s' % (', '.join(bad), '\n'.join(lines)))
    return '\n'.join(lines)


def control(dumpdir):
    """The check on the fan's own containers must flag every sign. -> lines; raises if one passes."""
    lines = []
    for name, kept, n, exact in scores(lambda c: open(os.path.join(dumpdir, 'ds_fan', *c.split('/')), 'rb').read(), dumpdir):
        if not flagged(name, kept, exact):
            raise DetectError('control: the fan\'s own %s is not flagged (%.2f)' % (name, kept))
        lines.append('fan %s keeps %.2f of %d: flagged' % (name, kept, n))
    return lines


if __name__ == '__main__':
    print(run(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else 'dump'))
