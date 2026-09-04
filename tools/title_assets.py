# -*- coding: utf-8 -*-
"""Title-screen logo and episode titles, from the player's own Collection.

Two halves, called by build.py (title screen, episode titles, Logic keyword cards):

  extract(bdir, dumpdir)   pull the English logo sprite and the two fonts out of
                           the Collection bundles into dump/title/, next to the
                           script dumps, so --skip-extract keeps working
  apply(dumpdir, rom_path) compose the DS title picture from that logo, render
                           the five official episode names in those fonts into
                           the splash-card and episode-select sprites, and
                           splice the three rebuilt files into the ROM in place

Everything here is derived from the user's install at build time. Nothing
Capcom-owned ships with the tool.
"""
import json, io, os, struct
import extract_logo, title_logo, title_text
from lz11 import decompress
from nitro import ncgr, nclr, nscr, tile_pixels
from PIL import Image

FONTS = {
    'FOT-MODEMINALARGEPRO-B': 'gk_common_title_assets_all_',
    'FOT-UDKAKUGO_SMALLPR6-M': 'gk_common_title_assets_all_',
}
LOGO_PNG = 'GK2_Logo_R_eng.png'


def title_dir(dumpdir):
    return os.path.join(dumpdir, 'title')


def required(dumpdir):
    """Files apply() needs; build.py checks these under --skip-extract."""
    t = title_dir(dumpdir)
    return [os.path.join(t, LOGO_PNG)] + [os.path.join(t, 'fonts', n + '.otf') for n in FONTS]


def extract(bdir, dumpdir):
    t = title_dir(dumpdir)
    os.makedirs(os.path.join(t, 'fonts'), exist_ok=True)
    logo = extract_logo.extract_logo(bdir)
    logo.save(os.path.join(t, LOGO_PNG))
    cache = {}
    for name, prefix in FONTS.items():
        src = title_text.extract_font(bdir, prefix, name, cache)
        with open(src, 'rb') as f, open(os.path.join(t, 'fonts', name + '.otf'), 'wb') as g:
            g.write(f.read())
    return t


def render_fan_title_screen(title_local_path):
    """True-colour 256x192 render of the fan title_local.bin (its copyright band
    is what the composer keeps)."""
    d = open(title_local_path, 'rb').read()
    n = struct.unpack_from('<I', d, 0)[0] // 8
    offs = [struct.unpack_from('<II', d, i * 8)[0] for i in range(n)] + [len(d)]
    live = sorted(o for o in offs[:-1] if o)
    def blob(i):
        o = offs[i]; nxt = [q for q in live if q > o]; b = d[o:(nxt[0] if nxt else len(d))]
        return decompress(b) if b[:1] == b'\x11' else b
    data, bpp, cnt, _, _ = ncgr(blob(0)); pal = nclr(blob(1)); w, h, ents = nscr(blob(2))
    img = Image.new('RGB', (w, h)); px = img.load()
    for i, ent in enumerate(ents):
        tid = ent & 0x3FF; hf, vf = bool(ent & 0x400), bool(ent & 0x800)
        if tid >= cnt:
            continue
        t = tile_pixels(data, tid, bpp)
        bx, by = (i % (w // 8)) * 8, (i // (w // 8)) * 8
        for y in range(8):
            for x in range(8):
                c = t[7 - y if vf else y][7 - x if hf else x]
                px[bx + x, by + y] = pal[c] if c < len(pal) else (255, 0, 255)
    return img


def apply(dumpdir, rom_path, log=print, version=None):
    t = title_dir(dumpdir)
    fan_title = os.path.join(dumpdir, 'ds_fan', 'jpn', 'title_local.bin')
    rom = open(rom_path, 'rb').read()

    # 1) top screen: the official logo over the fan copyright band, plus the
    #    build version in the empty top-right corner (title_version's 3x5 font)
    fan_screen = render_fan_title_screen(fan_title)
    tmp_screen = os.path.join(t, 'fan_title_1x.png'); fan_screen.save(tmp_screen)
    logo = Image.open(os.path.join(t, LOGO_PNG)).convert('RGBA')
    picture, (ox, oy, lw, lh, scale) = extract_logo.compose(logo, tmp_screen)
    picture = picture.convert('RGB')
    if version:
        import title_version
        title_version.paint_marker(picture, 'v' + version)
    pic_path = os.path.join(t, 'title_screen_official_1x.png'); picture.save(pic_path)
    new_title, st = title_logo.build(pic_path, open(fan_title, 'rb').read())
    rom = title_logo.splice(rom, 'jpn/title_local.bin', new_title)
    log('title screen: official logo %dx%d at (%d,%d), %d/%d tiles, %d colours'
        % (lw, lh, ox, oy, st['unique_tiles'], st['bank_tiles'], st['colours']))

    # 2) episode splash cards + select buttons, in the Collection's fonts
    fonts = {n: os.path.join(t, 'fonts', n + '.otf') for n in FONTS}
    lines, cache, outs = [], dict(fonts), {}
    for tag, spec in title_text.SURFACES.items():
        outs[spec['file'].split('/')[-1]] = title_text.build_surface(tag, spec, None, t, cache, lines)
    for name, path in outs.items():
        rom = title_logo.splice(rom, 'jpn/' + name, open(path, 'rb').read())
    for l in lines:
        log(l.strip())

    # 3) Logic keyword cards: Capcom's short names rendered into the fan's card images
    import logic_names, logic_cards
    names, total = logic_names.keyword_names(dumpdir)
    card_bin, repl, clog = logic_cards.build(t, names)
    rom = title_logo.splice(rom, 'jpn/logic_keyword_local.bin', open(card_bin, 'rb').read())
    bad = [l for l in clog if 'DOES NOT FIT' in l]
    log('logic keyword cards: %d of %d slots named officially, %d card images rewritten%s'
        % (len(names), total, len(repl), ('; NOT FITTING: %d' % len(bad)) if bad else ''))

    # 4) choice/prompt buttons: Capcom's option text on the fan's plates
    import choice_strips
    loc_en = json.load(io.open(os.path.join(dumpdir, 'loc_en.json'), encoding='utf-8'))
    rom, st = choice_strips.apply_to_rom(rom, loc_en, fonts['FOT-UDKAKUGO_SMALLPR6-M'], log)
    log('choice strips redrawn with official text: %d (%d condensed, %d at a smaller size, %d without English)'
        % (st['drawn'], st['condensed'], st['stepped'], st['skipped']))

    # 5) close-up text screens (reports, letters, notes): Capcom's rows rendered
    #    in the fan's own pixel face into the full-screen images. Stored as
    #    literals, so the container grows ~2 MB; accepted (2026-09-04).
    import txtcut, cg_names
    cut_bin, repl, tlog = txtcut.build(t)
    over = [l for l in tlog if 'OVERFLOW' in l]
    squeezed = sum(1 for l in tlog if any(k in l for k in ('gap', 'pitch', 'top')))
    log('close-up text screens rewritten with official text: %d (%d at tighter spacing%s)'
        % (len(repl), squeezed, ('; OVERFLOWING: %d' % len(over)) if over else ''))

    # 6) the room map and the two log tables: fan character names re-lettered
    #    in place with the official ones, on the container txtcut just wrote
    names_bin, nrepl, nlog = cg_names.build(cut_bin, t)
    rom = title_logo.splice(rom, 'jpn/upcut_local.bin', open(names_bin, 'rb').read())
    log('close-up graphics re-lettered with official names: %d' % len(nrepl))

    open(rom_path, 'wb').write(rom)
    return rom_path
