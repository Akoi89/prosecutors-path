# -*- coding: utf-8 -*-
"""Find every picture of the fan lettering "Grand Tower" in a DS ROM.

The fan patch drew "Grand Tower" (Capcom: "Bigg Building") into pictures, so no
text search can see it. This tool cuts the letters G r a n d T o w e r out of the
fan's own labels (one set per lettering face: the small strip face, the map-piece
wedge face, the city-map face), then slides them over every picture of every
graphic container, on the raw palette indices, so what it finds does not depend
on a palette:

  * a letter's ink pixels must all carry one and the same index v in the picture
    (any v: the same lettering is drawn in different colours);
  * the pixels of the letter's one-pixel ring (halo, shadow, gap) should not carry v.

letter score = (ink pixels that are v + ring pixels that are not v) / (ink + ring).
The fan sets each strip by hand (the same pair of letters sits one pixel closer or
farther apart from label to label), so a whole-word template does not match twice;
a WORD is therefore a chain of letter hits: the letters in order, one index, one
baseline, 0..5 empty columns between neighbours. A label is a hit when "Grand" is
chained; the chained "Tower" below it or after it is reported with it. "Tower" alone
("Tower Plaza") is never a hit.

    python tools/bigg_detect.py --rom out/x.nds --fan-rom <fan.nds> --out DIR [--prove]

--prove prints the weakest true hit and the strongest non-hit over the population.
"""
import os, sys, json, struct, collections, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import cv2

import gfx_views as gv
import room_names as rn
from choice_strips import rom_file, Idlocal

LETTER_INK = 0.85            # a letter candidate: this share of its ink pixels carry one index ...
LETTER_SCORE = 0.80          # ... and the ink-plus-ring score is at least this
WORD_MEAN = 0.93             # a word: mean letter score
GAP_MIN, GAP_MAX = 0, 5      # empty columns between two letters of a word

CONTAINERS = [
    'jpn/idlocal.bin', 'jpn/upcut_local.bin', 'jpn/cutobj_local.bin', 'jpn/logic_keyword_local.bin',
    'jpn/opening_local.bin', 'jpn/title_local.bin', 'jpn/save_local.bin', 'jpn/modelitemlocal.bin',
    'com/idcom.bin', 'com/bustup.bin', 'com/mapbg.bin', 'com/mapobj.bin', 'com/logicbg.bin',
    'com/logicmat.bin', 'com/logic_keyword.bin', 'com/logo.bin', 'com/modelitem.bin', 'com/upcut.bin',
]
# palette side for rendering (the nearest RLCN before/after the picture), as the 1.11.1 sweep found
PAL_PREF = {'jpn/upcut_local.bin': 'after', 'com/upcut.bin': 'after', 'com/mapbg.bin': 'after',
            'com/mapobj.bin': 'after', 'jpn/cutobj_local.bin': 'after', 'com/logic_keyword.bin': 'after'}

