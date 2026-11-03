# -*- coding: utf-8 -*-
"""Newspaper pictures: the fan's wording of a newspaper page replaced by Capcom's, in place (item_pics class 'newspaper').

The fan's picture is a scan of a page: a masthead, a tag, a headline and greeked columns on page-curl shaded paper. Capcom's
own page (a Collection texture, not at the same scale or framing as the DS picture) is not pasted; the DS picture stays and
only the lettering changes. For each piece of lettering (a `pieces` row of the spec in item_pics.NEWSPAPERS):

  1. the old ink is found in the fan's own pixels (dark against the local paper, plus red by chroma for the tag), grown a
     little, and kept inside the piece's box;
  2. the paper under it is rebuilt per column from the clean rows above and below (`paper`): the bands are vertical
     page-curl stripes that do not change down the picture, so this is exact there. No inpainting model is involved;
  3. Capcom's lettering is cut from its HD texture as an ink coverage (`alpha`), area-averaged (PIL box filter) down to the
     picture at the placement the spec gives (`place`), composited in the spec's ink colour, and the result snapped to the
     nearest colour of the picture's own palette (weights 3, 4, 2, index 0 and the padding never used);
  4. `patches` are baked pixel blocks (tools/newspaper_patch_<entry>.py, each with its own box and sha256 guards) written
     over the result last. The greeked column lines under the headline are one: they were made from Capcom's columns and
     are replaced by swapping that one file, see swap_patch() below.

The paper kinds are lerp, row and median (see item_pics.NEWSPAPERS); a page may have no pieces at all and be one baked patch
(entry 20). paint_icon below does the same for the 64 x 64 newspaper icon of com/idcom.bin (class 'newsicon').

Everything is numpy and PIL (no OpenCV, no scipy, no random numbers): the same inputs give the same pixels. Every changed
pixel must lie in a declared box (a piece's `box` or a patch's box), otherwise ItemError.

Swapping a patch: python tools/newspaper.py pack <indexed.png> <entry> writes tools/newspaper_patch_<entry>.py from the
box of the picture (the file keeps the box it already has unless --box x0,y0,x1,y1 is given); nothing else changes.
"""
import sys, os, hashlib, base64, zlib, importlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image

LUMW = (0.299, 0.587, 0.114)
W8 = np.array((3.0, 4.0, 2.0))
HERE = os.path.dirname(os.path.abspath(__file__))

# The baked patches are imported by name from item_pics.NEWSPAPERS, which PyInstaller cannot see; these static imports are
# what put them in the frozen exe. A file that is not there stays None and load_patch reports it as an ItemError.
try:
    import newspaper_patch_2
except ImportError:
    newspaper_patch_2 = None
try:
    import newspaper_patch_20
except ImportError:
    newspaper_patch_20 = None
_PATCHES = {'newspaper_patch_2': newspaper_patch_2, 'newspaper_patch_20': newspaper_patch_20}


def _err(msg):
    from item_pics import ItemError
    return ItemError(msg)


# ---------------------------------------------------------------- morphology (numpy only; equal to OpenCV's on these inputs)

def ellipse_kernel(k):
    """The elliptical structuring element OpenCV builds for a k x k window (k odd), as (dy, half width) per row."""
    r = c = k // 2
    inv = 1.0 / (r * r) if r else 0.0
    out = []
    for i in range(k):
        dy = i - r
        if abs(dy) <= r:
            out.append((dy, min(int(round(c * np.sqrt((r * r - dy * dy) * inv))), c)))
    return out


def dilate_ellipse(a, k):
    """Grey dilation by the k x k ellipse, the border replicated."""
    r = k // 2
    h, w = a.shape
    p = np.pad(a, r, mode='edge')
    se = ellipse_kernel(k)
    hm = {0: p}
    for d in range(1, max(dx for _dy, dx in se) + 1):
        hm[d] = np.maximum(np.maximum(hm[d - 1], np.roll(p, d, 1)), np.roll(p, -d, 1))
    out = None
    for dy, dx in se:
        s = np.roll(hm[dx], -dy, 0)
        out = s if out is None else np.maximum(out, s)
    return out[r:r + h, r:r + w]


