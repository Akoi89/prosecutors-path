# -*- coding: utf-8 -*-
"""The temperatures on the Zodiac Hall information board (jpn/upcut_local.bin entry 116).

The board shows four rooms, each with two lines in the fan's green digit face on a dim circle: the Fahrenheit figure
(79 F, 64 F, 54 F, 27 F) and under it the Celsius one (26 C, 18 C, 12 C, -3 C). Capcom's picture (cut02_011_eng) gives
78 F, 64 F, 53 F, 27 F and no Celsius lines. This module

  1. takes the eight lines off the picture. The ground under them is the circle (flat, or a boundary between two flat
     colours) and a few stars, so it is rebuilt from the picture's own pixels: every pixel of the lines (their ink and
     their two pixel outline) is replaced by what the nearest ground pixels left and right, or above and below, agree
     on (the nearer pair when both pairs agree), twice, the second time with only the pixels that really differ from
     the first estimate, so ground that was never under the lettering keeps its own pixels and the circle's edge keeps
     its shape;
  2. changes the 9 of 79 to an 8 and the 4 of 54 to a 3, with the glyphs of the fan's own 18 C and -3 C (same size,
     same colours, same outline; the digit is set as the old one was, right edge on the old right edge, one blank
     column before the degree sign);
  3. puts the four Fahrenheit lines back, each centred vertically on the rows the two lines filled (6 rows lower).

Only the tile data of the picture entry changes; palette, decoded size and every other entry stay the fan's. numpy only.
"""
import numpy as np


class BoardError(ValueError):
    pass


ZONE = (72, 136, 100, 170)                    # y0, y1, x0, x1 of the four temperature cells
# per quadrant: x range of the cell, the last row of the Fahrenheit line's pixels (its two pixel outline included; what
# lies below belongs to the Celsius line), and the digit swap (erase columns, source quadrant, source columns, dx)
QUADS = {
    'TL': dict(x=(100, 128), split=90, swap=dict(erase=(110, 114), src='TR', cols=(136, 140), dx=-26)),
    'TR': dict(x=(129, 160), split=90, swap=None),
    'BL': dict(x=(100, 128), split=119, swap=dict(erase=(110, 114), src='BR', cols=(136, 139), dx=-25)),
    'BR': dict(x=(129, 160), split=119, swap=None),
}
ROWS = {'T': (72, 104), 'B': (106, 136)}      # rows of the upper and the lower cells (the blue divider lies between)
SHIFT = 6                                     # rows: (21 rows the two lines filled - 9 rows of a figure) / 2
LINE_GAP = 12                                 # rows from a Fahrenheit line to the Celsius line under it


def _bridge(g, mask):
    H, W = g.shape
    out = g.copy()

    def nearest(y, x, dy, dx):
        d = 1
        while True:
            yy, xx = y + dy * d, x + dx * d
            if not (0 <= yy < H and 0 <= xx < W):
                return None
            if not mask[yy, xx]:
                return d, int(g[yy, xx])
            d += 1

    for y, x in zip(*np.nonzero(mask)):
        L, R, U, D = nearest(y, x, 0, -1), nearest(y, x, 0, 1), nearest(y, x, -1, 0), nearest(y, x, 1, 0)
        cand = []
        if L and R and L[1] == R[1]:
            cand.append((L[0] + R[0], L[1]))
        if U and D and U[1] == D[1]:
            cand.append((U[0] + D[0], U[1]))
        if cand:
            out[y, x] = min(cand)[1]
        else:
            near = [c for c in (L, R, U, D) if c]
            if not near:
                raise BoardError('no ground pixel left to fill (%d,%d)' % (x, y))
            out[y, x] = min(near)[1]
    return out


def _dilate(m, r):
    out = np.zeros_like(m)
    H, W = m.shape
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            ys0, ys1 = max(0, dy), min(H, H + dy)
            xs0, xs1 = max(0, dx), min(W, W + dx)
            out[ys0 - dy:ys1 - dy, xs0 - dx:xs1 - dx] |= m[ys0:ys1, xs0:xs1]
    return out


def patch(grid, pal):
    """grid: the picture's index grid (192 x 256); pal: its palette (RGB triples). -> the new index grid."""
    g0 = np.asarray(grid, np.int32)
    P = np.array(pal, np.int64)
    rgb = P[g0]
    zy0, zy1, zx0, zx1 = ZONE
    zone = np.zeros(g0.shape, bool)
    zone[zy0:zy1, zx0:zx1] = True
    ink = ((rgb[..., 1] - rgb[..., 2]) >= 20) & (rgb[..., 1] >= 100) & zone
    divider = (rgb[..., 2] >= 200) & (rgb[..., 0] < 60)
    mask1 = _dilate(ink, 2) & zone & ~divider
    ground = _bridge(g0, mask1)
    mask = mask1 & (g0 != ground)
    ground = _bridge(g0, mask)
    mask = mask1 & (g0 != ground)
    ground = _bridge(g0, mask)
    # the layers: every pixel of the lines, with the index it has, per quadrant, Fahrenheit and Celsius apart
    F, C = {}, {}
    for q, spec in QUADS.items():
        ry0, ry1 = ROWS[q[0]]
        x0, x1 = spec['x']
        f, c = {}, {}
        for y, x in zip(*np.nonzero(mask)):
            if ry0 <= y < ry1 and x0 <= x < x1:
                (f if y <= spec['split'] else c)[(int(y), int(x))] = int(g0[y, x])
        n_ink = int(ink[ry0:ry1, x0:x1].sum())
        if len(f) < 100 or len(c) < 80 or n_ink < 150:
            raise BoardError('quadrant %s: the temperature lines are not where the routine expects (%d, %d, %d pixels)' % (q, len(f), len(c), n_ink))
        F[q], C[q] = f, c
    # the digit swaps: the glyph of the fan's Celsius line in place of the old digit
    for q, spec in QUADS.items():
        sw = spec['swap']
        if not sw:
            continue
        e0, e1 = sw['erase']
        F[q] = {p: v for p, v in F[q].items() if not (e0 <= p[1] <= e1)}
        c0, c1 = sw['cols']
        got = 0
        for (y, x), v in C[sw['src']].items():
            if c0 <= x <= c1:
                F[q][(y - LINE_GAP, x + sw['dx'])] = v
                got += 1
        if got < 25:
            raise BoardError('quadrant %s: the glyph taken from %s has only %d pixels' % (q, sw['src'], got))
    out = ground.copy()
    for q in QUADS:
        for (y, x), v in F[q].items():
            out[y + SHIFT, x] = v
    return out
