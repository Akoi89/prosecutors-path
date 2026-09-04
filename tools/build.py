# -*- coding: utf-8 -*-
"""One-shot build: extract everything, then inject.

    gk2port --fan-rom "GK2 (AAI2 Final v2).nds"
            --collection "C:/.../Ace Attorney Investigations Collection"

Every input is a file the user already owns. Nothing is downloaded, and nothing
copyrighted ships with this tool.

The retail Japanese ROM used to be required as well, since two guards compare the
fan patch's layout against the original. Those guards need only COUNTS, never
text, so the counts now ship as dump/jp_structure.json - see tools/jp_profile.py.
"""
import sys, os, glob, json, argparse, traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import locate
from paths import work, data, FROZEN

VERSION = '1.7.0'
ISSUES = 'https://github.com/Akoi89/prosecutors-path/issues'
# sha256 of the ROM this version's tools produce from the AAI2 Final v2 base.
# --verify checks a built ROM against it. Update ONLY when the injector changes
# the output on purpose (v1.4.3: strings that dropped a DS-only engine command
# keep the fan's line - the Episode 1 hang at the handoff to player control;
# v1.6.4: a styled span split across a page break is closed and re-opened, so its
# second half keeps its colour - +512 bytes, 98 repaired spans;
# v1.7.0: the 39 close-up text screens carry Capcom's rows and the room map and
# two log tables the official names - +6,433,792 bytes, the rewritten
# upcut_local.bin appended as stored literals).
# NOTE this hash is VERSION-SPECIFIC: title_assets paints 'v' + VERSION onto the
# title screen, so bumping VERSION alone changes the ROM. Move both together.
REFERENCE_ROM_SHA256 = '71378f43a1fa35fc63c272d55b5df1876f0b03e2f75c8efe7f048ffbed10e909'

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


