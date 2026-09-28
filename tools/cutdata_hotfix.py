# -*- coding: utf-8 -*-
"""Hotfix: Case 4 entry 247 str 4, "point at the burn mark" (com/cutdata.bin
slot 47, cut 208, the Coroner's Findings close-up).

The accepted rectangle shipped in every release since 1.7.0 is a JP-retail
leftover (x111..187, y131..147, unchanged since the Japanese original) that
our re-wrapped document no longer lines up with: the box now sits over "of
victim's" instead of "burn" / "mark", so a tap on either target word is
penalised.

This derives one rectangle per line-run of "burn mark" from txtcut's own
layout of that document (screen entry 250, gk2_txtcut_en row 33) - the same
font metrics and line/justify math txtcut.render() uses to draw the pixels,
not typed coordinates - pads each rectangle 2 px a side like the JP box's own
margin around its glyphs, and rewrites slot 47 to hold both as index-0
records so {E161 0,6} in entry 247 str 4 needs no change.

Hash-guarded: this only runs when the row text txtcut renders for that screen
and the fan's whole com/cutdata.bin match the values it was proven against.
Either mismatching (a future re-wrap of row 33, a changed cutdata.bin) skips
the patch entirely, leaves cutdata.bin byte-identical to the fan's, and logs
why, rather than writing a guess.
"""
import hashlib, os, struct, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import txtcut
import title_logo
from lz11 import decompress

ENTRY = 250            # jpn/upcut_local.bin screen: Coroner's Findings
ROW = 33                # gk2_txtcut_en row txtcut.ROWS[ENTRY] maps to
TARGETS = ('burn', 'mark')
PAD = 2                 # px each side, matching the JP rectangle's own margin
SLOT = 47               # com/cutdata.bin slot serving cut 208 (cut 208 serves only entry 247 str 4)
AREA_INDEX = 0          # unchanged from the original single record

# sha256 of the exact row 33 text txtcut.prepare_rows() renders, and of the
# fan's whole com/cutdata.bin. Update only alongside a proven re-check of the
# derived rectangles.
EXPECTED_ROW_SHA256 = 'fe993bee95b776813767dc7dac723116595852101c264c8ef645c8b7c9bb1e4f'
EXPECTED_CUTDATA_SHA256 = '7171be39f1f6fad6b6fb7c5c4c17e54b90e7980ea5254ace2f9c6cbbf7c35590'


def _ink_extent(bits):
    """leftmost, rightmost lit column (0-based) in one glyph's own bitmap."""
    lit = [rx for row in bits for rx, ch in enumerate(row) if ch == '1']
    return min(lit), max(lit)


def word_boxes(entry=ENTRY, row=ROW, targets=TARGETS):
    """-> {word: [(x1, y1, x2, y2), ...]} tight ink rectangles (no padding),
    read straight from txtcut's own font metrics and the exact pen positions
    render() would draw at - not a pixel scan of a rendered screen, which
    over a chosen window can pick up neighbouring words' ink instead."""
    font, space = txtcut.load_font()
    rows, _, _ = txtcut.prepare_rows()
    row_text = rows[row][1]
    data = open(txtcut.SRC, 'rb').read()
    E = txtcut.table(data)
    gfx, palb = E[entry], E[entry + 1]
    colours, pal = txtcut.screen_colours(gfx, palb)
    log = []
    capture = []
    txtcut.render(entry, row_text, font, space, colours, log, capture=capture)
    found = {}
    for ln, base in capture:
        positions, _ = txtcut.line_positions(font, space, ln['toks'], ln['x'],
                                              ln['width'], ln['justify'], ln['align'])
        for tok, style, start in positions:
            if tok not in targets:
                continue
            pen = start
            chars = []
            for c in tok:
                g = font[c] if c in font else font['?']
                chars.append((pen, g))
                pen += 2 * font['"']['adv'] if c == '"' else txtcut.glyph_adv(font, c, space)
            top = bottom = None
            for _, g in chars:
                b = base + g['desc']
                t = b - (g['h'] - 1)
                top = t if top is None else min(top, t)
                bottom = b if bottom is None else max(bottom, b)
            l0, _ = _ink_extent(chars[0][1]['bits'])
            _, r1 = _ink_extent(chars[-1][1]['bits'])
            x1 = chars[0][0] + l0
            x2 = chars[-1][0] + r1
            found.setdefault(tok, []).append((x1, top, x2, bottom))
    return found


def _lz11_literal(raw):
    """A valid LZ11 stream made of literals only (no back-references): header
    0x11 + 24-bit decompressed size, then a zero flag byte before every 8
    literal bytes - the same shape every other cutdata.bin slot already uses."""
    out = bytearray(struct.pack('<I', 0x11 | (len(raw) << 8)))
    for i in range(0, len(raw), 8):
        out.append(0)
        out += raw[i:i + 8]
    return bytes(out)


