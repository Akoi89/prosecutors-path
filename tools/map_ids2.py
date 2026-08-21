import sys, os, io, json, collections
sys.path.insert(0, os.path.dirname(__file__))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from map_ids import sig, ds_entries

N = 6
def grams(s):
    return set(s[i:i+N] for i in range(len(s)-N+1)) if len(s) >= N else {s}

ds   = {i: sig(e, True) for i, e in ds_entries('dump/ds_jp/jpn/spt.bin')}
coll = {f[:-4]: sig(open('dump/jpn/'+f,'rb').read(), False) for f in os.listdir('dump/jpn')}
dg   = {i: grams(v) for i, v in ds.items()}
cg   = {k: grams(v) for k, v in coll.items()}

scores = {}
for i, a in dg.items():
    best = []
    for k, b in cg.items():
        if not a or not b: continue
        inter = len(a & b)
        if not inter: continue
        j = inter / len(a | b)
        best.append((j, k))
    best.sort(reverse=True)
    scores[i] = best[:3]

# mutual-best greedy assignment
pairs = sorted(((s[0][0], i, s[0][1]) for i, s in scores.items() if s), reverse=True)
used, m = set(), {}
for j, i, k in pairs:
    if k in used or i in m: continue
    m[i] = (k, j); used.add(k)

buckets = collections.Counter()
for i,(k,j) in m.items():
    buckets['>=0.95' if j>=.95 else '>=0.80' if j>=.8 else '>=0.50' if j>=.5 else '<0.50'] += 1
print('assigned %d / %d DS entries' % (len(m), len(ds)))
print('confidence:', dict(buckets))
print('\nweak/unassigned DS entries:')
for i in sorted(ds):
    if i not in m:
        print('  idx %-4d empty=%s len=%d' % (i, not ds[i], len(ds[i])))
    elif m[i][1] < 0.5:
        print('  idx %-4d -> %-28s j=%.2f len=%d' % (i, m[i][0], m[i][1], len(ds[i])))
json.dump({str(i): [k, round(j,4)] for i,(k,j) in m.items()},
          open('dump/ds_to_collection.json','w'), indent=1)
print('\nunused Collection JPN files:', sorted(set(coll) - used))
