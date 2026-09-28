# Fold the rows tools/rowsplit.py split back together, so the per-index audits
# see the same row layout as the fan ROM and the pre-split build.
#
# The build appends a continuation row to every entry that had a row too long
# for the engine's script buffer, and ends the first piece with {E081:new}. The
# audits compare rows to the fan's BY INDEX, so they must look at the unsplit
# rows. This folds piece 0 (minus its trailing {E081:new}) and its continuation
# back into the original row and drops the appended row. Nothing else changes.
#
# The fold is driven by the split manifest the build writes next to the ROM,
# <ROM path without .nds>.split_manifest.json. A ROM whose entries have more rows
# than the fan's and no manifest is an error, never a silent skip.
#
# audit_hint deliberately does not use this: it checks the header hint against
# the longest row the ENGINE will read, which is the split layout.
import json
import os
import struct
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
sys.path.insert(0, _HERE)
from spt import all_strings, parse, tails as _tails   # noqa: E402
from build_spt import build_ds, build_archive          # noqa: E402

CHAIN = 0xE081
_FAN_SPT = os.path.join(_REPO, 'dump', 'ds_fan', 'jpn', 'spt.bin')


def manifest_path(rom_path):
    return os.path.splitext(rom_path)[0] + '.split_manifest.json'


def _entries(blob):
    n = struct.unpack_from('<I', blob, 0)[0] // 8
    out = {}
    for i in range(n):
        o, s = struct.unpack_from('<II', blob, i * 8)
        out[i] = blob[o:o + s] if s else None
    return out


def _fold_entry(entry_id, ent, records):
    h = parse(ent, True)[0]
    S = list(all_strings(ent, True))
    rows = [list(t[3]) for t in S]
    tails = _tails(ent, True)
    ncnt = len(rows)
    added = len(records)
    old = ncnt - added
    idxs = [r['new_index'] for r in records]
    if old < 1 or idxs != list(range(old, ncnt)):
        raise RuntimeError('entry %d: manifest lists new rows %s but the entry has %d rows'
                           % (entry_id, idxs, ncnt))
    appended = set(idxs)
    folded = [list(r) for r in rows[:old]]
    ftails = list(tails[:old])
    for r in sorted({x['row'] for x in records}):
        # walk the row's chain in manifest order, checking every record against the entry
        mine = sorted((x for x in records if x['row'] == r), key=lambda x: x['piece'])
        at, cut = r, 0
        for k, x in enumerate(mine):
            if x['piece'] != k + 1:
                raise RuntimeError('entry %d row %d: manifest pieces are not 1..%d' % (entry_id, r, len(mine)))
            piece = rows[at]
            if len(piece) < 2 or piece[-2] != CHAIN or piece[-1] != x['new_index']:
                raise RuntimeError('entry %d row %d: piece %d does not end in {E081:%d}'
                                   % (entry_id, r, k, x['new_index']))
            cut += len(piece) - 2
            if x['cut_unit'] != cut:
                raise RuntimeError('entry %d row %d: manifest cut_unit %d but the piece ends at unit %d'
                                   % (entry_id, r, x['cut_unit'], cut))
            mk = struct.unpack_from('<I', ent, 0x10 + 8 * x['new_index'])[0]
            if mk != int(x['mark'], 16):
                raise RuntimeError('entry %d row %d: manifest mark %s but the entry holds %08x for row %d'
                                   % (entry_id, r, x['mark'], mk, x['new_index']))
            if x['units'] != len(rows[x['new_index']]):
                raise RuntimeError('entry %d row %d: manifest says row %d has %d units, it has %d'
                                   % (entry_id, r, x['new_index'], x['units'], len(rows[x['new_index']])))
            at = x['new_index']
        # rebuild the row: piece 0 body, then each continuation, dropping the added chains
        out, at = [], r
        for x in mine:
            out += rows[at][:-2]
            at = x['new_index']
        out += rows[at]
        folded[r] = out
        ftails[r] = tails[at]
    if any(rows[i][-2:-1] == [CHAIN] and rows[i][-1] in appended for i in range(old) if i not in
           {x['row'] for x in records}):
        raise RuntimeError('entry %d: a row outside the manifest chains to an appended row' % entry_id)
    trailer = struct.unpack_from('<I', ent, 0x10 + 8 * (old - 1))[0]
    keep = [t if t != [0] else None for t in ftails]
    return build_ds(folded[0], [(S[i][1], folded[i]) for i in range(1, old)], trailer,
                    h['scale'], h['last'], keep)


def fold_spt(blob, rom_path, ref_blob=None):
    """Return the spt.bin blob with split rows folded back (the same object when
    nothing is split). blob is jpn/spt.bin taken from the ROM at rom_path."""
    if ref_blob is None:
        if not os.path.exists(_FAN_SPT):
            raise RuntimeError('cannot check row counts: %s is missing (run a build once, or --skip-extract)'
                               % _FAN_SPT)
        ref_blob = open(_FAN_SPT, 'rb').read()
    mp = manifest_path(rom_path)
    man = {}
    if os.path.exists(mp):
        man = {int(k): v for k, v in json.load(open(mp)).items()}
    ents = _entries(blob)
    ref = _entries(ref_blob)
    changed = False
    for i in sorted(ents):
        e = ents[i]
        if not e or e[:4] != b' TPS':
            continue
        ncnt = struct.unpack_from('<H', e, 6)[0]
        r = ref.get(i)
        rn = struct.unpack_from('<H', r, 6)[0] if r and r[:4] == b' TPS' else None
        if i in man:
            ents[i] = _fold_entry(i, e, man[i])
            if rn is not None and struct.unpack_from('<H', ents[i], 6)[0] != rn:
                raise RuntimeError('entry %d: folded row count %d differs from the fan\'s %d'
                                   % (i, struct.unpack_from('<H', ents[i], 6)[0], rn))
            changed = True
        elif rn is not None and ncnt > rn:
            raise RuntimeError('entry %d has %d rows, the fan has %d, and there is no split '
                               'manifest entry for it (looked for %s)' % (i, ncnt, rn, mp))
    if not changed:
        return blob
    return build_archive(ents)      # all ids kept, empty entries included, so the entry count stays
