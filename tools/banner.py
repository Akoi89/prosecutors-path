# -*- coding: utf-8 -*-
"""DS banner title: write the official English title into the ROM's banner.

The banner is the block the DS menu and the flash-cart / emulator game list read
for the icon and the game name. The header's banner pointer (u32 at 0x68) gives
its offset; version 1 is 0x840 bytes:

    +0x000  u16 version (1)
    +0x002  u16 CRC16 over +0x020..+0x83F (modbus: poly 0xA001 reflected, init 0xFFFF)
    +0x020  icon bitmap (0x200) and palette (0x20), and the reserved bytes around them
    +0x240  six title slots, 0x100 bytes each (JP, EN, FR, DE, IT, ES), UTF-16LE,
            128 characters, zero padded; U+000A separates the lines

The fan ROM carries "Ace Attorney INVESTIGATIONS / Prosecutor's Path / CAPCOM" in all
six slots. This step sets all six to the official English name. The header title
(GYAKUKEN2), the game code and the header CRC (which covers only 0x000..0x15D) are not
touched, and neither are the icon and palette.

Runs as the LAST step of build.py, after compact (which copies the banner verbatim
and never resizes the ROM): the output has the same length as the input.

    python tools/banner.py ROM [--any-rom]      rewrite in place
"""
import os
import struct
import sys

OLD_TEXT = "Ace Attorney INVESTIGATIONS\nProsecutor's Path\nCAPCOM"
NEW_TEXT = "Ace Attorney INVESTIGATIONS\nProsecutor's Gambit\nCAPCOM"

SLOT0 = 0x240
SLOT_SIZE = 0x100
SLOTS = 6
SIZE_V1 = 0x840
SLOT_END = SLOT0 + SLOT_SIZE * SLOTS          # 0x840
CRC_FROM = 0x20


class BannerError(Exception):
    pass


def crc16(data):
    """CRC16 modbus as the DS banner uses it (same routine as inject.crc16)."""
    c = 0xFFFF
    for b in data:
        c ^= b
        for _ in range(8):
            c = (c >> 1) ^ 0xA001 if c & 1 else c >> 1
    return c


def encode_slot(text):
    raw = text.encode('utf-16le')
    if len(raw) > SLOT_SIZE:
        raise BannerError('title text is %d bytes, a slot holds %d' % (len(raw), SLOT_SIZE))
    return raw + b'\0' * (SLOT_SIZE - len(raw))


def decode_slot(slot):
    return bytes(slot).decode('utf-16le').split('\0', 1)[0]


def banner_offset(rom):
    off = struct.unpack_from('<I', rom, 0x68)[0]
    if off == 0 or off + SIZE_V1 > len(rom):
        raise BannerError('banner offset 0x%X is outside the ROM (%d bytes)' % (off, len(rom)))
    return off


def read_titles(rom):
    off = banner_offset(rom)
    return [decode_slot(rom[off + SLOT0 + i * SLOT_SIZE: off + SLOT0 + (i + 1) * SLOT_SIZE])
            for i in range(SLOTS)]


def patch(rom, old=OLD_TEXT, new=NEW_TEXT, any_rom=False, log=print):
    """Return (new ROM bytes, changed). Raises BannerError on a foreign banner
    unless any_rom, which logs the reason and leaves the ROM alone."""
    rom = bytes(rom)
    try:
        off = banner_offset(rom)
        ver = struct.unpack_from('<H', rom, off)[0]
        if ver != 1:
            raise BannerError('banner version is %d, only version 1 (0x840 bytes) is handled' % ver)
        titles = read_titles(rom)
        if all(t == new for t in titles):
            log('banner: already carries the official title, nothing to do')
            return rom, False
        bad = [i for i, t in enumerate(titles) if t != old]
        if bad:
            raise BannerError('banner title slot(s) %s are not the fan ROM\'s text %r: %r'
                              % (bad, old, [titles[i] for i in bad]))
        stored = struct.unpack_from('<H', rom, off + 2)[0]
        if stored != crc16(rom[off + CRC_FROM: off + SIZE_V1]):
            raise BannerError('banner CRC 0x%04X does not match its contents' % stored)
    except BannerError as e:
        if any_rom:
            log('banner: not changed (%s); continuing because --any-rom was given' % e)
            return rom, False
        raise

    out = bytearray(rom)
    slot = encode_slot(new)
    for i in range(SLOTS):
        out[off + SLOT0 + i * SLOT_SIZE: off + SLOT0 + (i + 1) * SLOT_SIZE] = slot
    crc = crc16(bytes(out[off + CRC_FROM: off + SIZE_V1]))
    struct.pack_into('<H', out, off + 2, crc)
    out = bytes(out)

    # read it back: CRC, titles, and nothing outside +2..+3 and +0x240..+0x83F moved
    if len(out) != len(rom):
        raise BannerError('ROM length changed')
    if struct.unpack_from('<H', out, off + 2)[0] != crc16(out[off + CRC_FROM: off + SIZE_V1]):
        raise BannerError('banner CRC does not read back')
    if read_titles(out) != [new] * SLOTS:
        raise BannerError('banner titles do not read back')
    keep = ((0, off + 2), (off + 4, off + SLOT0), (off + SLOT_END, len(rom)))
    for lo, hi in keep:
        if out[lo:hi] != rom[lo:hi]:
            raise BannerError('bytes outside the banner title and CRC changed (range 0x%X..0x%X)' % (lo, hi))
    log('banner: six title slots set to %r, CRC 0x%04X' % (new, crc))
    return out, True


def apply_file(path, any_rom=False, log=print):
    rom = open(path, 'rb').read()
    new, changed = patch(rom, any_rom=any_rom, log=log)
    if changed:
        open(path, 'wb').write(new)
    return changed


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('-')]
    if len(args) != 1:
        raise SystemExit('usage: banner.py ROM [--any-rom]')
    apply_file(args[0], any_rom='--any-rom' in sys.argv)
