# -*- coding: utf-8 -*-
"""Measure how much of the built ROM's text is official.

    python tools/coverage.py                     compare the default output ROM
    python tools/coverage.py path/to/rom.nds     compare any built ROM

The metric: for every string of every entry in the fan script archive, count the
character units - everything that is not a control code (0xE000-0xF8FF) or one of
its argument units (arities from dump/ctrl_args.json). A string counts as OFFICIAL
when its bytes in the built ROM differ from the fan ROM's - the injector only ever
replaces whole strings, so a byte difference means official content. The numerator
is the character units of those strings; the denominator is everyone's.

This counting exists so the README's coverage claim is something a user can
recompute. It is not comparable to the pre-v1.2.0 "85.7%" figure, whose script
never survived.
"""
import sys, os, json, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from spt import all_strings
from paths import work, data
from dstext import ARGS

CTRL = lambda v: 0xE000 <= v <= 0xF8FF


def charunits(u):
    n = 0
    i, ln = 0, len(u)
    while i < ln:
        v = u[i]
        if CTRL(v):
            i += 1 + ARGS.get(v, 0)
            continue
        n += 1
        i += 1
    return n


def entries(path):
    raw = open(path, 'rb').read()
    ntbl = struct.unpack_from('<I', raw, 0)[0] // 8
    out = {}
    for i in range(ntbl):
        o, s = struct.unpack_from('<II', raw, i * 8)
        if s:
            out[i] = raw[o:o+s]
    return out


