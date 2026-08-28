# -*- coding: utf-8 -*-
"""Patch DS entries from the Collection's Unity Localization string tables.

Evidence/profile descriptions, Logic cards and talk topics are NOT in the Collection's
SPT script files - they live in `localization-string-tables-<lang>_trial` (the "trial"
bundle actually carries the whole game's UI text). Match DS strings to the JAPANESE
table, then substitute the English from the same row id.
"""
import sys, os, json, re
sys.path.insert(0, os.path.dirname(__file__))
from spt import all_strings, parse
from build_spt import build_ds
import dstext

CTRL = lambda v: 0xE000 <= v <= 0xF8FF
from paths import work as _work
_D = _work('dump')
# DS-only tail the Collection dropped; the fan patch renders it as 'Touch the
# Check Button for details.' - which wraps to TWO of the description box's four
# lines at 180px and was pushing dozens of otherwise-fitting official
# descriptions over the limit. This shorter form keeps the instruction and the
# button's actual label on a single line. The wording is ours, not Capcom's.
SUFFIX_JA = '《詳細》で見られる。'
SUFFIX_EN = 'Touch Check for details.'

def _norm(s):
    return re.sub(r'\s+', '', s or '')

def load_lookup():
    ja = json.load(open(os.path.join(_D, 'loc_ja.json'), encoding='utf-8'))
    en = json.load(open(os.path.join(_D, 'loc_en.json'), encoding='utf-8'))
    out = {}
    for k in ja:
        ek = k[:-3] + '_en'
        if ek not in en:
            continue
        a = {i: t for i, t in ja[k]}
        b = {i: t for i, t in en[ek]}
        for i in a:
            if i in b and a[i] and b[i]:
                out.setdefault(_norm(a[i]), b[i])
    return out

def _ds_plain(u):
    return re.sub(r'\s+', '', ''.join(chr(v) for v in u if (not CTRL(v) and v > 0x20) or v == 0x0A))

def _to_units(s):
    return [ord(c) for c in s]

# The description box is not the dialogue box: it holds 4 lines (189 of the fan's
# strings use 4) and is wider - the fan's widest line measures 224px in dstext's model
# and nothing exceeds it. So wrap wider and never insert page breaks here.
# Every box in this game has its own geometry - measure the fan patch's own strings
# for that box rather than assuming the dialogue box's numbers.
#   (px, lines) taken as the fan's widest shipped line and its max line count.
# Measure the fan's own lines for THAT box, and EXCLUDE the padded 'Age: NN  Gender'
# header - its wide spacing inflates the maximum and made an earlier pass pick 224px,
# which clipped every description at the right edge.
#   detailMsg (excl. header): p95 179, p99 184, max 197
#   logicKW:                  p95 175, p99 181, max 185
BOXES = {
    'detailMsg': (180, 4),   # evidence / profile descriptions
    'logicKW':   (176, 3),   # Logic cards
}
DESC_PX = 224
DESC_LINES = 4

def _fan_age_line(u):
    """The fan patch prepends an 'Age: NN  Gender: X' line that the Japanese lacks;
    keep it, since the Collection stores those fields separately."""
    out = []
    for v in u:
        if v == 0x0A: break
        out.append(v)
    s = ''.join(chr(v - 0xFF01 + 0x21) if 0xFF01 <= v <= 0xFF5E else ' ' for v in out)
    return out if s.startswith('Age') else None

def patch_entry(ds_entry, jp_src, lookup, box='detailMsg'):
    """Substitute official English into a DS entry, aligned by the JP source file.
    Returns (bytes, replaced_count)."""
    D = list(all_strings(ds_entry, True))
    J = list(all_strings(open(jp_src, 'rb').read(), False))
    if len(D) != len(J):
        return ds_entry, 0
    h = parse(ds_entry, True)[0]
    recs, n = [], 0
    for k, (_, a, _, u) in enumerate(D):
        t = _ds_plain(J[k][3])
        eng = suffix = None
        if t and t in lookup:
            eng = lookup[t]
        elif t.endswith(_norm(SUFFIX_JA)) and t[:-len(_norm(SUFFIX_JA))] in lookup:
            eng = lookup[t[:-len(_norm(SUFFIX_JA))]]; suffix = SUFFIX_EN
        if eng is None:
            recs.append((a, list(u))); continue
        head = []
        for v in u:
            if CTRL(v) or v < 0x20: head.append(v)
            else: break
        age = _fan_age_line(u[len(head):])
        px, maxln = BOXES.get(box, (DESC_PX, DESC_LINES))
        old = dstext.LINE_PX
        dstext.LINE_PX = px
        try:
            # These tables are wrapped for the Collection's own card (~35 chars),
            # so their newlines are soft too - fold them and re-wrap for this box.
            # The suffix is ours, and does get a line of its own.
            conv, _ = dstext.convert(_to_units(eng), page=False, hard_nl=False)
            if suffix:
                sc, _ = dstext.convert(_to_units(suffix), page=False, hard_nl=False)
                conv = conv + [0x0A] + sc
        finally:
            dstext.LINE_PX = old
        if age: conv = age + [0x0A] + conv
        if 1 + sum(1 for v in conv if v == 0x0A) > maxln:
            # Official wording overruns the box; the fan's fits. Keep the fan's.
            recs.append((a, list(u))); continue
        tail = [v for v in u if CTRL(v) and v in dstext.RESET][-1:]
        recs.append((a, head + conv + tail))
        n += 1
    if not n:
        return ds_entry, 0
    return build_ds(recs[0][1], recs[1:], h['term'], h['scale'], h['last']), n