def close_ellipse(a, k):
    """Grey closing (dilate, then erode) by the k x k ellipse, the border replicated."""
    return -dilate_ellipse(-dilate_ellipse(a, k), k)


def dilate_rect(a, k):
    """Grey dilation by a k x k square (k odd); pixels beyond the edge do not count."""
    r = k // 2
    h, w = a.shape
    p = np.pad(a, r, mode='constant', constant_values=-np.inf)
    rows = p[:, r:r + w].copy()
    for d in range(1, r + 1):
        rows = np.maximum(rows, np.maximum(p[:, r - d:r - d + w], p[:, r + d:r + d + w]))
    out = rows[r:r + h].copy()
    for d in range(1, r + 1):
        out = np.maximum(out, np.maximum(rows[r - d:r - d + h], rows[r + d:r + d + h]))
    return out


def grow(m, n):
    """Binary dilation by a 3 x 3 square, n times; pixels beyond the edge do not count."""
    m = m.copy()
    for _ in range(n):
        p = np.pad(m, 1)
        out = m.copy()
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                out |= p[1 + dy:1 + dy + m.shape[0], 1 + dx:1 + dx + m.shape[1]]
        m = out
    return m


# ---------------------------------------------------------------- the pieces

def _inbox(m, box):
    k = np.zeros_like(m)
    k[box[1]:box[3], box[0]:box[2]] = True
    return m & k


def old_ink(lum, rgb0, spec):
    """Mask of the old lettering of a piece, from the fan's own pixels."""
    mk = spec['mask']
    x0, y0, x1, y1 = mk['box']
    sub = lum[y0:y1, x0:x1].astype(np.float32)
    bg = dilate_rect(sub, mk['k'])
    raw = np.zeros(lum.shape, bool)
    raw[y0:y1, x0:x1] = ((bg - sub) > mk['thr']) & (sub < 150)
    if mk.get('chroma') is not None:
        bx0, by0, bx1, by1 = spec['box']
        red = np.zeros(lum.shape, bool)
        red[by0:by1, bx0:bx1] = ((rgb0[..., 0] - rgb0[..., 1]) > mk['chroma'])[by0:by1, bx0:bx1]
        raw |= red
    return _inbox(grow(raw, mk['grow']), spec['box'])


def _paper_rows(rgb0, p, m=None, box=None):
    """-> (rows y0..y1 of the rebuilt paper as a (192, 256, 3) array, (y0, y1)). `m` is the old-ink mask and `box` the piece's box
    (only the 'median' kind reads them)."""
    out = np.zeros(rgb0.shape)
    y0, y1 = p['rows']
    if p['kind'] == 'median':
        # page-curl stripes that do not change down the band: per column the median of the clean reference rows `refrows`, plus
        # a vertical gradient g(y) shared by all columns (the median, over the columns that are paper in row y and in every
        # reference row, of row y minus the reference). A single reference row would copy leftover ink into a streak.
        refrows = list(p['refrows'])
        top = np.median(rgb0[refrows], axis=0)
        clean_ref = ~m[refrows].any(0)
        lum = rgb0 @ np.array(LUMW)
        for y in range(y0, y1):
            ok = (~m[y]) & clean_ref
            ok[:box[0]] = False
            ok[box[2]:] = False
            ok &= lum[y] > p['lum']
            out[y] = top + np.median(rgb0[y][ok] - top[ok], axis=0)
        return out, (y0, y1)
    for y in range(y0, y1):
        if p['kind'] == 'lerp':
            t = (y - p['ya']) / float(p['yb'] - p['ya'])
            out[y] = rgb0[p['ya']] * (1 - t) + rgb0[p['yb']] * t
        else:
            out[y] = rgb0[p['src']]
    return out, (y0, y1)