# ---------------------------------------------------------------------------
# templates
# ---------------------------------------------------------------------------
# (face, container, entry, view, box x0 x1 y0 y1, ink index, tokens of the column runs)
# Every source is a fan label whose letters are cut by column runs (room_names.segment);
# the number of runs is checked, the tool raises if a label is not what the source says.
# The wedge "To" is one run: the fan's T and o touch there. The big face (the lit-box labels such as
# Tower Plaza) has Tower cut from idlocal 340 and Grand from the label of 343; 343's own Tower is
# checked against 340's (same shapes: a cross-check that the two are one face).
SOURCES = [
    ('strip', 'jpn/idlocal.bin', 331, 'c1', (0, 67, 0, 15), 4, ['G', 'r', 'a', 'n', 'd', 'T', 'o', 'w', 'e', 'r', ':']),
    ('wedge', 'jpn/idlocal.bin', 340, 'c0', (53, 85, 19, 29), 7, ['G', 'r', 'a', 'n', 'd']),
    ('wedge', 'jpn/idlocal.bin', 340, 'c0', (53, 87, 30, 40), 7, ['To', 'w', 'e', 'r']),
    ('big', 'jpn/idlocal.bin', 340, 'c0', (44, 74, 79, 88), 9, ['T', 'o', 'w', 'e', 'r']),
    ('big', 'jpn/idlocal.bin', 343, 'c0', (52, 125, 19, 29), 13, ['G', 'r', 'a', 'n', 'd', 'T', 'o', 'w', 'e', 'r']),
    ('map', 'jpn/upcut_local.bin', 264, 'raw', (80, 115, 103, 112), 0, ['G', 'r', 'a', 'n', 'd']),
    ('map', 'jpn/upcut_local.bin', 264, 'raw', (80, 115, 114, 123), 0, ['T', 'o', 'w', 'e', 'r']),
]
WORDS = {
    'strip': {'Grand': ['G', 'r', 'a', 'n', 'd'], 'Tower': ['T', 'o', 'w', 'e', 'r']},
    'wedge': {'Grand': ['G', 'r', 'a', 'n', 'd'], 'Tower': ['To', 'w', 'e', 'r']},
    'big': {'Grand': ['G', 'r', 'a', 'n', 'd'], 'Tower': ['T', 'o', 'w', 'e', 'r']},
    'map': {'Grand': ['G', 'r', 'a', 'n', 'd'], 'Tower': ['T', 'o', 'w', 'e', 'r']},
}


class Template(object):
    def __init__(self, face, tok, pts, src):
        self.face, self.tok, self.src = face, tok, src
        xs = [x for x, _ in pts]; ys = [y for _, y in pts]
        self.x0, self.y0 = min(xs), min(ys)
        self.w, self.h = max(xs) - self.x0 + 1, max(ys) - self.y0 + 1
        self.ink = np.zeros((self.h + 2, self.w + 2), np.float32)       # one pixel of margin all round
        for x, y in pts:
            self.ink[y - self.y0 + 1, x - self.x0 + 1] = 1
        d = cv2.dilate(self.ink, np.ones((3, 3), np.uint8))
        self.ring = (d - self.ink).astype(np.float32)
        self.n_ink, self.n_ring = int(self.ink.sum()), int(self.ring.sum())
        # offsets of the ink and ring pixels from the ink bbox's top-left corner
        self.ink_off = [(int(y) - 1, int(x) - 1) for y, x in np.argwhere(self.ink > 0)]
        self.ring_off = [(int(y) - 1, int(x) - 1) for y, x in np.argwhere(self.ring > 0)]
        self.bits = tuple(''.join('#' if self.ink[y + 1, x + 1] else '.' for x in range(self.w)) for y in range(self.h))

    def key(self):
        return '%s:%s' % (self.face, self.tok)


def _blobs(rom, path):
    idl = Idlocal(rom_file(rom, path))
    out = []
    for e in range(idl.n):
        try:
            out.append(idl.blob(e) if idl.ents[e][0] else b'')
        except Exception:
            out.append(b'')
    return idl, out


def build_templates(fan_rom):
    """Letter templates cut from the fan's own pictures. -> (list of Template, notes)."""
    cache = {}
    out, seen, notes = [], {}, []
    for face, path, e, view, box, ink, toks in SOURCES:
        if path not in cache:
            cache[path] = _blobs(fan_rom, path)[1]
        grid = [g for l, g, _ in gv.entry_views(cache[path], e) if l == view][0]
        m = rn.ink_mask(grid, ink, box)
        runs = rn.segment(m, box)
        if len(runs) != len(toks):
            raise rn.RoomNamesError('%s %d %s %s: %d column runs, expected %d' % (path, e, view, box, len(runs), len(toks)))
        for tok, r in zip(toks, runs):
            t = Template(face, tok, r[4], '%s %d %s %r' % (path, e, view, tok))
            if (face, tok) in seen:
                notes.append('%s %r cut twice: %s' % (face, tok, 'same shape' if seen[(face, tok)].bits == t.bits else 'DIFFERENT shape (first kept)'))
                continue
            seen[(face, tok)] = t
            out.append(t)
    # the orange map-label face (tools/map_font.json: cutobj_local wedges, the room map) against the
    # map face cut from jpn/upcut_local.bin 264: the same letters?
    f = rn.map_face()
    for tok in ('G', 'r', 'a', 'n', 'd', 'T', 'o', 'w', 'e', 'r'):
        pts, _ = rn.layout(f, tok, 0, 12)
        o = Template('map', tok, pts, 'map_font.json %r' % tok)
        same = o.bits == seen[('map', tok)].bits
        notes.append('orange face %r %s the city-map face' % (tok, 'is identical to' if same else 'DIFFERS from'))
    return out, notes


