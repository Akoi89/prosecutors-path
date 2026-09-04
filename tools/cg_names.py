# -*- coding: utf-8 -*-
"""Re-letter the fan character names drawn into three close-up graphics.

jpn/upcut_local.bin entries 210 and 242 are log tables and entry 100 is a room
map; the fan patch drew its own character names into the artwork, and Capcom's
Collection has no text rows for these pictures. So the names are swapped in
place: the old name's pixels are erased to the ground colour and the official
name is rendered with the fan's own face (tools/txtcut_font.json), in the same
colour, at the same origin.

The tables are dark text on white cells (letter spacing as on the text
screens). The map labels are dark glyphs with a 1 px orthogonal halo, set one
pixel tighter than the screens, centred on their room.

Runs AFTER txtcut.py on the same container:
    python tools/cg_names.py IN_upcut_local.bin OUTDIR [--rom in.nds out.nds]
"""
import sys, os, struct, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from nitro import ncgr, nclr, _sections
from title_text import repack
from txtcut import table, load_font, blit, glyph_adv, write_gfx, W, H
from PIL import Image

# entry -> list of edits. Each edit: the box whose old ink is erased (any pixel
# not the ground colour inside it becomes ground), the new text, its left x or
# centre x, its baseline, the ink colour, and the style.
MAP_FONT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'map_font.json')
INK100, HALO100, TAN100 = (82, 82, 82), (247, 239, 231), (189, 165, 140)
HALO100B = (222, 214, 198)   # the halo's diagonal corners, a softer tone

EDITS = {
    # the contest map: Capcom's own English map (Collection cut02_003_eng) labels
    # the rooms Gusto's / Scone's / Tangaroa's / Frost's; the second line "Room"
    # stays as the fan drew it. Only the label's ink and halo are erased, since
    # the wedge outlines share the dark colour.
    100: {'ground': TAN100, 'erase': [INK100, HALO100, HALO100B], 'face': 'map',
          'edits': [{'box': (40, 42, 98, 56), 'text': "Gusto's", 'cx': 68, 'base': 52, 'ink': INK100, 'halo': HALO100, 'halo2': HALO100B},
                    {'box': (161, 42, 206, 56), 'text': "Scone's", 'cx': 183, 'base': 52, 'ink': INK100, 'halo': HALO100, 'halo2': HALO100B},
                    {'box': (19, 88, 68, 101), 'text': "Tangaroa's", 'cx': 43, 'base': 98, 'ink': INK100, 'halo': HALO100, 'halo2': HALO100B},
                    {'box': (191, 88, 235, 101), 'text': "Frost's", 'cx': 212, 'base': 98, 'ink': INK100, 'halo': HALO100, 'halo2': HALO100B}]},
    210: {'ground': (255, 255, 255), 'keep': [(165, 214, 231)],
          'edits': [{'box': (139, 73, 246, 89), 'text': 'Rosie Ringer', 'x': 141, 'base': 84, 'ink': (74, 74, 74)}]},
    242: {'ground': (255, 255, 255), 'keep': [(165, 214, 231)],
          'edits': [{'box': (139, 53, 246, 70), 'text': 'Verity Gavelle', 'x': 141, 'base': 66, 'ink': (74, 74, 74)},
                    {'box': (139, 73, 246, 89), 'text': 'Rosie Ringer', 'x': 141, 'base': 84, 'ink': (74, 74, 74)}]},
}


def palette_index(pal, rgb):
    for i, c in enumerate(pal):
        if c == rgb:
            return i
    raise KeyError('colour %s not in palette' % (rgb,))


