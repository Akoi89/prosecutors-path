# -*- coding: utf-8 -*-
"""Offline registration of the Collection's close-up textures onto the fan's upcut_local pictures
(tools/item_pics.py, UPCUT_SWAPS).

A DS picture is 256 x 192 (or 256 x 384); Capcom's texture is 1920 wide. For a picture whose scene Capcom
kept (a ticket on a grey ground) the DS picture is a rectangle of the texture: texel = offset + scale *
picture pixel, a scale and offset per axis. The fit is made against the JAPANESE twin of the English texture
(the art the fan's picture was drawn from; its lettering is the fan's, so the letters must not steer it) by
the overlap (intersection over union) of the object's silhouette, the pixels that are not the flat grey
ground, which does not care what is written on the object.

The result goes to tools/item_pics_reg.json: {"200": {"reg": [sx, sy, ox, oy], "iou": ...,
"texture": "...", "jp": "..."}, ...}. A development tool run once (needs scipy, which the built tool does not
bundle); the build only reads the json.

    python tools/item_pics_register.py DUMPDIR [--write] [--check] [--only 200,202]
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image
import item_pics as P


def picture_mask(entry, dumpdir, spec):
    """The fan's picture's object: pixels that are not its ground colour (the picture's most common colour)."""
    import choice_strips as cs
    from nitro import nclr
    d = open(os.path.join(dumpdir, 'ds_fan', 'jpn', 'upcut_local.bin'), 'rb').read()
    idl = cs.Idlocal(d)
    grid = P.pic_grid(P._content(idl, entry))
    pal = np.array(nclr(P._content(idl, entry + 1)), int)
    rgb = pal[grid]
    if spec.get('paper'):
        return (rgb @ np.array((0.299, 0.587, 0.114)) > spec['paper']).astype(np.float64)
    flat = rgb.reshape(-1, 3)
    vals, cnt = np.unique(flat, axis=0, return_counts=True)
    ground = vals[cnt.argmax()]
    return (np.abs(rgb - ground).sum(2) > 6).astype(np.float64)


def texture_mask(tex, spec=None):
    if spec is not None and spec.get('paper'):
        return (np.asarray(tex, np.float64) @ np.array((0.299, 0.587, 0.114)) > spec['paper']).astype(np.float64)
    return (np.abs(np.asarray(tex, np.float64) - float(P.GROUND)).sum(2) > 30).astype(np.float64)


def iou(fm, tmim, tshape, reg, w, h):
    sx, sy, ox, oy = reg
    box = (ox, oy, ox + sx * w, oy + sy * h)
    if box[0] < 0 or box[1] < 0 or box[2] > tshape[1] or box[3] > tshape[0]:
        return 0.0
    r = np.asarray(tmim.resize((w, h), Image.BOX, box=box)).astype(np.float64)
    return float(np.minimum(fm, r).sum() / max(np.maximum(fm, r).sum(), 1e-9))


def fit(fm, tm):
    from scipy.optimize import minimize
    h, w = fm.shape
    tmim = Image.fromarray(tm.astype(np.float32), mode='F')
    best = (0.0, None)
    for s in np.arange(3.0, 8.01, 0.25):
        for ox in np.arange(0, tm.shape[1] - s * w + 1, 16.0):
            for oy in np.arange(0, tm.shape[0] - s * h + 1, 16.0):
                v = iou(fm, tmim, tm.shape, [s, s, ox, oy], w, h)
                if v > best[0]:
                    best = (v, [s, s, ox, oy])
    if best[1] is None:
        raise SystemExit('no placement of the texture covers the picture')
    res = minimize(lambda p: -iou(fm, tmim, tm.shape, list(p), w, h), best[1], method='Powell',
                   options=dict(xtol=1e-3, ftol=1e-10))
    return [float(x) for x in res.x], float(-res.fun)


def fit_h(entry, dump, jp, start):
    """Homography (picture pixel -> texel, nine numbers) of the fan's picture onto the Japanese twin by ECC maximisation of the
    correlation of the two greyscale images (OpenCV, a development tool only), started from the scale/offset `start`
    (s, ox, oy). Used for pictures that are not a plain crop of the texture (a book photographed at an angle). -> (H, cc)."""
    import cv2
    import choice_strips as cs
    from nitro import nclr
    d = open(os.path.join(dump, 'ds_fan', 'jpn', 'upcut_local.bin'), 'rb').read()
    idl = cs.Idlocal(d)
    grid = P.pic_grid(P._content(idl, entry))
    pal = np.array(nclr(P._content(idl, entry + 1)), np.float64)
    lw = np.array((0.299, 0.587, 0.114))
    fan = (pal[grid] @ lw).astype(np.float32)
    tex = (P.load_texture(dump, jp) @ lw).astype(np.float32)
    F = 4.0
    small = cv2.resize(tex, (int(tex.shape[1] / F), int(tex.shape[0] / F)), interpolation=cv2.INTER_AREA)
    s0, ox, oy = start
    w0 = np.array([[s0 / F, 0, ox / F], [0, s0 / F, oy / F], [0, 0, 1]], np.float32)
    crit = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 400, 1e-7)
    cc, w1 = cv2.findTransformECC(cv2.GaussianBlur(fan, (0, 0), 1.0), cv2.GaussianBlur(small, (0, 0), 1.0), w0,
                                  cv2.MOTION_HOMOGRAPHY, crit, None, 5)
    return (np.diag([F, F, 1.0]) @ w1).flatten().tolist(), float(cc)


def main(argv):
    if len(argv) < 2:
        raise SystemExit(__doc__)
    dump = argv[1]
    only = None
    if '--only' in argv:
        only = {int(x) for x in argv[argv.index('--only') + 1].split(',')}
    try:
        stored = P.load_reg()
    except (OSError, ValueError):
        stored = {}
    out = {}
    for e, spec in sorted(P.UPCUT_SWAPS.items()):
        if only is not None and e not in only:
            continue
        if spec.get('homography'):
            reg, c = fit_h(e, dump, spec['jp'], spec['homography'])
            out[str(e)] = dict(reg=[round(x, 9) for x in reg], cc=round(c, 4), texture=spec['texture'], jp=spec['jp'])
            print(e, out[str(e)], flush=True)
            continue
        fm = picture_mask(e, dump, spec)
        tm = texture_mask(P.load_texture(dump, spec['jp']), spec)
        reg, c = fit(fm, tm)
        out[str(e)] = dict(reg=[round(x, 4) for x in reg], iou=round(c, 4), texture=spec['texture'], jp=spec['jp'])
        print(e, out[str(e)], flush=True)
    if '--check' in argv:
        bad = [k for k, v in out.items()
               if np.abs(np.array(v['reg']) - np.array(stored[k]['reg'])).max() > (0.25 if len(v['reg']) == 4 else 0.5) or abs(v.get('iou', v.get('cc')) - stored[k].get('iou', stored[k].get('cc'))) > 0.01]
        if bad:
            raise SystemExit('registration differs from the stored one for picture(s) %s' % ', '.join(bad))
        print('stored registration reproduced')
    if '--write' in argv:
        merged = dict(stored) if only is not None else {}
        merged.update(out)
        with open(P.REG_JSON, 'w', encoding='utf-8', newline='\n') as f:
            json.dump(dict(sorted(merged.items(), key=lambda kv: int(kv[0]))), f, indent=1)
            f.write('\n')
        print('wrote', P.REG_JSON)


if __name__ == '__main__':
    main(sys.argv)
