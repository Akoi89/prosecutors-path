# -*- coding: utf-8 -*-
"""Put DS button names where Capcom draws a controller button glyph.

WHY THIS EXISTS. Capcom's how-to-play lines carry {E2B0}, an inline glyph of the
controller button being described. The DS engine has never seen that code, so
inject.py's foreign-code gate throws the WHOLE string away and the fan
translation's version of that line survives. Measured on the shipped v1.9.1:
20 script strings, 15,212 character units, and they are almost exactly the
tutorial material - Gumshoe's Episode 1 partner conversations, the Little Thief
demonstration, the re-creation switch, the luminol lesson, fingerprint dusting.
Nothing else is wrong with those strings: Capcom's English for them is complete
and sits at the same string index as the DS's, box for box.

THE RULE FOR WHICH BUTTON. There is deliberately no global icon-to-button table
and one must not be added. The icon's argument is which controller button Capcom
draws, and the same button does different jobs in different scenes: icon 4 is the
information list in the partner conversation and Rewind in the Little Thief demo,
icon 0 is Examine/Talk in the park and Pause in front of the monitor. The DS
binding for each ACTION comes from the FAN row for that same scene, because the
DS engine's own bindings never changed. Capcom supplies the words, the fan row
supplies the button. Every row in button_icons.json was read that way by hand and
its icon ids verified against the real strings (34 of 34 matched).

TWO ROWS ARE NOT SUBSTITUTIONS. The DS does those jobs with hardware the
Collection has not got: dusting for fingerprints is the touch screen and blowing
the powder away is the microphone (sce4_c4_02), and spraying luminol is the touch
screen (logic03_05). Those rules drop a few characters of the sentence ahead of
the glyph and write the clause instead.

ENTRY 4 AND THE RE-CUT TRAP. The Gourd Lake scene, entry 4, was first left out of
this table on the belief that it could never be swapped: the fan moved message
boxes into string 4, 54 where the Japanese original has 62, and that string is
the Logic tutorial and the location card that HUNG Episode 1 before 1.5.2. THAT
BELIEF WAS WRONG. The fan's strings 3 and 4 hold 16 and 54 boxes where both the
Japanese and the Collection hold 8 and 62, so the PAIR totals 70 on both sides,
nothing is missing, and inject.recut_run(ds, en, [3, 4]) succeeds today. The only
thing keeping that scene on the fan translation was this glyph.

Its rules are therefore keyed to the strings AS THE RE-CUT LEAVES THEM, not as
the Collection file holds them: the re-cut moves eight boxes out of string 4 and
into string 3, and one glyph travels with them, so 4:3 has one rule and 4:4 has
five. A table keyed to the original Collection indices is WRONG for any re-cut
entry, and the guard below caught exactly that ("4:4 has 5 glyphs, the table has
6 rules") rather than writing a mangled sentence. Test such a row through a real
build, not by calling substitute() on the raw Collection string.

ENTRY 106 STRING 0 WAS HELD AND IS NOW IN. Capcom says to talk to Kay to switch
re-creations, and the fan row for that scene names no button at all: it says to
select Little Thief on the bottom screen. It was left out rather than guessed.
Three independent sources now agree on the Y Button, so it is in: Episode 5's own
fan rows give the same instruction, for the same action, in the form "press this
button and pick this menu option"; the fan's Episode 1 line has the protagonist
state, in dialogue, that pressing that button is how they'd consult their partner,
confirming it as the partner button; and StrategyWiki's DS walkthrough for
Episode 2 names the same button for the same menu option, illustrated with a DS
Y-button image. The rig also saw Y open a partner-topic menu in that courtyard,
and the reason it saw no switch is that the switch only exists after Kay sets up
the SECOND re-creation, the one of the show in progress.

Note the option's LABEL differs and ours is right: that walkthrough says "Change
Re-creation", which is the fan patch's wording, while our build letters the strip
with Capcom's own "Switch re-creations" (inventory/select_strip_map.json row 668)
and Capcom's own dialogue in DS[310] str23 names "Switch re-creations" too. So the
fan's line named an option our build no longer shows, and Capcom's line matches
the strip.

No Capcom prose is stored in this repo. A rule that deletes text says how many
characters to delete and carries a 12-hex-digit sha1 of the 40 characters of
Collection text it expects to find in front of the glyph, so a wrong file or a
changed dump fails loudly instead of writing a mangled sentence.
"""
import json, hashlib, os, sys, re

