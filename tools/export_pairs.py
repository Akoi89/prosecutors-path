import sys, os, io, json
sys.path.insert(0, os.path.dirname(__file__))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from spt import strings, render
from map_ids import ds_entries

m = json.load(open('dump/ds_to_collection_final.json'))
dsdata = dict(ds_entries('dump/ds_jp/jpn/spt.bin'))

def eng_path(name, src):
    folders = ('dump/eng', 'dump/eng_trial') if src == 'main' else ('dump/eng_trial', 'dump/eng')
    cands = [name]
    for suf in ('_tridl', '_dl'):
        if name.endswith(suf): cands.append(name[:-len(suf)])
    for c in cands:
        for folder in folders:
            p = os.path.join(folder, c + '.bin')
            if os.path.exists(p): return p
    return None

os.makedirs('out', exist_ok=True)
missing, done, rec_eq, rec_ne = [], 0, 0, 0
with io.open('out/gk2_jp_en_pairs.txt', 'w', encoding='utf-8') as fh:
    for k in sorted(m, key=int):
        i = int(k); info = m[k]
        ep = eng_path(info['name'], info['src'])
        if not ep:
            missing.append((i, info['name'], info['src'])); continue
        jp = [(c, render(u)) for _, _, c, u in strings(dsdata[i], True)]
        en = [(c, render(u)) for _, _, c, u in strings(open(ep, 'rb').read(), False)]
        if len(jp) == len(en): rec_eq += 1
        else: rec_ne += 1
        fh.write('=== DS[%d]  %s  (%s, score %.2f)  records JP=%d EN=%d\n'
                 % (i, info['name'], info['src'], info['score'], len(jp), len(en)))
        for n in range(max(len(jp), len(en))):
            fh.write('  [%d] JP: %s\n' % (n, jp[n][1] if n < len(jp) else '<none>'))
            fh.write('  [%d] EN: %s\n' % (n, en[n][1] if n < len(en) else '<none>'))
        fh.write('\n')
        done += 1
print('exported %d file pairs -> out/gk2_jp_en_pairs.txt' % done)
print('record counts equal: %d   mismatched: %d' % (rec_eq, rec_ne))
print('no English asset (%d):' % len(missing))
for i, n, s in missing: print('   DS[%d] %s (%s)' % (i, n, s))
