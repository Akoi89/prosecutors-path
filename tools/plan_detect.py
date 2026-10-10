# -*- coding: utf-8 -*-
"""Find the fan's old wording (and the retail Japanese) in the map pieces and floor plans.

tools/plan_labels.py replaces the fan's Hallway / Workroom / Special Cell / Courtyard / Palace /
Fountain Patio, and the retail Japanese the fan never translated, with Capcom's wording. No text search
can see wording that is drawn into a picture, so this tool cuts the letters of every OLD label out of the
fan's own pictures (and the kanji out of the retail Japanese ones), slides them over every picture the
rewrite touches, on the raw palette indices, and reports a word wherever its letters chain:

  * a letter's ink pixels must carry one and the same index v in the picture (the same lettering is drawn
    in different colours), its one-pixel ring should not carry v;
  * letter score = (ink pixels that are v + ring pixels that are not v) / (ink + ring), at least 0.80;
  * a word is its letters in order, one index, one baseline, 0..5 empty columns between neighbours,
    mean score at least 0.93.

The fan set each label by hand (the same word is a pixel narrower or wider from label to label), so
every label that spells a letter contributes its own template and a chain may mix them.

    python tools/plan_detect.py --rom out/x.nds --fan-dir dump/ds_fan --jp-dir dump/ds_jp [--expect-none]

Without --expect-none it just lists the hits (run it on the baseline ROM to see the old wording found);
with it, any hit exits 1.
"""
import sys, os, struct, collections, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import cv2
import room_names as rn
import plan_labels as pl
from choice_strips import Idlocal, rom_file

LETTER_SCORE = 0.80
WORD_MEAN = 0.93
GAP_MIN, GAP_MAX = 0, 5


class Template(object):
    def __init__(self, face, tok, pts, src, desc=0):
        self.face, self.tok, self.src, self.desc = face, tok, src, desc      # desc: rows below the baseline
        xs = [x for x, _ in pts]; ys = [y for _, y in pts]
        self.x0, self.y0 = min(xs), min(ys)
        self.w, self.h = max(xs) - self.x0 + 1, max(ys) - self.y0 + 1
        ink = np.zeros((self.h + 2, self.w + 2), np.float32)
        for x, y in pts:
            ink[y - self.y0 + 1, x - self.x0 + 1] = 1
        d = cv2.dilate(ink, np.ones((3, 3), np.uint8))
        self.ink = ink
        self.ring = (d - ink).astype(np.float32)
        self.n_ink, self.n_ring = int(ink.sum()), int(self.ring.sum())
        self.bits = tuple(''.join('#' if ink[y + 1, x + 1] else '.' for x in range(self.w)) for y in range(self.h))


def view_grid(idl, g, k):
    """Index grid of cell k of the idlocal picture whose tile bank is entry g."""
    return pl._bundle(idl, g).grid(k)[0]


def build_templates(fan_idl, jp_idl, sources=None, fan_up=None):
    """Templates from `sources` (pl.DETECT_SOURCES): (face, 'fan'|'jp', rgcn, cell, box, ink, tokens)."""
    out = []
    srcs = pl.DETECT_SOURCES if sources is None else sources
    for face, which, g, k, box, ink, toks in srcs:
        if which == 'fanup':
            grid = pl.up_grid(pl.up_table(fan_up)[g])
        else:
            grid = view_grid(fan_idl if which == 'fan' else jp_idl, g, k)
        if box is None:
            box = (0, grid.shape[1] - 1, 0, grid.shape[0] - 1)
        m = rn.ink_mask(grid, ink, box)
        runs = rn.segment(m, box)
        if len(runs) != len(toks):
            raise rn.RoomNamesError('%s %d c%d %s: %d column runs, expected %d (%s)' % (which, g, k, box, len(runs), len(toks), toks))
        base = collections.Counter(r[3] for r in runs).most_common(1)[0][0]
        for tok, r in zip(toks, runs):
            out.append(Template(face, tok, r[4], '%s %d c%s %r' % (which, g, k, tok), r[3] - base))
    return out


