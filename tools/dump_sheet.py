# -*- coding: utf-8 -*-
"""Dump an NCGR tileset as a flat tile sheet PNG (no tilemap needed)."""
import sys, os, struct
sys.path.insert(0, os.path.dirname(__file__))
from lz11 import decompress
from nitro import ncgr, nclr, tile_pixels
from render_title import entries
from PIL import Image

def sheet(path, gi, pi, cols=32, scale=2):
    e = entries(path)
    data, bpp, cnt, tw, th = ncgr(decompress(e[gi]))
    pal = nclr(decompress(e[pi])) if pi is not None else [(i, i, i) for i in range(256)]
    rows = (cnt + cols - 1) // cols
    img = Image.new('RGB', (cols*8, rows*8), (255, 0, 255))
    px = img.load()
    for t in range(cnt):
        tp = tile_pixels(data, t, bpp)
        bx, by = (t % cols)*8, (t // cols)*8
        for y in range(8):
            for x in range(8):
                c = tp[y][x]
                px[bx+x, by+y] = pal[c] if c < len(pal) else (255, 0, 255)
    return img.resize((img.width*scale, img.height*scale), Image.NEAREST), cnt, bpp

if __name__ == '__main__':
    img, cnt, bpp = sheet(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]) if sys.argv[3] != 'none' else None)
    img.save(sys.argv[4])
    print('%s: %d tiles %dbpp -> %s %s' % (os.path.basename(sys.argv[1]), cnt, bpp, sys.argv[4], img.size))
