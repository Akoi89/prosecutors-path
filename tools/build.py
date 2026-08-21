# -*- coding: utf-8 -*-
"""One-shot build: extract everything, then inject.

    gk2port --fan-rom "GK2 (AAI2 Final v2).nds" \
            --jp-rom  "Gyakuten Kenji 2 (Japan).nds" \
            --collection "C:/.../Ace Attorney Investigations Collection"

Every input is a file the user already owns. Nothing is downloaded, and nothing
copyrighted ships with this tool.
"""
import sys, os, glob, json, argparse, traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import work

# Bundle name prefixes -> where their TextAssets go. Addressables appends a content
# hash to every bundle, so these must be matched by prefix, never by full name.
SCRIPT_BUNDLES = {
    'gk2_scriptmessage_eng_assets_all_':       'eng',
    'gk2_scriptmessage_eng_trial_assets_all_': 'eng_trial',
    'gk2_scriptmessage_jpn_assets_all_':       'jpn',
    'gk2_scriptmessage_jpn_trial_assets_all_': 'jpn_trial',
}
# The "trial" string tables are not a demo subset - they carry the whole game's UI
# text, including the evidence and profile descriptions. Merge both, trial first.
LOC_BUNDLES = {
    'loc_en.json': ('localization-string-tables-english(en)_trial_assets_all_',
                    'localization-string-tables-english(en)_assets_all_'),
    'loc_ja.json': ('localization-string-tables-japanese(ja)_trial_assets_all_',
                    'localization-string-tables-japanese(ja)_assets_all_'),
}


def find_bundle_dir(root):
    """Accept the game folder, the StreamingAssets/aa folder, or the platform folder."""
    for pat in ('**/StreamingAssets/aa/*/*.bundle', '*/*.bundle', '*.bundle'):
        hits = glob.glob(os.path.join(root, pat), recursive=True)
        if hits:
            return os.path.dirname(hits[0])
    return None


def step(n, total, msg):
    print('[%d/%d] %s' % (n, total, msg), flush=True)


def extract_rom(rom, out):
    from ndsx import extract
    os.makedirs(out, exist_ok=True)
    extract(rom, out)


def extract_scripts(bdir, dumpdir):
    import UnityPy
    total = 0
    for prefix, sub in SCRIPT_BUNDLES.items():
        hits = [p for p in glob.glob(os.path.join(bdir, '*.bundle'))
                if os.path.basename(p).startswith(prefix)]
        if not hits:
            raise SystemExit('could not find a bundle starting with %r in %s' % (prefix, bdir))
        out = os.path.join(dumpdir, sub)
        os.makedirs(out, exist_ok=True)
        n = 0
        for obj in UnityPy.load(hits[0]).objects:
            if obj.type.name != 'TextAsset':
                continue
            d = obj.read()
            data = d.m_Script
            if isinstance(data, str):
                data = data.encode('utf-8', 'surrogateescape')
            open(os.path.join(out, d.m_Name + '.bin'), 'wb').write(data)
            n += 1
        print('      %-10s %4d script files' % (sub, n), flush=True)
        total += n
    return total


def extract_loc(bdir, dumpdir):
    from loc_dump import dump
    for outname, prefixes in LOC_BUNDLES.items():
        merged = {}
        for prefix in prefixes:
            hits = [p for p in glob.glob(os.path.join(bdir, '*.bundle'))
                    if os.path.basename(p).startswith(prefix)]
            if not hits:
                continue
            for k, v in dump(hits[0]).items():
                merged.setdefault(k, v)
        if not merged:
            raise SystemExit('no localization string tables found in %s' % bdir)
        json.dump({k: [[i, t] for i, t in v] for k, v in merged.items()},
                  open(os.path.join(dumpdir, outname), 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
        print('      %-12s %3d tables' % (outname, len(merged)), flush=True)


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog='gk2port',
        description="Port Capcom's official English localization of Gyakuten Kenji 2 "
                    'into the Nintendo DS ROM.')
    ap.add_argument('--fan-rom', required=True,
                    help='the AAI2 Final v2 fan-patched DS ROM')
    ap.add_argument('--jp-rom',
                    help='the retail Japanese DS ROM (the alignment reference). '
                         'Not needed with --skip-extract')
    ap.add_argument('--collection',
                    help='Ace Attorney Investigations Collection install folder. '
                         'Not needed with --skip-extract')
    ap.add_argument('-o', '--out', default=None, help='output ROM path')
    ap.add_argument('--skip-extract', action='store_true',
                    help='reuse an existing dump/ tree. Once dump/ exists it holds '
                         'everything the injection needs, so neither the Collection '
                         'nor the Japanese ROM has to stay on disk')
    a = ap.parse_args(argv)

    # Only the extraction step touches the Collection and the JP ROM; the injection
    # reads dump/ds_jp/jpn/spt.bin, not the ROM, and never opens a bundle.
    need = [('fan ROM', a.fan_rom)]
    if not a.skip_extract:
        for label, val in (('--jp-rom', a.jp_rom), ('--collection', a.collection)):
            if not val:
                raise SystemExit('%s is required unless you pass --skip-extract' % label)
        need += [('JP ROM', a.jp_rom), ('Collection', a.collection)]
    for label, path in need:
        if not os.path.exists(path):
            raise SystemExit('%s not found: %s' % (label, path))

    dumpdir = work('dump')
    os.makedirs(dumpdir, exist_ok=True)
    total = 5

    if not a.skip_extract:
        bdir = find_bundle_dir(a.collection)
        if not bdir:
            raise SystemExit('no .bundle files under %s\n'
                             'Point --collection at the folder containing the game.'
                             % a.collection)
        step(1, total, 'Reading the fan ROM filesystem')
        extract_rom(a.fan_rom, os.path.join(dumpdir, 'ds_fan'))
        step(2, total, 'Reading the Japanese ROM filesystem')
        extract_rom(a.jp_rom, os.path.join(dumpdir, 'ds_jp'))
        step(3, total, "Extracting Capcom's script from %s" % os.path.basename(bdir))
        extract_scripts(bdir, dumpdir)
        step(4, total, 'Extracting the localization string tables')
        extract_loc(bdir, dumpdir)
    else:
        missing = [d for d in ('ds_fan', 'ds_jp', 'eng', 'eng_trial', 'jpn', 'jpn_trial')
                   if not os.path.isdir(os.path.join(dumpdir, d))]
        missing += [f for f in ('loc_en.json', 'loc_ja.json')
                    if not os.path.exists(os.path.join(dumpdir, f))]
        if missing:
            raise SystemExit('--skip-extract, but %s is missing: %s. '
                             'Run once without --skip-extract to build it.'
                             % (dumpdir, ', '.join(missing)))
        print('[--skip-extract] reusing', dumpdir, flush=True)

    step(5, total, 'Injecting\n')
    import inject
    inject.main(a.fan_rom, a.out)
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        print('\nBuild failed. If this is reproducible, please open an issue at\n'
              'https://github.com/Akoi89/prosecutors-path/issues with the trace above.')
        sys.exit(1)