def alpha_of(cap, lum, a):
    """Capcom's lettering as ink coverage 0..1 (float32, the HD window of the texture) and the window's origin."""
    x0, y0, x1, y1 = a['hd']
    if a['kind'] == 'green':
        # green ink on grey paper: the green excess (g - r) is the coverage; the blue band under the tag has g < b
        c = cap[y0:y1, x0:x1]
        gr = np.asarray(c[..., 1] - c[..., 0])
        gb = np.asarray(c[..., 1] - c[..., 2])
        al = (np.clip((gr - 4.0) / 88.0, 0, 1) * np.clip((gb + 6.0) / 46.0, 0, 1)).astype(np.float32)
    else:
        sub = lum[y0:y1, x0:x1]
        paper = close_ellipse(sub, a['ker'])
        ink = np.percentile(sub, 1.0)
        al = np.clip((paper - sub) / np.maximum(paper - ink, 1.0), 0, 1)
        al = np.clip((al - 0.04) / 0.96, 0, 1)         # noise floor of the paper estimate
    ys, xs = np.nonzero(al > 0.5)
    if not len(ys):
        raise _err('no lettering found in the texture window %r' % (a['hd'],))
    keep = np.zeros_like(al)                           # nothing beyond the lettering's own extent
    keep[max(ys.min() - 4, 0):ys.max() + 5, max(xs.min() - 4, 0):xs.max() + 5] = 1
    return (al * keep).astype(np.float32)


def place(cap, lum, spec, w=256, h=192):
    """Capcom's lettering area-averaged to a (h, w) float32 coverage at the placement of the piece."""
    sp, a = spec['place'], spec['alpha']
    al = alpha_of(cap, lum, a)
    x0, y0, x1, y1 = a['hd']
    th, tw = cap.shape[:2]
    canvas = np.zeros((th, tw), np.float32)
    canvas[y0:y1, x0:x1] = al
    ys, xs = np.nonzero(al > 0.5)
    xmin, xmax = xs.min() + x0, xs.max() + x0 + 1
    s = sp['s']
    if sp.get('left') is None:
        left = sp['centre'] - ((xmax - xmin) / s) / 2.0
        left = round(left * 2) / 2.0
    else:
        left = sp['left']
    out = np.zeros((h, w), np.float32)
    wx0 = int(np.floor(left)) - 1
    wx1 = int(np.ceil(left + (xmax - xmin) / s)) + 2
    wy0 = int(np.floor(sp['base'] - (sp['ref_base'] - y0) / s)) - 1
    wy1 = int(np.ceil(sp['base'] + (y1 - sp['ref_base']) / s)) + 2
    wx0, wy0 = max(wx0, 0), max(wy0, 0)
    wx1, wy1 = min(wx1, w), min(wy1, h)
    bx0 = sp['ref_x'] + (wx0 - left) * s
    bx1 = sp['ref_x'] + (wx1 - left) * s
    by0 = sp['ref_base'] + (wy0 - sp['base']) * s
    by1 = sp['ref_base'] + (wy1 - sp['base']) * s
    if bx0 < 0 or by0 < 0 or bx1 > tw or by1 > th:
        raise _err('lettering %s reaches outside the texture %r' % (spec['name'], (bx0, by0, bx1, by1)))
    im = Image.fromarray(canvas, mode='F').resize((wx1 - wx0, wy1 - wy0), Image.BOX, box=(bx0, by0, bx1, by1))
    out[wy0:wy1, wx0:wx1] = np.asarray(im)
    return out


def snap(rgb, pal):
    """The nearest palette colour (weights 3, 4, 2); index 0 (the transparent key) is never chosen."""
    d = (((rgb[..., None, :] - pal[None, None]) * W8) ** 2).sum(3)
    d[..., 0] = 1e18
    return d.argmin(2).astype(np.uint8)