ICON = 0xE2B0

# Keyword colour. E041 sets orange, E040 restores white, E042 sets the blue the
# engine uses for Edgeworth's bracketed thoughts. All three are absolute setters,
# not a push/pop pair, so a span is "open orange, then set the colour that was
# there before" - and which one that is depends on whether we are inside a
# parenthetical. Overlay 7 emits E042 itself on a fullwidth '(' and E040 on ')',
# so inside brackets the restore is E042 and outside it is E040. Verified against
# the fan's own spans, e.g. DS[18] str1: a parenthetical instruction that
# highlights one button to hold, then a second to use with it in turn. Note
# where the span STARTS: after the article, with the leading space inside it.
# This matches the fan exactly.
#
# WHY HIGHLIGHT AT ALL, since the rest of Capcom's prose is left as Capcom wrote
# it: the thing being replaced here was an ICON, which stood out on its own
# because it was a picture. Substituting plain words for it loses that
# distinction, so the span restores what removing the graphic took away. It is
# applied ONLY to the phrases this module inserts, never to Capcom's own text,
# and only to phrases that name a physical control. The fan does NOT highlight
# the touch-screen and microphone phrasings (measured on DS[322] str12 and
# DS[381] str0), so neither do we.
ORANGE, WHITE, BLUE = 0xE041, 0xE040, 0xE042
# Capcom's script stores ASCII brackets and the fan's DS script stores fullwidth
# ones; dstext widens them on the way to the DS, which happens AFTER this module
# runs. So test both, or the parenthetical is never detected and every span
# restores to white inside a thought that should go back to blue. Measured:
# eng_trial/sce0_c0_m00_check.bin str35 holds 0x28/0x29, the fan's holds
# 0xFF08/0xFF09.
PARENS_OPEN = (0x28, 0xFF08)
PARENS_CLOSE = (0x29, 0xFF09)

_T = None

# button_icons.json sits beside this module, which in a frozen build is the
# bundle root, not a tools/ directory. v1.6.0 shipped without two files that
# were opened relative to __file__ and crashed at the description step; the
# --selftest list in build.py names this one for the same reason.
_HERE = sys._MEIPASS if getattr(sys, 'frozen', False) \
    else os.path.dirname(os.path.abspath(__file__))


def _table():
    global _T
    if _T is None:
        _T = json.load(open(os.path.join(_HERE, 'button_icons.json'), encoding='utf-8'))
    return _T


def rows():
    """The (entry, string) pairs this module has a rule for."""
    return {tuple(int(x) for x in k.split(':')) for k in _table()}


def _text_runs(units, args):
    """Indices of every unit that is plain text, in order, as a list of runs
    [(start, end)] - a run is a maximal stretch with no control code in it."""
    out = []
    i, n = 0, len(units)
    while i < n:
        v = units[i]
        if 0xE000 <= v <= 0xF8FF:
            i += 1 + args.get(v, 0)
            continue
        j = i
        while j < n and not (0xE000 <= units[j] <= 0xF8FF):
            j += 1
        out.append((i, j))
        i = j
    return out


