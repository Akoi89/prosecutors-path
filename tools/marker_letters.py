# -*- coding: utf-8 -*-
"""Capcom's letters in the character markers of jpn/cutobj_local.bin.

The floor plans and maps mark where people stand with round markers: a coloured circle with one white
letter, the initial of the person. The fan's markers carry the initials of the fan's names (a red "B"
for Blaise where Capcom's English script says Chairman Winner); Capcom's own pictures (the Collection's
cutObj*_eng textures in the bundle gk2_cutobjlocal) carry the initials of Capcom's names.

The two sets are the same pictures: Capcom's cell lists (SpriteList / Parts) give for every sprite part
the rectangle of its atlas that it draws (SrcX, SrcY, Width, Height, in DS pixels; the atlas is the DS
sprite sheet at 5.625 times the size) at the same place and size as the DS cell's OBJ. So the DS tile that
draws a marker and the Capcom circle that replaces it are matched by geometry, not by guessing, in every
cell of every entry.

At build time, from the user's own Collection install (extract() saves the 13 textures and their cell
lists under dump/title/bigg_markers/):
  - every Capcom circle of an entry (a round 70 to 135 px blob of the atlas) is located on the DS sheet;
  - if the DS marker shows a letter (one-pixel white strokes, 10 to 45 pixels) and Capcom's circle
    shows a different one (compared as pixels, tolerance one pixel of shift), the DS letter is replaced:
    Capcom's letter is cut out of the atlas (its white pixels), thinned to a one pixel line (the fan's
    face is a one pixel stroke face, eleven rows high in a twenty pixel circle) and drawn at the size and
    place that Capcom's letter has in its circle, scaled to the DS circle. The circle, rim, shading and
    palette of the DS sprite are not touched; only the letter's pixels and the fill that replaces the old
    letter's pixels change, in the tile data, once; every cell of the entry is rendered before and after
    and must differ only in those pixels;
  - markers that show a chess piece where Capcom has a letter: the retail Japanese sprite carries a kanji there, so the
    piece is the fan's own addition and not the game's symbol; the piece is erased and Capcom's letter drawn in its place
    (the fan's own glyph where its face has the letter);
  - markers that Capcom draws blank, or that show the same letter, are left alone.
The module needs numpy and Pillow only.
"""
import os, sys, glob, json, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image
from choice_strips import Idlocal, rebuild, rom_file
from ncer import ncer
from nitro import nclr
import gfx_views as gv
import room_names as rn
import input_hashes as ih


class MarkerError(ValueError):
    pass


BUNDLE_PREFIX = 'gk2_cutobjlocal_assets'
SC = 5.625                                     # atlas pixels per DS pixel
NAMES = {2: 'cutObj01_004', 4: 'cutObj01_008', 6: 'cutobj01_015', 8: 'cutobj01_018', 10: 'cutobj02_003',
         12: 'cutobj02_004', 14: 'cutobj03_004', 16: 'cutobj03_024', 18: 'cutObj04_010', 20: 'cutObj04_03a',
         22: 'cutObj04_03b', 24: 'cutObj04_045', 26: 'cutObj04_046'}          # entry 0 (cutObj04_02b) has no cell list
SHEET_W, SHEET_H = 256, 512
CIRCLE = (70, 135)                             # Capcom circle size range, atlas pixels
LETTER_PX = (8, 45)                            # DS white pixels of a one pixel stroke letter
GRAFT_NCC = 0.80                               # a fan letter at least this like Capcom's may lend its top rows (R from P)
SAME_NCC = 0.85                                # Capcom's letter against the DS letter (both blurred), best of nine one pixel shifts
RIM_DARK = 50
DARK_LETTER = 90                                # a dark letter's pixels (yellow markers): brightest channel below this
SYM_IOU = 0.85                                 # Capcom's letter against its own mirror image: above this the letter is drawn symmetric
BLOCK_COST = 0.03                              # a one pixel stroke face has no 2x2 blocks: each one costs this much of the stroke coverage score
IOU_SLACK = 0.02                               # a simpler figure is taken if its stroke covers Capcom's letter this nearly as well as the best
PATH_EPS = (3.0, 5.0, 8.0, 12.0)               # Capcom pixels: corner tolerances tried when a one-stroke letter is drawn as straight lines
# Letters built from the fan's own face instead of from Capcom's outline, (entry, marker) -> how:
#   ('A', (entry, marker))      the fan's own A (read from that marker of the unchanged fan sprite), its three foot rows
#                               cut to two so that it is as tall as the fan's other letters of this circle, centred in the circle
#   ('W', width, height, foot)  a W in the fan's own W construction (the red W of cutobj_local entry 4: outer legs upright
#                               for two rows then stepping in, feet flat, the middle peak one row below the top), drawn
#                               symmetric from a left half, in the width and height of this circle's letters
ADAPT = {(24, 4): ('A', (6, 0)), (22, 0): ('W', 13, 11, 3), (24, 3): ('W', 11, 10, 2)}
W_PEAK_DROP = 1                                 # rows between the top of the outer legs and the top of the middle peak


def cache_dir(dumpdir):
    return os.path.join(dumpdir, 'title', 'bigg_markers')


def required(dumpdir):
    c = cache_dir(dumpdir)
    return [os.path.join(c, n + '_eng.png') for n in sorted(NAMES.values())] + \
           [os.path.join(c, n + '_cells.json') for n in sorted(NAMES.values())]


def extract(bdir, dumpdir):
    """Save the English atlas (upright, RGBA) and the cell list of each of the 13 markers' pictures under
    dump/title/bigg_markers/. Raises SystemExit if the bundle or an asset is missing."""
    hits = [p for p in glob.glob(os.path.join(bdir, '*.bundle'))
            if os.path.basename(p).lower().startswith(BUNDLE_PREFIX)
            and '_trial' not in os.path.basename(p).lower() and '_classic' not in os.path.basename(p).lower()]
    if not hits:
        raise SystemExit('markers: no bundle starting with %r in %s' % (BUNDLE_PREFIX, bdir))
    import UnityPy
    env = UnityPy.load(hits[0])
    want = {n.lower(): n for n in NAMES.values()}
    tex, lists = {}, {}
    for obj in env.objects:
        if obj.type.name == 'Texture2D':
            d = obj.read()
            nm = d.m_Name
            if nm.lower().endswith('_eng') and nm[:-4].lower() in want:
                tex[want[nm[:-4].lower()]] = d.image.convert('RGBA').transpose(Image.FLIP_TOP_BOTTOM)
        elif obj.type.name == 'MonoBehaviour':
            try:
                tt = obj.read_typetree()
            except Exception:
                continue
            nm = tt.get('m_Name', '')
            if 'SpriteList' in tt and nm.lower() in want:
                lists[want[nm.lower()]] = [[{k: p[k] for k in ('DestX', 'DestY', 'SrcX', 'SrcY', 'Width', 'Height', 'Flag')}
                                            for p in s['Parts']] for s in tt['SpriteList']]
    missing = sorted(set(NAMES.values()) - set(tex)) + ['%s cell list' % n for n in sorted(set(NAMES.values()) - set(lists))]
    if missing:
        raise SystemExit('markers: %s missing from %s' % (', '.join(missing), os.path.basename(hits[0])))
    out = cache_dir(dumpdir)
    os.makedirs(out, exist_ok=True)
    for n, im in tex.items():
        im.save(os.path.join(out, n + '_eng.png'))
        with open(os.path.join(out, n + '_cells.json'), 'w') as f:
            json.dump(lists[n], f)
    return out


