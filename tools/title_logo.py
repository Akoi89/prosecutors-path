# -*- coding: utf-8 -*-
"""Replace the title screen's top-screen picture (jpn/title_local.bin) with a PNG.

The fan patch's title screen is a 256x192 8bpp background: NCGR tile bank (768
tiles) + NSCR map + NCLR palette, all inside title_local.bin. This rebuilds all
three from an image so the official 2024 logo can replace the fan-drawn one.

Constraints kept identical to the original so no header sizes move:
  - tile bank stays exactly 768 tiles (49152 bytes); the image is de-duplicated
    into <= 768 unique 8x8 tiles and the rest padded with blank tiles
  - palette keeps the original colour COUNT; the image is quantised to that many
    (minus one: index 0 is the backdrop and is forced to black)
  - map is 32x24 entries, palette bank 0, no flips
  - the container table keeps its full slot count (19 here, 8 live), and every
    entry is re-stored the way the original stored it: LZ11 blobs go back as
    stored-literal LZ11, raw blobs go back raw

Two things that black-screen the game on boot, both found by bisecting with
rig/title_bisect.py: writing the palette back RAW while its slot still carries
the compressed flag (the game LZ-decompresses garbage), and nothing else - a
plain repack, and new tiles + map, both boot fine.

    python tools/title_logo.py IMAGE.png dump/ds_fan/jpn/title_local.bin OUT.bin
    python tools/title_logo.py IMAGE.png dump/ds_fan/jpn/title_local.bin OUT.bin --rom in.nds out.nds

With --rom the new file is appended to a copy of the ROM and the FAT entry for
jpn/title_local.bin repointed, the same way inject.py ships spt.bin.
"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(__file__))
from title_version import _entries, _blob, _blob_raw, _store
from PIL import Image

W, H = 256, 192
COLS, ROWS = W // 8, H // 8


def _rgb555(rgb):
    r, g, b = rgb
    return (r >> 3) | ((g >> 3) << 5) | ((b >> 3) << 10)


def _pixels(q):
    return list(q.get_flattened_data()) if hasattr(q, 'get_flattened_data') else list(q.getdata())


def repack(data, repl):
    """Rebuild the container with entries in `repl` (index -> decompressed bytes)
    replaced. Each replaced entry is stored the way the original stored it."""
    ents = _entries(data)
    nslots = struct.unpack_from('<I', data, 0)[0] // 8
    slots = [struct.unpack_from('<II', data, i * 8) for i in range(nslots)]
    table = bytearray(nslots * 8)
    body = bytearray()
    for i, (o, s) in enumerate(slots):
        if i >= len(ents):
            struct.pack_into('<II', table, i * 8, o, s)          # terminator, verbatim
            continue
        if i in repl:
            was_lz = data[o:o + 1] == b'\x11' and bool(s & 0x80000000)
            if was_lz:
                stored, size, comp = _store(repl[i]), len(repl[i]), 0x80000000
            else:
                stored, size, comp = repl[i], len(repl[i]), 0
        else:
            stored, size, comp = _blob_raw(data, ents, i), s & 0x7FFFFFFF, s & 0x80000000
        while (nslots * 8 + len(body)) % 4:
            body += b'\x00'
        struct.pack_into('<II', table, i * 8, nslots * 8 + len(body), size | comp)
        body += stored
    return bytes(table) + bytes(body)


def build(png_path, title_local_bytes):
    data = title_local_bytes
    ents = _entries(data)
    gfx = bytearray(_blob(data, ents, 0))
    pal = bytearray(_blob(data, ents, 1))
    scr = bytearray(_blob(data, ents, 2))
    assert gfx[:4] == b'RGCN' and pal[:4] == b'RLCN' and scr[:4] == b'RCSN', 'unexpected entry types'

    tiles_off = 0x18 + 24
    tiles_len = struct.unpack_from('<I', gfx, 0x18 + 16)[0]
    ntiles = tiles_len // 64
    # PLTT body starts at 0x18 (16-byte file header + 8-byte section header);
    # its data (BGR555) starts 16 bytes into the body.
    pal_dsize = struct.unpack_from('<I', pal, 0x18 + 8)[0]
    pal_off = 0x18 + 16
    ncol = pal_dsize // 2
    mw, mh = struct.unpack_from('<HH', scr, 0x18)
    map_off = 0x18 + 12
    assert (mw, mh) == (W, H), 'map is %dx%d, expected %dx%d' % (mw, mh, W, H)

    im = Image.open(png_path).convert('RGB')
    assert im.size == (W, H), 'image is %s, need %dx%d' % (im.size, W, H)

    # Quantise to (ncol - 1) colours, then shift every index up by one so
    # index 0 can be the black backdrop the game expects.
    q = im.quantize(colors=ncol - 1, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.FLOYDSTEINBERG)
    qpal = q.getpalette()[:(ncol - 1) * 3]
    colours = [(0, 0, 0)] + [tuple(qpal[i:i + 3]) for i in range(0, len(qpal), 3)]
    idx = [v + 1 for v in _pixels(q)]

    # Slice into 8x8 tiles, de-duplicate.
    uniq, order, tile_map = {}, [], []
    for ty in range(ROWS):
        for tx in range(COLS):
            t = bytes(idx[(ty * 8 + y) * W + tx * 8 + x] for y in range(8) for x in range(8))
            if t not in uniq:
                uniq[t] = len(order); order.append(t)
            tile_map.append(uniq[t])
    if len(order) > ntiles:
        raise ValueError('image needs %d unique tiles, bank holds %d' % (len(order), ntiles))

    bank = bytearray(tiles_len)
    for i, t in enumerate(order):
        bank[i * 64:(i + 1) * 64] = t
    gfx[tiles_off:tiles_off + tiles_len] = bank

    for k, tid in enumerate(tile_map):
        struct.pack_into('<H', scr, map_off + k * 2, tid)

    for i in range(ncol):
        c = colours[i] if i < len(colours) else (0, 0, 0)
        struct.pack_into('<H', pal, pal_off + i * 2, _rgb555(c))

    out = repack(data, {0: bytes(gfx), 1: bytes(pal), 2: bytes(scr)})
    stats = dict(unique_tiles=len(order), bank_tiles=ntiles, colours=ncol,
                 slots=struct.unpack_from('<I', out, 0)[0] // 8)
    return out, stats


# --- ROM splice -------------------------------------------------------------

def splice(rom_bytes, path, newfile):
    from inject import file_id, crc16
    rom = bytearray(rom_bytes)
    fid = file_id(rom, path)
    fat = struct.unpack_from('<I', rom, 0x48)[0]
    while len(rom) % 512:
        rom += b'\xFF'
    start = len(rom)
    rom += newfile
    while len(rom) % 512:
        rom += b'\xFF'
    struct.pack_into('<II', rom, fat + fid * 8, start, start + len(newfile))
    struct.pack_into('<I', rom, 0x80, len(rom))
    cap = 0
    while (128 * 1024) << cap < len(rom):
        cap += 1
    rom[0x14] = cap
    struct.pack_into('<H', rom, 0x15E, crc16(bytes(rom[:0x15E])))
    return bytes(rom)


if __name__ == '__main__':
    png, src, out = sys.argv[1:4]
    newfile, st = build(png, open(src, 'rb').read())
    open(out, 'wb').write(newfile)
    print('wrote %s  (%d bytes)  unique tiles %d/%d, %d colours, %d table slots'
          % (out, len(newfile), st['unique_tiles'], st['bank_tiles'], st['colours'], st['slots']))
    if '--rom' in sys.argv:
        i = sys.argv.index('--rom')
        rin, rout = sys.argv[i + 1], sys.argv[i + 2]
        rom = splice(open(rin, 'rb').read(), 'jpn/title_local.bin', newfile)
        open(rout, 'wb').write(rom)
        print('wrote %s  (%.2f MB)' % (rout, len(rom) / 1e6))