def match(grid, templates, min_score=LETTER_SCORE):
    hits = []
    if not (grid >= 0).any():
        return hits
    H, W = grid.shape
    for v in np.unique(grid[grid >= 0]).tolist():
        A = (grid == v).astype(np.float32)
        Ap = cv2.copyMakeBorder(A, 3, 3, 3, 3, cv2.BORDER_CONSTANT, value=0)
        for t in templates:
            if A.sum() < 0.85 * t.n_ink:
                continue
            ink_hits = cv2.matchTemplate(Ap, t.ink, cv2.TM_CCORR)
            ring_hits = cv2.matchTemplate(Ap, t.ring, cv2.TM_CCORR)
            score = (ink_hits + (t.n_ring - ring_hits)) / float(t.n_ink + t.n_ring)
            ok = (ink_hits >= 0.85 * t.n_ink) & (score >= min_score)
            for y, x in np.argwhere(ok):
                # (x, y) of the result is the window's top-left in the padded image: padding 3 and
                # the template's own 1 px margin put the ink bbox corner at (x + 1 - 3 + 0, y + 1 - 3 + 0)
                hits.append(dict(t=t, x=int(x) - 2, y=int(y) - 2, v=v, score=float(score[y, x]),
                                 exact=bool(ink_hits[y, x] == t.n_ink and ring_hits[y, x] == 0)))
    return hits


def chain(hits, face, toks):
    by = collections.defaultdict(list)
    for h in hits:
        if h['t'].face == face:
            by[(h['t'].tok, h['v'])].append(h)
    words = []
    for v in set(h['v'] for h in hits if h['t'].face == face):
        for first in by.get((toks[0], v), []):
            base = first['y'] + first['t'].h - 1 - first['t'].desc
            seq, cur = [first], first
            for tok in toks[1:]:
                best = None
                for h in by.get((tok, v), []):
                    if h['y'] + h['t'].h - 1 - h['t'].desc != base:
                        continue
                    gap = h['x'] - (cur['x'] + cur['t'].w)
                    if GAP_MIN <= gap <= GAP_MAX and (best is None or h['score'] > best['score']):
                        best = h
                if best is None:
                    break
                seq.append(best); cur = best
            if len(seq) == len(toks):
                sc = [h['score'] for h in seq]
                words.append(dict(x=first['x'], x_end=cur['x'] + cur['t'].w - 1, base=base, v=v,
                                  mean=sum(sc) / len(sc), letters=''.join(h['t'].tok for h in seq)))
    return [w for w in words if w['mean'] >= WORD_MEAN]


def pictures(idl_bytes, fan_idl=None):
    """-> list of (label, grid) for every cell (0: the piece, 1: the strip) of the entries tools/plan_labels.py rewrites."""
    idl = Idlocal(idl_bytes)
    out = []
    for g in sorted(set(e for es in pl.CLASS_ENTRIES.values() for e in es)):
        for k in (0, 1):
            try:
                lab = 'idlocal %d c%d' % (g, k)
                if fan_idl is not None and idl.blob(g) == fan_idl.blob(g):
                    lab += ' (UNCHANGED)'
                out.append((lab, view_grid(idl, g, k)))
            except Exception:
                pass
    return out


def up_pictures(up_bytes, fan_up_bytes):
    """-> list of (label, grid) of the plan pictures of upcut_local, marked UNCHANGED where the build left them."""
    tab, ftab = pl.up_table(up_bytes), pl.up_table(fan_up_bytes)
    out = []
    for e in pl.PLAN_ENTRIES:
        lab = 'upcut_local %d' % e + (' (UNCHANGED)' if tab[e] == ftab[e] else '')
        out.append((lab, pl.up_grid(tab[e])))
    return out


def sprite_pictures(co_bytes, fan_co_bytes):
    """-> [(label, grid)] of cell 1 (the Autumn cloud) of cutobj_local entry 12, marked UNCHANGED where the build left it."""
    co, fco = Idlocal(co_bytes), Idlocal(fan_co_bytes)
    blob = co.blob(pl.SPRITE12['entry'])
    o = struct.unpack_from('<3I', blob, 0)
    grid = rn.Bundle(blob[o[0]:o[1]], blob[o[2]:]).grid(pl.SPRITE12['cell'])[0]
    lab = 'cutobj_local %d c%d' % (pl.SPRITE12['entry'], pl.SPRITE12['cell'])
    if blob == fco.blob(pl.SPRITE12['entry']):
        lab += ' (UNCHANGED)'
    return [(lab, grid)]


