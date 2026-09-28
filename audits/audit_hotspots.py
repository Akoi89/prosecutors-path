# -*- coding: utf-8 -*-
"""Point-at-document hotspots: does the accepted rectangle in com/cutdata.bin
still cover the target ink, and nothing else?

Ten {E160} point-at prompts have a close-up that is a jpn/upcut_local.bin
picture (container 0x5003) rather than a com/upcut.bin one. Of those, only
entry 250 (Case 4's Coroner's Findings, cut 208, cutdata slot 47, entry 247
str 4 "point at the burn mark") is also one of the 39 txtcut text screens -
the other nine are photos and maps with no rendered phrase, so there is
nothing to check there but "did anything change".

Two different checks, by prompt kind:

  TEXT (entry 250): render the document the way txtcut.build() does - its own
  font metrics and line layout, not typed coordinates - to know exactly which
  pixels are "burn" and which are "mark", read the ROM's OWN decoded image and
  the ROM's OWN cutdata.bin rectangles (never the in-memory values a build
  just computed), and check: every target-word pixel is real ink in that
  image (the layout claim matches what actually got drawn); every target-word
  pixel sits inside some accepted rectangle carrying the correct answer's area
  index; and no OTHER lit pixel of the document does.

  PICTURE (the other nine): the audit cannot tell whether "the alligator" is
  still under its rectangle from pixels alone. The only defect it can catch is
  a silent change - the image bytes or the cutdata slot moving without this
  catalog being told - so it compares both to the fan ROM's own and fails on
  any difference.

    python audits/audit_hotspots.py [rom.nds] [fan_rom.nds]
"""
import os as _os
import sys as _sys

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

import struct
import sys

import txtcut
import nitro
from inject import file_id                    # noqa: E402

OURS_ROM = sys.argv[1] if len(sys.argv) > 1 else _default_built()
FAN_ROM = sys.argv[2] if len(sys.argv) > 2 else _default_fan()

# local upcut_local entry -> cutdata slot, for the nine {E160} point-at
# prompts whose close-up is a jpn/upcut_local.bin picture (container 0x5003)
# other than entry 250 itself: read from the fan's own cutdata.bin and the
# {E117}/{E160} script commands that name each cut and its hotspot slot. No
# phrase to check on a photo or map; only "did it change" is catchable.
PICTURE_PROMPTS = {
    4: 1, 78: 27, 82: 28, 36: 13, 40: 15, 64: 21, 104: 30, 234: 46, 280: 65,
}

# the one text prompt: entry 247 str 4, "point at the burn mark"
TEXT_LOCAL = 250
TEXT_SLOT = 47
TEXT_TARGETS = ('burn', 'mark')
TEXT_AREA_INDEX = 0        # {E161 0,6} - the correct-answer branch


def read_file(rom, path):
    fat = struct.unpack_from('<I', rom, 0x48)[0]
    fid = file_id(rom, path)
    a, b = struct.unpack_from('<II', rom, fat + fid * 8)
    return rom[a:b]