def extract_loc_keys(bdir, dumpdir):
    """Key names of every gk2 localization table (SharedTableData): id -> key.
    The Logic keyword names have no text on the DS, and joining the Collection's
    name and description tables needs these keys (see tools/logic_names.py)."""
    import UnityPy
    out = {}
    for pat in ('localization-assets-shared*.bundle', 'localization-string-tables-english(en)*.bundle'):
        for b in glob.glob(os.path.join(bdir, pat)):
            env = UnityPy.load(b)
            for o in env.objects:
                if o.type.name != 'MonoBehaviour':
                    continue
                try:
                    tt = o.read_typetree()
                except Exception:
                    continue
                ents = tt.get('m_Entries')
                name = tt.get('m_Name', '')
                if ents and isinstance(ents, list) and ents and 'm_Key' in ents[0] and 'gk2' in name.lower():
                    out[name.replace(' Shared Data', '')] = {str(e['m_Id']): e['m_Key'] for e in ents}
    json.dump(out, open(os.path.join(dumpdir, 'loc_keys.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    return len(out)


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


def owns_console():
    """True when we were launched by double-click rather than from a shell.

    Nothing else distinguishes the two, and it matters: a double-clicked console
    program takes its window with it when it exits, so every error message above
    is invisible to exactly the people who need to read it.
    """
    if sys.platform != 'win32':
        return False
    try:
        import ctypes
        buf = (ctypes.c_uint * 8)()
        n = ctypes.windll.kernel32.GetConsoleProcessList(buf, 8)
    except Exception:
        return False
    # A onefile PyInstaller build runs the real program as a child of the
    # bootloader, so we own a fresh window at two processes. A shell that
    # launched us is a third.
    return 0 < n <= 2


def pause():
    try:
        input('\nPress Enter to close this window. ')
    except (EOFError, KeyboardInterrupt):
        pass


def selftest():
    """Prove a frozen build is actually complete.

    Both halves of this have failed a real release: PyInstaller resolves
    --add-data against the spec file rather than the working directory, and
    UnityPy imports PIL from inside a module the analyser does not follow.
    Neither shows up until someone runs a build for real.
    """
    ok = True
    print('gk2port %s  (%s)' % (VERSION, 'frozen' if FROZEN else 'source'))
    for f in ('ctrl_args.json', 'ds_to_collection_final.json', 'jp_structure.json'):
        good = os.path.exists(data(f))
        ok &= good
        print('  data  %-30s %s' % (f, 'ok' if good else 'MISSING'))
    # data files that live beside the tool modules and are opened relative to
    # __file__: in a frozen build that is the bundle root. v1.6.0 shipped
    # without them and crashed at the description step.
    tools_dir = sys._MEIPASS if FROZEN else os.path.dirname(os.path.abspath(__file__))
    for f in ('desc_font.json', 'select_strips.json', 'txtcut_font.json', 'txtcut_condensed.json', 'map_font.json'):
        good = os.path.exists(os.path.join(tools_dir, f))
        ok &= good
        print('  tools %-30s %s' % (f, 'ok' if good else 'MISSING'))
    # UnityPy.UnityPyBoost is a C extension and lz4 is how Addressables bundles are
    # actually compressed - both are reached only during extraction, so a build
    # missing them looks perfectly healthy until someone points it at the game.
    for mod in ('UnityPy', 'UnityPy.UnityPyBoost', 'lz4.block', 'brotli', 'PIL.Image',
                'spt', 'dstext', 'inject', 'locate', 'ndsx', 'names', 'plates',
                'lz11', 'nitro'):
        try:
            __import__(mod)
            print('  import %-29s ok' % mod)
        except Exception as e:
            ok = False
            print('  import %-29s FAILED: %s' % (mod, e))
    print('\nselftest %s' % ('passed' if ok else 'FAILED'))
    return 0 if ok else 1


def yes(prompt, default=True):
    try:
        r = input('%s [%s] ' % (prompt, 'Y/n' if default else 'y/N')).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    return default if not r else r.startswith('y')


def ask_path(prompt):
    try:
        # Windows' "Copy as path" wraps the result in quotes; dragging a folder
        # into a console can leave a trailing separator.
        return input(prompt).strip().strip('"').strip("'") or None
    except (EOFError, KeyboardInterrupt):
        print()
        return None


BANNER = r"""
  Prosecutor's Path %s
  Ports Capcom's official English localization of Gyakuten Kenji 2 into the DS ROM.
""".rstrip()


def wizard(a):
    """Fill in what wasn't given, with everything on screen before anything runs."""
    print(BANNER % VERSION)
    print()
    here = work()

    rom, verified = a.fan_rom, False
    if rom:
        verified = locate.check_fan_rom(rom)[0]
    else:
        rom, verified = locate.find_fan_rom([here, os.getcwd()])
    if not rom:
        print('  fan ROM     not found')
        print('              Put "Gyakuten Kenji 2 (AAI2 Final v2).nds" next to this')
        print('              program, or paste its full path below.')
        rom = ask_path('  path to the fan ROM: ')
        print()
        if not rom:
            return None
        if not os.path.exists(rom):
            print('  no such file: %s' % rom)
            return None
        verified = locate.check_fan_rom(rom)[0]
    print('  fan ROM     %s%s' % (os.path.basename(rom),
                                  '   [verified AAI2 Final v2]' if verified
                                  else '   [WARNING: not AAI2 Final v2]'))

    col = a.collection
    if not a.skip_extract:
        if col and not os.path.isdir(col):
            print('  Collection  %s does not exist' % col)
            col = None
        if not col:
            print('  searching Steam for the Collection...', flush=True)
            col = locate.find_collection([os.getcwd(), here])
        if col:
            print('  Collection  %s' % col)
        elif os.path.isdir(os.path.join(here, 'dump', 'eng')):
            # Already extracted once. The Collection is only read at extraction
            # time, so there is nothing left for it to do.
            print('  Collection  not installed - reusing dump/ from a previous run')
            a.skip_extract = True
        else:
            print('  Collection  not found in any Steam library')
            print('              Paste the Ace Attorney Investigations Collection')
            print('              folder below (the one containing GK12_Data).')
            col = ask_path('  path to the Collection: ')
            print()
            if not col:
                return None
            if not find_bundle_dir(col):
                print('  no Unity bundles under %s' % col)
                print('  Expected a GK12_Data/StreamingAssets/aa folder inside it.')
                return None
            print('  Collection  %s' % col)

    import inject
    out = a.out or os.path.join(here, inject.DEFAULT_OUT)
    print('  output      %s' % out)
    print()
    if not verified and not a.any_rom:
        print('  The fan ROM does not match AAI2 Final v2. Building on anything else')
        print('  produces a ROM that boots to a black screen.')
        if not yes('  Continue anyway?', default=False):
            return None
        a.any_rom = True
    if not yes('  Build?'):
        return None
    print()
    a.fan_rom, a.collection = rom, col
    return a


def verify(path):
    """Hash a built ROM and check it against this version's published reference.

    Lets anyone confirm their build - or a ROM a friend built - is the genuine,
    unmodified output of this tool, without trusting the person who ran it.
    """
    import locate, inject
    # Resolve before anything can change the working directory: a relative path
    # must mean "relative to where the user ran this", nothing else.
    path = os.path.abspath(path) if path else os.path.join(work(), inject.DEFAULT_OUT)
    print('gk2port %s  reference ROM %s' % (VERSION, REFERENCE_ROM_SHA256))
    if not os.path.exists(path):
        print('\nno ROM at %s' % path)
        print('Build one first, or pass the path: gk2port --verify "your.nds"')
        return 1
    h = locate.sha256(path)
    print('\n  %s' % os.path.basename(path))
    print('  sha256 %s' % h)
    if h == REFERENCE_ROM_SHA256:
        print('\nMATCH - this is the genuine gk2port %s output.' % VERSION)
        return 0
    print('\nNO MATCH. This ROM is not the reference %s output. Either it was built' % VERSION)
    print('by a different version, edited after building, or built on the wrong base.')
    print('Rebuild with this version, or check your AAI2 Final v2 ROM is')
    print('sha256 %s.' % locate.FAN_ROM_SHA256)
    return 1


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog='gk2port',
        description="Port Capcom's official English localization of Gyakuten Kenji 2 "
                    'into the Nintendo DS ROM. Run with no arguments to be walked '
                    'through it.')
    # Dropping a file onto the program on Windows passes it as argv[1], which is
    # the least typing any of this can involve.
    ap.add_argument('rom', nargs='?', help='the AAI2 Final v2 ROM, same as --fan-rom '
                                           '(so you can drag it onto this program)')
    ap.add_argument('--fan-rom', help='the AAI2 Final v2 fan-patched DS ROM')
    ap.add_argument('--jp-rom', help=argparse.SUPPRESS)   # no longer needed
    ap.add_argument('--collection',
                    help='Ace Attorney Investigations Collection install folder. '
                         'Found automatically in any Steam library. Not needed with '
                         '--skip-extract')
    ap.add_argument('-o', '--out', default=None, help='output ROM path')
    ap.add_argument('--skip-extract', action='store_true',
                    help='reuse an existing dump/ tree. Once dump/ exists it holds '
                         'everything the injection needs, so neither the Collection '
                         'nor the Japanese ROM has to stay on disk')
    ap.add_argument('--any-rom', action='store_true',
                    help='build on a ROM that is not AAI2 Final v2. Expect a black '
                         'screen; this exists so the check is never a dead end')
    ap.add_argument('--selftest', action='store_true',
                    help='check that this build has its bundled data and libraries')
    ap.add_argument('--verify', nargs='?', const='', metavar='ROM',
                    help="hash a built ROM and check it against this version's "
                         'published reference; with no path, checks the default output')
    ap.add_argument('--no-pause', action='store_true',
                    help='never wait for a keypress before exiting')
    ap.add_argument('--version', action='version', version='gk2port ' + VERSION)
    a = ap.parse_args(argv)

    if a.selftest:
        return selftest()

    if a.verify is not None:
        return verify(a.verify or None)

    # No arguments at all means a double-click, or a first-time user who has not
    # read anything yet. Either way, asking beats an argparse usage error in a
    # window that closes before it can be read.
    if not (sys.argv[1:] if argv is None else argv):
        if wizard(a) is None:
            print('\nNothing was built.')
            return 1
    else:
        a.fan_rom = a.fan_rom or a.rom
        if not a.fan_rom:
            raise SystemExit('no ROM given. Pass --fan-rom "...nds", drop the ROM onto '
                             'this program, or run it with no arguments at all to be '
                             'walked through it.')
        if not a.collection and not a.skip_extract:
            a.collection = locate.find_collection([os.getcwd(), work()])
            if a.collection:
                print('found the Collection at', a.collection, flush=True)

    # Only the extraction step touches the Collection; the injection never opens a
    # bundle. The retail Japanese ROM is no longer needed at all - the structural
    # counts the guards take from it now ship as dump/jp_structure.json.
    need = [('fan ROM', a.fan_rom)]
    if not a.skip_extract:
        if not a.collection:
            raise SystemExit(
                'could not find the Ace Attorney Investigations Collection in any '
                'Steam library.\nPass --collection "<the folder containing GK12_Data>", '
                'or --skip-extract if you have built once already.')
        need += [('Collection', a.collection)]
    if a.jp_rom:
        print('note: --jp-rom is no longer needed and is ignored; the profile it used '
              'to provide ships with the tool.', flush=True)
    for label, path in need:
        if not os.path.exists(path):
            raise SystemExit('%s not found: %s' % (label, path))

    # inject() changes directory, so relative paths have to be resolved first.
    a.fan_rom = os.path.abspath(a.fan_rom)
    if a.out:
        a.out = os.path.abspath(a.out)

    ok, why = locate.check_fan_rom(a.fan_rom)
    if ok:
        print('fan ROM verified: AAI2 Final v2', flush=True)
    elif a.any_rom:
        print('WARNING: %s\nContinuing because --any-rom was given.' % why, flush=True)
    else:
        raise SystemExit('%s\nsha256 %s\n\nIf you are certain, pass --any-rom.'
                         % (why, locate.sha256(a.fan_rom)))

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
        step(2, total, "Extracting Capcom's script from %s" % os.path.basename(bdir))
        extract_scripts(bdir, dumpdir)
        step(3, total, 'Extracting the localization string tables')
        extract_loc(bdir, dumpdir)
        extract_loc_keys(bdir, dumpdir)
        import title_assets, voices
        title_assets.extract(bdir, dumpdir)
        voices.extract(bdir, dumpdir)
    else:
        missing = [d for d in ('ds_fan', 'eng', 'eng_trial', 'jpn', 'jpn_trial')
                   if not os.path.isdir(os.path.join(dumpdir, d))]
        # ...and the specific files the injector opens, so a truncated or
        # half-deleted dump fails HERE instead of minutes into the injection
        missing += [f for f in ('loc_en.json', 'loc_ja.json', 'loc_keys.json',
                                os.path.join('ds_fan', 'jpn', 'spt.bin'),
                                os.path.join('jpn_trial', 'detailMsg.bin'),
                                os.path.join('jpn', 'logicKW.bin'))
                    if not os.path.exists(os.path.join(dumpdir, f))]
        import title_assets, voices
        missing += [os.path.relpath(f, dumpdir) for f in title_assets.required(dumpdir) + voices.required(dumpdir)
                    if not os.path.exists(f)]
        if missing:
            raise SystemExit('--skip-extract, but %s is missing: %s. '
                             'Run once without --skip-extract to build it.'
                             % (dumpdir, ', '.join(missing)))
        print('[--skip-extract] reusing', dumpdir, flush=True)

    step(4, total, 'Injecting\n')
    import inject
    inject.main(a.fan_rom, a.out)
    step(5, total, 'Title screen, episode titles, Logic keyword cards, close-up text screens and voices')
    import title_assets, voices
    out_path = a.out or os.path.join(work(), inject.DEFAULT_OUT)
    title_assets.apply(dumpdir, out_path, version=VERSION)
    voices.apply(dumpdir, out_path)
    return 0


def run():
    """Everything main() can raise, turned into an exit code and a message.

    Nothing may escape as an exception: the caller still has to get to pause(),
    or a double-clicked build takes its own error message off the screen.
    """
    try:
        return main() or 0
    except SystemExit as e:
        if isinstance(e.code, str):          # our own raise SystemExit('...')
            print('\nerror: %s' % e.code, file=sys.stderr)
            return 1
        return 0 if e.code is None else e.code
    except KeyboardInterrupt:
        print('\ninterrupted')
        return 130
    except Exception:
        traceback.print_exc()
        print('\nBuild failed. If this is reproducible, please open an issue at\n'
              '%s with the trace above.' % ISSUES)
        return 1


if __name__ == '__main__':
    code = run()
    if FROZEN and '--no-pause' not in sys.argv and (owns_console() or not sys.argv[1:]):
        pause()
    sys.exit(code)
