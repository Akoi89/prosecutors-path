# -*- coding: utf-8 -*-
"""The fan patch's own Logic-keyword lettering, harvested from the user's ROM at build time.

jpn/logic_keyword_local.bin carries the fan team's English in two pixel faces:
  style A  80x40 blue cards: white ink (index 9) with a 1px dark outline (index 8) on the
           four sides, over a diagonal blue gradient;
  style B  160x16 or 192x16 banners: white ink (index 1) on transparent.
Until 1.8.4 the port drew Capcom's names with the Collection's vector font thresholded to
one bit, squeezed long names sideways and wiped the card interior to flat bands. A tester
said the cards looked odd; side by side they did (uneven strokes, merged letters, the
gradient gone, text against the top edge).

What this module takes from the fan cards, and how each part was proven on them:
  * glyphs: every fan line listed in logic_fan_text.json is cut at its blank columns and
    the runs paired with the line's letters; the most common bitmap per letter wins.
    Re-drawn from the harvested font and the spacing rules below, 159 of 162 fan card
    lines and 93 of 100 banner lines match the fan pixel for pixel (the rest are lines
    the fan hand-tightened);
  * spacing: 1 blank column between letters, a space of 4 (cards) or 6 (banners), and a
    few letters with their own side gaps - all measured, none chosen;
  * the text-free card: per pixel, the most common index over all fan cards away from
    their text (3,198 of 3,200 pixels unanimous). Base + outline + ink rebuilds 94 of 103
    fan cards exactly; the other nine differ by 1-6 px of hand touch-up.
Letters the fan never drew are derived from ones it did: '"' is two apostrophes, '0' the
'o' stretched to digit height, 'z' drawn on the 'x' box, and the banner 'I' is its 'l'.

The fan's own text is the harvest KEY only (tools/logic_fan_text.json), the same policy as
the item labels in plates.py; every pixel comes from the user's ROM.
"""
import os, json, collections

HERE = os.path.dirname(os.path.abspath(__file__))
A_INK, A_OUTLINE, B_INK = 9, 8, 1
BLUES = {3, 4, 5, 6, 7, 8}
OUTLINE_OFFS = ((1, 0), (-1, 0), (0, 1), (0, -1))
# Fan layout, measured over its cards: baselines by line count, the widest line (x 5..75),
# and centring that rounds the odd pixel right. Three lines never occur in the fan cards;
# 10/19/28 is the tightest pitch that keeps a descender on line 3 inside the interior (rows
# 2..31). Banners: one line, baseline 12, centred in the banner's own width.
A_BASELINES = {1: [20], 2: [13, 26], 3: [10, 19, 28]}
A_BASELINES_2_NO_DESC = [14, 27]
A_MAX_W = 70
B_BASELINE = 12
B_MARGIN = 1


def _lines(m):
    H = len(m); on = [any(r) for r in m]; out, s = [], None
    for y in range(H + 1):
        v = y < H and on[y]
        if v and s is None: s = y
        if not v and s is not None: out.append((s, y)); s = None
    return out


def _runs(m, y0, y1):
    W = len(m[0]); on = [any(m[y][x] for y in range(y0, y1)) for x in range(W)]
    out, s = [], None
    for x in range(W + 1):
        v = x < W and on[x]
        if v and s is None: s = x
        if not v and s is not None: out.append((s, x)); s = None
    return out


def _interior(rows):
    blue = [(x, y) for y, r in enumerate(rows) for x, v in enumerate(r) if v in BLUES]
    if not blue:
        return None
    return (min(x for x, y in blue), min(y for x, y in blue),
            max(x for x, y in blue), max(y for x, y in blue))


def _ink_mask(rows, style):
    ink = A_INK if style == 'A' else B_INK
    m = [[1 if v == ink else 0 for v in r] for r in rows]
    if style == 'A':
        box = _interior(rows)
        if not box:
            return None
        x0, y0, x1, y1 = box
        m = [[m[y][x] if (x0 < x < x1 and y0 < y < y1) else 0 for x in range(len(r))]
             for y, r in enumerate(m)]
    return m


class Face(object):
    """One harvested pixel face: glyphs {char: (columns-as-rows bitmap, bottom offset from
    the baseline)}, letter gap, space, per-letter side gaps."""

    def __init__(self, glyphs, letter, space, side):
        self.g, self.letter, self.space, self.side = glyphs, letter, space, side

    def layout(self, text, space=None):
        sp = self.space if space is None else space
        x, out, prev = 0, [], None
        for ch in text:
            if ch == ' ':
                x += sp; prev = ' '; continue
            bm, off = self.g[ch]
            if prev not in (None, ' '):
                gap = self.letter
                if prev in self.side: gap = max(gap, self.side[prev][1])
                if ch in self.side: gap = max(gap, self.side[ch][0])
                x += gap
            out.append((x, off - len(bm), bm))
            x += len(bm[0]); prev = ch
        return out, x

    def width(self, text, space=None):
        return self.layout(text, space)[1]

    def missing(self, text):
        return sorted({c for c in text if c != ' ' and c not in self.g})


