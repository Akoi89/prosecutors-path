# -*- coding: utf-8 -*-
"""Render the official episode titles into the DS title sprites, using the fonts
the Collection itself ships.

Two surfaces, both OAM cell banks (see ncer.py / title_art.py):

  splash card    jpn/opening_local.bin  cell entry 2, cells 0-4, tiles entry 0, pal 1
                 title line = the sprites on the cell's lower row (a 208x16 band)
  select button  jpn/save_local.bin     cell entry 1, cells 14-18, tiles entry 2, pal 3
                 title = the ten small sprites; the six 32x64 frame sprites are shared
                 with every other button and are never touched

Nothing is drawn outside the sprites the game already draws, so the OAM is left
alone: the new text is painted into the tiles those sprites point at. Any ink
that would fall outside them is counted and reported, and the font size steps
down until nothing is lost.

Fonts come out of the player's own Collection at build time (Unity Font assets
carry the OTF): Mode Mina B for the splash serif, UD Kakugo M for the buttons.
Nothing Capcom-owned ships with the tool.

    python tools/title_text.py BUNDLE_DIR OUTDIR [--rom in.nds out.nds]

Writes OUTDIR/opening_local.bin and OUTDIR/save_local.bin (+ preview PNGs), and
with --rom splices both into a copy of the ROM.
"""
import sys, os, glob, struct, tempfile
sys.path.insert(0, os.path.dirname(__file__))
from lz11 import decompress
from nitro import ncgr
from ncer import ncer
from title_art import entries, dec, palette, cell_indices, BOUNDARY
from title_version import _store
from episode_titles import OFFICIAL
from PIL import Image, ImageDraw, ImageFont

FAN_TITLES = ['Turnabout Target', 'The Imprisoned Turnabout', 'The Inherited Turnabout',
              'The Forgotten Turnabout', 'The Grand Turnabout']

SURFACES = {
    # tag: (file, cell entry, tile entry, pal entry, cell ids, font asset, bundle prefix, start px, style)
    'splash': dict(file='dump/ds_fan/jpn/opening_local.bin', ci=2, gi=0, pi=1, ids=[0, 1, 2, 3, 4],
                   font='FOT-MODEMINALARGEPRO-B', bundle='gk_common_title_assets_all_', px=13,
                   align='right', outline=False, bold=True, regrid=False, tracking=0),
    'button': dict(file='dump/ds_fan/jpn/save_local.bin', ci=1, gi=2, pi=3, ids=[14, 15, 16, 17, 18],
                   font='FOT-UDKAKUGO_SMALLPR6-M', bundle='gk_common_title_assets_all_', px=15,
                   align='center', outline=False, bold=False, regrid=True),
}
# shared frame tiles in the button cells (32x64 sprites) - never repainted
FRAME_MIN_SIZE = (32, 64)


# ---------------------------------------------------------------- fonts

def extract_font(bundle_dir, bundle_prefix, name, cache):
    if name in cache:
        return cache[name]
    import UnityPy
    hits = [p for p in glob.glob(os.path.join(bundle_dir, '*.bundle'))
            if os.path.basename(p).startswith(bundle_prefix)]
    if not hits:
        raise SystemExit('no bundle starting with %r in %s' % (bundle_prefix, bundle_dir))
    env = UnityPy.load(hits[0])
    for o in env.objects:
        if o.type.name == 'Font':
            d = o.read()
            if d.m_Name == name:
                data = bytes(d.m_FontData)
                path = os.path.join(tempfile.gettempdir(), 'gk2port_%s.otf' % name)
                open(path, 'wb').write(data)
                cache[name] = path
                return path
    raise SystemExit('font %s not found in %s' % (name, os.path.basename(hits[0])))


# ---------------------------------------------------------------- painting

def text_sprites(objs, tag):
    """The sprites that carry this cell's TITLE text.
    splash: only the lower row (the upper row is 'Episode N' and is kept).
    button: everything but the shared 32x64 frame sprites."""
    small = [o for o in objs if o['h'] < FRAME_MIN_SIZE[1]]
    if tag == 'splash':
        ymax = max(o['y'] for o in small)
        return [o for o in small if o['y'] == ymax]
    return [o for o in small if (o['w'], o['h']) == (32, 16) or 8 <= o['x'] < 168]


