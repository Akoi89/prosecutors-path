# -*- coding: utf-8 -*-
"""Paint a build marker into the title screen's empty top-right corner.

`jpn/title_local.bin` entry 0 is the 256x192 8bpp title image, entry 1 its
256-colour palette, entry 2 the tilemap. Three facts make this cheap:

  * 460 of the 768 stored tiles are actually referenced, so 308 slots sit unused
    in the file already - new glyphs need no growth and no palette change.
  * Tile row 0 is entirely uniform background, palette index 1 (pure black).
  * Palette index 2 is already pure white.

The tilemap is the one hazard: tiles are shared, so painting one that is
referenced elsewhere would make the marker appear in several places at once.
Writing into UNUSED slots and repointing a few map entries avoids that entirely.

Nothing here is Capcom's or the fan team's artwork - it draws digits into black
space that no tile currently occupies.
"""
import struct

import lz11

# 3x5 pixel glyphs. Only what a version string needs.
FONT = {
    '0': ('111', '101', '101', '101', '111'),
    '1': ('010', '110', '010', '010', '111'),
    '2': ('111', '001', '111', '100', '111'),
    '3': ('111', '001', '111', '001', '111'),
    '4': ('101', '101', '111', '001', '001'),
    '5': ('111', '100', '111', '001', '111'),
    '6': ('111', '100', '111', '101', '111'),
    '7': ('111', '001', '001', '001', '001'),
    '8': ('111', '101', '111', '101', '111'),
    '9': ('111', '101', '111', '001', '111'),
    'v': ('000', '101', '101', '101', '010'),
    '.': ('000', '000', '000', '000', '010'),
    ' ': ('000', '000', '000', '000', '000'),
}

BG_INDEX = 1     # pure black, what row 0 already draws
INK_INDEX = 2    # pure white, already in the palette
TILE_ROW = 0     # top row of tiles
MARGIN = 2       # pixels of clearance from the right edge


def text_width(text):
    """Rendered width in pixels, 3px glyph + 1px gap, no trailing gap."""
    return max(0, len(text) * 4 - 1)


def paint_marker(picture, text, ink=(255, 255, 255)):
    """Draw `text` in the 3x5 font into the top-right corner of a PIL image,
    same placement as stamp() (row 1, MARGIN px from the right edge).

    Used since 1.5.0, when the title picture is composed from the official
    logo and re-tiled whole by title_logo.build: painting the marker into that
    picture before tiling is simpler than repointing tiles afterwards, and the
    corner is uniform black so no backing is needed."""
    px = picture.load()
    x0 = picture.width - MARGIN - text_width(text)
    for ch in text:
        rows = FONT.get(ch)
        if rows is None:
            raise ValueError('no glyph for %r' % ch)
        for dy, row in enumerate(rows):
            for dx, bit in enumerate(row):
                if bit == '1':
                    px[x0 + dx, 1 + dy] = ink
        x0 += 4
    return picture


def _entries(d):
    """(offset, size_field) pairs until the table runs into the first blob."""
    out = []
    n = 0
    while True:
        o, s = struct.unpack_from('<II', d, n * 8)
        if o == 0 or o >= len(d) or (out and n * 8 >= out[0][0]):
            break
        out.append((o, s))
        n += 1
        if n > 64:
            break
    return out


def _blob(d, ents, i):
    """Raw bytes of entry i - the extent is the NEXT entry's offset, never the
    size field, which holds the DECOMPRESSED size."""
    o = ents[i][0]
    end = ents[i + 1][0] if i + 1 < len(ents) else len(d)
    b = d[o:end]
    return lz11.decompress(b) if b[:1] == b'\x11' and (ents[i][1] & 0x80000000) else b


def _store(raw):
    """LZ11 wrapper with all-literal flags. The engine accepts these, so no
    compressor is needed - the same trick the nameplate rebuild uses."""
    out = bytearray(b'\x11' + len(raw).to_bytes(3, 'little'))
    for p in range(0, len(raw), 8):
        out.append(0)
        out += raw[p:p + 8]
    return bytes(out)


