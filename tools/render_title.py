# -*- coding: utf-8 -*-
"""Render a title_local.bin screen (NCGR + NCLR + NSCR) to PNG."""
import sys, os, struct
sys.path.insert(0, os.path.dirname(__file__))
from lz11 import decompress
from nitro import ncgr, nclr, nscr, tile_pixels
from PIL import Image

def entries(path):
    d = open(path, 'rb').read()
    n = struct.unpack_from('<I', d, 0)[0] // 8
    offs = [struct.unpack_from('<II', d, i*8)[0] for i in range(n)] + [len(d)]
    return [d[offs[i]:offs[i+1]] for i in range(n)]

def render(path, gi=0, pi=1, si=2):
    e = entries(path)
    data, bpp, cnt, tw, th = ncgr(decompress(e[gi]))
    pal = nclr(decompress(e[pi]))
    w, h, ents = nscr(decompress(e[si]))
    img = Image.new('RGB', (w, h))
    px = img.load()
    for i, ent in enumerate(ents):
        tid = ent & 0x3FF
        hf, vf = bool(ent & 0x400), bool(ent & 0x800)
        pnum = ent >> 12
        if tid >= cnt: continue
        t = tile_pixels(data, tid, bpp)
        bx, by = (i % (w // 8)) * 8, (i // (w // 8)) * 8
        for y in range(8):
            for x in range(8):
                c = t[7-y if vf else y][7-x if hf else x]
                idx = c + (pnum * 16 if bpp == 4 else 0)
                px[bx+x, by+y] = pal[idx] if idx < len(pal) else (255, 0, 255)
    return img

if __name__ == '__main__':
    img = render(sys.argv[1])
    img = img.resize((img.width*2, img.height*2), Image.NEAREST)
    img.save(sys.argv[2])
    print('wrote', sys.argv[2], img.size)