def _harvest(E, cards_of, style, keys):
    import logic_cards as L
    shapes = collections.defaultdict(collections.Counter)
    gaps = collections.Counter(); pair = collections.defaultdict(collections.Counter)
    used = 0
    for e_s, lines in keys.items():
        e = int(e_s)
        if not E[e] or E[e][:4] != L.SUB_MAGIC:
            continue
        rows = cards_of(e)
        m = _ink_mask(rows, style)
        if m is None:
            continue
        segs = _lines(m)
        for li_s, text in lines.items():
            li = int(li_s)
            if li >= len(segs):
                continue
            y0, y1 = segs[li]
            runs = _runs(m, y0, y1)
            # a key may bracket letters the fan drew touching, e.g. '33 lbs [(1]5 Kg)':
            # that run is one token, used for spacing but never as a glyph source
            letters, word_break, i = [], [], 0
            while i < len(text):
                c = text[i]
                if c == ' ':
                    i += 1; continue
                brk = i > 0 and text[i - 1] == ' '
                if c == '[':
                    j = text.index(']', i)
                    letters.append(text[i:j + 1]); i = j + 1
                else:
                    letters.append(c); i += 1
                word_break.append(brk)
            if len(runs) != len(letters):
                continue
            used += 1
            bms, bots = [], []
            for (a, b) in runs:
                col = [[m[y][x] for x in range(a, b)] for y in range(y0, y1)]
                ys = [i for i, r in enumerate(col) if any(r)]
                bms.append(col[ys[0]:ys[-1] + 1]); bots.append(y0 + ys[-1] + 1)
            base = collections.Counter(bots).most_common(1)[0][0]
            for ch, bm, bot in zip(letters, bms, bots):
                if len(ch) == 1:
                    shapes[ch][(json.dumps(bm), bot - base)] += 1
            for i in range(1, len(runs)):
                g = runs[i][0] - runs[i - 1][1]
                if word_break[i]:
                    gaps[('space', g)] += 1
                else:
                    gaps[('letter', g)] += 1
                    if len(letters[i - 1]) == 1 and len(letters[i]) == 1:
                        pair[(letters[i - 1], letters[i])][g] += 1
    glyphs = {}
    for ch, c in shapes.items():
        (bm, off), _ = c.most_common(1)[0]
        glyphs[ch] = (json.loads(bm), off)
    letter = max((n, g) for (kind, g), n in gaps.items() if kind == 'letter')[1]
    space = max((n, g) for (kind, g), n in gaps.items() if kind == 'space')[1]
    side = {}
    for ch in glyphs:
        before = collections.Counter(); after = collections.Counter()
        for (a, b), c in pair.items():
            if b == ch: before.update(c)
            if a == ch: after.update(c)
        bb = before.most_common(1)[0][0] if before else letter
        aa = after.most_common(1)[0][0] if after else letter
        if bb != letter or aa != letter:
            side[ch] = (bb, aa)
    return Face(glyphs, letter, space, side), used


def _derive(face, style):
    g = face.g
    if "'" in g and '"' not in g:
        bm, off = g["'"]
        g['"'] = ([r + [0] + r for r in bm], off)
    if 'o' in g and '3' in g and '0' not in g:
        o = [list(r) for r in g['o'][0]]; h = len(g['3'][0]); mid = len(o) // 2
        while len(o) < h:
            o.insert(mid, list(o[mid]))
        g['0'] = (o, g['3'][1])
    if 'x' in g and 'z' not in g:
        h, w = len(g['x'][0]), len(g['x'][0][0])
        z = [[0] * w for _ in range(h)]; z[0] = [1] * w; z[-1] = [1] * w
        for y in range(1, h - 1):
            z[y][round((w - 1) * (1 - y / (h - 1)))] = 1
        g['z'] = (z, g['x'][1])
    if style == 'B' and 'I' not in g and 'l' in g:
        g['I'] = ([list(r) for r in g['l'][0]], g['l'][1])


def _base(E, cards_of, rng):
    import logic_cards as L
    votes = None
    for e in rng:
        if not E[e] or E[e][:4] != L.SUB_MAGIC:
            continue
        rows = cards_of(e)
        m = _ink_mask(rows, 'A')
        if m is None:
            continue
        H, W = len(rows), len(rows[0])
        if votes is None:
            votes = [[collections.Counter() for _ in range(W)] for _ in range(H)]
        near = set()
        for y in range(H):
            for x in range(W):
                if m[y][x]:
                    for dx in (-1, 0, 1, 2):
                        for dy in (-1, 0, 1, 2):
                            near.add((x + dx, y + dy))
        for y in range(H):
            for x in range(W):
                if (x, y) not in near:
                    votes[y][x][rows[y][x]] += 1
    return [[(v.most_common(1)[0][0] if v else 0) for v in r] for r in votes]