def main_band(txt, origin, tag):
    """The rectangle the text is laid out in: for buttons the row of 32x16 sprites
    (the 32x8 pieces are extra coverage for descenders, not layout); for the
    splash the whole title row."""
    core = [o for o in txt if o['h'] == 16] if tag == 'button' else txt
    x0, y0 = origin
    return (min(o['x'] for o in core) - x0, min(o['y'] for o in core) - y0,
            max(o['x'] + o['w'] for o in core) - x0 - 1, max(o['y'] + o['h'] for o in core) - y0 - 1)


def coverage(objs, origin, size):
    """Boolean canvas (cell coords) of pixels some text sprite can represent."""
    W, H = size
    cov = [[False] * W for _ in range(H)]
    x0, y0 = origin
    for o in objs:
        for yy in range(o['h']):
            Y = o['y'] - y0 + yy
            if not 0 <= Y < H:
                continue
            for xx in range(o['w']):
                X = o['x'] - x0 + xx
                if 0 <= X < W:
                    cov[Y][X] = True
    return cov


def oam_offsets(recn, cid):
    """Byte offsets (inside the decompressed RECN blob) of each OAM entry of cell cid."""
    from ncer import _sections as _sec
    n = struct.unpack_from('<H', recn, 14)[0]
    p = 16
    for _ in range(n):
        magic = recn[p:p + 4]; size = struct.unpack_from('<I', recn, p + 4)[0]
        if magic == b'KBEC':
            body = p + 8
            n_cells, attr = struct.unpack_from('<HH', recn, body)
            cell_off = struct.unpack_from('<I', recn, body + 4)[0]
            rec = 16 if (attr & 1) else 8
            base = body + cell_off
            oam_base = base + n_cells * rec
            q = base + cid * rec
            n_oam = struct.unpack_from('<H', recn, q)[0]
            off = struct.unpack_from('<I', recn, q + 4)[0]
            return [oam_base + off + j * 6 for j in range(n_oam)]
        p += size
    raise ValueError('no KBEC section')


def replace_button_layout(recn, cid, objs):
    """Shift the five 32x16 text sprites of a button cell up by two rows (y 19->17)
    so a face with descenders fits inside them. Nothing else moves: the 32x8
    pieces at the panel edges also carry border pixels and stay put."""
    offs = oam_offsets(recn, cid)
    big = [(j, o) for j, o in enumerate(objs) if (o['w'], o['h']) == (32, 16)]
    if len(big) != 5:
        raise ValueError('button cell %d: expected 5 text sprites of 32x16' % cid)
    return