def load_capcom(dumpdir, name):
    c = cache_dir(dumpdir)
    p = os.path.join(c, name + '_eng.png')
    q = os.path.join(c, name + '_cells.json')
    if not (os.path.isfile(p) and os.path.isfile(q)):
        raise MarkerError('%s is missing; run the build once without --skip-extract' % name)
    a = np.asarray(Image.open(p).convert('RGBA'))
    if a.shape[:2] != (2880, 1440):
        raise MarkerError('%s atlas is %dx%d, expected 1440x2880' % (name, a.shape[1], a.shape[0]))
    cells = json.load(open(q))
    if ih.GUARD_INPUTS:
        want = ih.MARKER_TEXTURE_SHA256.get(name)
        if want is None or ih.sha(a.tobytes()) != want[0] or ih.sha(json.dumps(cells, sort_keys=True).encode()) != want[1]:
            raise MarkerError('%s (atlas pixels or cell list) is not the Collection picture this routine was proven on' % name)
    return a, cells


# ---------------------------------------------------------------------------
# thinning
# ---------------------------------------------------------------------------
def thin(m):
    """Zhang-Suen thinning of a boolean grid (numpy only)."""
    m = m.copy().astype(np.uint8)
    while True:
        changed = False
        for it in (0, 1):
            p = np.pad(m, 1)
            P2, P3, P4, P5, P6, P7, P8, P9 = (p[:-2, 1:-1], p[:-2, 2:], p[1:-1, 2:], p[2:, 2:], p[2:, 1:-1], p[2:, :-2],
                                              p[1:-1, :-2], p[:-2, :-2])
            B = P2 + P3 + P4 + P5 + P6 + P7 + P8 + P9
            seq = [P2, P3, P4, P5, P6, P7, P8, P9, P2]
            A = sum(((seq[i] == 0) & (seq[i + 1] == 1)).astype(np.uint8) for i in range(8))
            if it == 0:
                c1, c2 = (P2 * P4 * P6 == 0), (P4 * P6 * P8 == 0)
            else:
                c1, c2 = (P2 * P4 * P8 == 0), (P2 * P6 * P8 == 0)
            d = (m == 1) & (B >= 2) & (B <= 6) & (A == 1) & c1 & c2
            if d.any():
                m[d] = 0
                changed = True
        if not changed:
            return m.astype(bool)


def erode_disc(m, r):
    yy, xx = np.mgrid[-r:r + 1, -r:r + 1]
    disc = (yy ** 2 + xx ** 2) <= r * r
    p = np.pad(~m, r, constant_values=True)
    inv = np.zeros_like(m)
    for dy in range(2 * r + 1):
        for dx in range(2 * r + 1):
            if disc[dy, dx]:
                inv |= p[dy:dy + m.shape[0], dx:dx + m.shape[1]]
    return ~inv


# ---------------------------------------------------------------------------
# Capcom side
# ---------------------------------------------------------------------------
def components(mask):
    """4-connected components of a boolean grid, numpy only. -> list of (x0, y0, x1, y1, area)."""
    h, w = mask.shape
    lab = np.zeros((h, w), np.int32)
    out, n = [], 0
    for y, x in zip(*np.nonzero(mask)):
        if lab[y, x]:
            continue
        n += 1
        stack = [(y, x)]
        lab[y, x] = n
        x0 = x1 = x; y0 = y1 = y; area = 0
        while stack:
            cy, cx = stack.pop()
            area += 1
            x0, x1, y0, y1 = min(x0, cx), max(x1, cx), min(y0, cy), max(y1, cy)
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                yy, xx = cy + dy, cx + dx
                if 0 <= yy < h and 0 <= xx < w and mask[yy, xx] and not lab[yy, xx]:
                    lab[yy, xx] = n
                    stack.append((yy, xx))
        out.append((x0, y0, x1 + 1, y1 + 1, area))
    return out