# ---------------------------------------------------------------------------
# matching
# ---------------------------------------------------------------------------
def match_view(grid, templates, min_score=LETTER_SCORE):
    """Letter candidates. -> list of dict(t, x, y, v, score, exact), (x, y) the ink bbox's top-left corner.
    Sparse form of a sliding match: a position can hold a letter with at most (1 - LETTER_INK) of its ink
    missing only if one of ANCHORS spread-out ink pixels is there, so only those positions are scored."""
    hits = []
    H, W = grid.shape
    if not (grid >= 0).any():
        return hits
    PAD = 40
    pg = np.pad(grid, PAD, constant_values=-1)
    vals, counts = np.unique(grid[grid >= 0], return_counts=True)
    for v, c in zip(vals.tolist(), counts.tolist()):
        P = None
        for t in templates:
            if c < LETTER_INK * t.n_ink or t.h > H or t.w > W:
                continue
            if P is None:
                P = np.argwhere(grid == v)
            miss = int(np.floor((1 - LETTER_INK) * t.n_ink + 1e-9))
            ink_off, ring_off = t.ink_off, t.ring_off
            idx = np.unique(np.linspace(0, len(ink_off) - 1, miss + 1).astype(int))
            codes = []
            for i in idx:
                oy, ox = ink_off[i]
                codes.append((P[:, 0] - oy + 1) * (W + 4) + (P[:, 1] - ox + 1))
            codes = np.unique(np.concatenate(codes))
            C = np.stack([codes // (W + 4) - 1, codes % (W + 4) - 1], axis=1)
            C = C[(C[:, 0] >= -1) & (C[:, 1] >= -1) & (C[:, 0] <= H - t.h + 1) & (C[:, 1] <= W - t.w + 1)]
            if not len(C):
                continue
            allowed = t.n_ink - int(np.ceil(LETTER_INK * t.n_ink - 1e-9))
            misses = np.zeros(len(C), np.int32)
            for j, (oy, ox) in enumerate(ink_off):
                misses += (pg[C[:, 0] + oy + PAD, C[:, 1] + ox + PAD] != v)
                if j % 4 == 3:
                    keep = misses <= allowed
                    C, misses = C[keep], misses[keep]
                    if not len(C):
                        break
            if not len(C):
                continue
            keep = misses <= allowed
            C, misses = C[keep], misses[keep]
            if not len(C):
                continue
            ink_hits = t.n_ink - misses
            ring_hits = np.zeros(len(C), np.int32)
            for oy, ox in ring_off:
                ring_hits += (pg[C[:, 0] + oy + PAD, C[:, 1] + ox + PAD] == v)
            score = (ink_hits + (t.n_ring - ring_hits)) / float(t.n_ink + t.n_ring)
            for k in np.nonzero(score >= min_score)[0]:
                hits.append(dict(t=t, x=int(C[k, 1]), y=int(C[k, 0]), v=v, score=float(score[k]),
                                 exact=bool(ink_hits[k] == t.n_ink and ring_hits[k] == 0)))
    return hits


def chain(hits, face, toks):
    """Words made of letters `toks` of `face`. -> list of dict(x, x_end, base, v, mean, min, exact, letters)."""
    by = collections.defaultdict(list)
    for h in hits:
        if h['t'].face == face:
            by[(h['t'].tok, h['v'])].append(h)
    words = []
    for v in set(h['v'] for h in hits if h['t'].face == face):
        for first in by.get((toks[0], v), []):
            base = first['y'] + first['t'].h - 1
            seq, cur = [first], first
            for tok in toks[1:]:
                best = None
                for h in by.get((tok, v), []):
                    if h['y'] + h['t'].h - 1 != base:
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
                                  mean=sum(sc) / len(sc), min=min(sc), exact=sum(1 for h in seq if h['exact']),
                                  letters=[(h['t'].tok, h['x'], round(h['score'], 3)) for h in seq]))
    return [w for w in words if w['mean'] >= WORD_MEAN]


