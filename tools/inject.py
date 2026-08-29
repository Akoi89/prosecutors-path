# -*- coding: utf-8 -*-
"""Inject the Collection's official English script into the GK2 DS ROM.

Structure is taken from the DS side and only the string CONTENT is swapped:
the DS engine addresses strings by index, so record count, per-record A fields and
the trailer word are carried over from the DS entry. An entry is only touched when
its string count matches the Collection file's exactly.
"""
import sys, os, io, json, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# The audit this prints contains Japanese, which the Windows console's default
# codepage cannot encode. reconfigure() rather than a fresh TextIOWrapper: wrapping
# sys.stdout.buffer again abandons whatever the old wrapper still had buffered, so
# anything printed before this module was imported would silently disappear.
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except AttributeError:                                    # pragma: no cover
    sys.stdout.flush()
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from spt import all_strings, parse
from build_spt import build_ds, build_archive
import dstext
from dstext import convert, ARGS
from episode_titles import retitle
from loc_patch import load_lookup, patch_entry
from map_ids import ds_entries
from paths import work, data

# Codes that end a message box (the box-count fingerprint used for alignment checks).
BOXEND = {0xE102, 0xE104, 0xE106, 0xE185, 0xE081}

# Capcom renamed every episode (Turnabout Target -> Turnabout Trigger, The Imprisoned
# Turnabout -> The Captive Turnabout, ...). Those names live in DS[460] strings 24-93,
# which is only the SAVE/LOAD slot list - the episode-select screen shows them as a
# BITMAP we have not located (it is somewhere in jpn/idlocal.bin, 676 entries).
# Switching only the save slots puts two different names for the same episode one menu
# apart, so leave the fan's names until the bitmap can be redrawn to match.
RETITLE = False

# Recover entries whose string COUNTS differ because the fan patch restructured
# them: joining long retail strings was split back, and regions re-cut into a
# different number of pieces are re-cut again at the fan's own boundaries
# (region_align below - it subsumed the earlier single-join `split_merged` and
# reproduces its 9 entries byte-identically, plus the shapes it could not reach:
# multiple joins in one entry, and p:q regions). Verification is strict per-string
# box-end code MULTISET equality against the fan layout - stronger than the JP
# profile's per-string counts, which is why realigned entries skip the relaid
# check. Every E081 argument (the index of the next string to play - all 2,650
# tail occurrences in the corpus are valid in-range indices; linear scenes use
# k+1, investigation hubs share a return target) is rewritten positionally from
# the fan counterpart, because official-layout indices are skewed after a re-cut
# and a stale index can make a string jump to itself.
SPLIT_MERGED = True

# Recover strings the fan patch RELAID by moving the cut point between neighbours.
# In 42 runs of adjacent strings (concentrated in Ep1 and Ep4-5) the fan shifted
# message boxes between two or three consecutive strings - always conserving the
# total (+8/-8, -38/+38) or adding exactly one E081 terminator when the retail
# layout's neighbour was empty. Joining the official strings for the run (absorbing
# each inner E081 tail where present - strings that end an entry carry none) and
# re-cutting at the fan's own boundaries reproduces the fan layout exactly. The
# only gate is strict per-string box-end code-multiset equality with the fan
# string: an official string that merged a box pair, or used a different box-end
# variant (DS[236] has E104 where the official holds E102), fails it and the whole
# run stays fan. No count tolerance applies here, unlike the ordinary swap path.
RECUT_SHIFTED = True


def _boxend_counts(u):
    """Box-end code multiset, walking with arities so argument units are never
    mistaken for codes."""
    c = collections.Counter()
    i, n = 0, len(u)
    while i < n:
        v = u[i]
        if 0xE000 <= v <= 0xF8FF:
            if v in BOXEND:
                c[v] += 1
            i += 1 + ARGS.get(v, 0)
        else:
            i += 1
    return c


def _code_positions(u):
    """Indices of control-code units, walking arities so argument units are never
    mistaken for codes."""
    out = []
    i = 0
    while i < len(u):
        v = u[i]
        if 0xE000 <= v <= 0xF8FF:
            out.append(i)
            i += 1 + ARGS.get(v, 0)
        else:
            i += 1
    return out