def _green(grid, pal):
    P = np.array(pal, np.int64)
    rgb = P[grid]
    return ((rgb[..., 1] - rgb[..., 2]) >= 20) & (rgb[..., 1] >= 100)


def board_check(up_bytes, fan_up_bytes):
    """The information board (upcut_local 116): nothing of the old figures may be left. -> list of problems (strings).
    The green ink of the picture's temperature cells must lie only in the rows of the four new Fahrenheit lines (the
    old Fahrenheit rows and every Celsius row hold none), and the digit slots of 78 and 53 must be the glyphs the fan's
    18 C and -3 C have, not the old 9 and 4."""
    from nitro import nclr
    tab, ftab = pl.up_table(up_bytes), pl.up_table(fan_up_bytes)
    e = pl.BOARD_ENTRY
    if tab[e] == ftab[e]:
        return ['79 F, 54 F and the Celsius lines are still in the picture']
    new, old = pl.up_grid(tab[e]), pl.up_grid(ftab[e])
    pal = nclr(tab[e + 1])
    gn, go = _green(new, pal), _green(old, pal)
    problems = []
    y0, y1, x0, x1 = 72, 136, 100, 170
    ok_rows = [(86, 94), (115, 123)]
    for y in range(y0, y1):
        if not any(a - 1 <= y <= b + 1 for a, b in ok_rows) and gn[y, x0:x1].any():
            problems.append('green ink in row %d, outside the four Fahrenheit lines' % y)
    for q, (cx0, cx1) in (('left', (100, 128)), ('right', (129, 160))):
        for top, label in ((86, 'upper'), (115, 'lower')):
            if int(gn[top:top + 9, cx0:cx1].sum()) < 60:
                problems.append('the %s %s figure is missing' % (label, q))
    for (ty, tx), (sy, sx), name in (((86, 111), (92, 137), '78'), ((115, 111), (121, 136), '53')):
        slot = gn[ty:ty + 9, tx:tx + 4]
        src = go[sy:sy + 9, sx:sx + 4]
        if not (slot == src).all():
            problems.append('the second digit of %s is not the glyph of the fan 18 C / -3 C' % name)
    return [p for p in problems]


def gallery_check(up_bytes, fan_up_bytes, dumpdir):
    """The leaflet (upcut_local 114) is swapped whole: it must equal Capcom's picture reduced by tools/gallery_art.py
    (compared when the texture is in the dump) and share almost no pixels with the fan's. -> list of problems."""
    from nitro import nclr
    tab, ftab = pl.up_table(up_bytes), pl.up_table(fan_up_bytes)
    e = pl.GALLERY_ENTRY
    if tab[e] == ftab[e]:
        return ['the fan leaflet is still in the picture']
    new, old = pl.up_grid(tab[e]), pl.up_grid(ftab[e])
    problems = []
    same = float((new == old).mean())
    if same > 0.5:
        problems.append('%.0f%% of the leaflet pixels are still the fan picture' % (100 * same))
    if dumpdir and os.path.isfile(os.path.join(dumpdir, 'title', 'gallery', 'cut02_010_eng.png')):
        import gallery_art
        if not (gallery_art.picture(dumpdir, nclr(tab[e + 1])) == new).all():
            problems.append('the leaflet is not the Capcom picture as tools/gallery_art.py reduces it')
    return problems


def scan(idl_bytes, templates, words, fan_idl=None, up=None, extra=()):
    """words: list of (face, text, tokens). -> list of (picture label, word text, dict)."""
    found = []
    pics = pictures(idl_bytes, fan_idl) + (up_pictures(*up) if up else []) + list(extra)
    for label, grid in pics:
        hits = match(grid, templates)
        for face, text, toks in words:
            seen = set()
            for w in chain(hits, face, toks):
                key = (w['x'], w['x_end'], w['base'], w['v'])
                if key not in seen:
                    seen.add(key)
                    found.append((label, text, w))
    return found


