# -*- coding: utf-8 -*-
"""Prove each audit can FAIL.

An audit that has never failed has not been tested, it has only been run. This
project learned that twice in one night: my chapter-sweep hang detector reported
"zero frozen" across 25 chapters while measuring something that could never
happen, and claude-2f's structural audit passed a build they had already proven
broken because it silently compared nothing.

This breaks a COPY of the ROM in exactly the way each audit claims to detect and
checks the audit notices. out/ is never touched.

WHAT IT HAS ALREADY CAUGHT: audit_empty gave byte-identical output on a ROM with
400 box-ends stripped out - because it looks for strings empty of TEXT and only
PRINTS box counts, never tests them. The v1.4.2 defect class had no standing audit
at all. audit_boxes.py exists because this harness was written.

Method: patch units IN PLACE. Every substitution is the same width, so no offset
moves and the file stays structurally valid - a fixture that were merely corrupt
would be detected for the wrong reason. Text is stored XOR 0x55AA, so unit u sits
on disk as (u ^ 0x55AA) little-endian.

    python audits\audit_fixtures.py
"""
import os as _os
import sys as _sys

# Portable paths: the audits live in <repo>/audits and the toolchain in
# <repo>/tools, so everything is found relative to this file rather than to any
# one machine. The ROMs are yours and are located the same way build.py does it.
_REPO = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
_sys.path.insert(0, _os.path.join(_REPO, 'tools'))


def _default_built():
    p = _os.path.join(_REPO, 'out', 'GK2 (Official English, DS port).nds')
    if _os.path.exists(p):
        return p
    cand = [f for f in _os.listdir(_os.path.join(_REPO, 'out'))
            if f.lower().endswith('.nds')] if _os.path.isdir(_os.path.join(_REPO, 'out')) else []
    if len(cand) == 1:
        return _os.path.join(_REPO, 'out', cand[0])
    raise SystemExit('no built ROM in %s - run a build first, or pass one as the '
                     'first argument' % _os.path.join(_REPO, 'out'))


def _default_fan():
    import locate
    rom, _ = locate.find_fan_rom([_REPO, _os.path.dirname(_REPO), _os.getcwd()])
    if not rom:
        raise SystemExit('could not find your AAI2 Final v2 ROM - pass it as the '
                         'second argument')
    return rom

import os
import struct
import subprocess
import sys
import tempfile


import spt                                    # noqa: E402
from dstext import ARGS                       # noqa: E402
from inject import file_id                    # noqa: E402

REAL = _default_built()
RIG = _os.path.dirname(_os.path.abspath(__file__))
WORK = os.path.join(tempfile.gettempdir(), 'claude', 'fixtures')
XOR = 0x55AA


def enc(u):
    return struct.pack('<H', u ^ XOR)


def spt_span(rom):
    fat = struct.unpack_from('<I', rom, 0x48)[0]
    fid = file_id(rom, 'jpn/spt.bin')
    return struct.unpack_from('<II', rom, fat + fid * 8)


def swap_code(rom, frm, to, limit):
    """Replace up to `limit` encoded occurrences of unit `frm` with `to`."""
    a, b = spt_span(rom)
    src, dst = enc(frm), enc(to)
    out = bytearray(rom)
    n, i = 0, a
    while n < limit:
        j = out.find(src, i, b)
        if j < 0:
            break
        if (j - a) % 2 == 0:
            out[j:j + 2] = dst
            n += 1
            i = j + 2
        else:
            i = j + 1
    return bytes(out), n


def break_boxes(rom):
    """Strip box-ends: the v1.4.2 defect. E102 -> E040, same width, arity 0."""
    return swap_code(rom, 0xE102, 0xE040, 400)


def break_dsonly(rom):
    """Delete the DS-only tutorial pair: the v1.4.3 hang."""
    return swap_code(rom, 0xE041, 0xE040, 200)


def break_arity(rom):
    """Fullwidth a control-code argument: the v1.3.3 Little Thief signature.

    E108 takes one argument and carries an ASCII letter at ~398 sites, which is
    precisely the shape that defeated the arity heuristic.
    """
    a, b = spt_span(rom)
    out = bytearray(rom)
    code = enc(0xE108)
    n, i = 0, a
    while n < 120:
        j = out.find(code, i, b)
        if j < 0:
            break
        if (j - a) % 2 == 0 and j + 4 <= b:
            arg = struct.unpack_from('<H', out, j + 2)[0] ^ XOR
            if 0x41 <= arg <= 0x7A:
                out[j + 2:j + 4] = enc(0xFF00 + (arg - 0x20))
                n += 1
        i = j + 2
    return bytes(out), n


