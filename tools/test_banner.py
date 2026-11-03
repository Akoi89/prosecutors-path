# -*- coding: utf-8 -*-
"""Tests for tools/banner.py. Run from the port folder:
    python tools/test_banner.py [BUILT_ROM]

With a built v1.11.x ROM (default out/GK2-v1.11.4-official-english.nds when present; that file
is the reference for the CRC check, 0x42AD) it also checks the CRC function on the real banner
bytes and a round trip on the real ROM. Without one, a synthetic ROM is used and the real-ROM
checks are skipped (said so). Raises on any failure.
"""
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import banner

REAL_CRC = 0x42AD
OFF = 0x78000


def synthetic(old=banner.OLD_TEXT):
    rom = bytearray(0x79000)
    struct.pack_into('<I', rom, 0x68, OFF)
    struct.pack_into('<H', rom, OFF, 1)
    for i in range(0x20, 0x240):                      # icon + palette stand-in
        rom[OFF + i] = (i * 7) & 0xFF
    for i in range(banner.SLOTS):
        rom[OFF + banner.SLOT0 + i * banner.SLOT_SIZE:OFF + banner.SLOT0 + (i + 1) * banner.SLOT_SIZE] = banner.encode_slot(old)
    struct.pack_into('<H', rom, OFF + 2, banner.crc16(bytes(rom[OFF + 0x20:OFF + 0x840])))
    rom[0x1000:0x1010] = b'file data here..'
    return bytes(rom)


def raises(fn, what):
    try:
        fn()
    except banner.BannerError:
        return
    raise AssertionError('did not raise: ' + what)


def main():
    quiet = lambda *_a: None
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, '..', 'out', 'GK2-v1.11.4-official-english.nds')
    n = 0

    # CRC: known-answer on an independent bit-wise definition and on the real banner
    assert banner.crc16(b'') == 0xFFFF
    assert banner.crc16(b'123456789') == 0x4B37, hex(banner.crc16(b'123456789'))   # CRC-16/MODBUS check value
    n += 2
    real = open(path, 'rb').read() if os.path.exists(path) else None
    if real:
        off = struct.unpack_from('<I', real, 0x68)[0]
        b = real[off:off + 0x840]
        stored = struct.unpack_from('<H', b, 2)[0]
        got = banner.crc16(b[0x20:])
        print('real banner: offset 0x%X, stored CRC 0x%04X, computed 0x%04X' % (off, stored, got))
        assert got == stored
        if banner.read_titles(real) == [banner.OLD_TEXT] * 6:
            assert stored == REAL_CRC, hex(stored)          # the v1.11.4 build as shipped
        n += 1
    else:
        print('SKIPPED real-ROM checks: %s not found' % path)

    # round trip on the synthetic ROM and (if present) the real one
    for label, rom in [('synthetic', synthetic())] + ([('real', real)] if real and banner.read_titles(real) == [banner.OLD_TEXT] * 6 else []):
        new, changed = banner.patch(rom, log=quiet)
        assert changed and len(new) == len(rom)
        assert banner.read_titles(new) == [banner.NEW_TEXT] * 6
        off = struct.unpack_from('<I', rom, 0x68)[0]
        assert struct.unpack_from('<H', new, off + 2)[0] == banner.crc16(new[off + 0x20:off + 0x840])
        diff = [i for i in range(len(rom)) if rom[i] != new[i]] if label == 'synthetic' else None
        if diff is not None:
            assert all(off + 2 <= i < off + 4 or off + 0x240 <= i < off + 0x840 for i in diff)
        assert new[off + 0x20:off + 0x240] == rom[off + 0x20:off + 0x240]       # icon and palette
        assert new[:0x160] == rom[:0x160]                                          # header incl. title, code, CRC
        again, changed2 = banner.patch(new, log=quiet)                            # second run is a no-op
        assert not changed2 and again == new
        print('round trip ok (%s)' % label)
        n += 1

    # the text itself
    assert banner.NEW_TEXT == "Ace Attorney INVESTIGATIONS\nProsecutor's Gambit\nCAPCOM"
    assert len(banner.encode_slot(banner.NEW_TEXT)) == 0x100
    n += 1

    # guards
    good = synthetic()
    other = synthetic(old='Something Else\nEntirely')
    raises(lambda: banner.patch(other, log=quiet), 'different old text')
    mixed = bytearray(good)
    mixed[OFF + banner.SLOT0 + 3 * 0x100:OFF + banner.SLOT0 + 4 * 0x100] = banner.encode_slot('French?')
    struct.pack_into('<H', mixed, OFF + 2, banner.crc16(bytes(mixed[OFF + 0x20:OFF + 0x840])))
    raises(lambda: banner.patch(bytes(mixed), log=quiet), 'one slot different')
    v2 = bytearray(good); struct.pack_into('<H', v2, OFF, 2)
    raises(lambda: banner.patch(bytes(v2), log=quiet), 'banner version 2')
    badcrc = bytearray(good); badcrc[OFF + 2] ^= 1
    raises(lambda: banner.patch(bytes(badcrc), log=quiet), 'wrong stored CRC')
    nooff = bytearray(good); struct.pack_into('<I', nooff, 0x68, 0)
    raises(lambda: banner.patch(bytes(nooff), log=quiet), 'banner offset 0')
    n += 5
    # --any-rom logs and leaves the ROM alone
    msgs = []
    r, c = banner.patch(other, any_rom=True, log=msgs.append)
    assert r == other and not c and msgs and 'any-rom' in msgs[0]
    n += 1
    print('test_banner: %d checks passed' % n)


if __name__ == '__main__':
    main()