def best_prefix(hits, face, toks):
    """Longest run of the letters of `toks` (from the first) that chains in `face`, and the mean score of
    the best such chain: the nearest a non-hit comes to the word. -> (letters, mean score)."""
    by = collections.defaultdict(list)
    for h in hits:
        if h['t'].face == face:
            by[(h['t'].tok, h['v'])].append(h)
    best = (0, 0.0)
    for v in set(h['v'] for h in hits if h['t'].face == face):
        for first in by.get((toks[0], v), []):
            base = first['y'] + first['t'].h - 1
            seq, cur = [first], first
            for tok in toks[1:]:
                nxt = None
                for h in by.get((tok, v), []):
                    if h['y'] + h['t'].h - 1 == base and GAP_MIN <= h['x'] - (cur['x'] + cur['t'].w) <= GAP_MAX                             and (nxt is None or h['score'] > nxt['score']):
                        nxt = h
                if nxt is None:
                    break
                seq.append(nxt); cur = nxt
            cand = (len(seq), sum(h['score'] for h in seq) / len(seq))
            if cand > best:
                best = cand
    return best


def find_labels(grid, templates, extra=None):
    """Every "Grand" word of every face in a picture, with the "Tower" that goes with it.
    -> list of dict(face, grand, tower or None, layout). If `extra` is a dict it collects, for the
    precision figures, the "Tower" words that have no "Grand" (list under 'tower_alone') and the best
    partial "Grand" of a picture that has none (under 'partial', (letters, mean score, face))."""
    out = []
    hits = match_view(grid, templates)
    for face, w in WORDS.items():
        grands = chain(hits, face, w['Grand'])
        towers = chain(hits, face, w['Tower'])
        used = set()
        for g in grands:
            best = None
            for t in towers:
                if t['v'] != g['v']:
                    continue
                below = 6 <= t['base'] - g['base'] <= 16 and abs(t['x'] - g['x']) <= 16
                after = t['base'] == g['base'] and 3 <= t['x'] - g['x_end'] <= 12
                if (below or after) and (best is None or t['mean'] > best[0]['mean']):
                    best = (t, 'below' if below else 'after')
            if best:
                used.add((best[0]['x'], best[0]['base']))
            out.append(dict(face=face, grand=g, tower=best[0] if best else None, layout=best[1] if best else None))
        if extra is not None:
            for t in towers:
                if (t['x'], t['base']) not in used:
                    extra.setdefault('tower_alone', []).append((face, t['x'], t['base'], round(t['mean'], 3)))
            if not grands:
                n, m = best_prefix(hits, face, w['Grand'])
                if (n, m) > extra.get('partial', (0, 0.0, ''))[:2]:
                    extra['partial'] = (n, m, face)
    return out


def retail_blobs(jp_dir, path):
    """Decoded entries of the retail Japanese file, or None if it is not there."""
    p = os.path.join(jp_dir, *path.split('/'))
    if not os.path.exists(p):
        return None
    idl = Idlocal(open(p, 'rb').read())
    out = []
    for e in range(idl.n):
        try:
            out.append(idl.blob(e) if idl.ents[e][0] else b'')
        except Exception:
            out.append(None)
    return out


