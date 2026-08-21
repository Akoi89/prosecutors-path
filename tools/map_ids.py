import sys, os, struct, re, hashlib, collections
sys.path.insert(0, os.path.dirname(__file__))
from spt import parse, units, all_strings

CTRL = lambda u: 0xE000 <= u <= 0xF8FF

def sig(d, ds):
    """Text-only signature of a whole SPT file: printable chars, control codes dropped.

    MUST use all_strings, not the record table alone - string 0 is described by the
    header and holds ALL the text in some entries (82 of them, 62,836 chars). Missing
    it made those entries look empty, so they went unmapped or matched garbage.
    """
    out = []
    for _, _, _, u in all_strings(d, ds):
        for v in u:
            if v and not CTRL(v) and v not in (0x0A, 0x09, 0x20):
                out.append(chr(v))
    return ''.join(out)

def ds_entries(path):
    d = open(path, 'rb').read()
    n = struct.unpack_from('<I', d, 0)[0] // 8
    for i in range(n):
        o, s = struct.unpack_from('<II', d, i*8)
        if s and d[o:o+4] == b' TPS':
            yield i, d[o:o+s]

if __name__ == '__main__':
    ds = {i: sig(e, True) for i, e in ds_entries('dump/ds_jp/jpn/spt.bin')}
    coll = {}
    for f in os.listdir('dump/jpn'):
        coll[f[:-4]] = sig(open('dump/jpn/' + f, 'rb').read(), False)
    print('DS entries=%d  Collection JPN=%d' % (len(ds), len(coll)))

    by = collections.defaultdict(list)
    for k, v in coll.items():
        by[v].append(k)
    exact = {i: by[v][0] for i, v in ds.items() if len(by.get(v, [])) == 1}
    amb   = {i: by[v]    for i, v in ds.items() if len(by.get(v, [])) > 1}
    print('exact unique matches: %d   ambiguous: %d   unmatched: %d'
          % (len(exact), len(amb), len(ds) - len(exact) - len(amb)))
    un = [i for i in ds if i not in exact and i not in amb]
    print('sample unmatched DS idx:', un[:12])
    for i in un[:3]:
        print('  idx %d len=%d  %r' % (i, len(ds[i]), ds[i][:90]))