def rebuild_region(fan_strs, en_strs):
    """Join en_strs (absorbing inner E081 tails where present - strings that end
    an entry carry none), then re-cut into len(fan_strs) pieces at the fan's own
    boundaries, restoring the fan's E081 tails verbatim. The E081 argument is the
    index of the next string to jump to, so the fan's value is correct by
    construction here - the rebuild reproduces the fan's string indices. Strict
    per-string box-end multiset equality or None."""
    joined = []
    for t, u in enumerate(en_strs):
        u = list(u)
        if t < len(en_strs) - 1 and len(u) >= 2 and u[-2] == 0xE081:
            u = u[:-2]
        joined += u
    out, pos = [], 0
    for t, a in enumerate(fan_strs):
        if t == len(fan_strs) - 1:
            h = joined[pos:]
            # the official region can end without a terminator (empty retail
            # neighbour) - restore the fan's tail exactly like an inner one
            if _boxend_counts(h) != _boxend_counts(a) and len(a) >= 2 and a[-2] == 0xE081:
                w = _boxend_counts(a)
                w[0xE081] -= 1
                if _boxend_counts(h) == +w:
                    h = h + list(a[-2:])
        else:
            if len(a) < 2 or a[-2] != 0xE081:
                return None
            k = sum(1 for v in a if v in BOXEND) - 1
            if k <= 0:
                return None
            cut = _cut_after(joined[pos:], k)
            if cut is None:
                return None
            h = joined[pos:pos + cut] + list(a[-2:])
            pos += cut
        if _boxend_counts(h) != _boxend_counts(a):
            return None
        out.append(h)
    return out


def region_align(ds, en, maxspan=4):
    """Align official strings to the FAN layout when the string counts differ.

    Greedy: strings whose box-end multisets match pair 1:1; at a mismatch, the
    smallest (p fan : q en) region whose rebuild verifies is taken. Trailing
    empty/fragment official strings with no fan counterpart are consumed. This
    subsumes the fan's two restructurings - joining retail strings (with an added
    E081 terminator) and re-cutting a region into a different number of pieces -
    including several of them in one entry. Returns an en-shaped list or None;
    every returned string is multiset-verified against the fan, which is stronger
    than the count-level JP-profile check, so the relaid guard is skipped for
    entries rebuilt here.
    """
    du = [list(t[3]) for t in ds]
    eu = [list(t[3]) for t in en]
    P, Q = len(du), len(eu)
    i = j = 0
    out = []
    while i < P or j < Q:
        if i >= P and j < Q and len(eu[j]) <= 4 and not _boxend_counts(eu[j]):
            j += 1
            continue
        if i < P and j < Q and _boxend_counts(du[i]) == _boxend_counts(eu[j]):
            out.append(eu[j])
            i += 1; j += 1
            continue
        done = False
        for span in range(2, 2 * maxspan + 1):
            for p in range(1, min(maxspan, P - i) + 1):
                q = span - p
                if q < 1 or q > min(maxspan, Q - j) or (p == 1 and q == 1):
                    continue
                got = rebuild_region(du[i:i + p], eu[j:j + q])
                if got is not None:
                    out += got
                    i += p; j += q
                    done = True
                    break
            if done:
                break
        if not done:
            return None
    if len(out) != P:
        return None
    # Every E081 argument is a STRING INDEX in this entry - and after a p:q
    # region with p != q, indices carried from the official layout are skewed
    # against the fan layout this entry now uses (a copied arg can even point a
    # string at itself, which is a text loop). Rewrite every argument from the
    # fan counterpart positionally; the multiset gate guarantees the counts
    # match, so the copy is total.
    for t in range(P):
        u, a = out[t], du[t]
        pu = [k for k in _code_positions(u) if u[k] == 0xE081]
        pa = [k for k in _code_positions(a) if a[k] == 0xE081]
        if len(pu) != len(pa):
            return None
        for ku, ka in zip(pu, pa):
            if ku + 1 < len(u) and ka + 1 < len(a):
                u[ku + 1] = a[ka + 1]
    return [(0, 0, 0, u) for u in out]