def decode_image(gfx):
    """-> 256x192 index grid (list of rows), the same tile layout write_gfx
    (tools/txtcut.py) writes, read back rather than re-rendered."""
    data, bpp, cnt, tw, th = nitro.ncgr(gfx)
    W, H = txtcut.W, txtcut.H
    tw_tiles = W // 8
    grid = [[0] * W for _ in range(H)]
    for t in range(len(data) // 64):
        bx, by = (t % tw_tiles) * 8, (t // tw_tiles) * 8
        for y in range(8):
            for x in range(8):
                grid[by + y][bx + x] = data[t * 64 + y * 8 + x]
    return grid


def cutdata_records(slot_bytes):
    """-> [(x1, y1, x2, y2, shape, index), ...] for one decoded cutdata slot."""
    cnt = struct.unpack_from('<H', slot_bytes, 4)[0]
    out = []
    for k in range(cnt):
        f = struct.unpack_from('<11i', slot_bytes, 20 + 44 * k)
        out.append((f[2] >> 12, f[3] >> 12, f[4] >> 12, f[5] >> 12, f[6], f[7]))
    return out


def target_word_pixels(entry=TEXT_LOCAL, targets=TEXT_TARGETS):
    """-> {word: set of (x, y)} - every pixel txtcut's own font metrics and
    layout say a target word occupies, from the row text it actually renders
    (dump/loc_en.json + txtcut_condensed.json, prepare_rows()), independent of
    any rectangle a build computed."""
    font, space = txtcut.load_font()
    rows, _, _ = txtcut.prepare_rows()
    row_text = rows[txtcut.ROWS[entry]][1]
    capture = []
    txtcut.render(entry, row_text, font, space, {'bg': 0, None: 1, 'red': 1, 'blue': 1},
                  [], capture=capture)
    out = {w: set() for w in targets}
    for ln, base in capture:
        positions, _ = txtcut.line_positions(font, space, ln['toks'], ln['x'],
                                              ln['width'], ln['justify'], ln['align'])
        for tok, style, start in positions:
            if tok not in out:
                continue
            pen = start
            for c in tok:
                g = font[c] if c in font else font['?']
                bottom = base + g['desc']
                top = bottom - (g['h'] - 1)
                for ry, row in enumerate(g['bits']):
                    for rx, ch in enumerate(row):
                        if ch == '1':
                            out[tok].add((pen + rx, top + ry))
                pen += 2 * font['"']['adv'] if c == '"' else txtcut.glyph_adv(font, c, space)
    return out


def check_text_prompt(ours, log):
    fail = []
    gfx, palb = txtcut.table(read_file(ours, 'jpn/upcut_local.bin'))[TEXT_LOCAL:TEXT_LOCAL + 2]
    grid = decode_image(gfx)
    colours, _ = txtcut.screen_colours(gfx, palb)
    fg = colours[None]

    slots = txtcut.table(read_file(ours, 'com/cutdata.bin'))
    records = cutdata_records(slots[TEXT_SLOT])
    accepted = [(x1, y1, x2, y2) for x1, y1, x2, y2, shape, idx in records if idx == TEXT_AREA_INDEX]
    if not accepted:
        fail.append('slot %d has no area-%d rectangle at all' % (TEXT_SLOT, TEXT_AREA_INDEX))
        log('entry %d: %s' % (TEXT_LOCAL, fail[-1]))
        return fail

    def in_any_box(x, y):
        return any(x1 <= x <= x2 and y1 <= y <= y2 for x1, y1, x2, y2 in accepted)

    targets = target_word_pixels()
    target_all = set()
    for word, pix in targets.items():
        target_all |= pix
        not_ink = [p for p in pix if grid[p[1]][p[0]] != fg]
        if not_ink:
            fail.append('%r: %d of its %d expected pixels are not ink in the built image '
                        '(layout/render disagree) e.g. %s' % (word, len(not_ink), len(pix), not_ink[:3]))
            continue
        outside = [p for p in pix if not in_any_box(*p)]
        if outside:
            fail.append('%r: %d/%d pixels fall outside every accepted rectangle %s, e.g. %s'
                        % (word, len(outside), len(pix), accepted, outside[:3]))

    W, H = txtcut.W, txtcut.H
    extra = []
    for y in range(H):
        row = grid[y]
        for x in range(W):
            if row[x] == fg and (x, y) not in target_all and in_any_box(x, y):
                extra.append((x, y))
    if extra:
        fail.append('%d pixel(s) of OTHER text also fall inside the accepted rectangle(s) %s, '
                    'e.g. %s' % (len(extra), accepted, extra[:5]))

    log('entry %d (slot %d): accepted %s, burn %d px, mark %d px, other-text-in-box %d px%s'
        % (TEXT_LOCAL, TEXT_SLOT, accepted, len(targets.get('burn', ())), len(targets.get('mark', ())),
           len(extra), ' - FAIL' if fail else ' - OK'))
    return fail


def check_picture_prompts(ours, fan, log):
    fail = []
    ours_local = txtcut.table(read_file(ours, 'jpn/upcut_local.bin'))
    fan_local = txtcut.table(read_file(fan, 'jpn/upcut_local.bin'))
    ours_cut = txtcut.table(read_file(ours, 'com/cutdata.bin'))
    fan_cut = txtcut.table(read_file(fan, 'com/cutdata.bin'))
    for local, slot in sorted(PICTURE_PROMPTS.items()):
        img_ok = ours_local[local] == fan_local[local] and ours_local[local + 1] == fan_local[local + 1]
        cut_ok = ours_cut[slot] == fan_cut[slot]
        if not img_ok:
            fail.append('local image %d changed from the fan\'s (image bytes)' % local)
        if not cut_ok:
            fail.append('cutdata slot %d (local image %d) changed from the fan\'s' % (slot, local))
        log('local %3d slot %2d: image %s, hitboxes %s' % (
            local, slot, 'OK' if img_ok else 'CHANGED', 'OK' if cut_ok else 'CHANGED'))
    return fail


def main():
    ours = open(OURS_ROM, 'rb').read()
    fan = open(FAN_ROM, 'rb').read()
    log = print
    print('ours: %s' % OURS_ROM)
    print('fan:  %s' % FAN_ROM)
    print()
    fail = []
    fail += check_text_prompt(ours, log)
    print()
    fail += check_picture_prompts(ours, fan, log)
    print()
    if fail:
        print('FAIL:')
        for f in fail:
            print('  - %s' % f)
        return 1
    print('all ten local-image point-at prompts OK')
    return 0


if __name__ == '__main__':
    sys.exit(main())
