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
    import cg_art, mindchess, opening_card, idcom_icons, bigg_ground, marker_letters, item_pics, gallery_art, props, props_bust
    t = title_dir(dumpdir)
    return ([os.path.join(t, LOGO_PNG)] + [os.path.join(t, 'fonts', n + '.otf') for n in FONTS]
            + cg_art.required(dumpdir) + mindchess.required(dumpdir) + opening_card.required(dumpdir)
            + idcom_icons.required(dumpdir) + bigg_ground.required(dumpdir) + marker_letters.required(dumpdir)
            + item_pics.required(dumpdir) + gallery_art.required(dumpdir) + props.required(dumpdir)
            + props_bust.required(dumpdir))


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
    import cg_art
    cg_art.extract(bdir, dumpdir)
    import mindchess
    mindchess.extract(bdir, dumpdir)
    import opening_card
    opening_card.extract(bdir, dumpdir)
    import idcom_icons
    idcom_icons.extract(bdir, dumpdir)
    import bigg_ground
    bigg_ground.extract(bdir, dumpdir)
    import marker_letters
    marker_letters.extract(bdir, dumpdir)
    import item_pics
    item_pics.extract(bdir, dumpdir)
    import gallery_art
    gallery_art.extract(bdir, dumpdir)
    import props
    props.extract(bdir, dumpdir)
    import props_bust
    props_bust.extract(bdir, dumpdir)
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