def turned_hallway(idl_bytes, faces):
    """The vertical corridor's "Hallway" (idlocal 297: the horizontal label turned a quarter clockwise, 9 rows
    wide, from (68, 40)): -> a list with one entry if most of its ink is still in the picture."""
    idl = Idlocal(idl_bytes)
    grid = view_grid(idl, 297, 0)
    ink = pl.rot_label(faces['big'], 'Hallway', 68, 40, 9)
    for v in (7,):
        n = sum(1 for (x, y) in ink if grid[y, x] == v)
        if n >= 0.9 * len(ink):
            return [('idlocal 297 c0', 'Hallway (turned)', dict(x=68, x_end=76, base=0, v=v, mean=n / float(len(ink))))]
    return []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--rom', required=True)
    ap.add_argument('--fan-dir', default='dump/ds_fan')
    ap.add_argument('--jp-dir', default='dump/ds_jp')
    ap.add_argument('--expect-none', action='store_true')
    a = ap.parse_args()
    fan = Idlocal(open(os.path.join(a.fan_dir, 'jpn', 'idlocal.bin'), 'rb').read())
    jp = Idlocal(open(os.path.join(a.jp_dir, 'jpn', 'idlocal.bin'), 'rb').read())
    rom = open(a.rom, 'rb').read()
    fan_up = open(os.path.join(a.fan_dir, 'jpn', 'upcut_local.bin'), 'rb').read()
    templates = build_templates(fan, jp, None, fan_up)
    fan_co = open(os.path.join(a.fan_dir, 'jpn', 'cutobj_local.bin'), 'rb').read()
    found = scan(rom_file(rom, 'jpn/idlocal.bin'), templates, pl.DETECT_WORDS, fan,
                 (rom_file(rom, 'jpn/upcut_local.bin'), fan_up), sprite_pictures(rom_file(rom, 'jpn/cutobj_local.bin'), fan_co))
    for lab, probs in (('upcut_local 116 board', board_check(rom_file(rom, 'jpn/upcut_local.bin'), fan_up)),
                       ('upcut_local 114 leaflet', gallery_check(rom_file(rom, 'jpn/upcut_local.bin'), fan_up,
                                                                  os.path.dirname(os.path.abspath(a.fan_dir))))):
        un = ' (UNCHANGED)' if (lab.endswith('board') and pl.up_table(rom_file(rom, 'jpn/upcut_local.bin'))[pl.BOARD_ENTRY] == pl.up_table(fan_up)[pl.BOARD_ENTRY]) or (
            lab.endswith('leaflet') and pl.up_table(rom_file(rom, 'jpn/upcut_local.bin'))[pl.GALLERY_ENTRY] == pl.up_table(fan_up)[pl.GALLERY_ENTRY]) else ''
        found += [(lab + un, p, dict(x=0, x_end=0, base=0, v=0, mean=1.0)) for p in probs]
    found += turned_hallway(rom_file(rom, 'jpn/idlocal.bin'), pl.build_faces(fan))
    for label, text, w in sorted(found, key=lambda f: (f[0], f[1], f[2]['x'])):
        print('%-18s %-12s x %3d-%3d base %3d index %2d mean %.3f' % (label, text, w['x'], w['x_end'], w['base'], w['v'], w['mean']))
    live = [f for f in found if 'UNCHANGED' not in f[0]]
    left = [f for f in live if ((f[0], f[1]) in pl.KNOWN_LEFT and int(f[0].split()[1]) not in (pl.UP_LARGER if f[0].startswith('upcut_local') else pl.LARGER))
            or (f[0], f[1]) in pl.DETECT_IGNORE]
    live = [f for f in live if f not in left]
    print('%d old-wording hits: %d in pictures this build leaves as the fan had them, %d known and left on purpose '
          '(plan_labels.KNOWN_LEFT: over the stored size of that entry in the fan ROM; plan_labels.DETECT_IGNORE: a new word that contains the old letters), %d to fix' % (len(found), len(found) - len(live) - len(left), len(left), len(live)))
    return 1 if (live and a.expect_none) else 0


if __name__ == '__main__':
    sys.exit(main())
