# -*- coding: utf-8 -*-
"""A small pixel face for the brass plaques of the Angel's Cookbook close-ups (upcut_local 104, 106).

Capcom's plaque lettering is hairline sans about 3.5 pixels tall at the DS picture's scale, which no area average
keeps legible. The plaques are therefore lettered the way the fan's other small print is: one pixel strokes, light on
the plaque's dark face. Capitals and ascenders are five rows, lower case four (rows 1 to 4 of the cap box), a
descender adds one row below; letters are three pixels wide (i and l one, f r t two), a pixel of space between
letters, three between words. Each glyph is a tuple (rows, top): `top` is the row of its first row below the cap line.
Letters are drawn by hand from the strokes of the fan's bottle-label face (tools/icon_labels.py), reduced to this size.

    layout(text) -> (list of (x, rows, top), width)
"""

CAP = 5
DESC = 1
GAP = 1
SPACE = 3

FACE = {
    'A': (('.#.', '#.#', '###', '#.#', '#.#'), 0),
    'B': (('##.', '#.#', '##.', '#.#', '##.'), 0),
    'D': (('##.', '#.#', '#.#', '#.#', '##.'), 0),
    'C': (('.##', '#..', '#..', '#..', '.##'), 0),
    'L': (('#..', '#..', '#..', '#..', '###'), 0),
    'T': (('###', '.#.', '.#.', '.#.', '.#.'), 0),
    # capitals of the news banner (upcut_local 216)
    'E': (('###', '#..', '##.', '#..', '###'), 0),
    'G': (('.##', '#..', '#.#', '#.#', '.##'), 0),
    'H': (('#.#', '#.#', '###', '#.#', '#.#'), 0),
    'I': (('###', '.#.', '.#.', '.#.', '###'), 0),
    'N': (('#..#', '##.#', '#.##', '#..#', '#..#'), 0),
    'O': (('###', '#.#', '#.#', '#.#', '###'), 0),
    'R': (('##.', '#.#', '##.', '#.#', '#.#'), 0),
    'S': (('.##', '#..', '.#.', '..#', '##.'), 0),
    'U': (('#.#', '#.#', '#.#', '#.#', '###'), 0),
    'V': (('#.#', '#.#', '#.#', '#.#', '.#.'), 0),
    'W': (('#...#', '#...#', '#.#.#', '#.#.#', '.#.#.'), 0),
    'Y': (('#.#', '#.#', '.#.', '.#.', '.#.'), 0),
    '-': (('###',), 2),
    # ascenders
    'b': (('#..', '##.', '#.#', '#.#', '##.'), 0),
    'f': (('.#', '##', '#.', '#.', '#.'), 0),
    'h': (('#..', '##.', '#.#', '#.#', '#.#'), 0),
    'i': (('#', '.', '#', '#', '#'), 0),
    'k': (('#..', '#.#', '##.', '#.#', '#.#'), 0),
    'l': (('#', '#', '#', '#', '#'), 0),
    '!': (('#', '#', '#', '.', '#'), 0),
    't': (('#.', '##', '#.', '#.', '.#'), 0),
    # x-height four rows
    'a': (('.##', '#.#', '#.#', '.##'), 1),
    'c': (('.##', '#..', '#..', '.##'), 1),
    'e': (('.##', '###', '#..', '.##'), 1),
    'n': (('##.', '#.#', '#.#', '#.#'), 1),
    'o': (('.#.', '#.#', '#.#', '.#.'), 1),
    'u': (('#.#', '#.#', '#.#', '.##'), 1),
    'r': (('##', '#.', '#.', '#.'), 1),
    's': (('.##', '#..', '..#', '##.'), 1),
    # descenders
    'g': (('.##', '#.#', '.##', '..#', '##.'), 1),
    'p': (('##.', '#.#', '#.#', '##.', '#..'), 1),
    'y': (('#.#', '#.#', '.##', '..#', '##.'), 1),
}


def layout(text, gap=GAP, space=SPACE):
    out, x = [], 0
    for ch in text:
        if ch == ' ':
            x += space - gap
            continue
        rows, top = FACE[ch]
        w = max(len(r) for r in rows)
        out.append((x, rows, top))
        x += w + gap
    return out, x - gap
