# -*- coding: utf-8 -*-
"""Inject the Collection's official English script into the GK2 DS ROM.

Structure is taken from the DS side and only the string CONTENT is swapped:
the DS engine addresses strings by index, so record count, per-record A fields and
the trailer word are carried over from the DS entry. An entry is only touched when
its string count matches the Collection file's exactly.
"""
import sys, os, io, json, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from spt import all_strings, parse
from build_spt import build_ds, build_archive
from dstext import convert
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

def main(base=None, out=None):
    os.chdir(work())
    BASE = base or os.environ.get('GK2_ROM',
                                  'Gyakuten Kenji 2 (AAI2 Final v2).nds')
    OUT = out or os.path.join('out', 'GK2 (Official English, DS port).nds')
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
    restructured = relaidn = 0
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
        if len(ds) != len(en):
            mismatch += 1; continue          # index layout must not shift
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
        prof = jp.get(str(i))
        if prof:
            jpb = prof['boxes']
            if len(jpb) != len(ds):
                restructured += 1; continue      # cannot compare; leave it alone
            relaid = {j2 for j2 in range(len(ds))
                      if sum(1 for v in ds[j2][3] if v in BOXEND) != jpb[j2]}
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
        # (b) whole-entry SHIFT: the Collection spreads the same scene across strings
        # differently (DS[115] str5 = 3,582 units on the DS, 0 in the Collection).
        # Index-by-index substitution would scramble the scene, so reject the entry.
        if any(PRINT(ds[j2][3]) > 200 and PRINT(conv[j2]) < 0.2 * PRINT(ds[j2][3])
               for j2 in range(len(ds))):
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
                shape += 1; continue
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
    print('kept fan text - over 64 KB u16 cap:     %d' % overflow)
    print('records kept as fan - DEMO TEXT stub:      %d' % demo)
    print('records kept as fan - still Japanese:       %d' % untranslated)
    print('kept fan text - too little text to map: %d' % tiny)
    print('kept fan text - control-code shape off:  %d' % shape)
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