def break_empty(rom):
    """Blank a whole string's visible text, leaving its structure intact.

    audit_empty looks for strings with no printable characters where the fan ROM
    had some. Replacing each visible unit with 0x0A keeps every offset and the
    box structure while emptying the text - the v1.2.1 / Episode 1 NPC shape.
    """
    a, b = spt_span(rom)
    out = bytearray(rom)
    cont = bytes(rom[a:b])
    n = struct.unpack_from('<I', cont, 0)[0] // 8
    done = 0
    for i in range(n):
        if done >= 6:
            break
        o, s = struct.unpack_from('<II', cont, i * 8)
        e = cont[o:o + s] if s else b''
        if not e or e[:4] != b' TPS':
            continue
        try:
            rows = list(spt.all_strings(e, True))
        except Exception:                                    # noqa: BLE001
            continue
        cnt = struct.unpack_from('<H', e, 0x06)[0]
        for j in range(1, min(cnt, len(rows))):
            off, clen = struct.unpack_from('<HH', e, 0x10 + (j - 1) * 8 + 4)
            base = a + o + off * 2
            if clen < 12 or base + clen * 2 > b:
                continue
            vis = 0
            for k in range(clen):
                v = struct.unpack_from('<H', out, base + k * 2)[0] ^ XOR
                if 0xFF01 <= v <= 0xFF5E or 0x21 <= v <= 0x7E:
                    out[base + k * 2:base + k * 2 + 2] = enc(0x0A)
                    vis += 1
            if vis >= 10:
                done += 1
                break
    return bytes(out), done


def _tps_entries(rom):
    """(entry index, absolute offset, bytes) for every ' TPS' entry of spt.bin."""
    a, b = spt_span(rom)
    cont = bytes(rom[a:b])
    n = struct.unpack_from('<I', cont, 0)[0] // 8
    for i in range(n):
        o, s = struct.unpack_from('<II', cont, i * 8)
        e = cont[o:o + s] if s else b''
        if e[:4] == b' TPS':
            yield i, a + o, e


def break_hint(rom):
    """Shrink the 0x08 buffer-size hint below the longest string it must hold.

    audit_hint compares the hint against the DATA, so a hint two units short of
    the longest string is exactly the defect it claims to catch. Same width (u16
    in place), nothing else moves.
    """
    out = bytearray(rom)
    done = 0
    for i, base, e in _tps_entries(rom):
        if done >= 8:
            break
        try:
            longest = max(len(u) for _, _, _, u in spt.all_strings(e, True))
        except Exception:                                    # noqa: BLE001
            continue
        hint = struct.unpack_from('<H', e, 0x08)[0]
        if longest < 4 or hint < longest:
            continue
        struct.pack_into('<H', out, base + 0x08, longest - 2)
        done += 1
    return bytes(out), done


WIDE_UNIT = 0xFF37          # fullwidth 'W', 9px in the dialogue width model


def break_widgets(rom):
    """Widen option rows past anything the fan ever drew in that widget.

    Bank 453 (confrontation lines) has a fan-proven maximum of about 251px.
    Every visible unit and every line break in a row becomes a 9px 'W', so a row
    of 32+ units renders at 288px or more on one line - wider than the widget
    and wider than its own fan row. Control codes and their arguments are left
    alone so the row is wide for the right reason, not corrupt.
    """
    a, b = spt_span(rom)
    out = bytearray(rom)
    done = 0
    for i, base, e in _tps_entries(rom):
        if i != 453:
            continue
        cnt = struct.unpack_from('<H', e, 0x06)[0]
        for j in range(1, cnt):
            if done >= 8:
                break
            off, clen = struct.unpack_from('<HH', e, 0x10 + (j - 1) * 8 + 4)
            sbase = base + off * 2
            if sbase + clen * 2 > b:
                continue
            units = [struct.unpack_from('<H', out, sbase + k * 2)[0] ^ XOR for k in range(clen)]
            targets, skip = [], 0
            for k, v in enumerate(units):
                if skip:
                    skip -= 1
                    continue
                if 0xE000 <= v <= 0xF8FF:
                    skip = ARGS.get(v, 0)
                    continue
                if v == 0x0A or 0x21 <= v <= 0x7E or 0xFF01 <= v <= 0xFF5E:
                    targets.append(k)
            if len(targets) < 32:
                continue
            for k in targets:
                out[sbase + k * 2:sbase + k * 2 + 2] = enc(WIDE_UNIT)
            done += 1
        break
    return bytes(out), done


def _repack_idlocal(D, repl):
    """Rebuild the idlocal container with entries in `repl` (index -> decompressed
    bytes) stored as literal-only LZ11 - the same shape plates.Plates.rebuild
    writes, so the fixture differs from a real build only in the pixels."""
    n = struct.unpack_from('<I', D, 0)[0] // 8
    ents = [struct.unpack_from('<II', D, i * 8) for i in range(n)]
    order = sorted(range(n), key=lambda i: ents[i][0])
    ext = {}
    for k, i in enumerate(order):
        ext[i] = (ents[i][0], ents[order[k + 1]][0] if k + 1 < n else len(D))
    table = bytearray(n * 8)
    body = bytearray()
    for i in range(n):
        o, s = ents[i]
        comp, size, stored = s & 0x80000000, s & 0x7FFFFFFF, D[ext[i][0]:ext[i][1]]
        if i in repl:
            raw = repl[i]
            lz = bytearray(b'\x11' + len(raw).to_bytes(3, 'little'))
            for p in range(0, len(raw), 8):
                lz.append(0)
                lz += raw[p:p + 8]
            stored, size, comp = bytes(lz), len(raw), 0x80000000
        while (n * 8 + len(body)) % 4:
            body += b'\x00'
        struct.pack_into('<II', table, i * 8, n * 8 + len(body), size | comp)
        body += stored
    return bytes(table) + bytes(body)