def capcom_circles(atlas):
    """Round blobs of the atlas (upright): dicts x, y, w, h in atlas pixels, in reading order."""
    solid = atlas[..., 3] > 128
    # only the part of the atlas that holds sprite sheet rows is scanned (top 520 DS rows)
    solid = solid[:int(SHEET_H * SC), :]
    # cheap prefilter: rows / columns with solid pixels
    out = []
    for x0, y0, x1, y1, area in components(solid):
        w, h = x1 - x0, y1 - y0
        if CIRCLE[0] <= w <= CIRCLE[1] and CIRCLE[0] <= h <= CIRCLE[1] and 0.9 < w / h < 1.12 and 0.7 < area / (w * h) < 0.85:
            out.append(dict(x=x0, y=y0, w=w, h=h))
    return sorted(out, key=lambda c: (c['y'] // 40, c['x']))


def capcom_coverage(atlas, c, dark=False):
    """Letter coverage 0..1 inside the circle (rim excluded): a white letter on the circle's colour, or with
    dark=True a dark letter on a light circle (the yellow markers)."""
    x, y, w, h = c['x'], c['y'], c['w'], c['h']
    rgb = atlas[y:y + h, x:x + w, :3].astype(int)
    yy, xx = np.mgrid[0:h, 0:w]
    r = np.hypot(xx - (w - 1) / 2, yy - (h - 1) / 2)
    inside = r < (w / 2 - 0.12 * w)
    if dark:
        mx = rgb.max(-1)
        base = mx[inside & (mx >= 150)]
        fill = np.median(base) if base.size else 255
        return np.clip((fill - mx) / (fill + 1e-6), 0, 1) * inside
    mn = rgb.min(-1)
    base = mn[inside & (mn < 200)]
    fillmn = np.median(base) if base.size else 0
    return np.clip((mn - fillmn) / (255 - fillmn + 1e-6), 0, 1) * inside


def simplify(path, eps):
    """Douglas-Peucker on a list of (y, x)."""
    pts = np.array(path, float)
    keep = [0, len(pts) - 1]
    stack = [(0, len(pts) - 1)]
    while stack:
        a, b = stack.pop()
        if b <= a + 1:
            continue
        p, q = pts[a], pts[b]
        d = q - p
        n = np.hypot(*d)
        seg = pts[a + 1:b] - p
        dist = np.abs(seg[:, 0] * d[1] - seg[:, 1] * d[0]) / n if n else np.hypot(seg[:, 0], seg[:, 1])
        k = int(np.argmax(dist))
        if dist[k] > eps:
            m = a + 1 + k
            keep.append(m)
            stack += [(a, m), (m, b)]
    return [tuple(pts[i]) for i in sorted(keep)]


def bresenham(x0, y0, x1, y1):
    out = []
    dx, dy = abs(x1 - x0), -abs(y1 - y0)
    sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
    err = dx + dy
    while True:
        out.append((x0, y0))
        if x0 == x1 and y0 == y1:
            return out
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy


RING = ((-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1))   # N NE E SE S SW W NW as (dy, dx)


def minimal_skeleton(sk):
    """Delete every simple (topology-preserving) non-end pixel of a thinned letter, so that a corner or a
    staircase becomes a one pixel wide 8-connected line and only true branch points keep three neighbours."""
    pad = np.pad(sk.astype(bool), 1)
    order = sorted(zip(*[a.tolist() for a in np.nonzero(pad)]))
    changed = True
    while changed:
        changed = False
        for y, x in order:
            if not pad[y, x]:
                continue
            r = [bool(pad[y + dy, x + dx]) for dy, dx in RING]
            if sum(r) < 2 or all(r[i] for i in (0, 2, 4, 6)):
                continue                                   # an end, or no background 4-neighbour (deleting would open a hole)
            idx = [i for i in range(8) if r[i]]
            seen, comps = set(), 0
            for i in idx:
                if i in seen:
                    continue
                comps += 1
                stack = [i]
                seen.add(i)
                while stack:
                    a = stack.pop()
                    for b in idx:
                        if b not in seen and max(abs(RING[a][0] - RING[b][0]), abs(RING[a][1] - RING[b][1])) <= 1:
                            seen.add(b)
                            stack.append(b)
            if comps == 1:
                pad[y, x] = False
                changed = True
    return pad[1:-1, 1:-1]


def skeleton_chains(sk):
    """The minimal skeleton as chains. Each chain is a dict: pts = polyline [(y, x) floats] from one end or branch
    point to the next (a cluster of adjacent branch pixels is one point, its centroid); px = the pixels the chain
    owns; free = how many of its two ends are free ends (0, 1 or 2)."""
    pts = set(zip(*[a.tolist() for a in np.nonzero(sk)]))
    def nbrs(p):
        return [(p[0] + dy, p[1] + dx) for dy, dx in RING if (p[0] + dy, p[1] + dx) in pts]
    deg = {p: len(nbrs(p)) for p in pts}
    node_px = set(p for p in pts if deg[p] != 2)
    cluster, clusters = {}, []
    for p in sorted(node_px):
        if p in cluster:
            continue
        group, stack = [], [p]
        cluster[p] = len(clusters)
        while stack:
            a = stack.pop()
            group.append(a)
            for b in nbrs(a):
                if b in node_px and b not in cluster and (deg[b] >= 3) == (deg[a] >= 3):
                    cluster[b] = len(clusters)
                    stack.append(b)
        clusters.append(group)
    cen = [(sum(q[0] for q in g) / float(len(g)), sum(q[1] for q in g) / float(len(g))) for g in clusters]
    isfree = [len(g) == 1 and deg[g[0]] == 1 for g in clusters]
    chains, done, visited = [], set(), set()
    for ci, g in enumerate(clusters):
        for a in g:
            for b in nbrs(a):
                if cluster.get(b) == ci:
                    continue
                path, prev, cur = [], a, b
                while cur not in cluster:
                    path.append(cur)
                    nx = [q for q in nbrs(cur) if q != prev and q not in path]
                    if not nx:
                        break
                    prev, cur = cur, nx[0]
                cj = cluster.get(cur)
                key = (frozenset(path), frozenset((ci, cj)))
                if cj is None or key in done:
                    continue
                done.add(key)
                visited.update(path)
                px = list(path) + [q for k in (ci, cj) if isfree[k] for q in clusters[k]]
                chains.append(dict(pts=[cen[ci]] + [(float(p[0]), float(p[1])) for p in path] + [cen[cj]],
                                   px=px, free=int(isfree[ci]) + int(isfree[cj])))
    rest = [p for p in pts if p not in visited and p not in cluster]       # closed loops: no end, no branch point
    while rest:
        start = min(rest)
        loop, prev, cur = [start], None, start
        while True:
            nx = [q for q in nbrs(cur) if q != prev and q not in loop]
            if not nx:
                break
            prev, cur = cur, nx[0]
            loop.append(cur)
        visited.update(loop)
        h = len(loop) // 2
        for part in (loop[:h + 1], loop[h:] + [loop[0]]):
            chains.append(dict(pts=[(float(p[0]), float(p[1])) for p in part], px=[], free=0))
        rest = [p for p in pts if p not in visited and p not in cluster]
    return chains


def clean_skeleton(sk, spur):
    """Thinned letter -> minimal skeleton without the stubs (a branch that ends free and is shorter than `spur` pixels)."""
    sk = minimal_skeleton(sk)
    for _ in range(6):
        short = [c for c in skeleton_chains(sk) if c['free'] == 1 and len(c['px']) < spur]
        if not short:
            break
        sk = sk.copy()
        for c in short:
            for (y, x) in c['px']:
                sk[y, x] = False
        sk = minimal_skeleton(sk)
    return sk


def _isect(a, b, c, d):
    """Crossing of the line a-b with the line c-d (points are (y, x)); None when they are parallel."""
    r = (b[0] - a[0], b[1] - a[1])
    q = (d[0] - c[0], d[1] - c[1])
    den = r[0] * q[1] - r[1] * q[0]
    if abs(den) < 1e-9:
        return None
    t = ((c[0] - a[0]) * q[1] - (c[1] - a[1]) * q[0]) / den
    return (a[0] + t * r[0], a[1] + t * r[1])


def sharpen(v, k):
    """Thinning rounds the corner of a thick stroke into a short diagonal (or a short flat at the foot of a V):
    a segment shorter than k between two longer ones is replaced by the crossing of its neighbours when that
    crossing is near it."""
    v = list(v)
    i = 1
    while i < len(v) - 2:
        a, b, c, d = v[i - 1], v[i], v[i + 1], v[i + 2]
        L = np.hypot(b[0] - c[0], b[1] - c[1])
        if L < k and np.hypot(a[0] - b[0], a[1] - b[1]) > L and np.hypot(c[0] - d[0], c[1] - d[1]) > L:
            x = _isect(a, b, c, d)
            if x is not None and np.hypot(x[0] - (b[0] + c[0]) / 2.0, x[1] - (b[1] + c[1]) / 2.0) <= 1.6 * L:
                v[i:i + 2] = [x]
                i = max(1, i - 1)
                continue
        i += 1
    return v


def derive_path(sk, left, top, Wd, Hd, eps, sharp=0.0):
    """Every chain of the letter's skeleton reduced to its corners (Douglas-Peucker; corners the thinning rounded
    are restored when sharp > 0), the whole figure scaled so that it fills the letter's box, and the corners
    joined by straight pixel lines. -> (set of (x, y), (kx0, kx1, ky0, ky1)) or None."""
    chains = skeleton_chains(sk)
    if not chains:
        return None
    figs = []
    for c in chains:
        verts = simplify(c['pts'], eps) if len(c['pts']) > 2 else list(c['pts'])
        figs.append(sharpen(verts, sharp) if sharp else verts)
    allp = [q for f in figs for q in f]
    ys = [p[0] for p in allp]; xs = [p[1] for p in allp]
    kx0, kx1, ky0, ky1 = min(xs), max(xs), min(ys), max(ys)
    out = set()
    # an end or corner within 0.8 pixel of the top, bottom, left or right of the letter sits exactly on that line
    # (the cap line, the baseline), so that the feet of a W or the arms of a K do not stagger by a pixel
    def snap(v, lo, hi):
        return lo if abs(v - lo) <= 0.8 else (hi if abs(v - hi) <= 0.8 else v)
    for verts in figs:
        pts = [[snap(left + (x - kx0) / float(max(1e-9, kx1 - kx0)) * (Wd - 1), left, left + Wd - 1),
                snap(top + (y - ky0) / float(max(1e-9, ky1 - ky0)) * (Hd - 1), top, top + Hd - 1)] for y, x in verts]
        # a line that is within one pixel of level (or upright) over three or more pixels is drawn level (upright)
        for a, b in zip(pts, pts[1:]):
            if abs(a[1] - b[1]) <= 1.0 and abs(a[0] - b[0]) >= 3:
                a[1] = b[1] = (a[1] + b[1]) / 2.0
            elif abs(a[0] - b[0]) <= 1.0 and abs(a[1] - b[1]) >= 3:
                a[0] = b[0] = (a[0] + b[0]) / 2.0
        pts = [(int(np.floor(x + 0.5)), int(np.floor(y + 0.5))) for x, y in pts]
        for (xa, ya), (xb, yb) in zip(pts, pts[1:]):
            out |= set(bresenham(xa, ya, xb, yb))
    return out, (kx0, kx1, ky0, ky1)


def w_glyph(width, height, foot, drop=W_PEAK_DROP):
    """The fan's W as a symmetric one pixel line figure in a width x height box (width odd), pixels (x, y) from (0, 0):
    the outer leg runs from the top corner to the foot (x = foot, bottom row), the inner stroke from the foot's upper
    pixel to the middle peak (x = width // 2, row `drop`); the right half is the mirror image of the left, so the
    figure is the same left and right."""
    if width % 2 != 1 or foot < 1 or width // 2 - foot < 2 or height < 8:
        raise MarkerError('no W for a %dx%d box with foot %d' % (width, height, foot))
    cx = width // 2
    left = set(bresenham(0, 0, foot, height - 1)) | set(bresenham(foot, height - 2, cx, drop))
    return left | set((width - 1 - x, y) for (x, y) in left)


def blocks_2x2(g):
    """Number of 2x2 squares of set pixels: where a drawn stroke is two pixels thick."""
    return sum(1 for (x, y) in g if (x + 1, y) in g and (x, y + 1) in g and (x + 1, y + 1) in g)


def stroke_iou(g, mapping, box_lt, m, wstroke):
    """Intersection over union of Capcom's letter mask and the pixel line g drawn as a stroke of the letter's own width."""
    left, top, Wd, Hd = box_lt
    kx0, kx1, ky0, ky1 = mapping
    h, w = m.shape
    yy, xx = np.mgrid[0:h, 0:w]
    cover = np.zeros((h, w), bool)
    rad = max(wstroke / 2.0, 3.0) + 1.0
    for (x, y) in g:
        X = kx0 + (x - left) / float(max(1, Wd - 1)) * (kx1 - kx0)
        Y = ky0 + (y - top) / float(max(1, Hd - 1)) * (ky1 - ky0)
        cover |= (xx - X) ** 2 + (yy - Y) ** 2 <= rad * rad
    return float((cover & m).sum()) / max(1, int((cover | m).sum()))


def derive_glyph(cov, c, box):
    """Capcom's letter (coverage in the circle c) as a one pixel line in DS pixels. box = the DS circle
    (x0, x1, y0, y1) in the coordinates of the result. -> (set of (x, y), (left, top, width, height))."""
    m = cov > 0.5
    ys, xs = np.nonzero(m)
    if len(ys) < 40:
        raise MarkerError('no letter in the circle')
    L, R, T, B = xs.min(), xs.max(), ys.min(), ys.max()
    sk0 = thin(m)
    wstroke = m.sum() / float(max(1, sk0.sum()))
    x0, x1, y0, y1 = box
    Dw = x1 - x0 + 1
    s = Dw / float(c['w'])
    ccx, ccy = (c['w'] - 1) / 2.0, (c['h'] - 1) / 2.0
    dcx, dcy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    Wd = int(round((R - L + 1) * s))
    Hd = int(round((B - T + 1) * s))
    mx = ((L + R) / 2.0 - ccx) * s + dcx
    my = ((T + B) / 2.0 - ccy) * s + dcy
    left = int(np.floor(mx - (Wd - 1) / 2.0 + 0.5))
    top = int(np.floor(my - (Hd - 1) / 2.0 + 0.5))
    # candidates: the skeleton of the letter (stubs removed) as straight pixel lines through its corners, for several
    # corner tolerances, with and without the corners restored; the one whose stroke covers Capcom's letter best wins
    sk = clean_skeleton(sk0, 1.6 * wstroke)
    cands = []
    for eps in PATH_EPS:                                   # small to large tolerance
        for sharp in (0.0, 2.0 * wstroke):
            r = derive_path(sk, left, top, Wd, Hd, eps, sharp)
            if r and r[0]:
                g, mapping = r
                cands.append((stroke_iou(g, mapping, (left, top, Wd, Hd), m, wstroke) - BLOCK_COST * blocks_2x2(g), eps, sharp, g, mapping))
    # the simplest figure (largest tolerance, fewest pixels) among those that cover Capcom's letter nearly as well as the best
    top_iou = max(k[0] for k in cands) if cands else 0
    ok = [k for k in cands if k[0] >= top_iou - IOU_SLACK]
    if not ok:
        raise MarkerError('no skeleton for the letter')
    score0, _eps, _sharp, best, mapping = sorted(ok, key=lambda k: (-k[1], -k[2], -k[0]))[0]
    iou0 = stroke_iou(best, mapping, (left, top, Wd, Hd), m, wstroke)
    # a letter that is the same left and right (A, H, W) is drawn the same left and right, from the better half
    mm = m[:, L:R + 1]
    if (mm & mm[:, ::-1]).sum() / float(max(1, (mm | mm[:, ::-1]).sum())) >= SYM_IOU:
        gl, gr = min(p[0] for p in best), max(p[0] for p in best)
        halves = [set((x, y) for (x, y) in best if 2 * x <= gl + gr), set((x, y) for (x, y) in best if 2 * x >= gl + gr)]
        sym = [h | set((gl + gr - x, y) for (x, y) in h) for h in halves]
        scored = [(stroke_iou(g, mapping, (left, top, Wd, Hd), m, wstroke), g) for g in sym]
        iou1, g1 = max(scored, key=lambda t: t[0])
        if iou1 >= iou0 - 0.02:
            best = g1
    return best, (left, top, Wd, Hd)


# ---------------------------------------------------------------------------
# DS side: the sprite sheet of an entry, with a write path into the tile data
# ---------------------------------------------------------------------------
class Entry(object):
    def __init__(self, blob, parts):
        o = struct.unpack_from('<3I', blob, 0)
        self.blob, self.o = blob, o
        self.B = rn.Bundle(blob[o[0]:o[1]], blob[o[2]:])
        if len(parts) != len(self.B.cells):
            raise MarkerError('cell list has %d cells, the DS entry %d' % (len(parts), len(self.B.cells)))
        h, w = SHEET_H, SHEET_W
        self.idx = np.full((h, w), -1, np.int32)
        self.bank = np.zeros((h, w), np.int32)
        self.off = np.full((h, w), -1, np.int64)
        self.nib = np.zeros((h, w), np.int8)
        self.tile_of_px = np.full((h, w), -1, np.int64)
        self.srcs = collections.defaultdict(set)       # tile -> set of (SrcX, SrcY, w, h)
        self.uses = collections.Counter()              # tile -> OBJs that draw it, in all cells
        self.matched = collections.Counter()           # tile -> OBJs of those that have a Capcom rectangle
        seen = set()
        for k, objs in enumerate(self.B.cells):
            plist = list(parts[k])
            for ob in objs:
                self.uses[ob['tile']] += 1
                hit = None
                for p in plist:
                    if (p['DestX'], p['DestY'], p['Width'], p['Height']) == (ob['x'], ob['y'], ob['w'], ob['h']):
                        hit = p
                        break
                if hit is None:
                    continue
                plist.remove(hit)
                self.matched[ob['tile']] += 1
                sx, sy = int(hit['SrcX']), int(hit['SrcY'])
                self.srcs[ob['tile']].add((sx, sy, ob['w'], ob['h'], ob['hflip'], ob['vflip']))
                key = (ob['tile'], sx, sy, ob['w'], ob['h'])
                if key in seen:
                    continue
                seen.add(key)
                for py in range(ob['h']):
                    for px in range(ob['w']):
                        t, tx, ty = self.B.tile_of(ob, px, py)
                        v = self.B.rgcn[self.B.tile_off + t * 32 + ty * 4 + tx // 2]
                        if 0 <= sy + py < h and 0 <= sx + px < w:
                            self.idx[sy + py, sx + px] = (v >> 4) if tx & 1 else (v & 15)
                            self.bank[sy + py, sx + px] = ob['pal']
                            self.off[sy + py, sx + px] = self.B.tile_off + t * 32 + ty * 4 + tx // 2
                            self.nib[sy + py, sx + px] = tx & 1
                            self.tile_of_px[sy + py, sx + px] = ob['tile']

    def write_pixel(self, x, y, v):
        off = self.off[y, x]
        if off < 0:
            raise MarkerError('sheet pixel (%d,%d) is not drawn by any OBJ' % (x, y))
        t = int(self.tile_of_px[y, x])
        if self.uses[t] != self.matched[t]:
            raise MarkerError('tile %d is drawn by %d OBJs that have no Capcom rectangle; cannot change it for one marker' % (t, self.uses[t] - self.matched[t]))
        if len(self.srcs[t]) != 1:
            raise MarkerError('tile %d is drawn for %d different Capcom rectangles; cannot change it for one marker' % (t, len(self.srcs[t])))
        b = self.B.new[off]
        self.B.new[off] = ((b & 0x0F) | (v << 4)) if self.nib[y, x] else ((b & 0xF0) | v)
        self.idx[y, x] = v


def _render_cell(B, k, data):
    """The cell drawn like the hardware: the first OBJ on top, index 0 of an OBJ transparent. -> (index grid, the
    tile pixel (byte * 2 + nibble) each pixel comes from, -1 where nothing is drawn)."""
    x0, y0, x1, y1 = B.bbox(k)
    val = np.zeros((y1 - y0, x1 - x0), np.int32)
    src = np.full(val.shape, -1, np.int64)
    for o in reversed(B.cells[k]):
        for py in range(o['h']):
            for px in range(o['w']):
                t, tx, ty = B.tile_of(o, px, py)
                off = B.tile_off + t * 32 + ty * 4 + tx // 2
                v = (data[off] >> 4) if tx & 1 else (data[off] & 15)
                if v:
                    val[o['y'] - y0 + py, o['x'] - x0 + px] = v
                    src[o['y'] - y0 + py, o['x'] - x0 + px] = off * 2 + (tx & 1)
    return val, src


def check_cells(E, written):
    """Render every cell before and after (transparency as on the hardware); the cells may differ only in pixels
    that come from a tile pixel this module wrote. -> (cells that differ, pixels that differ in them)."""
    tiles_changed = set()
    for (x, y) in written:
        tiles_changed.add(int(E.off[y, x]) * 2 + int(E.nib[y, x]))
    B = E.B
    before, after = bytes(B.rgcn), bytes(B.new)
    cells_changed = 0
    total = 0
    for k, objs in enumerate(B.cells):
        if not objs:
            continue
        v0, s0 = _render_cell(B, k, before)
        v1, s1 = _render_cell(B, k, after)
        for yy, xx in zip(*np.nonzero(s0 != s1)):          # a pixel that became (or stopped being) transparent: both ends written
            if not all(int(q) == -1 or int(q) in tiles_changed for q in (s0[yy, xx], s1[yy, xx])):
                raise MarkerError('cell %d: pixel (%d,%d) now comes from another tile pixel' % (k, xx, yy))
        d = v0 != v1
        for yy, xx in zip(*np.nonzero(d)):
            if int(s0[yy, xx]) not in tiles_changed and int(s1[yy, xx]) not in tiles_changed:
                raise MarkerError('cell %d: pixel (%d,%d) changed but is not a written pixel' % (k, xx, yy))
        n = int(d.sum())
        if n:
            cells_changed += 1
            total += n
    return cells_changed, total


# ---------------------------------------------------------------------------
# the entry point
# ---------------------------------------------------------------------------
def _blur(a):
    k = np.array([0.25, 0.5, 0.25])
    p = np.pad(a, 1)
    a1 = sum(k[i] * p[i:i + a.shape[0], 1:-1] for i in range(3))
    p = np.pad(a1, 1)
    return sum(k[i] * p[1:-1, i:i + a.shape[1]] for i in range(3))


def _ncc(a, b):
    a, b = a - a.mean(), b - b.mean()
    d = np.sqrt((a * a).sum() * (b * b).sum())
    return float((a * b).sum() / d) if d else 0.0


def coverage_on_sheet(cov, c, box):
    """Capcom's letter coverage area-averaged onto the DS grid of the circle box, 2 pixels of margin."""
    x0, x1, y0, y1 = box
    w, h = x1 - x0 + 1, y1 - y0 + 1
    out = np.zeros((h + 4, w + 4))
    for yy in range(h + 4):
        for xx in range(w + 4):
            ax0 = max(int(round((x0 - 2 + xx) * SC)) - c['x'], 0)
            ay0 = max(int(round((y0 - 2 + yy) * SC)) - c['y'], 0)
            ax1 = min(int(round((x0 - 1 + xx) * SC)) - c['x'], c['w'])
            ay1 = min(int(round((y0 - 1 + yy) * SC)) - c['y'], c['h'])
            if ax1 > ax0 and ay1 > ay0:
                out[yy, xx] = cov[ay0:ay1, ax0:ax1].mean()
    return out


def letter_ncc(letter, cov, c, box):
    """letter: set of DS sheet pixels. Normalised correlation with Capcom's letter, blurred, best of nine shifts."""
    x0, x1, y0, y1 = box
    A = _blur(coverage_on_sheet(cov, c, box))
    B = np.zeros_like(A)
    for (x, y) in letter:
        if 0 <= y - (y0 - 2) < B.shape[0] and 0 <= x - (x0 - 2) < B.shape[1]:
            B[y - (y0 - 2), x - (x0 - 2)] = 1
    B = _blur(B)
    return max(_ncc(np.roll(np.roll(A, dy, 0), dx, 1), B) for dx in (-1, 0, 1) for dy in (-1, 0, 1))


def eight_connected(mask, seeds):
    """The pixels of `mask` that are 8-connected, through mask pixels, to a mask pixel in `seeds`."""
    h, w = mask.shape
    out = np.zeros((h, w), bool)
    stack = [(int(y), int(x)) for y, x in zip(*np.nonzero(mask & seeds))]
    for y, x in stack:
        out[y, x] = True
    while stack:
        y, x = stack.pop()
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                yy, xx = y + dy, x + dx
                if 0 <= yy < h and 0 <= xx < w and mask[yy, xx] and not out[yy, xx]:
                    out[yy, xx] = True
                    stack.append((yy, xx))
    return out


def has_block(white):
    """A one pixel stroke letter has at most one 2x2 white block (measured 0 or 1); the chess pieces have 23 or more."""
    return int((white[:-1, :-1] & white[1:, :-1] & white[:-1, 1:] & white[1:, 1:]).sum()) >= 4


def analyse(E, pal, atlas):
    """-> list of marker dicts for one entry (nothing is written)."""
    res = []
    for i, c in enumerate(capcom_circles(atlas)):
        x0, y0 = int(round(c['x'] / SC)), int(round(c['y'] / SC))
        bw, bh = int(round(c['w'] / SC)), int(round(c['h'] / SC))
        box = (x0, x0 + bw - 1, y0, y0 + bh - 1)         # DS circle on the sheet
        sub = E.idx[y0:y0 + bh, x0:x0 + bw]
        if (sub < 0).mean() > 0.3:
            res.append(dict(i=i, box=box, kind='not on the DS sheet'))
            continue
        rgbv = np.zeros(sub.shape + (3,), int)
        for yy in range(sub.shape[0]):
            for xx in range(sub.shape[1]):
                v = int(sub[yy, xx])
                if v > 0:
                    pi = v + 16 * int(E.bank[y0 + yy, x0 + xx])
                    rgbv[yy, xx] = pal[pi] if pi < len(pal) else (255, 0, 255)
        cx, cy = (bw - 1) / 2.0, (bh - 1) / 2.0
        yy, xx = np.mgrid[0:bh, 0:bw]
        interior = np.hypot(xx - cx, yy - cy) < bw / 2.0 - 2.5
        cov = capcom_coverage(atlas, c)
        cap_letter = int((cov > 0.5).sum()) >= 40
        dark_mode = False
        if not cap_letter:                               # no white letter: a dark one on a light circle?
            covd = capcom_coverage(atlas, c, dark=True)
            if int((covd > 0.5).sum()) >= 40:
                cov, cap_letter, dark_mode = covd, True, True
        if dark_mode:
            white = (rgbv.max(-1) < DARK_LETTER) & (sub > 0) & interior
            dark_inside = 0
        else:
            white = (rgbv.min(-1) >= 230) & (sub > 0)
            dark_inside = int(((rgbv.max(-1) < RIM_DARK) & (sub > 0) & interior).sum())
        nw = int(white.sum())
        m = dict(i=i, box=box, ds_white=nw, cap_letter=cap_letter, c=c, cov=cov)
        wy, wx = np.nonzero(white)
        m['ds_letter'] = set((int(x + x0), int(y + y0)) for x, y in zip(wx, wy))
        ys_, xs_ = np.nonzero(interior & ~white & (sub > 0))
        cols = collections.Counter(int(sub[y, x]) for y, x in zip(ys_, xs_))
        m['fill'] = cols.most_common(1)[0][0] if cols else None
        if not cap_letter:
            m['kind'] = 'blank in Capcom' if nw == 0 else 'DS letter, Capcom blank'
        elif dark_inside > 6 or nw > LETTER_PX[1] or has_block(white):
            # a chess piece where Capcom has a letter (the retail marker carries a kanji there, so the fan's piece is not the
            # game's own symbol): the piece is erased and Capcom's letter takes its place
            bank = int(np.bincount(E.bank[y0:y0 + bh, x0:x0 + bw][sub > 0]).argmax())
            piece = (sub > 0) & (rgbv.min(-1) >= 230)                       # white pieces
            dark = (sub > 0) & (rgbv.max(-1) < RIM_DARK)                    # the rim's outline, and black pieces inside it
            ring = eight_connected(dark, np.hypot(xx - cx, yy - cy) >= bw / 2.0 - 1.5)
            piece |= dark & ~ring                                           # a dark pixel that is not joined to the outline
            piece &= ~(np.hypot(xx - cx, yy - cy) >= bw / 2.0 - 1.5)
            for yy_, xx_ in zip(*np.nonzero(piece)):
                if sub[yy_, xx_] == m['fill']:
                    raise MarkerError('marker %d (circle %r): the fill colour is part of the piece' % (i, box))
            if int(piece.sum()) < 40:
                raise MarkerError('marker %d: no piece found' % i)
            wh = collections.Counter()
            for k in range(1, 16):
                if 16 * bank + k < len(pal) and min(pal[16 * bank + k]) >= 240:
                    wh[k] = int((E.idx[E.bank == bank] == k).sum())
            if not wh:
                raise MarkerError('marker %d: no white in the palette bank %d' % (i, bank))
            py_, px_ = np.nonzero(piece)
            m['ds_letter'] = set((int(x + x0), int(y + y0)) for x, y in zip(px_, py_))
            m['white_idx'] = wh.most_common(1)[0][0]
            glyph, tb = derive_glyph(cov, c, box)
            m['glyph'], m['derived'], m['target'], m['source'] = glyph, glyph, tb, "drawn from Capcom's letter"
            m['ncc'] = 0.0
            m['kind'] = 'piece'
        elif nw < LETTER_PX[0]:
            m['kind'] = 'DS blank, Capcom letter'
        else:
            glyph, tb = derive_glyph(cov, c, box)
            m['glyph'], m['derived'], m['target'], m['source'] = glyph, glyph, tb, "drawn from Capcom's letter"
            m['ncc'] = letter_ncc(m['ds_letter'], cov, c, box)
            m['kind'] = 'same' if m['ncc'] >= SAME_NCC else 'differs'
            wcols = collections.Counter(int(E.idx[y, x]) for (x, y) in m['ds_letter'])
            m['white_idx'] = wcols.most_common(1)[0][0]
        res.append(m)
    return res


def fan_letters(all_markers):
    """Every letter the fan's own markers carry: {(circle w, h): [(pixels relative to the circle's corner, (entry, marker))]}.
    Taken from the unchanged fan sprites; the same letter drawn twice is listed once."""
    lib, seen = collections.defaultdict(list), set()
    for e, markers in sorted(all_markers.items()):
        for m in markers:
            if m['kind'] not in ('same', 'differs') or not m.get('ds_letter'):
                continue
            x0, x1, y0, y1 = m['box']
            rel = frozenset((x - x0, y - y0) for (x, y) in m['ds_letter'])
            key = ((x1 - x0 + 1, y1 - y0 + 1), rel)
            if key not in seen:
                seen.add(key)
                lib[key[0]].append((rel, (e, m['i'])))
    return lib


def baselines(lib):
    """The row (relative to the circle's top) on which the fan's letters stand, per circle size: the most common bottom row."""
    out = {}
    for size, items in lib.items():
        cnt = collections.Counter(max(y for _x, y in rel) for rel, _src in items)
        out[size] = cnt.most_common(1)[0][0]
    return out


def _unmatched(a, b):
    """How many pixels of a are further than one pixel (in either direction) from every pixel of b."""
    return sum(1 for (x, y) in a if not any(max(abs(x - u), abs(y - v)) <= 1 for (u, v) in b))


def graft(m, g, items, x0, y0, baseline):
    """A letter the fan's face lacks but that is a fan letter with a different tail (R is P with a leg): the rows
    of a fan letter that agree with the drawn letter (within one pixel, both ways) are taken from the fan's glyph,
    which carries the fan's rounded corners, and the rows below from the drawn one. Used only if it resembles
    Capcom's letter clearly better than the drawn letter alone. -> (pixels, source text, ncc) or None."""
    base_ncc = letter_ncc(g, m['cov'], m['c'], m['box'])
    best = None
    rows = sorted(set(y for _x, y in g))
    for rel, src in items:
        f = set((x0 + rx, y0 + ry) for rx, ry in rel)
        if f == m['ds_letter'] or (baseline is not None and max(y for _x, y in f) != y0 + baseline):
            continue
        if letter_ncc(f, m['cov'], m['c'], m['box']) < GRAFT_NCC:
            continue
        # u(y): pixels of the drawn letter down to row y that the fan glyph does not reach; the rows agree while u stays at its
        # level four rows in (the fan's rounded corner costs a pixel or two at the top), the strokes the fan glyph lacks then raise it
        us = [(y, _unmatched(set(p for p in g if p[1] <= y), set(p for p in f if p[1] <= y)),
               _unmatched(set(p for p in f if p[1] <= y), set(p for p in g if p[1] <= y))) for y in rows]
        if len(us) < 6:
            continue
        k0, kv = min(u for _y, u, _v in us[3:]), min(v for _y, _u, v in us[3:])
        r = None
        for y, u, v in us:
            if y >= rows[3] and u <= k0 and v <= kv:
                r = y
            elif r is not None:
                break
        if r is None or r - min(rows) < 3 or r >= max(rows) - 1:
            continue
        comp = set(p for p in f if p[1] <= r) | set(p for p in g if p[1] > r)
        n = letter_ncc(comp, m['cov'], m['c'], m['box'])
        if n >= base_ncc - 0.05 and (best is None or n > best[0]):
            best = (n, comp, src)
    if best:
        return best[1], "the fan's own letter (entry %d marker %d) down to the bowl, Capcom's strokes below" % best[2], best[0]
    return None


def adapted_glyph(spec, m, lib, base):
    """A letter from the fan's own strokes (see ADAPT). -> (pixels, source text)."""
    x0, x1, y0, y1 = m['box']
    size = (x1 - x0 + 1, y1 - y0 + 1)
    if size not in base:
        raise MarkerError('no baseline for circles of size %r' % (size,))
    bottom = y0 + base[size]
    if spec[0] == 'W':
        _, width, height, foot = spec
        left = x0 + size[0] // 2 - (width - 1) // 2
        top = bottom - (height - 1)
        return set((left + x, top + y) for (x, y) in w_glyph(width, height, foot)), "the fan's W construction, %dx%d" % (width, height)
    if spec[0] == 'A':
        src = [rel for items in lib.values() for rel, s_ in items if s_ == spec[1]]
        if len(src) != 1:
            raise MarkerError('the fan letter of entry %d marker %d is not in the library' % spec[1])
        rows = sorted(set(y for _x, y in src[0]))
        pat = [tuple(sorted(x for x, y in src[0] if y == r)) for r in rows]
        if len(rows) < 10 or not (pat[-1] == pat[-2] == pat[-3]):
            raise MarkerError('the fan letter of entry %d marker %d has no three equal foot rows' % spec[1])
        keep = rows[:-2] + rows[-1:]
        if len(keep) > size[1] - 4:
            raise MarkerError('the fan A does not fit a circle of size %r' % (size,))
        xs = [x for x, _y in src[0]]
        w = max(xs) - min(xs) + 1
        left = x0 + (size[0] - w) // 2 - min(xs)
        out = set()
        for j, r in enumerate(keep):
            for x, y in src[0]:
                if y == r:
                    out.add((left + x, bottom - (len(keep) - 1 - j)))
        return out, "the fan's own A (entry %d marker %d), foot rows 3 to 2" % spec[1]
    raise MarkerError('unknown adapted letter %r' % (spec,))


def settle_letters(markers, lib, base, entry=None):
    """For every marker whose letter must change, decide the pixels.
    1. The letter drawn from Capcom's is put on the baseline of the fan's letters of that circle size (it is
       moved by one row at most; Capcom centres its letters a little higher than the fan's face does).
    2. If the fan's own face already has this letter (a glyph of a circle of the same size, standing on the
       baseline, that matches Capcom's letter as a same letter does and lies within one pixel of the drawn
       letter except for at most two pixels each way) the sprite takes the fan's own pixels."""
    for m in markers:
        if m['kind'] not in ('differs', 'piece'):
            continue
        if (entry, m['i']) in ADAPT:
            m['glyph'], m['source'] = adapted_glyph(ADAPT[(entry, m['i'])], m, lib, base)
            continue
        x0, x1, y0, y1 = m['box']
        size = (x1 - x0 + 1, y1 - y0 + 1)
        g = m['derived']
        if size in base:
            d = (y0 + base[size]) - max(y for _x, y in g)
            if d and abs(d) <= 1:
                g = set((x, y + d) for (x, y) in g)
                m['derived'] = m['glyph'] = g
        best = None
        for rel, src in lib.get(size, []):
            f = set((x0 + rx, y0 + ry) for rx, ry in rel)
            if f == m['ds_letter'] or (size in base and max(y for _x, y in f) != y0 + base[size]):
                continue
            if _unmatched(g, f) > 2 or _unmatched(f, g) > 2:
                continue
            n = letter_ncc(f, m['cov'], m['c'], m['box'])
            if n >= SAME_NCC and (best is None or n > best[0]):
                best = (n, f, src)
        if best:
            m['glyph'], m['source'] = best[1], "the fan's own letter (entry %d marker %d)" % best[2]
            m['lib_ncc'] = best[0]
        else:
            gr = graft(m, g, lib.get(size, []), x0, y0, base.get(size))
            if gr:
                m['glyph'], m['source'], m['lib_ncc'] = gr


def apply_entry(E, markers, log=None):
    """Replace the letters (and the chess pieces) of the markers whose kind is 'differs' or 'piece'.
    -> (pixels written, markers changed)."""
    written = []
    changed = 0
    for m in markers:
        if m['kind'] not in ('differs', 'piece'):
            continue
        old, new = m['ds_letter'], m['glyph']
        x0, x1, y0, y1 = m['box']
        for (x, y) in new:
            if not (x0 + 2 <= x <= x1 - 2 and y0 + 2 <= y <= y1 - 2):
                raise MarkerError('entry marker %d: glyph pixel (%d,%d) is outside the circle %r' % (m['i'], x, y, m['box']))
            if (x, y) not in old and E.idx[y, x] != m['fill']:
                raise MarkerError('marker %d: glyph pixel (%d,%d) would land on index %d, not the fill' % (m['i'], x, y, E.idx[y, x]))
        for (x, y) in old - new:
            E.write_pixel(x, y, m['fill'])
            written.append((x, y))
        for (x, y) in sorted(new):
            if E.idx[y, x] != m['white_idx']:
                E.write_pixel(x, y, m['white_idx'])
                written.append((x, y))
        changed += 1
    return written, changed


def analyse_all(co_bytes, dumpdir):
    """Read every marker of the 13 entries and decide each letter. -> (blobs, entries, markers per entry)."""
    co = Idlocal(co_bytes)
    blobs = []
    for e in range(co.n):
        try:
            blobs.append(co.blob(e) if co.ents[e][0] else b'')
        except Exception:
            blobs.append(b'')
    if ih.GUARD_INPUTS:
        for e in sorted(ih.MARKER_INPUT_SHA256):
            if ih.sha(blobs[e]) not in ih.MARKER_INPUT_SHA256[e]:
                raise MarkerError("jpn/cutobj_local.bin entry %d is not the fan's (or what the earlier steps leave of it)" % e)
    ents, per = {}, {}
    for e, name in sorted(NAMES.items()):
        atlas, parts = load_capcom(dumpdir, name)
        E = Entry(blobs[e], parts)
        _, pal = gv.palette_of(blobs, e, 'after')
        ents[e] = E
        per[e] = analyse(E, pal, atlas)
    lib = fan_letters(per)
    base = baselines(lib)
    for e in sorted(ents):
        settle_letters(per[e], lib, base, e)
    return blobs, ents, per


def patch_cutobj(co_bytes, dumpdir, log=None):
    """-> (new cutobj_local bytes, report, per entry markers)."""
    blobs, ents, per = analyse_all(co_bytes, dumpdir)
    repl, report = {}, {}
    for e in sorted(ents):
        E = ents[e]
        written, changed = apply_entry(E, per[e])
        if written:
            cells, total = check_cells(E, written)
            nb = blobs[e][:E.o[2]] + E.B.result()
            if len(nb) != len(blobs[e]):
                raise MarkerError('entry %d changed size' % e)
            repl[e] = nb
            report[e] = dict(markers=changed, tile_pixels=len(written), cells_changed=cells, cell_pixels=total)
    if not repl:
        return co_bytes, report, per
    out = rebuild(co_bytes, repl, lz=tuple(sorted(repl)))
    return out, report, per


# The markers whose letter this module replaces, entry -> marker numbers (reading order of Capcom's circles on the sheet).
# A different base ROM would give a different list: the build stops instead of drawing something else.
EXPECTED = {2: [0, 1], 4: [1, 2], 6: [0, 2, 3], 8: [1], 10: [0, 1], 16: [0, 1, 2, 3, 4], 20: [0, 1], 22: [0, 1],
            24: [0, 1, 2, 3, 4, 5, 6], 26: [0, 1]}


def changed_markers(per):
    return {e: [m['i'] for m in ms if m['kind'] in ('differs', 'piece')] for e, ms in per.items()
            if any(m['kind'] in ('differs', 'piece') for m in ms)}


def apply_to_rom(rom, dumpdir, log=None, any_rom=False):
    """Put Capcom's letters into the markers of jpn/cutobj_local.bin inside a ROM image: returns (rom, changed).
    Run after the step that re-letters entry 26 (tools/bigg_building.py)."""
    import title_logo
    log = log or (lambda s: None)
    try:
        co = rom_file(rom, 'jpn/cutobj_local.bin')
        new, report, per = patch_cutobj(co, dumpdir)
        got = changed_markers(per)
        if got != EXPECTED:
            raise MarkerError('the markers to change are %r, expected %r' % (got, EXPECTED))
    except MarkerError as e:
        if not any_rom:
            raise MarkerError('%s (pass --any-rom to build without the marker letters)' % e)
        log('marker letters: NOT redrawn, --any-rom given (%s)' % e)
        return rom, False
    for e in sorted(report):
        r = report[e]
        log('marker letters (cutobj_local entry %d): %d markers, %d tile pixels, %d cells differ by %d pixels' % (
            e, r['markers'], r['tile_pixels'], r['cells_changed'], r['cell_pixels']))
    return title_logo.splice(rom, 'jpn/cutobj_local.bin', new), True