def _cut_after(u, k):
    """Index just past the k-th box-end code, argument units included, or None."""
    i, n, seen = 0, len(u), 0
    while i < n:
        v = u[i]
        i += 1 + (ARGS.get(v, 0) if 0xE000 <= v <= 0xF8FF else 0)
        if v in BOXEND:
            seen += 1
            if seen == k:
                return i
    return None


def recut_run(ds, en, js):
    """Rebuild official strings js (consecutive indices) in the FAN's layout.

    Joins the official strings, then cuts at each fan boundary. Returns one unit
    list per index, or None the moment anything fails strict verification.
    """
    joined = []
    for t, j in enumerate(js):
        u = list(en[j][3])
        if t < len(js) - 1 and len(u) >= 2 and u[-2] == 0xE081:
            u = u[:-2]                # inner terminator absorbed by the fan's move
        joined += u
    out, pos = [], 0
    for t, j in enumerate(js):
        a = ds[j][3]
        if t == len(js) - 1:
            h = joined[pos:]
            # the official run can end on an EMPTY retail string - then the joined
            # stream has no final terminator and the fan's E081 tail is restored
            # exactly like an inner one
            if _boxend_counts(h) != _boxend_counts(a) and len(a) >= 2 and a[-2] == 0xE081:
                w = _boxend_counts(a)
                w[0xE081] -= 1
                if _boxend_counts(h) == +w:
                    h = h + list(a[-2:])
        else:
            if len(a) < 2 or a[-2] != 0xE081:
                return None
            k = sum(1 for v in a if v in BOXEND) - 1
            if k <= 0:
                return None
            cut = _cut_after(joined[pos:], k)
            if cut is None:
                return None
            h = joined[pos:pos + cut] + list(a[-2:])
            pos += cut
        if _boxend_counts(h) != _boxend_counts(a):
            return None
        out.append(h)
    return out


def file_id(rom, want):
    fnt = struct.unpack_from('<I', rom, 0x40)[0]
    def walk(dirid, prefix=''):
        off = fnt + (dirid & 0xFFF) * 8
        suboff, firstid, _ = struct.unpack_from('<IHH', rom, off)
        p = fnt + suboff; fid = firstid
        while True:
            t = rom[p]; p += 1
            if t == 0: return None
            ln = t & 0x7F; name = rom[p:p+ln].decode('shift_jis', 'replace'); p += ln
            if t & 0x80:
                sub = struct.unpack_from('<H', rom, p)[0]; p += 2
                r = walk(sub, prefix + name + '/')
                if r is not None: return r
            else:
                if prefix + name == want: return fid
                fid += 1
    return walk(0xF000)

def crc16(data):
    c = 0xFFFF
    for b in data:
        c ^= b
        for _ in range(8):
            c = (c >> 1) ^ 0xA001 if c & 1 else c >> 1
    return c

def eng_path(name, src):
    fs = ('dump/eng', 'dump/eng_trial') if src == 'main' else ('dump/eng_trial', 'dump/eng')
    for c in [name] + [name[:-len(x)] for x in ('_tridl', '_dl') if name.endswith(x)]:
        for f in fs:
            p = os.path.join(f, c + '.bin')
            if os.path.exists(p): return p

DEFAULT_OUT = os.path.join('out', 'GK2 (Official English, DS port).nds')