class LogicFont(object):
    def __init__(self, E, cards_of):
        import logic_cards as L
        keys = json.load(open(os.path.join(HERE, 'logic_fan_text.json')))
        self.A, self.usedA = _harvest(E, cards_of, 'A', keys['A'])
        self.B, self.usedB = _harvest(E, cards_of, 'B', keys['B'])
        _derive(self.A, 'A'); _derive(self.B, 'B')
        self.base = _base(E, cards_of, L.A_RANGE)

    # ---- fitting ---------------------------------------------------------------
    def fit_card(self, name):
        """-> (lines, space) or (None, None). One line, then two balanced lines, then
        spaces narrowed to 3 and 2 (the fan narrowed spaces by hand, never letters), then
        three lines at the normal spacing."""
        F = self.A; words = name.split()
        for sp in (F.space, F.space - 1, F.space - 2):
            if F.width(name, sp) <= A_MAX_W:
                return [name], sp
            best = None
            for cut in range(1, len(words)):
                a, b = ' '.join(words[:cut]), ' '.join(words[cut:])
                w = max(F.width(a, sp), F.width(b, sp))
                if w <= A_MAX_W and (best is None or w < best[0]):
                    best = (w, [a, b])
            if best:
                return best[1], sp
        best = None
        for i in range(1, len(words)):
            for j in range(i + 1, len(words)):
                ls = [' '.join(words[:i]), ' '.join(words[i:j]), ' '.join(words[j:])]
                w = max(F.width(t) for t in ls)
                if w <= A_MAX_W and (best is None or w < best[0]):
                    best = (w, ls)
        return (best[1], F.space) if best else (None, None)

    def fit_banner(self, name, W):
        F = self.B
        for sp in (F.space, F.space - 1, F.space - 2):
            if F.width(name, sp) <= W - 2 * B_MARGIN:
                return sp
        return None

    # ---- drawing ---------------------------------------------------------------
    @staticmethod
    def _paint(rows, placements, x0, base, ink, outline=None, clip=None):
        pts = set()
        for x, yoff, bm in placements:
            for yy, r in enumerate(bm):
                for xx, v in enumerate(r):
                    if v: pts.add((x0 + x + xx, base + yoff + yy))
        H, W = len(rows), len(rows[0])
        cx0, cy0, cx1, cy1 = clip or (0, 0, W - 1, H - 1)
        inside = lambda X, Y: cx0 <= X <= cx1 and cy0 <= Y <= cy1
        lost = 0
        if outline is not None:
            for (x, y) in pts:
                for dx, dy in OUTLINE_OFFS:
                    X, Y = x + dx, y + dy
                    if (X, Y) not in pts and inside(X, Y):
                        rows[Y][X] = outline
        for (x, y) in pts:
            if inside(x, y): rows[y][x] = ink
            else: lost += 1
        return lost

    def draw_card(self, rows, name):
        """Repaint a style-A card: fan base inside the blue interior, then the name.
        Returns a log line, or None if the name has letters the face lacks / does not fit."""
        if self.A.missing(name):
            return None
        box = _interior(rows)
        if not box:
            return None
        lines, sp = self.fit_card(name)
        if not lines:
            return None
        x0, y0, x1, y1 = box
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                rows[y][x] = self.base[y][x]
        W = len(rows[0])
        if len(lines) == 2 and not any(self.A.g[c][1] > 0 for c in lines[0] if c != ' '):
            bases = A_BASELINES_2_NO_DESC
        else:
            bases = A_BASELINES[len(lines)]
        lost = 0
        for t, b in zip(lines, bases):
            pl, w = self.A.layout(t, sp)
            lost += self._paint(rows, pl, (W - w + 1) // 2, b, A_INK, A_OUTLINE, box)
        return 'A %-30s %d line(s)%s%s' % (name, len(lines), '' if sp == self.A.space else ' space %d' % sp,
                                          ' LOST %d px' % lost if lost else '')

    def draw_banner(self, rows, name):
        if self.B.missing(name):
            return None
        W = len(rows[0])
        sp = self.fit_banner(name, W)
        if sp is None:
            return None
        for r in rows:
            for x in range(W): r[x] = 0
        pl, w = self.B.layout(name, sp)
        lost = self._paint(rows, pl, (W - w) // 2, B_BASELINE, B_INK)
        return 'B %-30s W%d%s%s' % (name, W, '' if sp == self.B.space else ' space %d' % sp,
                                   ' LOST %d px' % lost if lost else '')
