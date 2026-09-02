# -*- coding: utf-8 -*-
"""Map each DS Logic keyword slot to Capcom's official short name.

The DS has no keyword names as text: they exist only as card images
(jpn/logic_keyword_local.bin). What it does have is each keyword's Japanese
DESCRIPTION (jpn/logicKW.bin, 133 slots, 30 of them the dummy 削除). The
Collection has both the descriptions and the names, in two string tables whose
rows are keyed gk2_logic{ep}_{idx}: names use HEX indices (00a, 00b, 01a), the
descriptions DECIMAL ones (010, 011, 026), and the numbering drifts in Episode 3.
So the join is: DS description -> Collection description row -> the name row of
the same RANK within the episode, with two guards:

  - where an episode has more descriptions than names, the orphan description is
    the one whose removal maximises character overlap between paired names and
    descriptions (Episode 3 has a duplicated description);
  - Episode 3 lists 'Railing' and 'Where Kay fell' in the opposite order from
    their descriptions; those two are assigned by meaning (see OVERRIDES).

Needs dump/loc_en.json, dump/loc_ja.json and dump/loc_keys.json (shared-table
key names, written by build.py's extraction step).

    python tools/logic_names.py            prints the map and the leftovers
"""
import io, os, re, json, sys
sys.path.insert(0, os.path.dirname(__file__))
from spt import all_strings
from loc_patch import _ds_plain
from paths import work

DUMMY = u'削除'
# (description prefix -> official English name) for the Episode 3 swap
OVERRIDES = [
    (u'屋台の方角から歩いてきたレインコート', 'Where Kay fell'),
    (u'美雲が落ちたのは柵の向こう側', 'Railing'),
]


def _norm(s):
    return ''.join((s or '').split())


def _ep_idx(key, base):
    m = re.match(r'gk2_logic(\d\d)_([0-9a-f]+)_[nsb]$', key)
    return int(m.group(1)), int(m.group(2), base)


def _bigrams(s):
    s = _norm(s)
    return {s[i:i + 2] for i in range(len(s) - 1)}


def tables(dumpdir):
    en = json.load(io.open(os.path.join(dumpdir, 'loc_en.json'), encoding='utf-8'))
    ja = json.load(io.open(os.path.join(dumpdir, 'loc_ja.json'), encoding='utf-8'))
    keys = json.load(io.open(os.path.join(dumpdir, 'loc_keys.json'), encoding='utf-8'))
    out = {}
    for tbl in ('gk2_logic_name', 'gk2_logic_text'):
        k2 = {int(i): k for i, k in keys[tbl].items()}
        e = {i: t for i, t in en[tbl + '_en']}
        j = {i: t for i, t in ja[tbl + '_ja']}
        out[tbl] = {k2[i]: {'ja': j.get(i), 'en': e.get(i)} for i in k2 if i in e or i in j}
    return out


def pair_by_rank(T):
    texts, names = {}, {}
    for k, v in T['gk2_logic_text'].items():
        if v.get('ja'):
            ep, i = _ep_idx(k, 10); texts.setdefault(ep, []).append((i, v))
    for k, v in T['gk2_logic_name'].items():
        ep, i = _ep_idx(k, 16); names.setdefault(ep, []).append((i, v))
    pair = {}
    for ep in sorted(texts):
        tl = sorted(texts[ep]); nl = sorted(names.get(ep, []))
        while len(tl) > len(nl):
            best = None
            for drop in range(len(tl)):
                cand = tl[:drop] + tl[drop + 1:]
                s = sum(len(_bigrams(tv['ja']) & _bigrams(nv['ja'])) for (_, tv), (_, nv) in zip(cand, nl))
                if best is None or s > best[0]:
                    best = (s, cand)
            tl = best[1]
        for (_, tv), (_, nv) in zip(tl, nl):
            pair[_norm(tv['ja'])] = nv
    return pair


def keyword_names(dumpdir=None):
    """-> {ds_keyword_index: {'ja': ..., 'en': ...}} for every DS slot that has an official name."""
    dumpdir = dumpdir or work('dump')
    T = tables(dumpdir)
    pair = pair_by_rank(T)
    byen = {v['en']: v for v in T['gk2_logic_name'].values()}
    KW = list(all_strings(open(os.path.join(dumpdir, 'jpn', 'logicKW.bin'), 'rb').read(), False))
    out = {}
    for k, (_, _, _, u) in enumerate(KW):
        t = _ds_plain(u)
        if t.startswith(DUMMY):
            continue
        for prefix, en in OVERRIDES:
            if t.startswith(prefix):
                out[k] = dict(byen[en]); break
        else:
            if _norm(t) in pair:
                out[k] = dict(pair[_norm(t)])
    return out, len(KW)


if __name__ == '__main__':
    names, n = keyword_names()
    print('DS keyword slots: %d, with an official name: %d' % (n, len(names)))
    for k in sorted(names):
        print('  %3d  %-30s %s' % (k, names[k]['en'], names[k]['ja']))