def main(argv=None):
    os.chdir(work())
    args = list(argv or sys.argv[1:])
    # This figure is MODEL-DEPENDENT and was silently wrong until 2026-09-19.
    # The rename check below re-wraps fan rows through dstext to see whether a row
    # is only a name swap. Re-wrap with a different width model than the ROM was
    # BUILT with and those rows stop matching, so fan writing is counted as
    # official and the total drifts up. Measured both ways on both ROMs, the
    # reported figure tracked the MISMATCH, not the ROM: 93.8% model-consistent
    # either side, 94.5% whenever the models disagreed. Builds from 2026-09-19
    # use the ROM's real advances, so that is the default here; pass --estimate to
    # measure a ROM built before the change.
    estimate = '--estimate' in args
    args = [a for a in args if a != '--estimate']
    rom = (args or [os.path.join('out', 'GK2 (Official English, DS port).nds')])[0]
    if not estimate:
        import dstext, fontwidths, locate
        fanrom, _ = locate.find_fan_rom([work(), os.path.dirname(work()), os.getcwd()])
        adv, px = fontwidths.widths(fanrom) if fanrom else (None, None)
        if not dstext.use_real_widths(adv, px):
            print('note: could not read the ROM advances; measuring with the estimate')
        # Mind Chess's SMALL-font advances (2026-09-27), so the harmonize_entry
        # self-comparison below (names.use_small_widths) checks a renamed
        # 453/454/455 row's width the same way the build itself did. Left
        # unset, names._SMALL stays empty and row_px_small() prices every
        # renamed row 9999 - always "over budget" - so the simulated `hu`
        # below falls back to the UN-renamed fan row even for a row the build
        # actually shipped renamed, and that shipped row then matches
        # NEITHER `fu` nor `hu` and gets miscounted as official.
        import names as _small_names
        _small_names.use_small_widths(fontwidths.small_widths(fanrom))
    import ndsx
    tmp = os.path.join(os.environ.get('TEMP', '.'), '_coverage_extract')
    import shutil
    if os.path.isdir(tmp):
        shutil.rmtree(tmp)
    ndsx.extract(rom, tmp)
    built = entries(os.path.join(tmp, 'jpn', 'spt.bin'))
    fan = entries('dump/ds_fan/jpn/spt.bin')
    m = json.load(open(data('ds_to_collection_final.json')))

    def bucket(i):
        info = m.get(str(i))
        name = info['name'] if info else ''
        if name.startswith('sce') and len(name) > 3 and name[3].isdigit():
            return 'Episode %d' % (int(name[3]) + 1)
        return 'Menus & UI'

    # A fan row that only had character names (or, in bank 460, episode names)
    # swapped in is still the fan's writing: count it as FAN, not official.
    # Otherwise the rename pass would inflate this figure for free. A fan row
    # that only had its own wrapped line break moved (tools/linefix.py, spt
    # 19/26 - fan-inherited dialogue text over the real-pixel budget) is the
    # same case: still the fan's writing, not new text, so its (entry,
    # string) key alone is enough to count it as fan regardless of whether
    # the byte comparisons above happen to match (found 2026-09-27: they
    # do not, since linefix's edit makes the built row differ from both the
    # raw fan row and the harmonize_entry-simulated `hu` here, which inflated
    # this figure by that row's own char count for exactly the same reason
    # the rename check exists).
    import names as _names, episode_titles as _titles, linefix as _linefix
    # PART C (2026-09-27/28): a fan row that already reads exactly what Capcom
    # wrote - Mind Chess press-button lines like "Objection!"/"Hold it!", where
    # the fan translated the same short exclamation Capcom later shipped - is
    # still officially worded, even though the byte-equality test above cannot
    # tell it apart from a row Capcom never touched: both end up byte-identical
    # to the fan ROM. Confirmed for real by tools/inject.py's own end-of-loop
    # catch-all (`GUARD_OTHER:IDENTICAL_TO_CAPCOM_TEXT` in the 2026-09-27
    # fan-row-inventory instrumentation): Capcom's own converted text landed
    # byte-identical to the fan's row without ever passing through an explicit
    # keep-fan site. Every row found this way sits in inject.SMALL_WIDGET_BANKS
    # (453-455, Mind Chess press statements/topic banners), the ONE-LINE,
    # un-wrapped widget path inject.py itself uses for these banks
    # (`convert(u, wrap=False, page=False, hard_nl=False)`, SMALL-font accents
    # off - see inject.py's widget-gate comments), not the ordinary
    # dialogue-box convert() the per-string loop uses everywhere else. This
    # recomputes exactly that same call, independently, for every still-fan row
    # in those three banks, and compares it (after the same name-harmonisation
    # as the rename check above) to the fan's row. Bounded to ~1,264 strings
    # across 453-455, not the whole 1.8M-unit script, so this stays cheap and
    # does not try to re-derive a figure the injector could equally have
    # produced for every entry. Re-checked 2026-09-28 against the rebased tree
    # (condensed 453-455 wording): the figure is recomputed fresh from
    # whatever text is actually in dump/ and the built ROM, not cached, so a
    # condensed row that no longer matches Capcom's own wording drops out on
    # its own, and any row that newly matches is picked up the same way.
    import inject as _inject
    import dstext as _dstext

    def _capcom_candidates(i, ds_strings):
        """{string_index: candidate_units} for entry i, Mind Chess widget banks
        only. Empty when the Collection file is missing or its string count does
        not match the fan's (never observed for 453-455, but never assumed)."""
        info = m.get(str(i))
        if not info:
            return {}
        p = _inject.eng_path(info['name'], info['src'])
        if not p or not os.path.exists(p):
            return {}
        en = list(all_strings(open(p, 'rb').read(), False))
        if len(en) != len(ds_strings):
            return {}
        out = {}
        saved = _dstext.ACCENT_SLOTS_ON
        _dstext.ACCENT_SLOTS_ON = False
        try:
            for n_, (_, _, _, u) in enumerate(en):
                asc = ''.join(chr(v) for v in u if v < 0x80)
                cj = sum(1 for v in u if 0x3040 <= v <= 0x30FF or 0x4E00 <= v <= 0x9FFF)
                la = sum(1 for v in u if 0x41 <= v <= 0x5A or 0x61 <= v <= 0x7A)
                if 'DEMO TEXT' in asc or cj > max(4, la * 0.25):
                    continue      # untranslated/placeholder - never equals a real fan row
                try:
                    d, _unmapped = _dstext.convert(list(u), wrap=False, page=False, hard_nl=False)
                except Exception:
                    continue
                out[n_] = d
        finally:
            _dstext.ACCENT_SLOTS_ON = saved
        return out

    tab = {}
    identical_rows = 0
    identical_units = 0
    identical_list = []
    for i, fent in fan.items():
        b = built.get(i)
        if b is None or fent[:4] != b' TPS':
            continue          # a few entries are not script containers
        fs = list(all_strings(fent, True))
        bs = list(all_strings(b, True))
        if len(fs) != len(bs):
            continue          # never happens: the injector preserves string counts
        try:
            hf = _names.harmonize_entry(fent, fent, i)[0]
            hf = _titles.retitle(hf)[0] if i == 460 else hf
            hs = [tuple(u) for _, _, _, u in all_strings(hf, True)]
        except Exception:
            hs = [tuple(u) for _, _, _, u in fs]
        if len(hs) != len(fs):
            hs = [tuple(u) for _, _, _, u in fs]
        cap = _capcom_candidates(i, fs) if i in _inject.SMALL_WIDGET_BANKS else {}
        for n_, ((fa, fb, fc, fu), (_, _, _, bu), hu) in enumerate(zip(fs, bs, hs)):
            n = charunits(fu)
            if not n:
                continue
            k = bucket(i)
            off, tot = tab.get(k, (0, 0))
            is_fan = (list(fu) == list(bu) or tuple(bu) == hu
                      or (i, fa) in _linefix.LINEFIX)
            # PART C: this row is FAN by the byte-equality test above, but
            # Capcom's OWN independently-recomputed candidate for this exact
            # position is the same wording (name-harmonised) - the row is
            # officially worded by coincidence, not merely kept because
            # nothing else was available.
            identical = is_fan and n_ in cap and tuple(cap[n_]) == hu
            if identical:
                identical_rows += 1
                identical_units += n
                identical_list.append((i, fa, n))
            tab[k] = (off + (0 if (is_fan and not identical) else n), tot + n)

    print('%-12s %9s %12s' % ('', 'official', 'char units'))
    to = tt = 0
    for k in sorted(tab, key=lambda x: (x == 'Menus & UI', x)):
        off, tot = tab[k]
        to += off; tt += tot
        print('%-12s %8.1f%%  %s / %s' % (k, 100.0 * off / tot, format(off, ','), format(tot, ',')))
    print('%-12s %8.1f%%  %s / %s' % ('TOTAL', 100.0 * to / tt, format(to, ','), format(tt, ',')))
    to_before = to - identical_units
    print('TOTAL (without the identical-wording counter fix): %5.1f%%  %s / %s'
          % (100.0 * to_before / tt, format(to_before, ','), format(tt, ',')))
    print('identical-wording counter fix adds: %d rows / %s char units (fan text that already '
          'reads Capcom\'s own wording, e.g. Mind Chess "Objection!"/"Hold it!")'
          % (identical_rows, format(identical_units, ',')))
    for (bi, bs_, bn) in sorted(identical_list):
        print('  DS[%d] str %d  (%d char units)' % (bi, bs_, bn))
    shutil.rmtree(tmp)
    return 0


if __name__ == '__main__':
    sys.exit(main())