def park_descender_pieces(recn, cid, objs, txt, img, place, origin, band):
    """Move the mid-panel 32x8 pieces to y = band bottom + 1, under the columns
    where `img` (placed at `place`) has ink below the band. Returns False if the
    descenders need more than the two pieces can cover."""
    pieces = [o for o in txt if (o['w'], o['h']) == (32, 8)]
    if not pieces:
        return True
    px = img.load()
    cols = sorted({place[0] + xx for yy in range(img.height) for xx in range(img.width)
                   if place[1] + yy > band[3] and px[xx, yy][3] >= 96})
    clusters = []
    for c in cols:
        if clusters and c - clusters[-1][1] <= 6:
            clusters[-1][1] = c
        else:
            clusters.append([c, c])
    if len(clusters) > len(pieces) or any(c1 - c0 + 1 > 32 for c0, c1 in clusters):
        return False
    offs = oam_offsets(recn, cid)
    idx = {id(o): j for j, o in enumerate(objs)}
    for k, o in enumerate(pieces):
        if k < len(clusters):
            c0, c1 = clusters[k]
            x_cell = max(band[0], min(c0 - (32 - (c1 - c0 + 1)) // 2, band[2] - 31))
        else:
            x_cell = band[0] + 32 * k           # unused piece: park it inside the band, blank
        _place(recn, offs[idx[id(o)]], o, x_cell + origin[0], band[3] + 1 + origin[1])
    return True


def _place(recn, off, o, x, y):
    a0, a1 = struct.unpack_from('<HH', recn, off)
    a0 = (a0 & ~0xFF) | (y & 0xFF)
    a1 = (a1 & ~0x1FF) | (x & 0x1FF)
    struct.pack_into('<HH', recn, off, a0, a1)
    o['x'], o['y'] = x, y


def band_of(cov):
    """Bounding box of the covered area: (x0, y0, x1, y1) inclusive."""
    ys = [y for y, r in enumerate(cov) if any(r)]
    xs = [x for x in range(len(cov[0])) if any(cov[y][x] for y in ys)]
    return min(xs), min(ys), max(xs), max(ys)


def render_text(text, fontfile, px, fill, outline, bold=False, tracking=0):
    """Render `text` to RGBA. `tracking` adds that many pixels between glyphs
    (negative tightens; the fan's hand lettering sits tighter than the font's
    default advances)."""
    f = ImageFont.truetype(fontfile, px)
    bb = f.getbbox(text)
    pad = 2
    extra = tracking * max(0, len(text) - 1)
    im = Image.new('RGBA', (bb[2] - bb[0] + 2 * pad + max(0, extra), bb[3] - bb[1] + 2 * pad), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    ox, oy = pad - bb[0], pad - bb[1]

    def draw(dx, dy, colour):
        if tracking == 0:
            d.text((ox + dx, oy + dy), text, font=f, fill=colour)
            return
        x = ox + dx
        for ch in text:
            d.text((x, oy + dy), ch, font=f, fill=colour)
            x += f.getlength(ch) + tracking

    if outline:
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx or dy:
                    draw(dx, dy, outline)
    draw(0, 0, fill)
    if bold:
        draw(1, 0, fill)
    bb = im.getchannel('A').getbbox()          # crop to the ink so placement uses real bounds
    return im.crop(bb) if bb else im


def nearest_index(rgb, pal, allowed):
    r, g, b = rgb
    best, bd = None, 1e9
    for i in allowed:
        pr, pg, pb = pal[i]
        d = (pr - r) ** 2 + (pg - g) ** 2 + (pb - b) ** 2
        if d < bd:
            best, bd = i, d
    return best


def paint_cell(rows, cov, text_img, place, pal, allowed, base=(0, 0, 0)):
    """Composite text_img (RGBA) at `place` into the index canvas `rows`, only where
    covered. Edge pixels are blended over `base` (the colour the cleared sprite
    shows) by their alpha and then snapped to the nearest palette entry the fan
    text used, so the anti-aliasing comes out in the same grey steps as the
    fan's own lettering instead of a hard threshold. Returns the number of ink
    pixels that fell outside coverage."""
    H, W = len(rows), len(rows[0])
    px = text_img.load()
    lost = 0
    for yy in range(text_img.height):
        for xx in range(text_img.width):
            r, g, b, a = px[xx, yy]
            if a < 24:
                continue
            X, Y = place[0] + xx, place[1] + yy
            if not (0 <= X < W and 0 <= Y < H) or not cov[Y][X]:
                if a >= 96:
                    lost += 1
                continue
            k = a / 255.0
            rgb = tuple(int(round(c * k + bc * (1 - k))) for c, bc in zip((r, g, b), base))
            idx = nearest_index(rgb, pal, allowed)
            # a faint edge that snaps back to the base colour stays transparent
            if pal[idx] == tuple(base) and a < 128:
                continue
            rows[Y][X] = idx
    return lost


def scrub_edge_pieces(tiles, objs, bg, bpp):
    """The 32x8 edge pieces (x<8 / x>=168) are opaque boxes that redraw the panel
    border where they overlap it, and their innermost columns hold the fan's
    anti-aliased letter edges. Fill just those inner columns with the panel
    colour; the border bar sits further out and is left alone."""
    per = 64 if bpp == 8 else 32
    for o in objs:
        if (o['w'], o['h']) != (32, 8) or 8 <= o['x'] < 168:
            continue
        cols = range(28, 32) if o['x'] < 8 else range(0, 4)      # sprite-local columns
        start = o['tile'] * BOUNDARY
        for tx in range(4):
            off = (start + tx) * per
            blk = bytearray(tiles[off:off + per])
            for yy in range(8):
                for xx in range(8):
                    if (tx * 8 + xx) not in cols:
                        continue
                    i = yy * 4 + xx // 2
                    if xx & 1:
                        blk[i] = (blk[i] & 0x0F) | ((bg & 0xF) << 4)
                    else:
                        blk[i] = (blk[i] & 0xF0) | (bg & 0xF)
            tiles[off:off + per] = blk


def write_sprites(tiles, objs, rows, origin, bpp):
    """Write the index canvas back into the tiles of the given sprites (4bpp)."""
    per = 64 if bpp == 8 else 32
    x0, y0 = origin
    for o in objs:
        tw, th = o['w'] // 8, o['h'] // 8
        start = o['tile'] * BOUNDARY
        for ty in range(th):
            for tx in range(tw):
                off = (start + ty * tw + tx) * per
                blk = bytearray(per)
                for yy in range(8):
                    for xx in range(8):
                        sx, sy = tx * 8 + xx, ty * 8 + yy
                        if o['hflip']:
                            sx = tw * 8 - 1 - sx
                        if o['vflip']:
                            sy = th * 8 - 1 - sy
                        X, Y = o['x'] - x0 + sx, o['y'] - y0 + sy
                        v = rows[Y][X] if (0 <= Y < len(rows) and 0 <= X < len(rows[0])) else 0
                        c = v % 16 if bpp == 4 else v
                        if bpp == 4:
                            i = yy * 4 + xx // 2
                            blk[i] |= (c << 4) if (xx & 1) else c
                        else:
                            blk[yy * 8 + xx] = c
                tiles[off:off + per] = blk


# ---------------------------------------------------------------- container

def repack(data, repl):
    """Rebuild an 8-byte-table container. Zero slots may sit anywhere; each real
    entry is re-stored the way the original stored it (LZ11 -> stored-literal)."""
    n = struct.unpack_from('<I', data, 0)[0] // 8
    slots = [struct.unpack_from('<II', data, i * 8) for i in range(n)]
    live = sorted(o for o, s in slots if o)
    table = bytearray(n * 8)
    body = bytearray()
    for i, (o, s) in enumerate(slots):
        if o == 0:
            struct.pack_into('<II', table, i * 8, 0, s)
            continue
        nxt = [q for q in live if q > o]
        end = nxt[0] if nxt else len(data)
        raw = data[o:end]
        was_lz = raw[:1] == b'\x11' and bool(s & 0x80000000)
        if i in repl:
            if was_lz:
                stored, size, comp = _store(repl[i]), len(repl[i]), 0x80000000
            else:
                stored, size, comp = repl[i], len(repl[i]), 0
        else:
            stored, size, comp = raw, s & 0x7FFFFFFF, s & 0x80000000
        while (n * 8 + len(body)) % 4:
            body += b'\x00'
        struct.pack_into('<II', table, i * 8, n * 8 + len(body), size | comp)
        body += stored
    return bytes(table) + bytes(body)


# ---------------------------------------------------------------- main

def build_surface(tag, spec, bundle_dir, outdir, fontcache, log):
    data = open(spec['file'], 'rb').read()
    e = entries(spec['file'])
    recn = bytearray(dec(e[spec['ci']]))
    cells, _ = ncer(bytes(recn))
    tiles_b, bpp, cnt, _, _ = ncgr(dec(e[spec['gi']]))
    tiles = bytearray(tiles_b)
    pal = palette(e[spec['pi']])
    fontfile = extract_font(bundle_dir, spec['bundle'], spec['font'], fontcache)
    previews = []
    uniform = None
    for _pass in ('measure', 'paint'):
      sizes = []
      previews = []
      for n, cid in enumerate(spec['ids']):
          objs = cells[cid]
          if spec.get('regrid') and _pass == 'measure':
              replace_button_layout(recn, cid, objs)
          rows, origin = cell_indices(objs, tiles, bpp)
          size = (len(rows[0]), len(rows))
          txt = text_sprites(objs, tag)
          cov = coverage(txt, origin, size)
          bx0, by0, bx1, by1 = main_band(txt, origin, tag)
          # palette indices the fan text actually used inside these sprites
          allowed = sorted({rows[y][x] for y in range(size[1]) for x in range(size[0]) if cov[y][x] and rows[y][x]})
          # the ink colour = the most common allowed index; outline = darkest allowed
          def lum(i): return sum(pal[i])
          ink_rgb = pal[max(allowed, key=lum)] if tag == 'splash' else pal[min(allowed, key=lum)]
          out_rgb = pal[min(allowed, key=lum)] if spec['outline'] else None
          title = OFFICIAL[FAN_TITLES[n]]
            # fill index: whatever the fan filled these sprites with most (opaque pink on
          # the buttons, which hides junk in the shared frame tiles behind them)
          from collections import Counter
          bg = Counter(rows[y][x] for y in range(size[1]) for x in range(size[0]) if cov[y][x]).most_common(1)[0][0]
          # clear the text sprites' area to that fill
          for y in range(size[1]):
              for x in range(size[0]):
                  if cov[y][x]:
                      rows[y][x] = 0
          px = uniform if uniform else spec['px']
          while True:
              img = render_text(title, fontfile, px, ink_rgb + (255,), (out_rgb + (255,)) if out_rgb else None,
                                bold=spec.get('bold', False), tracking=spec.get('tracking', 0))
              band_w, band_h = bx1 - bx0 + 1, by1 - by0 + 1
              if img.width > band_w:
                  img = img.resize((band_w, img.height), Image.LANCZOS)   # condense, as the fan did
              if spec['align'] == 'right':
                  place = (bx1 + 1 - img.width, by0 + max(0, (band_h - img.height) // 2))
              else:
                  place = (bx0 + (band_w - img.width) // 2, by0)
              if spec.get('regrid'):
                  ok = park_descender_pieces(recn, cid, objs, txt, img, place, origin, (bx0, by0, bx1, by1))
                  cov = coverage(txt, origin, size)
                  for y in range(size[1]):
                      for x in range(size[0]):
                          if cov[y][x]:
                              rows[y][x] = bg
                  if not ok:
                      px -= 1
                      continue
              trial = [r[:] for r in rows]
              lost = paint_cell(trial, cov, img, place, pal, allowed,
                                base=(0, 0, 0) if tag == 'splash' else pal[bg])
              if lost == 0 or px <= 11:
                  rows = trial
                  break
              px -= 1
          sizes.append(px)
          if _pass == 'paint':
              log.append('  %s ep%d %-24s font %dpx at %s  lost=%d' % (tag, n + 1, title, px, place, lost))
              write_sprites(tiles, txt, rows, origin, bpp)
              if tag == 'button':
                  scrub_edge_pieces(tiles, objs, bg, bpp)
          # preview
          pv = Image.new('RGB', size, (0, 0, 0) if tag == 'splash' else (250, 235, 232))
          pp = pv.load()
          for y in range(size[1]):
              for x in range(size[0]):
                  v = rows[y][x]
                  if v:
                      pp[x, y] = pal[v]
          previews.append(pv)
      uniform = min(sizes)
    # rebuild the NCGR blob with the new tile data, then the container
    gfx = bytearray(dec(e[spec['gi']]))
    doff = struct.unpack_from('<I', gfx, 0x18 + 20)[0]
    dsize = struct.unpack_from('<I', gfx, 0x18 + 16)[0]
    gfx[0x18 + doff:0x18 + doff + dsize] = tiles[:dsize]
    repl = {spec['gi']: bytes(gfx)}
    if spec.get('regrid'):
        repl[spec['ci']] = bytes(recn)
    new = repack(data, repl)
    out = os.path.join(outdir, os.path.basename(spec['file']))
    open(out, 'wb').write(new)
    W = max(p.width for p in previews); H = sum(p.height + 4 for p in previews)
    sheet = Image.new('RGB', (W, H), (90, 90, 90)); y = 0
    for p in previews:
        sheet.paste(p, (0, y)); y += p.height + 4
    sheet.resize((W * 3, H * 3), Image.NEAREST).save(os.path.join(outdir, '%s_preview3x.png' % tag))
    return out


def main():
    bundle_dir, outdir = sys.argv[1], sys.argv[2]
    os.makedirs(outdir, exist_ok=True)
    log, cache, outs = [], {}, {}
    for tag, spec in SURFACES.items():
        outs[spec['file'].split('/')[-1]] = build_surface(tag, spec, bundle_dir, outdir, cache, log)
    print('\n'.join(log))
    if '--rom' in sys.argv:
        from title_logo import splice
        i = sys.argv.index('--rom')
        rom = open(sys.argv[i + 1], 'rb').read()
        for name, path in outs.items():
            rom = splice(rom, 'jpn/' + name, open(path, 'rb').read())
        open(sys.argv[i + 2], 'wb').write(rom)
        print('wrote %s (%.2f MB)' % (sys.argv[i + 2], len(rom) / 1e6))


if __name__ == '__main__':
    main()
