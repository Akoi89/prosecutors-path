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
import condense

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

# Fan location terms harmonised to Capcom's in rows that KEEP fan text, so a
# description can't call a room one thing while the official dialogue beside it
# calls it another (the updated Rubber Glove said "workroom A" where every
# official line says "workshop"). Substitution only - same letter count, and
# 'workshop' measures 2px narrower, so wrapping cannot change. Applied solely
# to the description/Logic banks this module patches; full fan scenes elsewhere
# keep their own vocabulary untouched.
def _fw_units(s):
    return [0x3000 if c == ' ' else ord(c) - 0x21 + 0xFF01 for c in s]

FAN_TERMS = [(_fw_units('workroom'), _fw_units('workshop')),
             (_fw_units('Workroom'), _fw_units('Workshop'))]

def _fix_fan_terms(u):
    u = list(u)
    for find, repl in FAN_TERMS:
        k = 0
        while k <= len(u) - len(find):
            if u[k:k+len(find)] == find:
                u[k:k+len(find)] = repl
                k += len(repl)
            else:
                k += 1
    return u

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
# The evidence/profile description card draws a SMALLER font than the dialogue box, and
# dstext._w (the dialogue model) does not describe it: a budget of 180 dialogue-units let
# lines run past the card's edge and the game clipped their last glyph in v1.4.x-1.5.2
# ('outside the Autumn Wing after' lost its "r", "Jammin' Ninja's face. Made of" its "f").
# The card was therefore measured in game (2026-09-02): the text field is 140 DS px wide
# (window x 259..617 in a 687x1064 capture, 2.5625 px per DS px) and every line whose
# ink reached that column was cut, so the field is the hard limit. Per-glyph advances of
# the card's font were fitted from rendered lines and live in tools/desc_font.json; the
# fitter wraps with those advances and a margin below the field width. Glyphs never seen
# in the samples get a deliberately generous advance so an unmeasured letter can only
# wrap early, never clip. logicKW keeps the old dialogue-unit budget: it was measured the
# same flawed way but no clipped Logic card has been observed.
BOXES = {
    'detailMsg': (None, 4),  # width comes from DESC_FONT below (real DS px)
    'logicKW':   (176, 3),   # Logic cards
}
_DESC_FONT = None
def desc_font():
    """(width_fn, line_px) for the description card, loaded from tools/desc_font.json."""
    global _DESC_FONT
    if _DESC_FONT is None:
        import json as _json, os as _os
        d = _json.load(open(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'desc_font.json'), encoding='utf-8'))
        adv = {k: float(v) for k, v in d['advances'].items()}
        fb = d['fallback']           # {'space','narrow','wide','upper','lower','digit','other'}
        narrow, wide = set(d['narrow']), set(d['wide'])
        def w(ch):
            o = ord(ch)
            if o == 0xFF3F: ch = ' '
            elif 0xFF01 <= o <= 0xFF5E: ch = chr(o - 0xFF01 + 0x21)
            elif o == 0x201D or o == 0x2019: ch = "'"
            elif o == 0x2025: ch = '.'
            if ch in adv: return adv[ch]
            if ch == ' ': return fb['space']
            if ch in narrow: return fb['narrow']
            if ch in wide: return fb['wide']
            if ch.isupper(): return fb['upper']
            if ch.isdigit(): return fb['digit']
            if ch.islower(): return fb['lower']
            if ord(ch) >= 0x2E80: return fb['cjk']
            return fb['other']
        _DESC_FONT = (w, float(d['line_px']))
    return _DESC_FONT

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
            fu = _fix_fan_terms(u)
            if fu != list(u): n += 1
            recs.append((a, fu)); continue
        # a few official descriptions are condensed to fit the box - only rows
        # whose fan wording contradicts official dialogue; see tools/condense.py
        c = condense.apply(t, eng)
        if c is not None:
            eng = c
        head = []
        for v in u:
            if CTRL(v) or v < 0x20: head.append(v)
            else: break
        age = _fan_age_line(u[len(head):])
        px, maxln = BOXES.get(box, (DESC_PX, DESC_LINES))
        old = dstext.LINE_PX
        old_fn = dstext.WIDTH_FN
        if px is None:                       # measured widget font (description card)
            dstext.WIDTH_FN, px = desc_font()
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
            dstext.WIDTH_FN = old_fn
        if age: conv = age + [0x0A] + conv
        if 1 + sum(1 for v in conv if v == 0x0A) > maxln:
            # Official wording overruns the box; the fan's fits. Keep the fan's.
            fu = _fix_fan_terms(u)
            if fu != list(u): n += 1
            recs.append((a, fu)); continue
        tail = [v for v in u if CTRL(v) and v in dstext.RESET][-1:]
        recs.append((a, head + conv + tail))
        n += 1
    if not n:
        return ds_entry, 0
    return build_ds(recs[0][1], recs[1:], h['term'], h['scale'], h['last']), n
