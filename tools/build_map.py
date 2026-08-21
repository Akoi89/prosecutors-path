import sys, os, io, json, collections
sys.path.insert(0, os.path.dirname(__file__))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from map_ids import sig, ds_entries

N = 6
g = lambda s: set(s[i:i+N] for i in range(len(s)-N+1)) if len(s) >= N else ({s} if s else set())

ds = {i: sig(e, True) for i, e in ds_entries('dump/ds_jp/jpn/spt.bin')}

# JPN pool for matching; ENG pool for the eventual text source
jp, en = {}, {}
for folder, tag in (('dump/jpn', 'main'), ('dump/jpn_trial', 'trial')):
    for f in os.listdir(folder):
        jp[(f[:-4], tag)] = sig(open(os.path.join(folder, f), 'rb').read(), False)
for folder, tag in (('dump/eng', 'main'), ('dump/eng_trial', 'trial')):
    for f in os.listdir(folder):
        en[(f[:-4], tag)] = os.path.join(folder, f)

jg = {k: g(v) for k, v in jp.items()}
cand = collections.defaultdict(list)
for i, a in ds.items():
    if not a: continue
    ga = g(a)
    for k, b in jg.items():
        inter = len(ga & b)
        if inter:
            cand[i].append((inter / len(ga | b), k))
    cand[i].sort(reverse=True)

pairs = sorted(((c[0][0], i, c[0][1]) for i, c in cand.items() if c), reverse=True)
used, m = set(), {}
for j, i, k in pairs:
    if k in used or i in m: continue
    m[i] = (k, j); used.add(k)
# second pass over what's left
for i, c in cand.items():
    if i in m: continue
    for j, k in c:
        if k not in used:
            m[i] = (k, j); used.add(k); break

conf = collections.Counter()
covered = miss_en = 0
tot_chars = sum(len(v) for v in ds.values())
cov_chars = 0
out = {}
for i in sorted(ds):
    if not ds[i]:
        conf['empty (no text)'] += 1; continue
    if i not in m:
        conf['unmatched'] += 1; continue
    (name, tag), j = m[i]
    b = '>=0.90' if j >= .9 else '>=0.70' if j >= .7 else '>=0.40' if j >= .4 else '<0.40'
    conf[b] += 1
    if j >= .4:
        covered += 1; cov_chars += len(ds[i])
        if (name, tag) not in en and (name, 'main') not in en and (name, 'trial') not in en:
            miss_en += 1
    out[i] = dict(name=name, src=tag, score=round(j, 4), ds_chars=len(ds[i]))

print('DS entries: %d  (with text: %d)' % (len(ds), sum(1 for v in ds.values() if v)))
print('match confidence:', dict(conf))
print('usable matches (>=0.40): %d   of which English asset missing: %d' % (covered, miss_en))
print('DS text coverage: %d / %d chars = %.1f%%' % (cov_chars, tot_chars, 100*cov_chars/tot_chars))
json.dump(out, open('dump/ds_to_collection_final.json', 'w'), indent=1)
print('\nstill unmatched / weak (non-empty):')
for i in sorted(ds):
    if ds[i] and (i not in m or m[i][1] < 0.4):
        w = ('%s %.2f' % (m[i][0][0], m[i][1])) if i in m else '-'
        print('  idx %-4d chars=%-6d best=%s' % (i, len(ds[i]), w))