def image_of(gfx, pal):
    data, bpp, cnt, tw, th = ncgr(gfx)
    im = Image.new('P', (W, H))
    px = im.load()
    for t in range(cnt):
        bx, by = (t % tw) * 8, (t // tw) * 8
        blk = data[t * 64:(t + 1) * 64]
        for y in range(8):
            for x in range(8):
                px[bx + x, by + y] = blk[y * 8 + x]
    return im


def draw_text(px, font, space, text, x, base, ink, spacing=0, halo=None, halo2=None):
    """Render text at pen x / baseline; spacing adjusts every advance. halo is
    the index of a 1 px outline drawn first: orthogonal neighbours in halo,
    diagonal-only corners in halo2 (the fan's softer corner tone)."""
    if halo is not None:
        tmp = Image.new('P', (W, H), 0)
        tp = tmp.load()
        pen = x
        for c in text:
            if c == ' ':
                pen += space + spacing; continue
            blit(tp, font, c, pen, base, 1)
            pen += glyph_adv(font, c, space) + spacing
        for yy in range(H):
            for xx in range(W):
                if tp[xx, yy]:
                    continue
                orth = any(0 <= xx + dx < W and 0 <= yy + dy < H and tp[xx + dx, yy + dy]
                           for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
                diag = any(0 <= xx + dx < W and 0 <= yy + dy < H and tp[xx + dx, yy + dy]
                           for dx, dy in ((1, 1), (1, -1), (-1, 1), (-1, -1)))
                if orth:
                    px[xx, yy] = halo
                elif diag and halo2 is not None:
                    px[xx, yy] = halo2
    pen = x
    for c in text:
        if c == ' ':
            pen += space + spacing; continue
        blit(px, font, c, pen, base, ink)
        pen += glyph_adv(font, c, space) + spacing
    return pen


def text_width(font, space, text, spacing=0):
    return sum(glyph_adv(font, c, space) + spacing for c in text) - 2 - spacing


def apply_entry(gfx, pal, spec, faces, log, entry):
    font, space = faces[spec.get('face', 'text')]
    im = image_of(gfx, pal)
    px = im.load()
    ground = palette_index(pal, spec['ground'])
    keep = {palette_index(pal, c) for c in spec.get('keep', [])}
    erase = {palette_index(pal, c) for c in spec.get('erase', [])}
    for ed in spec['edits']:
        x0, y0, x1, y1 = ed['box']
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                v = px[x, y]
                if (v in erase) if erase else (v != ground and v not in keep):
                    px[x, y] = ground
        ink = palette_index(pal, ed['ink'])
        halo = palette_index(pal, ed['halo']) if ed.get('halo') else None
        halo2 = palette_index(pal, ed['halo2']) if ed.get('halo2') else None
        spacing = ed.get('spacing', 0)
        w = text_width(font, space, ed['text'], spacing)
        x = ed['x'] if 'x' in ed else ed['cx'] - w // 2
        draw_text(px, font, space, ed['text'], x, ed['base'], ink, spacing, halo, halo2)
        log.append('entry %d: %r at x=%d base=%d, %d px wide' % (entry, ed['text'], x, ed['base'], w))
    return write_gfx(gfx, im)


def build(src, outdir):
    mf = json.load(open(MAP_FONT, encoding='utf-8'))
    faces = {'text': load_font(), 'map': (mf['font'], mf['space'])}
    data = open(src, 'rb').read()
    E = table(data)
    repl, log = {}, []
    os.makedirs(outdir, exist_ok=True)
    for entry, spec in sorted(EDITS.items()):
        gfx, palb = E[entry], E[entry + 1]
        assert gfx[:4] == b'RGCN' and palb[:4] == b'RLCN', entry
        pal = nclr(palb)
        repl[entry] = apply_entry(gfx, pal, spec, faces, log, entry)
        im = image_of(repl[entry], pal)
        flat = [c for rgb in pal for c in rgb]
        im.putpalette(flat + [0] * (768 - len(flat)))
        im.convert('RGB').resize((W * 3, H * 3), Image.NEAREST).save(os.path.join(outdir, 'cg_names_%03d_preview3x.png' % entry))
    new = repack(data, repl)
    out = os.path.join(outdir, 'upcut_local.bin')
    open(out, 'wb').write(new)
    return out, repl, log


if __name__ == '__main__':
    src, outdir = sys.argv[1], sys.argv[2]
    out, repl, log = build(src, outdir)
    print('\n'.join(log))
    print('graphics re-lettered: %d' % len(repl))
    if '--rom' in sys.argv:
        from title_logo import splice
        i = sys.argv.index('--rom')
        rom = splice(open(sys.argv[i + 1], 'rb').read(), 'jpn/upcut_local.bin', open(out, 'rb').read())
        open(sys.argv[i + 2], 'wb').write(rom)
        print('wrote', sys.argv[i + 2])