def main(base=None, out=None):
    os.chdir(work())
    BASE = base or os.environ.get('GK2_ROM',
                                  'Gyakuten Kenji 2 (AAI2 Final v2).nds')
    OUT = out or DEFAULT_OUT
    # Injecting a ROM onto itself destroys the input halfway through and yields a
    # doubly-patched file. Easy to do by accident once a previous output is lying
    # around next to the fan ROM.
    if os.path.abspath(BASE) == os.path.abspath(OUT):
        raise SystemExit('the output would overwrite the input ROM: %s' % OUT)
    # ships with the tool (inside the bundle when frozen), unlike everything
    # else under dump/, which the user extracts from their own copies
    m = json.load(open(data('ds_to_collection_final.json')))
    # The two guards below compare against the retail JAPANESE script, but need
    # only COUNTS from it, never text - so the counts ship with the tool and the
    # user does not have to supply a second ROM. See tools/jp_profile.py.
    jp = json.load(open(data('jp_structure.json')))
    raw = open('dump/ds_fan/jpn/spt.bin', 'rb').read()
    ntbl = struct.unpack_from('<I', raw, 0)[0] // 8
    entries = {}
    for i in range(ntbl):
        o, s = struct.unpack_from('<II', raw, i * 8)
        entries[i] = raw[o:o+s] if s else None
    fan = dict(ds_entries('dump/ds_fan/jpn/spt.bin'))

    swapped = overflow = mismatch = skipped = demo = untranslated = tiny = shape = dropped = boxkeep = 0
    restructured = relaidn = unmerged = recut = hollowed = 0
    sparse_kept = sparse_entries = 0
    unmapped = {}
    for k in sorted(m, key=int):
        i = int(k); info = m[k]
        if info['score'] < 0.40 or i not in fan:
            skipped += 1; continue
        # A DS entry with almost no text produces a 1-2 character signature, which
        # fuzzy-matches anything and scores a meaningless 1.00 (DS[319] -> map0b).
        # There is nothing to gain translating these, so leave them alone.
        if info['ds_chars'] < 12:
            tiny += 1; continue
        p = eng_path(info['name'], info['src'])
        if not p:
            skipped += 1; continue
        ds = list(all_strings(fan[i], True))
        en = list(all_strings(open(p, 'rb').read(), False))
        # Capcom's English bundle is imperfect in two ways, and BOTH are per-RECORD,
        # not per-file: a few records are literal "DEMO TEXT" placeholders, and some
        # files were never localised and still hold Japanese. Skipping whole files
        # threw away 16,780 letters of perfectly good official English that sat
        # alongside ~1,000 letters of stub. Fall back only on the offending records.
        realigned = False
        if len(ds) != len(en):
            r = region_align(ds, en) if SPLIT_MERGED else None
            if r is None:
                mismatch += 1; continue      # index layout must not shift
            en = r; unmerged += 1; realigned = True
        # STRUCTURAL PREREQUISITE - the fan patch's own layout must still match the
        # JAPANESE original. The Collection matches the JP script box-for-box, but
        # the fan REDISTRIBUTED message boxes between strings in 54 entries
        # (DS[4]: +8 boxes into str3, -8 out of str4; DS[27]: -38/+38). Swapping
        # per string into a restructured entry replays the moved boxes in official
        # wording after the fan has already shown them, and overwrites whatever the
        # DS keeps at those indices - for DS[4] that is the Logic tutorial and the
        # 'Gourd Lake Park / Stage' location card, and the game hangs there.
        # Box counts are the tell: 375 entries match the JP exactly and are safe.
        # The relayout is confined to the STRINGS whose box count moved, so revert
        # just those and keep the rest of the entry official (DS[4]: only str3/4/6
        # moved, so str0/1/2/5/7 - including the Newspaper Clipping scene - are
        # still safe to swap).
        relaid = set()
        jpb = None
        # Entries rebuilt by region_align skip the JP-profile relaid check: every
        # one of their strings was verified against the fan by box-end code
        # MULTISET, which is strictly stronger than the profile's per-string
        # counts (and the profile's string indices no longer line up anyway).
        prof = None if realigned else jp.get(str(i))
        if prof:
            jpb = prof['boxes']
            if len(jpb) != len(ds):
                restructured += 1; continue      # cannot compare; leave it alone
            relaid = {j2 for j2 in range(len(ds))
                      if sum(1 for v in ds[j2][3] if v in BOXEND) != jpb[j2]}
        if relaid and RECUT_SHIFTED:
            en = list(en)
            block = []
            for j2 in sorted(relaid) + [None]:
                if block and j2 != block[-1] + 1:
                    if len(block) >= 2:
                        got = recut_run(ds, en, block)
                        if got is not None:
                            for t, jj in enumerate(block):
                                en[jj] = (0, 0, 0, got[t])
                            relaid -= set(block)
                            recut += len(block)
                    block = []
                block.append(j2)
        conv = []
        for n_, (_, _, _, u) in enumerate(en):
            if n_ in relaid:
                conv.append(list(ds[n_][3])); relaidn += 1; continue
            asc = ''.join(chr(v) for v in u if v < 0x80)
            cj = sum(1 for v in u if 0x3040 <= v <= 0x30FF or 0x4E00 <= v <= 0x9FFF)
            la = sum(1 for v in u if 0x41 <= v <= 0x5A or 0x61 <= v <= 0x7A)
            if 'DEMO TEXT' in asc:
                conv.append(list(ds[n_][3])); demo += 1; continue
            if cj > max(4, la * 0.25):
                conv.append(list(ds[n_][3])); untranslated += 1; continue
            d, un = convert(u)
            for v in un: unmapped[v] = unmapped.get(v, 0) + 1
            conv.append(d)
        hfan = parse(fan[i], True)[0]
        # STRUCTURAL ALIGNMENT CHECK. Matching string COUNTS is not enough: the
        # Collection sometimes distributes the same scene across strings differently
        # (DS[115] str5 = 3,582 units on the DS, 0 in the Collection), and it omits
        # DS-only content such as the touch/A-Button tutorials (DS[4] str3: 16 message
        # boxes on the DS, 10 in the Collection). Substituting index-by-index then
        # scrambles the scene or drops a message the engine waits on - which HANGS the
        # game. Reject the whole entry if any string would lose message boxes.
        END = {0xE102, 0xE104, 0xE106, 0xE185, 0xE081}
        PRINT = lambda u: sum(1 for v in u if 0xFF01 <= v <= 0xFF5E or 0x21 <= v <= 0x7E)
        # (b) scene SHIFT / hollow strings: a DS string with real dialogue whose
        # official counterpart is nearly empty. Two very different causes share the
        # symptom. When the JP profile confirms the string's box count is unchanged,
        # the scene is NOT redistributed - the Collection simply has a hole at that
        # slot (trial-build cuts, all in Ep1 free roam), and the string reverts to
        # fan individually, exactly like a DEMO TEXT record. Only when the profile
        # cannot vouch for the alignment is the whole entry rejected, because then
        # index-by-index substitution could scramble the scene (the original case,
        # DS[115] str5 = 3,582 units on the DS and 0 in the Collection, is now
        # normally repaired upstream by recut_run).
        hollow = [j2 for j2 in range(len(ds))
                  if PRINT(ds[j2][3]) > 200 and PRINT(conv[j2]) < 0.2 * PRINT(ds[j2][3])]
        if hollow:
            jpb_ok = jpb is not None and len(jpb) == len(ds)
            if jpb_ok and all(sum(1 for v in ds[j2][3] if v in BOXEND) == jpb[j2]
                              for j2 in hollow):
                for j2 in hollow:
                    conv[j2] = list(ds[j2][3]); hollowed += 1
            else:
                dropped += 1; continue
        # (a) per-string: the Collection omits DS-only content such as the touch /
        # A-Button tutorials (DS[4] str3: 16 message boxes on the DS, 10 here). Losing
        # a box the engine waits on HANGS the game, so keep the fan's string for it.
        # Losing ONE box is benign and common (868 of 913 cases) - the official
        # localization simply merges a pair. Losing two or more means DS-only content
        # is missing, e.g. DS[4] str3 drops 6 boxes including the A-Button tutorial,
        # and the engine hangs waiting for it.
        for j2 in range(len(ds)):
            a2 = sum(1 for v in ds[j2][3] if v in END)
            b2 = sum(1 for v in conv[j2] if v in END)
            if a2 - b2 >= 2:
                conv[j2] = list(ds[j2][3]); boxkeep += 1
        trailer, scale, longest = hfan['term'], hfan['scale'], hfan['last']
        # Structural sanity check: the Collection file should drive roughly the same
        # engine commands as the DS original. A wrong match shows up as near-zero
        # overlap in the control-code profile.
        if prof:
            a = collections.Counter({int(k, 16): v for k, v in prof['ctrl'].items()})
            b = collections.Counter(v for c2 in conv for v in c2 if 0xE000 <= v <= 0xF8FF)
            if a and sum((a & b).values()) / sum(a.values()) < 0.35:
                # A near-zero profile overlap usually means a WRONG file match -
                # reject. But the exam/exam_ask confrontation banks fail this test
                # for a different reason: only the trial bundle carries them, and
                # it populates just the demo's rows (215 of 848), so the converted
                # file can never cover the full JP profile. For matches this
                # confident, fall back to swapping the populated rows one by one -
                # official English text in a string whose box-end multiset equals
                # the fan's exactly - and keep fan for everything else.
                if info['score'] < 0.90:
                    shape += 1; continue
                # These rows are OPTION-WIDGET lines, not dialogue: every fan row
                # is a single line, up to ~306px - far wider than the dialogue box
                # the default conversion wraps for. Re-convert unwrapped, and use
                # the fan's own widest row as the widget's proven budget: anything
                # wider keeps the fan line rather than risking a clip.
                TYPO = {0x2018: "'", 0x2019: "'", 0x201C: '"', 0x201D: '"',
                        0x2013: '-', 0x2014: '-', 0x2026: '.', 0x2025: '.'}
                def _rowpx(u):
                    segs = [0]
                    k2 = 0
                    while k2 < len(u):
                        v = u[k2]
                        if 0xE000 <= v <= 0xF8FF:
                            k2 += 1 + ARGS.get(v, 0); continue
                        if v == 0x0A:
                            segs.append(0)
                        else:
                            ch = (chr(v - 0xFEE0) if 0xFF01 <= v <= 0xFF5E else
                                  ' ' if v == 0xFF3F else
                                  TYPO.get(v) or (chr(v) if 0x20 <= v < 0x7F else None))
                            # an unpriceable glyph poisons the row: force it wide so
                            # the budget test can only fail toward keeping fan
                            segs[-1] += 9999 if ch is None else dstext._w(ch)
                        k2 += 1
                    return max(segs), len(segs)
                # the budget comes from the fan's ENGLISH rows only - the bank's
                # untranslated Japanese placeholder rows are not display-proven
                # and their glyphs are unpriceable anyway
                lat = [t[3] for t in ds
                       if t[3] and sum(1 for v in t[3]
                                       if 0xFF21 <= v <= 0xFF5A or 0x41 <= v <= 0x7A) > 4]
                if not lat:
                    shape += 1; continue
                budget = max(_rowpx(u)[0] for u in lat)
                kept = gained = 0
                for j2 in range(len(ds)):
                    u2 = en[j2][3]
                    flat, _ = convert(u2, wrap=False, page=False, hard_nl=False)
                    la2 = sum(1 for v in flat if 0xFF21 <= v <= 0xFF5A or 0x41 <= v <= 0x7A)
                    px2, nl2 = _rowpx(flat)
                    if (la2 == 0 or j2 in relaid or nl2 > 1 or px2 > budget
                            or _boxend_counts(flat) != _boxend_counts(ds[j2][3])):
                        if list(conv[j2]) != list(ds[j2][3]):
                            conv[j2] = list(ds[j2][3]); kept += 1
                    else:
                        conv[j2] = flat
                        if list(flat) != list(ds[j2][3]):
                            gained += 1
                if not gained:
                    # nothing official survived the per-row gate - keep the fan
                    # entry byte-for-byte rather than rebuilding its container
                    shape += 1; continue
                sparse_kept += kept; sparse_entries += 1
        # Last net: a SHORT fan string emptied outright by the Collection (DS[13]
        # str1, an Ep1 NPC line the trial build cut - 53 chars, one box, invisible
        # to both the 200-char hollow floor and the lose-two-boxes guard). Runs
        # AFTER every entry-level guard so it can never change an entry's verdict,
        # and demands English fan text with a box (walked with arities, so argument
        # bytes never count as text) - the demo entries' Japanese placeholder stubs
        # stay gone.
        def _wprint(u):
            n2 = i2 = 0
            while i2 < len(u):
                v2 = u[i2]
                if 0xE000 <= v2 <= 0xF8FF:
                    i2 += 1 + ARGS.get(v2, 0); continue
                if 0xFF01 <= v2 <= 0xFF5E or 0x21 <= v2 <= 0x7E:
                    n2 += 1
                i2 += 1
            return n2
        for j2 in range(len(ds)):
            fu = ds[j2][3]
            cj2 = sum(1 for v in fu if 0x3040 <= v <= 0x30FF or 0x4E00 <= v <= 0x9FFF)
            la2 = sum(1 for v in fu if 0xFF21 <= v <= 0xFF5A or 0x41 <= v <= 0x7A)
            if (_wprint(fu) > 0 and _wprint(conv[j2]) == 0
                    and la2 > max(4, cj2)
                    and sum(1 for v in fu if v in BOXEND) > 0):
                conv[j2] = list(fu); hollowed += 1
        recs = [(ds[j][1], conv[j]) for j in range(1, len(ds))]
        try:
            entries[i] = build_ds(conv[0], recs, trailer, scale, longest)
            swapped += 1
        except OverflowError:
            overflow += 1

    # Evidence/profile descriptions, Logic cards and topics are not in the Collection's
    # script files at all - they live in the localization string tables. Patch those in.
    loc = load_lookup()
    locn = 0
    for idx, src, box in ((432, 'dump/jpn_trial/detailMsg.bin', 'detailMsg'),
                          (395, 'dump/jpn/logicKW.bin', 'logicKW')):
        if entries.get(idx) and entries[idx][:4] == b' TPS':
            nd, c = patch_entry(entries[idx], src, loc, box)
            if c: entries[idx] = nd; locn += c
    print('strings patched from localization tables:  %d' % locn)

    # The episode titles live in DS[460], which is kept as fan text (its Collection
    # counterpart is untranslated). Patch the official names in on top.
    titles = 0
    if RETITLE:
        for i, d in entries.items():
            if d and d[:4] == b' TPS':
                nd, c = retitle(d)
                if c: entries[i] = nd; titles += c
    print('episode titles switched to official names:   %d%s'
          % (titles, '' if RETITLE else '  (RETITLE off - keeping fan names)'))

    newspt = build_archive(entries)
    print('entries replaced with official English: %d' % swapped)
    print('kept fan text - string count mismatch:  %d' % mismatch)
    print('entries where a joined string was split back: %d' % unmerged)
    print('relaid strings rebuilt in the fan layout:   %d' % recut)
    print('hollow official strings kept as fan:       %d' % hollowed)
    print('kept fan text - over 64 KB u16 cap:     %d' % overflow)
    print('records kept as fan - DEMO TEXT stub:      %d' % demo)
    print('records kept as fan - still Japanese:       %d' % untranslated)
    print('kept fan text - too little text to map: %d' % tiny)
    print('kept fan text - control-code shape off:  %d' % shape)
    print('sparse official banks swapped row-by-row: %d (%d rows kept fan)'
          % (sparse_entries, sparse_kept))
    print('kept fan text - scene shifted between strings: %d' % dropped)
    print('kept fan text - cannot align to JP original: %d' % restructured)
    print('records kept as fan - fan relaid it vs JP:    %d' % relaidn)
    print('records kept as fan - would lose a message box: %d' % boxkeep)
    print('kept fan text - no/weak mapping:        %d' % skipped)
    print('spt.bin: fan %.2f MB -> new %.2f MB' % (len(raw)/1e6, len(newspt)/1e6))
    if unmapped:
        print('unmapped code points: %d distinct, %d occurrences'
              % (len(unmapped), sum(unmapped.values())))

    rom = bytearray(open(BASE, 'rb').read())
    fid = file_id(rom, 'jpn/spt.bin')
    fat = struct.unpack_from('<I', rom, 0x48)[0]
    while len(rom) % 512: rom += b'\xFF'
    start = len(rom)
    rom += newspt
    while len(rom) % 512: rom += b'\xFF'
    struct.pack_into('<II', rom, fat + fid * 8, start, start + len(newspt))
    struct.pack_into('<I', rom, 0x80, len(rom))
    cap = 0
    while (128 * 1024) << cap < len(rom): cap += 1
    rom[0x14] = cap
    struct.pack_into('<H', rom, 0x15E, crc16(bytes(rom[:0x15E])))
    os.makedirs('out', exist_ok=True)
    open(OUT, 'wb').write(bytes(rom))
    print('wrote %s  (%.2f MB)' % (OUT, len(rom)/1e6))

if __name__ == '__main__':
    _a = [a for a in sys.argv[1:] if not a.startswith('-')]
    _o = sys.argv[sys.argv.index('-o') + 1] if '-o' in sys.argv[:-1] else None
    main(_a[0] if _a else None, _o)
