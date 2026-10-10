# -*- coding: utf-8 -*-
"""Redraw the dialogue nameplates with Capcom's official character names.

The 60 nameplates are graphics: jpn/idlocal.bin entries 27-86, each an LZ11'd
RGCN of 18 tiles = one 144x8 strip. Every plate is identical except its text, which
sits on the bar's fill (columns 51-92, palette index 6; text is index 4). The
official localization renamed most of the cast, and this port's dialogue is
98.4% Capcom's - so a plate saying "Ray" under a line that says "Fender" was
the loudest inconsistency left.

The FONT here is the fan patch's own: glyphs are harvested at build time from
the user's plates themselves (each plate's name is known, so its letters can
be cut apart), which also means no fan-drawn graphics ship with this tool -
only the official names (Capcom's, as plain words) and a few hand-drawn
fallback glyphs for letters the fan set lacks. Long names use the fan's own
narrower faces (see NARROW_SOURCES and THIN_CUTS). Plates whose name the official
localization kept are left byte-identical. See gk2_common_nametag_en for the
official names; the fan->official pairing was verified string-by-string
against both scripts (tools/names.py carries the same map for dialogue).
"""
import sys, os, struct, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lz11 import decompress
from nitro import ncgr, tile_pixels

# fan plate names (read off the plates; used to cut the font apart)
FAN_NAMES = {27:'Edgeworth',28:'Gumshoe',29:'Kay',30:'Ema',31:'Franziska',32:'Gregory',
             33:'Badd',34:'Lang',35:'Judge',36:'Courtney',37:'Debeste',38:'Ray',
             40:'Larry',41:'Lotta',42:'Missile',43:'Huang',44:'Knightley',45:'Nicole',
             47:'Doe',49:'Simon',51:'Roland',52:'Sahwit',53:'Regina',54:'Penny',
             55:'John',56:'Master',57:'Kate',60:'Dover',61:'Powers',63:'Blaise',
             64:'Karin',65:'Rooke',66:'Jill',67:'Cameron',68:'Officer',69:'Guard',
             70:'Bailiff',71:'Forensics',72:'Payne',73:'Audience',75:'Bodyguard',
             76:'Prisoner',78:'Driver',80:'Man',81:'Woman',82:'Announcer',83:'Reporter'}

# plate index -> official nametag (gk2_common_nametag_en); the accent in
# Gavèlle is drawn on the plate even though the text font cannot render it
PLATES = {36:'Gavèlle',37:'Eustace',38:'Fender',41:'Hart',43:'Wang',44:'Knight',
          45:'Lloyd',48:'Kanis',49:'Saint',50:'Carcerato',51:'Laguarde',55:'Shaun',
          56:'Tangaroa',57:'Bound',58:'Scone',59:'Gusto',60:'Frost',62:'Hertz',
          63:'Excelsius',64:'Niedler',65:'Rook',66:'Ringer',67:'Aldown',
          73:'Gallery',74:'Cameraman',77:'Azea',79:'Man in Black',84:'Stand Owner'}

# The visible bar is columns 51-92 (42 px of fill); columns 50 and 93 are its darker border. Text is
# centred on the fill like the fan's own plates (an odd leftover pixel goes to the left margin, as it
# does on the fan's) and never leaves it: the build raises instead of drawing on the border.
FILL_A, FILL_B = 51, 93          # FILL_B is exclusive
WIDTH = FILL_B - FILL_A          # 42
CLEAR_A, CLEAR_B = 48, 96        # the fan's old text is cleared anywhere in the 48-px bar piece
TEXT, FILL = 4, 6

def _rows(*rr):
    w = max(len(r) for r in rr)
    rr = [r.ljust(w, '.') for r in rr] + ['.' * w] * (8 - len(rr))
    return [tuple(1 if rr[y][x] == '#' else 0 for y in range(8)) for x in range(w)]

# hand-drawn, in the fan font's own style: letters its short plates never used
HAND = {
    'F': [(1,1,1,1,1,1,1,0),(1,0,0,1,0,0,0,0),(1,0,0,1,0,0,0,0),(1,0,0,1,0,0,0,0),(1,0,0,0,0,0,0,0)],
    'x': [(0,0,1,0,0,1,0,0),(0,0,0,1,1,0,0,0),(0,0,0,1,1,0,0,0),(0,0,1,0,0,1,0,0)],
}

# ---------------------------------------------------------------------------
# Long names do not fit the fan's normal letters, so the plates come in three tiers, all built from
# the fan's own letters:
#   normal  the harvested face (4-7 px letters), 1-3 px between letters;
#   narrow  the fan's own long-name face (its Announcer and Bodyguard plates, 3-4 px letters, 1 px apart),
#           with the fan's 7 px T trimmed to a 5 px bar (one outer column off each end) so its bar
#           and stem weigh what the 4 px letters do;
#   thin    3 px lowercase, for the three names that fit nothing wider (Cameraman, Man in Black,
#           Stand Owner). Every letter is cut from a fan plate; where the fan has only a 4-px
#           letter whose middle columns repeat, one repeated column is dropped (so the strokes are
#           the fan's). Only M (5 px), O (3 px), S (3 px) and the lowercase a and c, which have no such source,
#           are drawn, at native size, seven rows for capitals like the fan's, on its baseline.
NARROW_SOURCES = ((82, 'Announcer'), (75, 'Bodyguard'))
# (fan plate, its reading, letters taken from it)
THIN_CUTS = ((82, 'Announcer', 'er'), (39, 'von Karma', 'n'), (84, 'Shopkeeper', 'k'),
             (36, 'Courtney', 't'), (52, 'Sahwit', 'w'))
