# -*- coding: utf-8 -*-
"""Offline registration of the Collection's item textures onto the fan's evidence icons
(com/idcom.bin entries 281, 573, 575).

Fits one transform per icon, a separate scale and offset per axis, texel = offset +
scale * icon pixel, by maximising the normalised cross-correlation between the fan's
icon (grey) and the JAPANESE twin texture after the texture is area-averaged into the
icon grid (idcom_icons.resample). The Japanese twin is used because the fan's icon is
a downscale of that art; its lettering is the fan's own, so the fit is dominated by the
card's outline, shadow and tone. The English texture's frame is the same
(tools/idcom_icons.py says how the result is used).

The result goes to tools/idcom_icons_reg.json:

    {"281": {"reg": [sx, sy, ox, oy], "ncc": ..., "size": 64, "texture": "..."}, ...}

This is a development tool run once; the build only reads the json. It needs scipy,
which the built tool does not bundle, and is never imported by the build.

    python tools/idcom_icons_register.py FAN_idcom.bin DUMPDIR [--write] [--check]

--check recomputes the fit and fails if it disagrees with the stored json by more than
0.25 texels (or by NCC 0.01).
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import idcom_icons as I
from PIL import Image


def ncc(a, b):
    a = a - a.mean()
    b = b - b.mean()
    return float((a * b).sum() / np.sqrt((a * a).sum() * (b * b).sum()))


def grey_resample(g, reg, size):
    sx, sy, ox, oy = reg
    box = (ox + I.PAD, oy + I.PAD, ox + I.PAD + sx * size, oy + I.PAD + sy * size)
    p = np.pad(g, ((I.PAD, I.PAD), (I.PAD, I.PAD)), mode='edge')
    im = Image.fromarray(p.astype(np.float32), mode='F')
    return np.asarray(im.resize((size, size), Image.BOX, box=box))


def fit(ds, tex, size):
    from scipy.optimize import minimize
    g = I.tone(tex).mean(2)
    s = I.TEX_SIZE / size

    def f(p):
        try:
            return -ncc(ds, grey_resample(g, p, size))
        except ValueError:
            return 0.0
    best = (0.0, None)
    for sx in np.arange(s * 0.97, s * 1.04, s * 0.005):
        for sy in np.arange(s * 0.97, s * 1.04, s * 0.005):
            for ox in np.arange(-8, 14.1, 1.0):
                for oy in np.arange(-8, 14.1, 1.0):
                    v = -f([sx, sy, ox, oy])
                    if v > best[0]:
                        best = (v, [sx, sy, ox, oy])
    res = minimize(f, best[1], method='Powell', options=dict(xtol=1e-4, ftol=1e-10))
    return [float(x) for x in res.x], float(-res.fun)


def main(argv):
    if len(argv) < 3:
        raise SystemExit(__doc__)
    fan = open(argv[1], 'rb').read()
    dump = argv[2]
    out = {}
    for e, spec in I.ICONS.items():
        ds = I.fan_render(fan, e).astype(np.float64).mean(2)
        tex = I.load_texture(dump, spec['jp'])
        reg, c = fit(ds, tex, spec['size'])
        out[str(e)] = dict(reg=[round(x, 4) for x in reg], ncc=round(c, 4), size=spec['size'], texture=spec['jp'])
        print(e, spec['jp'], out[str(e)])
    if '--check' in argv:
        stored = I.load_reg()
        bad = []
        for k, v in out.items():
            d = np.abs(np.array(v['reg']) - np.array(stored[k]['reg']))
            if d.max() > 0.25 or abs(v['ncc'] - stored[k]['ncc']) > 0.01:
                bad.append(k)
        if bad:
            raise SystemExit('registration differs from the stored one for icon(s) %s' % ', '.join(bad))
        print('stored registration reproduced')
    if '--write' in argv:
        with open(I.REG_JSON, 'w', encoding='utf-8', newline='\n') as f:
            json.dump(out, f, indent=1)
            f.write('\n')
        print('wrote', I.REG_JSON)


if __name__ == '__main__':
    main(sys.argv)
