# -*- coding: utf-8 -*-
"""Dump Unity Localization StringTables from a bundle to JSON."""
import sys, json, UnityPy

def dump(path):
    env = UnityPy.load(path)
    out = {}
    for o in env.objects:
        if o.type.name != 'MonoBehaviour':
            continue
        try:
            tree = o.read_typetree()
        except Exception:
            continue
        nm = tree.get('m_Name')
        ents = tree.get('m_TableData') or []
        rows = [(e.get('m_Id'), e.get('m_Localized')) for e in ents if isinstance(e, dict)]
        if rows:
            out[nm] = rows
    return out

if __name__ == '__main__':
    d = dump(sys.argv[1])
    json.dump({k: [[i, t] for i, t in v] for k, v in d.items()},
              open(sys.argv[2], 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('tables: %d -> %s' % (len(d), sys.argv[2]))