# (fan plate, its reading, letter, how many repeated columns to drop)
THIN_SQUEEZE = ((75, 'Bodyguard', 'B', 1), (75, 'Bodyguard', 'd', 1), (36, 'Courtney', 'C', 2))
THIN_DRAWN = {
    'M': _rows('#...#','##.##','#.#.#','#...#','#...#','#...#','#...#'),
    'O': _rows('.#.','#.#','#.#','#.#','#.#','#.#','.#.'),
    # the fan's S with a column dropped has one-pixel hooks top and bottom and wobbles; flat strokes read as an S
    'S': _rows('.##','#..','#..','.#.','..#','..#','##.'),
    'a': _rows('','','.##','..#','###','#.#','.##'),
    'c': _rows('','','.##','#..','#..','#..','.##'),
}
THIN_SHARED = 'ilm'      # identical in the normal face (1, 1 and 5 px)

# fan plates read for the thin and narrow faces only (kept apart from FAN_NAMES so the normal face is unchanged)
FAN_NAMES_THIN = {39: 'von Karma', 84: 'Shopkeeper'}

# spacing: 1 px between letters, 3 px between words (the fan's own word gap, seen on von Karma,
# de Killer and TV Crew). A tier stops at WIDTH, the fan's own limit (its Edgeworth, Forensics,
# Bodyguard and Announcer plates fill it exactly). The thin tier asks for one px of margin on each
# side first (ink <= WIDTH - 2) by narrowing the later word gaps from 3 to 2; where even that
# cannot be done it takes the full WIDTH with word gap 2. THIN_EXCEPTIONS records the plates that
# end up with a word gap below 3, which the audit allows.
WORD_GAP = 3
# plates allowed a word gap below WORD_GAP, with the reason (audits/audit_plates.py reads this)
# entry -> (the exact word gaps the plate must have, why); the audit requires an exact match
THIN_EXCEPTIONS = {79: ([3, 2], 'Man in Black: word gaps 3 and 2 (ink 40) keep 1 px of margin on both sides'),
                   84: ([2], 'Stand Owner: word gap 2 (ink 42, margin 0/0); a gap of 3 would need 43 px')}
TRACKING = ((3, 30), (2, 37), (1, WIDTH))     # (letter gap, longest ink) for the normal face, the fan's habit
TRACKED = True