def _patch_module(name):
    """The baked patch module `name`. The shipped ones come from the static imports above (so PyInstaller bundles them); any
    other name (the test's temporary patch) is imported by name. A patch file that is not there is an ItemError."""
    m = _PATCHES.get(name)
    if m is None:
        try:
            m = importlib.import_module(name)
        except ImportError as ex:
            raise _err('patch %s is not available (%s)' % (name, ex))
    return m


def load_patch(name):
    """The baked patch module `name` -> (box, index array of the box, module). Raises if its own sha256 does not hold."""
    m = _patch_module(name)
    x0, y0, x1, y1 = m.BOX
    data = np.frombuffer(zlib.decompress(base64.b64decode(m.DATA)), np.uint8)
    if hashlib.sha256(data.tobytes()).hexdigest() != m.SHA:
        raise _err('patch %s does not match its own sha256' % name)
    if data.size != (x1 - x0) * (y1 - y0):
        raise _err('patch %s holds %d pixels, its box %r wants %d' % (name, data.size, m.BOX, (x1 - x0) * (y1 - y0)))
    return tuple(m.BOX), data.reshape(y1 - y0, x1 - x0), m


def paint_news(grid, pal, tex, spec):
    """The fan's index grid with the newspaper's lettering replaced. `pal` is the picture's real palette (no padding), `tex`
    Capcom's RGB texture (float, rows x cols x 3). -> new grid (uint8)."""
    pal = np.asarray(pal, np.float64)
    grid = np.asarray(grid, np.uint8)
    h, w = grid.shape
    rgb0 = pal[grid].astype(np.float64)
    lum = rgb0.astype(np.uint8) @ np.array(LUMW)
    # a page with no `pieces` (all baked patches) reads no Capcom texture
    cap = capl = None
    if spec['pieces']:
        cap = np.asarray(tex).astype(np.float32)
        capl = cap @ np.array(LUMW, np.float32)
    cur = rgb0.copy()
    region = np.zeros((h, w), bool)
    boxes = []
    pieces = spec['pieces']
    masks = []
    for pc in pieces:
        boxes.append(pc['box'])
        m = old_ink(lum, rgb0, pc)
        P, (py0, py1) = _paper_rows(rgb0, pc['paper'], m, pc['box'])
        if pc['paper'].get('edge') is not None:
            py0, py1 = min(py0, pc['paper']['edge']), max(py1, pc['paper']['edge'] + 1)
        if m[:py0].any() or m[py1:].any():
            raise _err('%s: the old lettering reaches outside the rows the paper is rebuilt for' % pc['name'])
        if pc['paper'].get('edge') is not None:
            # a row on a different surface (the blue band's top edge): masked pixels are interpolated along the row
            er = pc['paper']['edge']
            bx0, _by0, bx1, _by1 = pc['box']
            ms = m.copy()
            ms[er, :] = False
            cur[ms] = P[ms]
            xs = np.nonzero(m[er])[0]
            if len(xs):
                good = np.nonzero(~m[er, bx0:bx1])[0] + bx0
                for c in range(3):
                    cur[er, xs, c] = np.interp(xs, good, rgb0[er, good, c])
        else:
            cur[m] = P[m]
        region |= m
        masks.append(m)
    for pc in pieces:
        a = place(cap, capl, pc)
        a = a ** pc['gamma']
        kb = np.zeros_like(a)
        b = pc['box']
        kb[b[1]:b[3], b[0]:b[2]] = 1
        a = a * kb
        ink = np.array(pc['ink'], np.float64)
        cur = cur * (1 - a[..., None]) + ink * a[..., None]
        region |= a > 0.02
    new = np.where(region, snap(cur, pal), grid).astype(np.uint8)
    for name in spec.get('patches', ()):
        box, data, m = load_patch(name)
        x0, y0, x1, y1 = box
        if hashlib.sha256(grid[y0:y1, x0:x1].tobytes()).hexdigest() != m.FAN_SHA:
            raise _err('patch %s was made for a different picture (the fan\'s pixels in its box do not match)' % name)
        if int(data.max()) >= len(pal) or int(data.min()) == 0:
            raise _err('patch %s uses a palette index the picture does not have (or the transparent key 0)' % name)
        new[y0:y1, x0:x1] = data
        boxes.append(box)
    ys, xs = np.nonzero(new != grid)
    for x, y in zip(xs.tolist(), ys.tolist()):
        if not any(b[0] <= x < b[2] and b[1] <= y < b[3] for b in boxes):
            raise _err('the redrawn newspaper changes pixel (%d, %d), outside its declared boxes %r' % (x, y, boxes))
    return new