def _in_parenthetical(units, at):
    """Is the glyph at `at` inside a bracketed thought? Scans back to the start of
    this message box for an unclosed fullwidth '('. Box boundary matters: colour is
    re-established per box (the engine's render-context initialiser runs from the
    E100/E101 handlers), so a bracket in an earlier box says nothing about this one."""
    BOXEND = (0xE102, 0xE104, 0xE106, 0xE185, 0xE081)
    depth = 0
    for k in range(at - 1, -1, -1):
        v = units[k]
        if v in BOXEND:
            break
        if v in PARENS_CLOSE:
            depth += 1
        elif v in PARENS_OPEN:
            if depth == 0:
                return True
            depth -= 1
    return False


def _insert_units(rule, units, at):
    """The units to put where the glyph was.

    A rule's text marks what to colour with braces, so the span is stated rather
    than guessed: "the {A Button}" colours " A Button" and leaves "the" alone,
    the way the fan's own spans do. "the {D-Pad} while holding the {R Button}"
    colours the two control names and not the words between them. Text with no
    braces is inserted plain, which is what the touch-screen and microphone
    phrasings want because the fan does not colour those either.
    """
    text = rule['text']
    if '{' not in text:
        return [ord(c) for c in text]
    restore = BLUE if _in_parenthetical(units, at) else WHITE
    out = []
    for piece in re.split(r'(\{[^{}]*\})', text):
        if piece.startswith('{') and piece.endswith('}') and len(piece) > 2:
            out.append(ORANGE)
            out.extend(ord(c) for c in piece[1:-1])
            out.append(restore)
        else:
            out.extend(ord(c) for c in piece)
    return out


def substitute(entry, string_index, units, args, strict=True):
    """Return (new_units, n_replaced). units is left alone when there is no rule.

    Raises ValueError on any disagreement between the rule and the string when
    strict: a wrong icon id, the wrong number of glyphs, or a context hash that
    does not match. A silently mangled tutorial sentence is worse than a build
    that stops.
    """
    rules = _table().get('%d:%d' % (entry, string_index))
    if not rules:
        return units, 0
    units = list(units)
    found = [i for i, v in enumerate(units) if v == ICON]
    if len(found) != len(rules):
        if not strict:
            return units, 0
        raise ValueError('buttons: %d:%d has %d glyphs, the table has %d rules'
                         % (entry, string_index, len(found), len(rules)))

    # Work from the end so earlier indices stay valid.
    for k in range(len(rules) - 1, -1, -1):
        r = rules[k]
        at = found[k]
        got = units[at + 1] if at + 1 < len(units) else None
        if got != r['icon']:
            if not strict:
                return units, 0
            raise ValueError('buttons: %d:%d glyph %d is icon %r, the table expects %r'
                             % (entry, string_index, k, got, r['icon']))
        # the text run immediately in front of the glyph
        runs = _text_runs(units, args)
        pre = [(a, b) for a, b in runs if b <= at]
        head = ''.join(chr(v) for v in units[pre[-1][0]:pre[-1][1]] if v) if pre else ''
        want = hashlib.sha1(head[-40:].encode('utf-8')).hexdigest()[:12]
        if want != r['pre_sha1']:
            if not strict:
                return units, 0
            raise ValueError('buttons: %d:%d glyph %d context sha1 %s, the table expects %s'
                             % (entry, string_index, k, want, r['pre_sha1']))
        drop = r.get('pre_drop', 0)
        ins = _insert_units(r, units, at)
        if drop:
            a, b = pre[-1]
            # delete the last `drop` NON-ZERO units of that run, keeping any
            # padding zeros the engine put there
            cut = []
            j = b - 1
            while j >= a and len(cut) < drop:
                if units[j]:
                    cut.append(j)
                j -= 1
            if len(cut) != drop:
                if not strict:
                    return units, 0
                raise ValueError('buttons: %d:%d glyph %d cannot drop %d characters'
                                 % (entry, string_index, k, drop))
            for j in sorted(cut, reverse=True):
                del units[j]
            at -= drop
        units[at:at + 2] = ins
        found = [i for i, v in enumerate(units) if v == ICON]
    return units, len(rules)