class Plates(object):
    def __init__(self, idlocal_bytes):
        self.D = idlocal_bytes
        self.n = struct.unpack_from('<I', self.D, 0)[0] // 8
        self._harvest()

    def _blob(self, i):
        o, s = struct.unpack_from('<II', self.D, i * 8)
        ents = [struct.unpack_from('<II', self.D, k * 8)[0] for k in range(self.n)]
        nxt = min([e for e in ents if e > o] + [len(self.D)])
        b = self.D[o:nxt]
        return decompress(b) if b[:1] == b'\x11' and (s & 0x80000000) else b

    def _grid(self, i):
        data, bpp, cnt, w, h = ncgr(self._blob(i))
        g = [[0] * (cnt * 8) for _ in range(8)]
        for t in range(cnt):
            tp = tile_pixels(data, t, bpp)
            for y in range(8):
                for x in range(8):
                    g[y][t * 8 + x] = tp[y][x]
        return g

    def _harvest(self):
        self.glyphs = dict(HAND)
        pend = {}
        for idx, name in FAN_NAMES.items():
            try:
                g = self._grid(idx)
            except Exception:
                continue
            W = len(g[0])
            txt = [any(g[y][x] == TEXT for y in range(8)) for x in range(W)]
            runs, s = [], None
            for x in range(W):
                if txt[x] and s is None: s = x
                if not txt[x] and s is not None: runs.append((s, x)); s = None
            if s is not None: runs.append((s, W))
            letters = [c for c in name if c != ' ']
            if len(runs) != len(letters):
                pend[idx] = (g, runs, name)
                continue
            for (a, b), ch in zip(runs, letters):
                cols = [tuple(1 if g[y][x] == TEXT else 0 for y in range(8)) for x in range(a, b)]
                self.glyphs.setdefault(ch, cols)
        # z, T, V come from plates whose letters touch; cut them by known runs
        if 31 in pend:   # Franziska: runs are Fr,a,n,z,i,s,k,a
            g, runs, _ = pend[31]
            if len(runs) == 8:
                a, b = runs[3]
                self.glyphs.setdefault('z', [tuple(1 if g[y][x] == TEXT else 0 for y in range(8)) for x in range(a, b)])
        for idx, first_two in ((74, 'TV'),):
            try:
                g = self._grid(idx)
            except Exception:
                continue
            W = len(g[0])
            txt = [any(g[y][x] == TEXT for y in range(8)) for x in range(W)]
            runs, s = [], None
            for x in range(W):
                if txt[x] and s is None: s = x
                if not txt[x] and s is not None: runs.append((s, x)); s = None
            for (a, b), ch in zip(runs[:2], first_two):
                self.glyphs.setdefault(ch, [tuple(1 if g[y][x] == TEXT else 0 for y in range(8)) for x in range(a, b)])
        # e-grave = e plus its accent
        if 'e' in self.glyphs and 'è' not in self.glyphs:
            e = [list(c) for c in self.glyphs['e']]
            if len(e) >= 3:
                e[1][0] = 1; e[2][1] = 1
            self.glyphs['è'] = [tuple(c) for c in e]

    # -- the fan's own faces, cut from its plates at build time -----------------------------------
    def _cut(self, idx, name):
        """[(letter, columns)] of fan plate idx, or [] when its ink does not split into exactly
        the letters of `name` (a plate that is not the fan's, or whose letters touch)."""
        key = (idx, name)
        cache = self.__dict__.setdefault('_cutcache', {})
        if key not in cache:
            try:
                g = self._grid(idx)
            except Exception:
                g = None
            out = []
            if g is not None:
                W = len(g[0])
                txt = [any(g[y][x] == TEXT for y in range(8)) for x in range(W)]
                runs, st = [], None
                for x in range(W):
                    if txt[x] and st is None: st = x
                    if not txt[x] and st is not None: runs.append((st, x)); st = None
                if st is not None: runs.append((st, W))
                letters = [c for c in name if c != ' ']
                if len(runs) == len(letters):
                    out = [(ch, [tuple(1 if g[y][x] == TEXT else 0 for y in range(8)) for x in range(a, b)])
                           for (a, b), ch in zip(runs, letters)]
            cache[key] = out
        return cache[key]

    def _letter(self, idx, name, ch):
        for c, cols in self._cut(idx, name):
            if c == ch:
                return cols
        raise ValueError('fan plate %d does not read %r (no clean letter %r): is this the AAI2 Final v2 ROM?' % (idx, name, ch))

    @staticmethod
    def _squeeze(cols, k, what):
        """Drop k columns that exactly repeat the one before them (the later one of each pair)."""
        cols = list(cols)
        for _ in range(k):
            for i in range(len(cols) - 1):
                if cols[i] == cols[i + 1]:
                    del cols[i + 1]
                    break
            else:
                raise ValueError('the fan %s has no repeated column to drop' % what)
        return cols

    def faces(self):
        """(normal, narrow, thin): letter -> columns."""
        if '_faces' not in self.__dict__:
            normal = dict(self.glyphs)
            narrow = dict(normal)
            seen = set()
            for idx, nm in NARROW_SOURCES:
                for ch, cols in self._cut(idx, nm):
                    if ch not in seen:
                        seen.add(ch)
                        narrow[ch] = cols
            t = normal.get('T')
            if not t or len(t) != 7 or t[0] != t[1] or t[-1] != t[-2]:
                raise ValueError("the fan's T is not the 7 px bar with a repeated end column the narrow T is cut from")
            narrow['T'] = list(t[1:-1])
            thin = {ch: normal[ch] for ch in THIN_SHARED}
            for idx, nm, letters in THIN_CUTS:
                for ch in letters:
                    thin[ch] = self._letter(idx, nm, ch)
            for idx, nm, ch, k in THIN_SQUEEZE:
                thin[ch] = self._squeeze(self._letter(idx, nm, ch), k, '%s of %s' % (ch, nm))
            for ch, cols in THIN_DRAWN.items():
                thin.setdefault(ch, cols)
            self._faces = (normal, narrow, thin)
        return self._faces

    @staticmethod
    def _pack(words, face, gap, wgaps):
        """Columns of a name: its words in `face`, `gap` blank columns between letters, wgaps[i]
        blank columns between word i and word i+1."""
        z = tuple([0] * 8)
        cols = []
        for i, w in enumerate(words):
            for k, ch in enumerate(w):
                if ch not in face:
                    raise ValueError('no letter %r for the plate text %r' % (ch, ' '.join(words)))
                cols += list(face[ch])
                if k < len(w) - 1: cols += [z] * gap
            if i < len(words) - 1: cols += [z] * wgaps[i]
        return cols

    def layout(self, name):
        """-> (columns, tier, word gaps). Tiers are tried in order and the first that fits WIDTH wins."""
        words = name.split(' ')
        nw = len(words) - 1
        normal, narrow, thin = self.faces()
        steps = TRACKING if TRACKED else ((1, WIDTH),)
        for gap, lim in steps:
            cols = self._pack(words, normal, gap, [WORD_GAP] * nw)
            if len(cols) <= lim:
                return cols, 'normal', [WORD_GAP] * nw
        cols = self._pack(words, narrow, 1, [WORD_GAP] * nw)
        if len(cols) <= WIDTH:
            return cols, 'narrow', [WORD_GAP] * nw
        # thin: first look for a margin of 1 px on both sides, narrowing the LAST word gaps first
        for limit in (WIDTH - 2, WIDTH):
            for narrowed in range(0, nw + 1):
                wg = [WORD_GAP] * (nw - narrowed) + [WORD_GAP - 1] * narrowed
                cols = self._pack(words, thin, 1, wg)
                if len(cols) <= limit:
                    return cols, 'thin', wg
        raise ValueError('%s: %d px does not fit the %d px bar in any tier' % (name, len(cols), WIDTH))

    def compose(self, idx, name):
        g = self._grid(idx)
        for y in range(8):
            for x in range(CLEAR_A, CLEAR_B):
                if g[y][x] == TEXT: g[y][x] = FILL
        cols, tier, wg = self.layout(name)
        x0 = FILL_A + (WIDTH - len(cols) + 1) // 2
        if x0 < FILL_A or x0 + len(cols) > FILL_B:
            raise ValueError('%s: text would leave the bar (%d px at column %d)' % (name, len(cols), x0))
        for i, col in enumerate(cols):
            for y in range(8):
                if col[y]: g[y][x0 + i] = TEXT
        self.placed = getattr(self, 'placed', {})
        self.placed[idx] = (name, tier, wg, len(cols), x0 - FILL_A, FILL_B - x0 - len(cols))
        return g

    def _encode(self, idx, g):
        b = bytearray(self._blob(idx))
        data, bpp, cnt, w, h = ncgr(bytes(b))
        pos = bytes(b).find(data)
        if not (pos > 0 and bpp == 4):
            raise ValueError('tile data not found or unexpected bpp (pos=%d, bpp=%d)' % (pos, bpp))
        for t in range(cnt):
            for y in range(8):
                for xx in range(0, 8, 2):
                    b[pos + t * 32 + y * 4 + xx // 2] = (g[y][t * 8 + xx + 1] << 4) | g[y][t * 8 + xx]
        return bytes(b)

    def rebuild(self):
        """Return (new idlocal bytes, plate count). Untouched entries keep
        their stored bytes; replaced ones are stored as literal-only LZ11
        (the engine accepts it; no compressor needed)."""
        repl = {}
        for idx, name in PLATES.items():
            repl[idx] = self._encode(idx, self.compose(idx, name))
        repl.update(Titles(self).replacements())
        ents = [struct.unpack_from('<II', self.D, i * 8) for i in range(self.n)]
        order = sorted(range(self.n), key=lambda i: ents[i][0])
        ext = {}
        for k, i in enumerate(order):
            ext[i] = (ents[i][0], ents[order[k + 1]][0] if k + 1 < self.n else len(self.D))
        table = bytearray(self.n * 8)
        body = bytearray()
        for i in range(self.n):
            o, s = ents[i]
            comp = s & 0x80000000
            stored = self.D[ext[i][0]:ext[i][1]]
            size = s & 0x7FFFFFFF
            if i in repl:
                raw = repl[i]
                if i in LZ_STORED:
                    # real LZ11 (tools/lz11.py), not the literal-only form: the same decoded
                    # size, a stream under a third of the literal-only one. bufcheck k bounds a
                    # nameplate by the fan's own slot (a few dense ones exceed it by a few bytes
                    # and are listed there); bufcheck d bounds the Promise Notebook strip (410
                    # bytes against 352) by its literal-only size
                    from lz11 import compress
                    stored = compress(raw)
                    size = len(raw); comp = 0x80000000
                else:
                    out = bytearray(b'\x11' + len(raw).to_bytes(3, 'little'))
                    for p in range(0, len(raw), 8):
                        out.append(0); out += raw[p:p + 8]
                    stored = bytes(out); size = len(raw); comp = 0x80000000
            while (self.n * 8 + len(body)) % 4: body += b'\x00'
            struct.pack_into('<II', table, i * 8, self.n * 8 + len(body), size | comp)
            body += stored
        return bytes(table) + bytes(body), len(repl)


def rebuild_idlocal(path):
    return Plates(open(path, 'rb').read()).rebuild()


# Strips the fan never translated: still the retail Japanese pixels. They have no fan reading to
# count letter runs against, so each is guarded by the sha256 of its 1024 bytes of tile data
# (and by the retail text its TITLES row names) instead; compose() raises on any other strip.
# 172 is the Court Record title of the Promise Notebook (itm03_00c, gk2_item_name_en
# "Promise Notebook"), read off the strip as 約束ノート.
RETAIL_JAPANESE = {
 172: ("約束ノート", '90c1d4f09cc259606871114ad69b337f2a50d9a980632ea4d7560fcf3e3cf847'),
}

# Entries stored as real LZ11 instead of the literal-only form the other redrawn strips use (same
# decoded size, a stream under a third of it): the Promise Notebook title strip and every redrawn
# nameplate. 23 of the 28 plates then fit inside the fan's own slot; five (50, 51, 55, 63, 66) are 4 to
# 8 bytes over it, which real LZ11 cannot avoid for dense ink. bufcheck.PLATE_STORED_OVER lists them
# with their limits: the loader reads the stored extent into a temporary buffer that is freed, and the
# destination is sized to the decoded size, which is the fan's for every plate (bufcheck k).
LZ_STORED = (172,) + tuple(sorted(PLATES))

# ---------------------------------------------------------------------------
# Evidence/profile TITLE strips: 128x16 graphics embedded in the same file's
# sprite bundles (header 0x0C + RECN + RNAN + RGCN, 32 tiles as four 32x16
# OAM objects). Text strokes are palette index 1 on a bar of index 2. The
# fan pre-rendered every title; these tables carry Capcom's official item
# and profile names (gk2_item_name_en / the profile name rows), keyed by the
# strip's entry index and GUARDED by the fan text expected there - a strip
# whose harvested text does not match is left untouched.
TITLES = {
 90:("Newspaper Article","Newspaper Clipping"),
 91:("Nicole's Tape Recorder","Ms. Lloyd's Tape"),
 92:("Bullet's Trajectory","Bullet Trajectory"),
 93:("Kay's Camera Data","Kay's Photographs"),
 94:("Security Plans","Security Plan"),
 96:("Assassin's Revolver","Revolver"),
 97:("Knightley's Revolver","Mr. Knight's Revolver"),
 105:("Crime Scene Notes","Mr. Knight's Body"),
 108:("Door Sensor","Door Sensors"),
 109:("Door Sensor","Door Sensors"),
 110:("Chessboard","Pocket Chess Set"),
 113:("Hound Piece","Dog Chess Piece"),
 114:("Prison Investigation","Prison Search"),
 116:("Knightley's Memo","Chess Diagram"),
 117:("Security Gate","Security Gates"),
 118:("Security Footage","Security Camera Footage"),
 119:("Tunnel Footprints","Tunnel Prints"),
 122:("Bloodstained Sheet","Bloody Tarp"),
 123:("Dogen's Bells","Mr. Kanis's Bells"),
 124:("Knightley's Cell Key","Mr. Knight's Cell Key"),
 125:("Simon's Device","Mr. Saint's Trick"),
 126:("Circuit Breaker","Breakers"),
 127:("Sahwit's Bracelet","Mr. Sahwit's Bracelet"),
 128:("Floor Plans","Building Layout"),
 129:("Stolen Uniform","Missing Guard Uniform"),
 133:("Signet Crest","Seal"),
 134:("Jeff's Teapot","Mr. Tangaroa's Teapot"),
 135:("Frame Fingermarks","Frame Finger Marks"),
 137:("Rock Salt Lamp","Salt Lamp"),
 138:("Rock Salt Lamp","Salt Lamp"),
 139:("Fluorescent Cloth","Luminous Cloth"),
 140:("Fake Desserts","Fake Confections"),
 141:("Delicia's Testimony","Ms. Scone's Statement"),
 142:("Winter Palace Photo","Winter Wing Photo"),
 143:("Art Gallery Pamphlet","Gallery Pamphlet"),
 145:("Poison Gas","Poison Gas Ingredients"),
 147:("Pisces Sketch","Pisces Statue Sketch"),
 150:("Dover's Sherbet Salon","Mr. Frost's Room"),
 152:("Semifinal Desserts","Semifinal Entries"),
 153:("IS-7 Incident File","IS-7 Incident Case File"),
 154:("Angel's Recipe Book","Ultimate Cookbook"),
 156:("Lift Trolley","Lift Cart"),
 157:("Pottery Shard","Ceramic Fragment"),
 159:("Sketch of Beauties","Larry's Sketches"),
 160:("Liquid Analysis Results","Gemini Case Analysis Results"),
 161:("Statute of Limitations","Statutes of Limitations Book"),
 162:("Used Gas Burner","Used Blowtorch"),
 163:("Yatagarasu's Badge","Yatagarasu Pin"),
 167:("Purple Flower","Magenta Flower"),
 168:("Grand Tower Pamphlet","Bigg Building Pamphlet"),
 169:("Kay's Memories","Kay's Recollections"),
 171:("Candelabra","Candelabrum"),
 172:("約束ノート","Promise Notebook"),
 173:("Autopsy Report","Coroner's Findings"),
 176:("Conductor's Clothes","Ringleader's Appearance"),
 177:("Lotta's Testimony","Ms. Hart's Statement"),
 178:("Stuffed Animal","Broken Plushie"),
 180:("Lotta's Photo","Ms. Hart's Picture"),
 181:("Blood on Hidden Lift","Elevator Blood"),
 182:("Costume Trunk","Clothes Box"),
 183:("Meeting Room Blood","Committee Chamber Blood"),
 185:("Karin's Testimony","Nurse Niedler's Statement"),
 186:("IS-7 Incident Documents","IS-7 Incident Case File"),
 187:("Letter from Unknown","Forged Letter"),
 189:("Crime Scene Notes","President Wang's Autopsy Report"),
 190:("Grand Tower","Bigg Building"),
 191:("Monster Movie Flyer","Creature Feature Flyer"),
 192:("Combination Lock","Movie Set Locks"),
 193:("Commemorative Photo","Behind-the-Scenes Photo"),
 194:("Moozilla's Head","Taurusaurus Head"),
 195:("Moozilla Doll","Taurusaurus Plushie"),
 196:("Security Camera Photo","Security Camera Footage"),
 197:("John's Practice Video","Shaun's Rehearsal Tape"),
 199:("Report on Knightley","Report on Knight"),
 200:("Knightley's Mementos","Knight's Possessions"),
 203:("Monster's Footprints","Monster Footprints"),
 205:("SS-5 Incident Files","SS-5 Incident Case File"),
 206:("Cameron's Autopsy Report","Mr. Aldown's Autopsy Report"),
 207:("Bloodstained Button","Bloody Button"),
 208:("Cameron's Photo","Mr. Aldown's Photograph"),
 209:("Cameron's Testimony","Mr. Aldown's Final Call"),
 211:("Mysterious Bloodstain","Mysterious Blood Stain"),
 214:("Correspondence Chess Memo","Correspondence Chess Diagram"),
 215:("Sleeping Drugs","Sedative"),
 216:("Lion Balloon","Lion Hot Air Balloon"),
 225:("Justine Courtney","Verity Gav\u00e8lle"),
 226:("Sebastian Debeste","Eustace Winner"),
 227:("Raymond Shields","Eddie Fender"),
 228:("Raymond Shields","Eddie Fender"),
 229:("Raymond Shields","Eddie Fender"),
 233:("Di-Jun Huang","Di-Jun Wang"),
 234:("Horace Knightley","Bronco Knight"),
 235:("Horace Knightley","Bronco Knight"),
 236:("Nicole Swift","Tabby Lloyd"),
 239:("Sirhan Dogen","Bodhidharma Kanis"),
 240:("Simon Keyes","Simeon Saint"),
 241:("Jay Elbird","Rocco Carcerato"),
 242:("Patricia Roland","Fifi Laguarde"),
 246:("John Marsh","Shaun Fenn"),
 247:("Jeffrey Master","Samson Tangaroa"),
 248:("Jeffrey Master","Samson Tangaroa"),
 249:("Jeffrey Master","Samson Tangaroa"),
 250:("Katherine Hall","Judy Bound"),
 251:("Dane Gustavia","Carmelo Gusto"),
 252:("Katherine Hall","Judy Bound"),
 253:("Delicia Scones","Delicia Scone"),
 254:("Raymond Shields","Eddie Fender"),
 255:("Delicia Scones","Delicia Scone"),
 256:("Delicia Scones","Delicia Scone"),
 257:("Dane Gustavia","Carmelo Gusto"),
 258:("Dane Gustavia","Carmelo Gusto"),
 259:("Isaac Dover","Artie Frost"),
 260:("Isaac Dover","Artie Frost"),
 263:("Bonnie Young","Hilda Hertz"),
 264:("Blaise Debeste","Excelsius Winner"),
 265:("Isaac Dover","Artie Frost"),
 266:("Karin Jenson","Florence Niedler"),
 267:("Ethan Rooke","Bastian Rook"),
 268:("Jill Crane","Rosie Ringer"),
 270:("Jack Cameron","Alf Aldown"),
}


# fan title readings - the harvest keys that cut the title font apart, and
# the guard that keeps a mis-indexed strip from being overdrawn
FAN_TITLES = {
 88:"Prosecutor's Badge",89:"Steel Samurai Balloon",90:"Newspaper Article",
 91:"Nicole's Tape Recorder",92:"Bullet's Trajectory",93:"Kay's Camera Data",
 94:"Security Plans",95:"Revolver",96:"Assassin's Revolver",97:"Knightley's Revolver",
 98:"Red Raincoat",99:"Bulletproof Attach\u00e9 Case",100:"Crime Scene Notes",
 101:"Bulletproof Vest",102:"Security Monitors",103:"Calling Card",104:"Bloody Bullet",
 105:"Crime Scene Notes",106:"Rope",107:"Rubber Glove",108:"Door Sensor",
 109:"Door Sensor",110:"Chessboard",111:"Black Dog",112:"Prison Roll Call",
 113:"Hound Piece",114:"Prison Investigation",115:"Wiped Floor",116:"Knightley's Memo",
 117:"Security Gate",118:"Security Footage",119:"Tunnel Footprints",120:"Autopsy Report",
 121:"Chisel",122:"Bloodstained Sheet",123:"Dogen's Bells",124:"Knightley's Cell Key",
 125:"Simon's Device",126:"Circuit Breaker",127:"Sahwit's Bracelet",128:"Floor Plans",
 129:"Stolen Uniform",130:"Attorney's Badge",131:"Contest Rules",132:"Crime Scene Notes",
 133:"Signet Crest",134:"Jeff's Teapot",135:"Frame Fingermarks",136:"Mansion Key",
 137:"Rock Salt Lamp",138:"Rock Salt Lamp",139:"Fluorescent Cloth",140:"Fake Desserts",
 141:"Delicia's Testimony",142:"Winter Palace Photo",143:"Art Gallery Pamphlet",
 145:"Poison Gas",147:"Pisces Sketch",148:"Chocolates",149:"Instant Camera",
 150:"Dover's Sherbet Salon",151:"Victim's Blood",152:"Semifinal Desserts",
 153:"IS-7 Incident File",154:"Angel's Recipe Book",155:"Family Photo",
 156:"Lift Trolley",157:"Pottery Shard",158:"Teapot",159:"Sketch of Beauties",
 160:"Liquid Analysis Results",161:"Statute of Limitations",162:"Used Gas Burner",
 163:"Yatagarasu's Badge",164:"Jammin' Ninja Mask",165:"Letter",166:"Ticket Stub",
 167:"Purple Flower",168:"Grand Tower Pamphlet",169:"Kay's Memories",170:"Keycard",
 171:"Candelabra",173:"Autopsy Report",174:"Keycard Record",175:"Victim's Letter",
 176:"Conductor's Clothes",177:"Lotta's Testimony",178:"Stuffed Animal",179:"Masks",
 180:"Lotta's Photo",181:"Blood on Hidden Lift",182:"Costume Trunk",
 183:"Meeting Room Blood",184:"Red Raincoat",185:"Karin's Testimony",
 186:"IS-7 Incident Documents",187:"Letter from Unknown",188:"Crime Scene Notes",
 189:"Crime Scene Notes",190:"Grand Tower",191:"Monster Movie Flyer",
 192:"Combination Lock",193:"Commemorative Photo",194:"Moozilla's Head",
 195:"Moozilla Doll",196:"Security Camera Photo",197:"John's Practice Video",
 198:"Mechanic's Gloves",199:"Report on Knightley",200:"Knightley's Mementos",
 201:"Bug",203:"Monster's Footprints",204:"Bouquet",205:"SS-5 Incident Files",
 206:"Cameron's Autopsy Report",207:"Bloodstained Button",208:"Cameron's Photo",
 209:"Cameron's Testimony",210:"Victim's Shoes",211:"Mysterious Bloodstain",
 212:"Fire",213:"Child's Drawing",214:"Correspondence Chess Memo",
 215:"Sleeping Drugs",216:"Lion Balloon",217:"Blue Truck",
 218:"Maggey Byrde",219:"Dick Gumshoe",220:"Kay Faraday",221:"Ema Skye",
 222:"Franziska von Karma",223:"Tyrell Badd",224:"Shi-Long Lang",
 225:"Justine Courtney",226:"Sebastian Debeste",227:"Raymond Shields",
 228:"Raymond Shields",229:"Raymond Shields",230:"Manfred von Karma",
 231:"Laurice Deauxnim",232:"Lotta Hart",233:"Di-Jun Huang",234:"Horace Knightley",
 235:"Horace Knightley",236:"Nicole Swift",237:"John Doe",238:"Shelly de Killer",
 239:"Sirhan Dogen",240:"Simon Keyes",241:"Jay Elbird",242:"Patricia Roland",
 243:"Frank Sahwit",244:"Regina Berry",245:"Penny Nichols",246:"John Marsh",
 247:"Jeffrey Master",248:"Jeffrey Master",249:"Jeffrey Master",
 250:"Katherine Hall",251:"Dane Gustavia",252:"Katherine Hall",
 253:"Delicia Scones",254:"Raymond Shields",255:"Delicia Scones",
 256:"Delicia Scones",257:"Dane Gustavia",258:"Dane Gustavia",
 259:"Isaac Dover",260:"Isaac Dover",261:"Will Powers",263:"Bonnie Young",
 264:"Blaise Debeste",265:"Isaac Dover",266:"Karin Jenson",267:"Ethan Rooke",
 268:"Jill Crane",270:"Jack Cameron",
}


class Titles(object):
    """The 128x16 evidence/profile title strips (index-1 strokes on index-2 bar)."""
    def __init__(self, plates):
        self.P = plates
        self._harvest()

    def _embedded_off(self, i):
        d = self.P._blob(i)
        if len(d) < 12 or d[0] != 0x0C: return None, None
        for o in [struct.unpack_from('<I', d, q)[0] for q in range(0, 12, 4)]:
            if o < len(d) and d[o:o+4] == b'RGCN':
                return d, o
        return None, None

    def _grid(self, i):
        d, o = self._embedded_off(i)
        data, bpp, cnt, w, h = ncgr(d[o:])
        g = [[0]*128 for _ in range(16)]
        for t in range(cnt):
            tp = tile_pixels(data, t, bpp)
            bx, by = (t // 8)*32 + (t % 8 % 4)*8, (t % 8 // 4)*8
            for y in range(8):
                for x in range(8):
                    g[by+y][bx+x] = tp[y][x]
        return g

    def _runs(self, g):
        txt = [any(g[y][x] == 1 for y in range(16)) for x in range(128)]
        runs, s = [], None
        for x in range(128):
            if txt[x] and s is None: s = x
            if not txt[x] and s is not None: runs.append((s, x)); s = None
        if s is not None: runs.append((s, 128))
        return runs

    def _harvest(self):
        self.glyphs = {}
        for i, name in sorted(FAN_TITLES.items()):
            try:
                g = self._grid(i)
            except Exception:
                continue
            runs = self._runs(g)
            letters = [c for c in name if c != ' ']
            if len(runs) != len(letters):
                continue
            for (a, b), ch in zip(runs, letters):
                if ch in self.glyphs: continue
                self.glyphs[ch] = [tuple(1 if g[y][x] == 1 else 0 for y in range(16))
                                   for x in range(a, b)]
        # period: a 2x2 dot on the baseline rows used by the harvested comma-free font
        if '.' not in self.glyphs:
            col = [0]*16; col[10] = col[11] = 1
            self.glyphs['.'] = [tuple(col), tuple(col)]
        if '\u00e8' not in self.glyphs and 'e' in self.glyphs:
            e = [list(c) for c in self.glyphs['e']]
            if len(e) >= 3:
                e[1][0] = 1; e[2][1] = 1  # grave accent above
            self.glyphs['\u00e8'] = [tuple(c) for c in e]
        if '\u2019' in FAN_TITLES and False: pass

    # Official titles too wide for the 128px strip fall back to trims built only
    # from the official title's own words (same discipline as condense.py), in
    # order of preference. A trim at normal letter spacing beats the full title
    # with its letters touching: through 1.6.2 compose() squashed 18 titles to
    # gap 0 before it would consider a trim, and "Creature Feature Flyer" drawn
    # that way is hard to read (rig playtest, 2026-09-03). Only "Ringleader's
    # Appearance" has no trim that keeps its meaning; it still squashes.
    TRIMS = {
        'Missing Guard Uniform': ['Guard Uniform'],
        "Mr. Tangaroa's Teapot": ["Tangaroa's Teapot"],
        "Ms. Scone's Statement": ["Scone's Statement"],
        'Poison Gas Ingredients': ['Poison Ingredients'],
        'Gemini Case Analysis Results': ['Gemini Analysis Results', 'Gemini Results'],
        'Statutes of Limitations Book': ['Statutes of Limitations', 'Statutes Book'],
        'Bigg Building Pamphlet': ['Building Pamphlet'],
        "President Wang's Autopsy Report": ["Wang's Autopsy Report", "Wang's Autopsy"],
        'Correspondence Chess Diagram': ['Chess Diagram'],
        'Creature Feature Flyer': ['Creature Flyer'],
        'Behind-the-Scenes Photo': ['Behind-the-Scenes'],
        "Shaun's Rehearsal Tape": ['Rehearsal Tape'],
        'SS-5 Incident Case File': ['SS-5 Case File'],
        "Mr. Aldown's Autopsy Report": ["Aldown's Autopsy Report", "Aldown's Autopsy"],
        "Mr. Aldown's Photograph": ["Aldown's Photograph"],
        "Mr. Aldown's Final Call": ["Aldown's Final Call"],
        "Nurse Niedler's Statement": ["Niedler's Statement"],
        'Security Camera Footage': ['Security Footage'],
        'Committee Chamber Blood': ['Chamber Blood'],
        'Mysterious Blood Stain': ['Blood Stain'],
    }

    @classmethod
    def candidates(cls, official):
        """The texts compose() may draw for a title, best first."""
        return [official] + list(cls.TRIMS.get(official, []))

    def compose(self, i, fan_expected, official):
        g = self._grid(i)
        # Guard: the strip we are about to overwrite must be the one this row
        # describes, or a wrong official name lands on the wrong card. The
        # readings were verified two ways (an audit of every title strip): every strip
        # re-read by template-matching the harvested glyphs, and the dozen the
        # segmenter cannot split - the long titles the fan hand-squeezed - read
        # by eye. Letter-count is the check that survives both cases; a strip
        # whose letters touch simply cannot be counted, so it is not evidence
        # of a mismatch and is allowed through.
        runs = self._runs(g)
        letters = [c for c in fan_expected if c != ' ']
        if i in RETAIL_JAPANESE:
            # untranslated retail kanji: letter runs mean nothing, the pixels must be exactly
            # the retail strip this row was written for
            text, want = RETAIL_JAPANESE[i]
            d, o = self._embedded_off(i)
            have = hashlib.sha256(bytes(ncgr(d[o:])[0])).hexdigest()
            if fan_expected != text or have != want:
                raise ValueError('strip %d is not the retail strip %r (tile data sha256 %s, expected %s) - '
                                 'wrong card?' % (i, text, have[:12], want[:12]))
        elif runs and len(runs) > len(letters):
            raise ValueError('strip %d has %d letter runs but %r has %d - wrong '
                             'card?' % (i, len(runs), fan_expected, len(letters)))
        # clear text
        for y in range(16):
            for x in range(128):
                if g[y][x] == 1: g[y][x] = 2
        # Every candidate is tried at normal letter spacing (gap 1) before any
        # candidate is squashed to gap 0 - see TRIMS.
        texts = self.candidates(official)
        cols = None
        for gap, sp in ((1, 4), (1, 3), (0, 3), (0, 2)):
            for text in texts:
                cand = []
                for ch in text:
                    if ch == ' ':
                        cand += [tuple([0]*16)] * sp
                        continue
                    cand += self.glyphs[ch] + [tuple([0]*16)] * gap
                while cand and not any(cand[-1]): cand.pop()
                if len(cand) <= 126:
                    cols = cand; break
            if cols is not None: break
        if cols is None:
            raise ValueError('%s: does not fit 126px' % official)
        x0 = (128 - len(cols)) // 2
        for k, col in enumerate(cols):
            for y in range(16):
                if col[y]: g[y][x0 + k] = 1
        return g

    def encode(self, i, g):
        d, o = self._embedded_off(i)
        b = bytearray(d)
        data, bpp, cnt, w, h = ncgr(bytes(d[o:]))
        pos = bytes(d).find(data, o)
        if not (pos > 0 and bpp == 4):
            raise ValueError('tile data not found or unexpected bpp (pos=%d, bpp=%d)' % (pos, bpp))
        for t in range(cnt):
            bx, by = (t // 8)*32 + (t % 8 % 4)*8, (t % 8 // 4)*8
            for y in range(8):
                for xx in range(0, 8, 2):
                    lo = g[by+y][bx+xx]; hi = g[by+y][bx+xx+1]
                    b[pos + t*32 + y*4 + xx//2] = (hi << 4) | lo
        return bytes(b)

    def replacements(self):
        out = {}
        for i, (fan_expected, official) in sorted(TITLES.items()):
            out[i] = self.encode(i, self.compose(i, fan_expected, official))
        return out