def boxes_of(spec):
    """Every box (x0, y0, x1, y1) outside which a spec leaves the picture untouched."""
    out = [pc['box'] for pc in spec['pieces']]
    for name in spec.get('patches', ()):
        out.append(tuple(_patch_module(name).BOX))
    return out


# ---------------------------------------------------------------- the newspaper icon (idcom 4bpp, 64 x 64)

def _alpha_icon(cap, lum, pc):
    """Capcom's lettering of an icon piece as ink coverage 0..1 (float32 window of the 300 x 300 texture) and its extent."""
    x0, y0, x1, y1 = pc['hd']
    sub = lum[y0:y1, x0:x1]
    paper = close_ellipse(sub, pc['ker'])
    ink = np.percentile(sub, 1.0)
    a = np.clip((paper - sub) / np.maximum(paper - ink, 1.0), 0, 1)
    a = np.clip((a - pc['noise']) / (1.0 - pc['noise']), 0, 1)
    ys, xs = np.nonzero(a > 0.5)
    if not len(ys):
        raise _err('no lettering found in the texture window %r' % (pc['hd'],))
    keep = np.zeros_like(a)
    keep[max(ys.min() - 2, 0):ys.max() + 3, max(xs.min() - 2, 0):xs.max() + 3] = 1
    return (a * keep).astype(np.float32), (xs.min() + x0, xs.max() + x0 + 1)


def _place_icon(cap, lum, pc, shape):
    """Capcom's lettering area-averaged (PIL box filter) to the icon's grid at the placement of the piece -> float32 coverage."""
    a, (gx0, gx1) = _alpha_icon(cap, lum, pc)
    x0, y0, x1, y1 = pc['hd']
    s, left, base, ref_base = pc['s'], pc['left'], pc['base'], pc['ref_base']
    canvas = np.zeros(cap.shape[:2], np.float32)
    canvas[y0:y1, x0:x1] = a
    out = np.zeros(shape, np.float32)
    wx0, wx1 = int(np.floor(left)) - 1, int(np.ceil(left + (gx1 - gx0) / s)) + 2
    wy0 = int(np.floor(base - (ref_base - y0) / s)) - 1
    wy1 = int(np.ceil(base + (y1 - ref_base) / s)) + 2
    wx0, wy0 = max(wx0, 0), max(wy0, 0)
    wx1, wy1 = min(wx1, shape[1]), min(wy1, shape[0])
    bx0, bx1 = gx0 + (wx0 - left) * s, gx0 + (wx1 - left) * s
    by0, by1 = ref_base + (wy0 - base) * s, ref_base + (wy1 - base) * s
    pad = 40
    im = Image.fromarray(np.pad(canvas, pad), mode='F').resize((wx1 - wx0, wy1 - wy0), Image.BOX,
                                                              box=(bx0 + pad, by0 + pad, bx1 + pad, by1 + pad))
    out[wy0:wy1, wx0:wx1] = np.asarray(im)
    return out