def break_titles(_rom_unused):
    """Erase the first letter of four fan title strips.

    audit_titles re-reads every strip by glyph matching and compares to the
    FAN_TITLES table plates.py keys off. A strip missing its first letter reads
    as a different word, which is the misread-strip defect the audit exists for.
    Works on the FAN idlocal.bin the audit reads (not a ROM) and only on strips
    the audit currently reads correctly, so the disagreement count must rise.
    """
    import plates as P
    fan_path = os.path.join(_REPO, 'dump', 'ds_fan', 'jpn', 'idlocal.bin')
    D = open(fan_path, 'rb').read()
    PLA = P.Plates(D)
    T = P.Titles(PLA)
    repl, done = {}, 0
    for i in sorted(P.FAN_TITLES):
        if done >= 4:
            break
        g = T._grid(i)
        runs = T._runs(g)
        # only strips the audit can read today: one glyph run per letter. The
        # hand-squeezed titles fuse letters and already disagree, so breaking
        # one of those would not move the count.
        if not runs or len(runs) != len(P.FAN_TITLES[i].replace(' ', '')):
            continue
        a, b = runs[0]
        for y in range(16):
            for x in range(a, b):
                if g[y][x] == 1:
                    g[y][x] = 2                      # stroke -> bar: letter gone
        repl[i] = T.encode(i, g)
        done += 1
    return _repack_idlocal(D, repl), done


# (script, what the fixture breaks, how, what the audit reads)
#   'rom'     the audit takes a ROM path; the fixture is a broken copy of out/
#   'idlocal' the audit reads the FAN idlocal.bin; the fixture is a broken copy of
#             that file and the clean run is the audit's default input
FIXTURES = [
    ('audit_boxes.py',   'strip box-ends from many strings (the v1.4.2 defect)', break_boxes,   'rom'),
    ('audit_cmdloss.py', 'delete DS-only E041 codes (the v1.4.3 hang)',          break_dsonly,  'rom'),
    ('audit_arity.py',   'fullwidth E108 arguments (the v1.3.3 Little Thief bug)', break_arity, 'rom'),
    ('audit_empty.py',   'blank whole strings of visible text',                  break_empty,   'rom'),
    ('audit_hint.py',    'shrink SPT buffer hints below their longest string',   break_hint,    'rom'),
    ('audit_widgets.py', 'widen bank-453 option rows past the fan maximum',      break_widgets, 'rom'),
    ('audit_titles.py',  'erase the first letter of four fan title strips',      break_titles,  'idlocal'),
]


def run(script, arg):
    cmd = [sys.executable, os.path.join(RIG, script)] + ([arg] if arg else [])
    return subprocess.run(cmd, capture_output=True, text=True, timeout=1800).stdout.strip()


def _first_diff(clean, dirty):
    """The first output line that changed, so the summary says WHAT the audit
    noticed rather than only that something differed."""
    c, d = clean.splitlines(), dirty.splitlines()
    for x, y in zip(c, d):
        if x != y:
            return y.strip()
    return (d[len(c)] if len(d) > len(c) else '').strip()


def main():
    os.makedirs(WORK, exist_ok=True)
    rom = open(REAL, 'rb').read()
    results = []
    for script, what, make, kind in FIXTURES:
        print('\n=== %s ===' % script)
        print('  fixture: %s' % what)
        broken, n = make(rom)
        if not n:
            print('  COULD NOT BUILD THE FIXTURE')
            results.append((script, 'no fixture'))
            continue
        print('  patched %d site(s)' % n)
        path = os.path.join(WORK, script.replace('.py', '.nds' if kind == 'rom' else '.bin'))
        open(path, 'wb').write(broken)
        clean, dirty = run(script, REAL if kind == 'rom' else None), run(script, path)
        ok = clean != dirty
        print('  audit notices: %s' % ok)
        if ok:
            print('  first changed line: %s' % _first_diff(clean, dirty))
        else:
            print('  >>> identical output on an input it should object to')
        results.append((script, 'DETECTED' if ok else 'MISSED'))
        os.remove(path)

    print('\n=== summary ===')
    for s, r in results:
        print('  %-20s %s' % (s, r))
    bad = [s for s, r in results if r != 'DETECTED']
    if bad:
        print('\nNOT PROVEN: %s' % ', '.join(bad))
        return 1
    print('\nevery fixture was detected - these audits can fail')
    return 0


if __name__ == '__main__':
    sys.exit(main())
