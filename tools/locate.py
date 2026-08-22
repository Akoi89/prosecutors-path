# -*- coding: utf-8 -*-
"""Find the two things the user has to supply, so they don't have to type paths.

Neither lookup is authoritative - both are conveniences that --fan-rom and
--collection always override. They exist because the alternative is asking a
first-time user to go hunting for a Steam library folder.
"""
import os, sys, re, glob, hashlib

# AAI2 Final v2, the fan patch this tool injects into. Checking it is worth more
# than it looks: point the build at a raw Japanese cart or a different patch and
# it produces a ROM that boots to a black screen, with nothing to explain why.
FAN_ROM_SHA256 = '08e1f7afbbd99731d7d63f0fdf4b0dcaace590d14e1b1247cb4c105534c366de'
FAN_ROM_SIZE = 45165392

# The Collection's Unity data folder. Matching on this rather than on the folder
# name or the Steam appid means a renamed or manually-copied install still works.
MARKER = os.path.join('GK12_Data', 'StreamingAssets', 'aa')


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def check_fan_rom(path):
    """(ok, message). ok is False only when we are confident it is the wrong file."""
    try:
        size = os.path.getsize(path)
    except OSError as e:
        return False, str(e)
    if size == FAN_ROM_SIZE and sha256(path) == FAN_ROM_SHA256:
        return True, 'AAI2 Final v2'
    return False, ('this is not the AAI2 Final v2 ROM (expected %d bytes, sha256 %s...). '
                   'The build needs that exact patch - it supplies the variable-width '
                   'font and the English graphics.' % (FAN_ROM_SIZE, FAN_ROM_SHA256[:16]))


def _steam_roots():
    """Steam's own install directory, per platform."""
    roots = []
    if sys.platform == 'win32':
        try:
            import winreg
            for hive, key in ((winreg.HKEY_CURRENT_USER, r'Software\Valve\Steam'),
                              (winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\WOW6432Node\Valve\Steam')):
                try:
                    with winreg.OpenKey(hive, key) as k:
                        roots.append(winreg.QueryValueEx(k, 'SteamPath'
                                                         if hive == winreg.HKEY_CURRENT_USER
                                                         else 'InstallPath')[0])
                except OSError:
                    pass
        except ImportError:
            pass
        roots += [r'C:\Program Files (x86)\Steam', r'C:\Program Files\Steam']
    elif sys.platform == 'darwin':
        roots.append(os.path.expanduser('~/Library/Application Support/Steam'))
    else:
        roots += [os.path.expanduser(p) for p in (
            '~/.steam/steam', '~/.local/share/Steam',
            '~/.var/app/com.valvesoftware.Steam/.local/share/Steam')]
    return roots


def steam_libraries():
    """Every steamapps/common on the machine, not just the default one."""
    out, seen = [], set()

    def add(p):
        # The registry hands back a lowercased forward-slash path, the .vdf a
        # properly cased one. normcase folds them together on Windows.
        key = os.path.normcase(p)
        if os.path.isdir(p) and key not in seen:
            seen.add(key)
            out.append(p)

    for root in _steam_roots():
        root = os.path.normpath(root)
        if not os.path.isdir(root):
            continue
        add(os.path.join(root, 'steamapps', 'common'))
        # Games usually live on another drive. libraryfolders.vdf lists those.
        vdf = os.path.join(root, 'steamapps', 'libraryfolders.vdf')
        try:
            text = open(vdf, encoding='utf-8', errors='replace').read()
        except OSError:
            continue
        for lib in re.findall(r'"path"\s*"((?:[^"\\]|\\.)*)"', text):
            add(os.path.join(os.path.normpath(lib.replace('\\\\', os.sep)),
                             'steamapps', 'common'))
    return out


def find_collection(extra=()):
    """The Ace Attorney Investigations Collection install folder, or None."""
    for d in extra:
        if d and os.path.isdir(os.path.join(d, MARKER)):
            return d
    for common in steam_libraries():
        for game in sorted(glob.glob(os.path.join(common, '*'))):
            if os.path.isdir(os.path.join(game, MARKER)):
                return game
    return None


def find_fan_rom(dirs):
    """(path, verified). Prefers a hash match; falls back to a lone .nds."""
    seen, cands = set(), []
    for d in dirs:
        if not d or not os.path.isdir(d) or d in seen:
            continue
        seen.add(d)
        cands += sorted(glob.glob(os.path.join(d, '*.nds')))
    for p in cands:
        if os.path.getsize(p) == FAN_ROM_SIZE and sha256(p) == FAN_ROM_SHA256:
            return p, True
    return (cands[0], False) if len(cands) == 1 else (None, False)
