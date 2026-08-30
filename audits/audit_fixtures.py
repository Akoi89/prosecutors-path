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

    python rig\audit_fixtures.py
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


FIXTURES = [
    ('audit_boxes.py',   'strip box-ends from many strings (the v1.4.2 defect)', break_boxes),
    ('audit_cmdloss.py', 'delete DS-only E041 codes (the v1.4.3 hang)',          break_dsonly),
    ('audit_arity.py',   'fullwidth E108 arguments (the v1.3.3 Little Thief bug)', break_arity),
    ('audit_empty.py',   'blank whole strings of visible text',                  break_empty),
]


def run(script, rom_path):
    return subprocess.run([sys.executable, os.path.join(RIG, script), rom_path],
                          capture_output=True, text=True, timeout=1800).stdout.strip()


def main():
    os.makedirs(WORK, exist_ok=True)
    rom = open(REAL, 'rb').read()
    results = []
    for script, what, make in FIXTURES:
        print('\n=== %s ===' % script)
        print('  fixture: %s' % what)
        broken, n = make(rom)
        if not n:
            print('  COULD NOT BUILD THE FIXTURE')
            results.append((script, 'no fixture'))
            continue
        print('  patched %d site(s)' % n)
        path = os.path.join(WORK, script.replace('.py', '.nds'))
        open(path, 'wb').write(broken)
        clean, dirty = run(script, REAL), run(script, path)
        ok = clean != dirty
        print('  audit notices: %s' % ok)
        if not ok:
            print('  >>> identical output on a ROM it should object to')
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