def apply(dumpdir, rom_path, log=print, version=None, any_rom=False):
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

    # 2b) the cake-show logo card in the same file (jpn/opening_local.bin entries 13/14):
    #     Capcom's English logo from the Collection over the fan's card, in the card's
    #     palette, hash-guarded (see tools/opening_card.py); after the splash card above,
    #     which rewrites entry 0 of the same file
    import opening_card
    rom, op_changed = opening_card.apply_to_rom(rom, dumpdir, log, any_rom)
    if not op_changed:
        log('opening card: not redrawn (see reason above)')

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

    # 4b) the Mind (Logic) Chess banner: "Mind"/"Checkmate" in Capcom's own
    #     letters over the fan's cell/animation, the name row re-centred with
    #     "Chess" moved a few px so the two words sit like the fan's (idlocal
    #     entry 25; required() makes a --skip-extract build stop if the
    #     harvested letters are missing)
    import mindchess
    rom, changed = mindchess.apply_to_rom(rom, dumpdir, log)
    if not changed:
        log('Mind Chess banner: not redrawn (see reason above)')

    # 4c) the Mind Chess wait button's label ("Wait and see." -> "Bide my time"):
    #     the shared 80x16 text area of idlocal entry 673, hash-guarded, in
    #     the game's small face, the one the fan's label uses (see tools/mc_wait.py)
    import mc_wait
    rom, changed = mc_wait.apply_to_rom(rom, dumpdir, log)
    if not changed:
        log('Mind Chess wait button: not redrawn (see reason above)')

    # 4d) the cake-show room names drawn into the map pieces: Capcom's Gusto's /
    #     Scone's / Tangaroa's / Frost's over the fan's Gustavia's / Delicia's /
    #     Master's / Dover's, in the fan's own lettering (jpn/cutobj_local.bin entry
    #     10; jpn/idlocal.bin entries 321, 324, 327; see tools/room_names.py)
    import room_names
    rom, changed = room_names.apply_to_rom(rom, dumpdir, log, any_rom)
    if not changed:
        log('room names: not redrawn (see reason above)')

    # 5) close-up text screens (reports, letters, notes): Capcom's rows rendered
    #    in the fan's own pixel face into the full-screen images. Stored as
    #    literals, so the container grows ~2 MB; accepted (2026-09-04).
    import txtcut, cg_names
    cut_bin, repl, tlog, cnd_applied, cnd_fallback = txtcut.build(t)
    over = [l for l in tlog if 'OVERFLOW' in l]
    squeezed = sum(1 for l in tlog if any(k in l for k in ('gap', 'pitch', 'top')))
    log('close-up text screens rewritten with official text: %d (%d at tighter spacing%s)'
        % (len(repl), squeezed, ('; OVERFLOWING: %d' % len(over)) if over else ''))
    log('close-up rows reformatted from Capcom\'s row (hash-guarded): %d  (fallback: %d)'
        % (cnd_applied, cnd_fallback))

    # 6) the room map and the two log tables: fan character names re-lettered
    #    in place with the official ones, on the container txtcut just wrote
    names_bin, nrepl, nlog = cg_names.build(cut_bin, t)
    log('close-up graphics re-lettered with official names: %d' % len(nrepl))

    # 7) the six close-up ARTWORKS with lettering baked in (briefing diagrams,
    #    cake placards, TV logo and its 60 zoom frames, movie poster, magazine):
    #    finished pictures shipped in tools/cg_art_final/ (prepared outside the
    #    build from Capcom's Collection pictures), the zoom frames derived from
    #    the TV master; each picture is re-quantised with a new palette
    import cg_art
    art_bin, arepl, alog = cg_art.build(names_bin, dumpdir, t)
    rom = title_logo.splice(rom, 'jpn/upcut_local.bin', open(art_bin, 'rb').read())
    log('close-up artwork with official names: %d shipped pictures, %d TV zoom frames derived'
        % (sum(1 for e in arepl if e in cg_art.FINAL), sum(1 for e in arepl if e in cg_art.TV_FRAMES)))

    # 7b) the plan paper inside the bag model (jpn/modelitemlocal.bin entry 1, texture
    #     bag_01): the same picture as artwork 8, squashed onto a 3D paper, redrawn
    #     with the shipped picture's names in the changed texels only, in the
    #     texture's own palette (see tools/bag_tex.py)
    import bag_tex
    rom, bag_changed = bag_tex.apply_to_rom(rom, dumpdir, log, any_rom)
    if not bag_changed:
        log('bag texture: not redrawn (see reason above)')

    # 7c) the business card and the victim's letter evidence icons (com/idcom.bin entries
    #     281, 573, 575): Capcom's English item textures registered onto the fan icon's
    #     framing, downscaled and quantised into the fan's own entries, written in place
    #     (see tools/idcom_icons.py)
    import idcom_icons
    rom, icons_changed = idcom_icons.apply_to_rom(rom, dumpdir, log, any_rom)
    if not icons_changed:
        log('evidence icons: not redrawn (see reason above)')

    # 7d) the tower's name on the pictures the fan lettered "Grand Tower": Capcom's "Bigg Building" on
    #     the city map (jpn/upcut_local.bin 264, 280), the cross-section titles (upcut_local 208, 244,
    #     246, 278, 282; jpn/cutobj_local.bin 26) and the place cards (jpn/idlocal.bin 328, 331, 334,
    #     337, 340, 343), in the fan's own faces; after room_names (4d), which cuts letters from idlocal
    #     340, and after the last step that writes upcut_local (see tools/bigg_building.py)
    import bigg_building
    rom, bigg_changed = bigg_building.apply_to_rom(rom, dumpdir, log, any_rom)
    if not bigg_changed:
        log('bigg building: not redrawn (see reason above)')

    # 7e) the letters in the round character markers of the floor plans and maps (jpn/cutobj_local.bin):
    #     where the fan's marker carries the initial of its own name and Capcom's picture of the same
    #     marker carries another, Capcom's letter, in the sprite's own face (see tools/marker_letters.py);
    #     after 7d, which changes entry 26
    import marker_letters
    rom, markers_changed = marker_letters.apply_to_rom(rom, dumpdir, log, any_rom)
    if not markers_changed:
        log('marker letters: not redrawn (see reason above)')

    # 7f) Capcom's wording on the other labels of the city map (jpn/upcut_local.bin 264, 280), the room
    #     label of the cross-section pictures (upcut_local 244, 246, 278) and the 50th floor place strip
    #     (jpn/idlocal.bin 328), in the fan's faces; after 7d (see tools/city_labels.py)
    import city_labels
    rom, labels_changed = city_labels.apply_to_rom(rom, dumpdir, log, any_rom)
    if not labels_changed:
        log('city labels: not redrawn (see reason above)')

    # 7g) the map pieces and floor plans in Capcom's wording (Corridor, Workshop, Maximum Security, Yard,
    #     Wing, Fountain Room; the office of room 1202 that the fan left in Japanese), in the fan's own
    #     lettering (jpn/idlocal.bin 282-327, 349; jpn/cutobj_local.bin 12; see tools/plan_labels.py). After
    #     the room names (4d), whose 321, 324 and 327 it letters over, and after 7d: the Bigg Building step
    #     cuts its B from the fan's idlocal 294 and requires that entry to be unchanged in the ROM it builds
    import plan_labels
    rom, changed = plan_labels.apply_to_rom(rom, dumpdir, log, any_rom)
    if not changed:
        log('map pieces and plans: not redrawn (see reason above)')

    # 7h) the plans in Capcom's wording, in the fan's own lettering (jpn/upcut_local.bin 36, 40, 48, 52,
    #     78, 80, 82: the prison and the detention center; 102: the Zodiac Hall plan; 114: the Zodiac
    #     Hall leaflet, swapped whole from Capcom's picture; 116: the information board's temperatures);
    #     after the last step that writes upcut_local; its entries are its own (see tools/plan_labels.py)
    import plan_labels
    rom, plans_changed = plan_labels.apply_upcut_to_rom(rom, dumpdir, log, any_rom)
    if not plans_changed:
        log('plans: not redrawn (see reason above)')

    # 7i) item pictures with the fan's wording where Capcom's differs (tools/item_pics.py): small in-place
    #     re-letterings in jpn/upcut_local.bin, com/idcom.bin and com/logic_keyword.bin; after the last
    #     step that writes upcut_local, after the icon swaps above and after 7d-7h (which change other entries
    #     of the same files; no step reads an entry another one writes)
    import item_pics
    rom, items_changed = item_pics.apply_to_rom(rom, dumpdir, log, any_rom)
    if not items_changed:
        log('item pictures: not redrawn (see reason above)')

    # 7j) the partner card's "Change Re-creation" button: Capcom's "Switch re-creations" in the fan's face
    #     (jpn/idlocal.bin entry 357, cells 10 and 11; see tools/menu_button.py); after every other idlocal writer
    import menu_button
    rom, button_changed = menu_button.apply_to_rom(rom, dumpdir, log, any_rom)
    if not button_changed:
        log('menu button: not redrawn (see reason above)')

    # 7k) signs and props painted into the backgrounds (com/mapbg.bin, com/logicbg.bin, com/upcut.bin,
    #     jpn/upcut_local.bin):
    #     the fan's wording replaced by Capcom's, from the Collection's own pictures of the same
    #     backgrounds, written in place (see tools/props.py); its entries are its own (jpn/upcut_local.bin 42,
    #     206, 234: none another step writes or reads)
    import props
    rom, _signs = props.apply_to_rom(rom, dumpdir, log, any_rom)
    # 7l) the nurse's cap (com/bustup.bin 252-255, 264, and her portrait icons com/idcom.bin 951, 953):
    #     Capcom's SAFETY [pill] FIRST from the Collection's atlases, in every cell (see tools/props_bust.py);
    #     after every step that writes com/idcom.bin (7c, 7i: the item icons may lay it out again), since it
    #     writes 951 and 953 in place through the file's own table
    import props_bust
    rom, _cap = props_bust.apply_to_rom(rom, dumpdir, log, any_rom)

    # 8) hotfix: the Coroner's Findings "point at the burn mark" prompt (com/cutdata.bin
    #    slot 47, cut 208) - derive its hit-area rectangles from txtcut's own layout of
    #    the re-wrapped document instead of the JP-retail box our lettering no longer
    #    lines up with. Hash-guarded; see tools/cutdata_hotfix.py.
    import cutdata_hotfix
    rom, hotfix_applied = cutdata_hotfix.apply_to_rom(rom, dumpdir, log)
    if not hotfix_applied:
        log('cutdata hotfix: not applied (see reason above)')

    open(rom_path, 'wb').write(rom)
    return rom_path
