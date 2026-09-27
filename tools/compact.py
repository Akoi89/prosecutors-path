"""Repack the built ROM's file system so every live file is stored once.

The build never rebuilds the ROM's file system: tools/inject.py and
tools/title_logo.splice() each append their replacement file at the end of
the ROM and repoint the one FAT entry that changed, leaving the old copy of
that file sitting in the middle of the ROM, unreferenced. Over a whole build
that is tens of megabytes of dead weight (the fan base is 45,165,392 bytes;
the uncompacted output was about 72.7 MB). This module packs every FAT file
into a single new copy of the ROM, once, as the last build step.

Layout of the structural prefix (header, ARM9, ARM9 overlay table, ARM7,
ARM7 overlay table, banner, FNT, FAT) is copied byte for byte from the input
ROM rather than re-derived field by field. Measuring the fan base ROM found a
24-byte gap between the end of ARM9's header-declared size and the start of
the ARM9 overlay table (almost certainly a decompression/module footer the
header's arm9_size does not count) - none of inject.py or title_logo.splice
ever move or resize any of these regions, only individual FAT entry values
and the header's size/capacity/CRC fields, so copying the whole span intact
is both simpler and safer than reassembling it and risking silently dropping
bytes like that footer. "Keep the secure area and everything before the
first moved block byte-identical" falls out of this for free.

File order: kept in FAT id order (not sorted by original physical offset).
Measured on both the fan base ROM and the current uncompacted build, FAT id
order and physical order are identical already, so there is no correctness
difference; id order is simpler (no separate sort/back-map step) and is the
order the base ROM itself already uses.

Alignment: the fan base ROM was measured file by file (tools which produced
it pad every FAT file so the NEXT file starts on a 4-byte boundary, using
0x00 pad bytes; gaps are 0, 2 or occasionally 3 bytes, never a fixed 0x200).
That is the alignment this module reproduces - not the 512-byte boundary
tools/inject.py and title_logo.splice pad newly appended files to, which is
just those two call sites being generous, not a property of the ROM format.
"""
import struct


def _cap_byte(size):
    """Smallest device-capacity code (header byte 0x14) that fits `size`.
    Same rule tools/inject.py and tools/title_logo.splice already use."""
    cap = 0
    while (128 * 1024) << cap < size:
        cap += 1
    return cap


def compact(rom_bytes):
    """Return a new ROM with every live FAT file stored exactly once."""
    from inject import crc16  # read-only import; inject.py itself is untouched

    rom = bytes(rom_bytes)
    arm9_off, _, _, arm9_size = struct.unpack_from('<IIII', rom, 0x20)
    arm7_off, _, _, arm7_size = struct.unpack_from('<IIII', rom, 0x30)
    fnt_off, fnt_size = struct.unpack_from('<II', rom, 0x40)
    fat_off, fat_size = struct.unpack_from('<II', rom, 0x48)
    ov9_off, ov9_size = struct.unpack_from('<II', rom, 0x50)
    ov7_off, ov7_size = struct.unpack_from('<II', rom, 0x58)
    icon_off = struct.unpack_from('<I', rom, 0x68)[0]

    n = fat_size // 8
    entries = [struct.unpack_from('<II', rom, fat_off + i * 8) for i in range(n)]

    # Everything up to and including the FAT table, whatever its internal
    # layout, is never moved or resized by the rest of the build - copy it
    # verbatim, including the banner, whose end is bounded below.
    # Banner size by its version field (the header has no size field for it).
    banner_size = {1: 0x840, 2: 0x940, 3: 0xA40, 0x103: 0x23C0}.get(
        struct.unpack_from('<H', rom, icon_off)[0], 0x840) if icon_off else 0
    prefix_end = max(fnt_off + fnt_size, fat_off + fat_size, icon_off + banner_size,
                      arm9_off + arm9_size, arm7_off + arm7_size,
                      ov9_off + ov9_size, ov7_off + ov7_size)
    prefix_end = (prefix_end + 3) & ~3  # the ROM's own 4-byte rule
    out = bytearray(rom[:prefix_end])
    pos = len(out)

    new_entries = []
    for s, e in entries:
        if e <= s:
            # Spec: skip empty FAT entries. Point them at the current write
            # position (zero length) rather than leaving a stale offset that
            # could land outside the new, shorter ROM.
            new_entries.append((pos, pos))
            continue
        while pos % 4:
            out.append(0)
            pos += 1
        start = pos
        out += rom[s:e]
        pos += (e - s)
        new_entries.append((start, pos))
    while pos % 4:            # same rule applies after the last file too -
        out.append(0)          # matches the 2-byte pad measured past the fan
        pos += 1                # base ROM's own last FAT entry.

    for i, (s, e) in enumerate(new_entries):
        struct.pack_into('<II', out, fat_off + i * 8, s, e)

    total = len(out)
    struct.pack_into('<I', out, 0x80, total)
    out[0x14] = _cap_byte(total)
    struct.pack_into('<H', out, 0x15E, crc16(bytes(out[:0x15E])))
    return bytes(out)


def compact_file(path):
    """Compact the ROM at `path` in place; the one-line build.py hook."""
    old = open(path, 'rb').read()
    new = compact(old)
    open(path, 'wb').write(new)
    print('compact: %.2f MB -> %.2f MB (%d -> %d bytes)'
          % (len(old) / 1e6, len(new) / 1e6, len(old), len(new)), flush=True)
    return new


if __name__ == '__main__':
    import sys
    inp = sys.argv[1]
    if len(sys.argv) > 2:
        out = sys.argv[2]
        old = open(inp, 'rb').read()
        new = compact(old)
        open(out, 'wb').write(new)
        print('compact: %.2f MB -> %.2f MB (%d -> %d bytes)  wrote %s'
              % (len(old) / 1e6, len(new) / 1e6, len(old), len(new), out), flush=True)
    else:
        compact_file(inp)