def _build_slot(template_header, rects, area_index=AREA_INDEX):
    """template_header is the fan's decompressed slot 47 (header + its one
    record); every slot's header size fields (offsets 8, 12, 16) hold the
    slot's own decompressed byte length in their upper 16 bits (checked
    across every slot in the fan's cutdata.bin, not assumed)."""
    hdr = bytearray(template_header[:20])
    size = 20 + 44 * len(rects)
    struct.pack_into('<H', hdr, 4, len(rects))
    struct.pack_into('<I', hdr, 8, size << 16)
    struct.pack_into('<I', hdr, 12, size << 16)
    struct.pack_into('<I', hdr, 16, size << 16)
    recs = b''.join(
        struct.pack('<11i', 0, 0, x1 << 12, y1 << 12, x2 << 12, y2 << 12, 0, area_index, 0, 0, 0)
        for x1, y1, x2, y2 in rects)
    return bytes(hdr) + recs


def _rebuild_cutdata(fan_bytes, rects):
    """-> new com/cutdata.bin bytes. Every original byte stays at its
    original offset: slot 47's larger replacement is appended after the old
    end-of-file instead of shifting every later slot down to make room, so
    slot 47's own table entry and the table's own end-of-file marker are the
    only entries that change.

    The table's last entry is not a slot: it is the container's own
    end-of-file marker (offset == the file's own length, size 0 - every table
    in the fan's cutdata.bin and in the 1.10.0 output carries one). Appending
    past the old end-of-file moves it, so it is computed last, once the new
    file's length is known, rather than treated as an empty slot and zeroed."""
    d = fan_bytes
    n = struct.unpack_from('<I', d, 0)[0] // 8
    slots = [struct.unpack_from('<II', d, i * 8) for i in range(n)]

    end_idx = n - 1
    end_o, end_s = slots[end_idx]
    if end_s != 0 or end_o != len(d):
        raise ValueError('cutdata hotfix: expected the last table entry to be the end-of-file '
                         'marker (offset %d, size 0); got offset %d size %d' % (len(d), end_o, end_s))

    old_o, old_s = slots[SLOT]
    live = sorted(o for o, s in slots if o)
    nxt = [q for q in live if q > old_o]
    old_raw = d[old_o:nxt[0] if nxt else len(d)]
    old_slot = decompress(old_raw) if old_raw[:1] == b'\x11' else old_raw
    new_slot = _build_slot(old_slot, rects)
    comp = _lz11_literal(new_slot)
    if decompress(comp) != new_slot:
        raise ValueError('cutdata hotfix: the re-encoded slot 47 does not round-trip through LZ11')

    table = bytearray(d[:n * 8])
    body = bytearray(d[n * 8:])                 # every original blob, at its original offset
    while len(body) % 4:                        # the fan's own body already ends 4-aligned; kept
        body += b'\x00'                         # here so the appended blob would be too if it ever weren't
    new_off = n * 8 + len(body)
    body += comp
    while len(body) % 4:
        body += b'\x00'
    struct.pack_into('<II', table, SLOT * 8, new_off, 0x80000000 | len(new_slot))
    struct.pack_into('<II', table, end_idx * 8, n * 8 + len(body), 0)
    return bytes(table) + bytes(body)


def apply_to_rom(rom, dumpdir, log=print):
    """-> (rom, applied: bool). See module docstring for the hash guard."""
    src_path = os.path.join(dumpdir, 'ds_fan', 'com', 'cutdata.bin')
    fan_bytes = open(src_path, 'rb').read()
    got_cutdata_hash = hashlib.sha256(fan_bytes).hexdigest()
    if got_cutdata_hash != EXPECTED_CUTDATA_SHA256:
        log('cutdata hotfix: SKIPPED - com/cutdata.bin does not match the expected hash '
            '(got %s, wanted %s); leaving it untouched' % (got_cutdata_hash, EXPECTED_CUTDATA_SHA256))
        return rom, False

    rows, _, _ = txtcut.prepare_rows()
    row_text = rows[ROW][1]
    got_row_hash = hashlib.sha256(row_text.encode('utf-8')).hexdigest()
    if got_row_hash != EXPECTED_ROW_SHA256:
        log('cutdata hotfix: SKIPPED - entry %d row %d text does not match the expected hash '
            '(got %s, wanted %s); leaving cutdata.bin untouched' % (ENTRY, ROW, got_row_hash, EXPECTED_ROW_SHA256))
        return rom, False

    boxes = word_boxes()
    rects = []
    for w in TARGETS:
        hits = boxes.get(w, [])
        if len(hits) != 1:
            raise ValueError('cutdata hotfix: expected exactly one line-run of %r, found %d' % (w, len(hits)))
        x1, y1, x2, y2 = hits[0]
        rects.append((x1 - PAD, y1 - PAD, x2 + PAD, y2 + PAD))

    new_cutdata = _rebuild_cutdata(fan_bytes, rects)
    rom = title_logo.splice(rom, 'com/cutdata.bin', new_cutdata)
    log('cutdata hotfix: slot %d (cut 208, "burn mark") rewritten - %d records %s'
        % (SLOT, len(rects), rects))
    return rom, True


if __name__ == '__main__':
    # standalone check: print the derived rectangles without touching any ROM
    print('word boxes (unpadded):', word_boxes())