def stamp(data, text):
    """Return `data` with `text` painted into the title screen's top-right.

    Raises rather than guessing if the file is not shaped as expected - a
    silently unstamped build would be worse than a failed one.
    """
    ents = _entries(data)
    if len(ents) < 3:
        raise ValueError('title_local.bin: expected at least 3 entries, got %d' % len(ents))

    gfx, scr = bytearray(_blob(data, ents, 0)), bytearray(_blob(data, ents, 2))
    if gfx[:4] != b'RGCN' or scr[:4] != b'RCSN':
        raise ValueError('title_local.bin: entry 0/2 are %r/%r, not RGCN/RCSN'
                         % (bytes(gfx[:4]), bytes(scr[:4])))

    tiles_off = 0x18 + 24
    tiles_len = struct.unpack_from('<I', gfx, 0x18 + 16)[0]
    ntiles = tiles_len // 64
    mw, mh = struct.unpack_from('<HH', scr, 0x18)
    map_off = 0x18 + 12
    cols = mw // 8

    # Which tile ids does the map actually reference? Anything unreferenced is
    # free real estate.
    used = set()
    for k in range(cols * (mh // 8)):
        used.add(struct.unpack_from('<H', scr, map_off + k * 2)[0] & 0x3FF)
    free = [t for t in range(ntiles) if t not in used]

    width = text_width(text)
    need = (width + MARGIN + 7) // 8          # tiles the string spans
    if need > cols:
        raise ValueError('marker %r needs %d tiles, row is %d' % (text, need, cols))
    if len(free) < need:
        raise ValueError('only %d free tiles, need %d' % (len(free), need))

    first_col = cols - need
    slots = free[:need]

    # Paint the glyphs into a strip as wide as those tiles, right-aligned.
    strip = bytearray([BG_INDEX] * (need * 8 * 8))
    x0 = need * 8 - MARGIN - width
    for ch in text:
        rows = FONT.get(ch)
        if rows is None:
            raise ValueError('no glyph for %r' % ch)
        for dy, row in enumerate(rows):
            for dx, bit in enumerate(row):
                if bit == '1':
                    strip[(dy + 1) * (need * 8) + x0 + dx] = INK_INDEX
        x0 += 4

    # Slice the strip into 8x8 tiles and write them into the free slots.
    for t, slot in enumerate(slots):
        base = tiles_off + slot * 64
        for y in range(8):
            for x in range(8):
                gfx[base + y * 8 + x] = strip[y * (need * 8) + t * 8 + x]

    # Point the top-right map entries at them, keeping each entry's palette and
    # flip bits so only the tile id changes.
    for t, slot in enumerate(slots):
        k = TILE_ROW * cols + first_col + t
        cur = struct.unpack_from('<H', scr, map_off + k * 2)[0]
        struct.pack_into('<H', scr, map_off + k * 2, (cur & ~0x3FF) | slot)

    # Rebuild the container. Offsets are rewritten because a stored-literal blob
    # is larger than the original compressed one.
    repl = {0: bytes(gfx), 2: bytes(scr)}
    table = bytearray(len(ents) * 8)
    body = bytearray()
    for i, (o, s) in enumerate(ents):
        if i in repl:
            stored, size, comp = _store(repl[i]), len(repl[i]), 0x80000000
        else:
            stored, size, comp = _blob_raw(data, ents, i), s & 0x7FFFFFFF, s & 0x80000000
        while (len(ents) * 8 + len(body)) % 4:
            body += b'\x00'
        struct.pack_into('<II', table, i * 8, len(ents) * 8 + len(body), size | comp)
        body += stored
    return bytes(table) + bytes(body)


def _blob_raw(d, ents, i):
    """Entry i exactly as stored, compression untouched."""
    o = ents[i][0]
    end = ents[i + 1][0] if i + 1 < len(ents) else len(d)
    return d[o:end]