def paint_icon(grid, pal, tex, spec):
    """A newspaper icon (item_pics ICON_PICS class 'newsicon'): the fan's grid with the masthead and headline replaced by Capcom's,
    each inside its piece's box. Paper under the old lettering is a palette colour (`paper` = ('index', i)) or the clean row above
    ('row', y) copied across; the lettering is blended in the spec's ink and every pixel of the boxes snapped to the icon's own
    palette (index 0 never used). Nothing outside the boxes changes. -> new grid."""
    pal = np.asarray(pal, np.float64)
    grid = np.asarray(grid, np.uint8)
    h, w = grid.shape
    cap = np.asarray(tex).astype(np.float32)
    lum = cap @ np.array(LUMW, np.float32)
    rgb = pal[grid].copy()
    inbox = np.zeros((h, w), bool)
    for pc in spec['pieces']:
        x0, y0, x1, y1 = pc['box']
        kind, v = pc['paper']
        rgb[y0:y1, x0:x1] = pal[v] if kind == 'index' else pal[grid[v, x0:x1]][None]
        inbox[y0:y1, x0:x1] = True
    for pc in spec['pieces']:
        a = _place_icon(cap, lum, pc, (h, w))
        a = np.where(a < spec['floor'], 0, a) ** spec['gamma']
        m = np.zeros((h, w), bool)
        x0, y0, x1, y1 = pc['box']
        m[y0:y1, x0:x1] = True
        a = np.where(m, a, 0)[..., None]
        rgb = rgb * (1 - a) + np.array(spec['ink'], np.float64) * a
    return np.where(inbox, snap(rgb, pal), grid).astype(np.uint8)


# ---------------------------------------------------------------- packing a patch

def pack(grid, box, fan_grid, out_path):
    """Write the patch module for `box` of `grid` (indices) over `fan_grid` (the fan's indices)."""
    x0, y0, x1, y1 = box
    data = np.asarray(grid, np.uint8)[y0:y1, x0:x1].tobytes()
    fan = np.asarray(fan_grid, np.uint8)[y0:y1, x0:x1].tobytes()
    b64 = base64.b64encode(zlib.compress(data, 9)).decode('ascii')
    lines = [b64[i:i + 100] for i in range(0, len(b64), 100)]
    txt = ['# -*- coding: utf-8 -*-',
           '"""Baked pixels for tools/newspaper.py (a patch applied last, inside BOX): the indices of the picture\'s box,',
           'zlib-compressed and base64. SHA is the sha256 of the raw index bytes (row major, BOX wide); FAN_SHA that of the fan\'s',
           'pixels in the same box, so the patch only applies to the fan\'s picture. Regenerate with',
           'python tools/newspaper.py pack <indexed.png> <entry> [--box x0,y0,x1,y1]."""',
           'BOX = (%d, %d, %d, %d)' % tuple(box),
           "SHA = '%s'" % hashlib.sha256(data).hexdigest(),
           "FAN_SHA = '%s'" % hashlib.sha256(fan).hexdigest(),
           'DATA = (']
    txt += ["    '%s'" % ln for ln in lines]
    txt += [')', '']
    with open(out_path, 'wb') as f:
        f.write('\n'.join(txt).encode('ascii'))


def _main(argv):
    import item_pics as P
    if len(argv) < 4 or argv[1] != 'pack':
        print(__doc__.split('Swapping a patch:')[1].strip().splitlines()[0])
        return 2
    png, entry = argv[2], int(argv[3])
    box = None
    if '--box' in argv:
        box = tuple(int(v) for v in argv[argv.index('--box') + 1].split(','))
    name = 'newspaper_patch_%d' % entry
    if box is None:
        box = tuple(_patch_module(name).BOX)
    im = Image.open(png)
    if im.mode != 'P':
        raise SystemExit('%s is not an indexed picture' % png)
    grid = np.asarray(im)
    import choice_strips as cs
    fan = cs.Idlocal(open(os.path.join(os.path.dirname(HERE), 'dump', 'ds_fan', 'jpn', 'upcut_local.bin'), 'rb').read())
    fan_grid = P.pic_grid(P._content(fan, entry))
    if grid.shape != fan_grid.shape:
        raise SystemExit('%s is %r, the picture is %r' % (png, grid.shape, fan_grid.shape))
    out = os.path.join(HERE, name + '.py')
    pack(grid, box, fan_grid, out)
    print('wrote', out, 'box', box)
    return 0


if __name__ == '__main__':
    sys.exit(_main(sys.argv))