def scan_container(rom, path, templates, jp_dir=None):
    """-> (hits, stats). hits: dict(container, entry, view, face, grand, tower, layout);
    stats: entries, views, kinds, entries that gave no view and why.
    With jp_dir only entries that differ from the retail Japanese file are scanned (fan lettering
    cannot be in a picture the fan did not touch); without it every entry is."""
    idl, bl = _blobs(rom, path)
    jp = retail_blobs(jp_dir, path) if jp_dir else None
    hits, stats = [], dict(entries=idl.n, views=0, noview={}, kinds=collections.Counter(), scanned=0, skipped_same=0, tower_alone=[], partial=(0, 0.0, '', None, None))
    for e in range(idl.n):
        b = bl[e]
        k = gv.kind(b)
        stats['kinds'][k] += 1
        if k not in ('C', 'G', 'S'):
            continue
        if jp is not None and e < len(jp) and jp[e] == b:
            stats['skipped_same'] += 1
            continue
        stats['scanned'] += 1
        try:
            views = gv.entry_views(bl, e)
        except Exception as ex:
            stats['noview'][e] = 'unreadable (%s: %s)' % (type(ex).__name__, ex)
            continue
        if not views:
            stats['noview'][e] = 'no cells or tiles'
            continue
        for lab, g, info in views:
            stats['views'] += 1
            ex = {}
            for lb in find_labels(g, templates, ex):
                lb.update(container=path, entry=e, view=lab)
                hits.append(lb)
            for t in ex.get('tower_alone', []):
                stats['tower_alone'].append((e, lab) + t)
            if 'partial' in ex and ex['partial'] > stats['partial'][:3]:
                stats['partial'] = ex['partial'] + (e, lab)
    return hits, stats


def all_hits(rom, templates, containers=CONTAINERS, jp_dir=None):
    hits, stats = [], {}
    for c in containers:
        try:
            h, s = scan_container(rom, c, templates, jp_dir)
        except Exception as ex:
            stats[c] = dict(error='%s: %s' % (type(ex).__name__, ex))
            continue
        hits += h; stats[c] = s
    return hits, stats


def is_hit(h):
    return True      # find_labels only returns labels whose "Grand" chained; kept for callers


def write_tsv(hits, path):
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write('container\tentry\tview\tface\tx\ty\tindex\tscore_mean\tscore_min\tletters_exact\ttower\n')
        for h in sorted(hits, key=lambda h: (h['container'], h['entry'], h['view'], h['grand']['x'])):
            g = h['grand']
            t = h['tower']
            f.write('%s\t%d\t%s\t%s\t%d\t%d\t%d\t%.3f\t%.3f\t%d/5\t%s\n' % (
                h['container'], h['entry'], h['view'], h['face'], g['x'], g['base'] - 7, g['v'], g['mean'], g['min'], g['exact'],
                ('%s %.3f at x=%d base=%d' % (h['layout'], t['mean'], t['x'], t['base'])) if t else 'none'))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--rom', required=True)
    ap.add_argument('--fan-rom', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--jp-dir', default=os.path.join('dump', 'ds_jp'), help='retail Japanese files; only entries that differ are scanned')
    ap.add_argument('--all', action='store_true', help='scan every entry, edited or not (slow)')
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    rom = open(a.rom, 'rb').read()
    fan = open(a.fan_rom, 'rb').read()
    templates, notes = build_templates(fan)
    for t in templates:
        print('template %-9s %2dx%-2d ink %3d ring %3d  %s' % (t.key(), t.w, t.h, t.n_ink, t.n_ring, t.src))
    for n in notes:
        print('note:', n)
    hits, stats = all_hits(rom, templates, jp_dir=None if a.all else a.jp_dir)
    write_tsv(hits, os.path.join(a.out, 'DETECT.tsv'))
    for c, s in stats.items():
        if 'error' in s:
            print(c, 'ERROR', s['error'])
        else:
            print(c, 'best non-hit partial Grand (letters, mean, face, entry, view):', s['partial'], '; Tower without Grand:', s['tower_alone'][:12])
            print(c, 'entries', s['entries'], 'scanned', s['scanned'], 'identical to retail', s['skipped_same'], 'views', s['views'], dict(s['kinds']), 'no view:', sorted(s['noview'].items()))
    for h in hits:
        print('HIT', h['container'], h['entry'], h['view'], h['face'], 'x=%d base=%d' % (h['grand']['x'], h['grand']['base']),
              'mean %.3f' % h['grand']['mean'], 'tower' if h['tower'] else 'NO-TOWER')


if __name__ == '__main__':
    main()
