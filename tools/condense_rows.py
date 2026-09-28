# -*- coding: utf-8 -*-
"""Ship 85 approved condensed Capcom lines where the port today falls back to
the fan row because Capcom's own wording does not fit: Mind Chess press
statements/objectives (banks 453, 454, 455 - inject.py's small-font widget
gate) and Logic cards / evidence-profile description cards (banks 395, 432 -
loc_patch.py's line-count gate).

This table has gone through three review passes since it was first built,
each one re-measured against the same gate this module implements. The
current wording per row is the result; the (bank, string index) keys, source
hashes and gate mechanics have not changed across any of the three passes -
only which text a handful of rows carry.

Same hash-guard discipline as tools/stmt_trim.py / tools/linefix.py: each row
is keyed by (bank, string index) and holds a hash of the Capcom SOURCE text it
condenses, plus the approved replacement text. A row applies only when the
Capcom text the build actually sees still hashes to what this table was built
against; a mismatch (a different Collection dump, or - for banks 395/432, see
below - a source text this table was never built against in the first place)
leaves the row exactly as the port's existing gate already decides it, so a
stale or wrong row can only fall back to today's behaviour, never ship an
unverified substitution. Control codes around the text ({E04D}...{E040},
{E04C}...{E040}) are Capcom's own, copied exactly; only the words ever change.

As of the latest pass, both call sites (inject.py's Mind Chess widget loop,
loc_patch.py's patch_entry) try Capcom's OWN row through the gate first and
only substitute this table's text when Capcom's row fails it - so if a future
change ever widens the budget enough for Capcom's full line to fit on its
own, the port ships that instead of a condensed line still sitting in this
table unused.

TWO SOURCE DOMAINS, ONE TABLE SHAPE.
Mind Chess (453/454/455): the 'hash' is computed directly over Capcom's raw
pre-convert unit stream (en[j2][3] in inject.py's per-row widget loop) via the
same struct-pack scheme linefix.py uses - hash and injection read the exact
same representation, so there is no separate rendering step that could drift
out of sync with it. Checked row by row against the reviewed wording list for
all 54 rows: zero drift.

Logic cards / description cards (395/432): Capcom's text here is a plain
string pulled from the Collection's localization tables AFTER
loc_patch.py's existing condense.apply(t, eng) step (loc_patch.py's `eng`,
post-condense, before word-wrap) - not a script-file unit stream - so the
'hash' is a straight sha1 of that string with its own internal '\n' (the
Collection's own ~35-char soft wrap for its card) folded to a single space,
matching the reviewed wording list's recorded source text for each row.
Hashing the *pre*-condense.apply string instead (skipping that existing step)
disagrees with the reviewed source text for 17 of the 31 loc rows -
condense.apply() already shortens several of these descriptions before this
table ever sees them, and the review was done against ITS output, not the
raw localization string. Hashing after condense.apply(), as loc_patch.py's
own pipeline does, reproduces the reviewed source text exactly for all 31
rows (verified against a real build: 0 fallbacks from a hash mismatch on
this domain). All 54 Mind Chess rows (453/454/455, no condense.py step in
their path) also matched with zero drift.
"""
import hashlib
import struct

import dstext

# (bank, string index) -> {'hash': <source hash>, 'text': <approved text>}
CONDENSE_ROWS = {
    (395, 22): {'hash': '73edfe3b123e4340', 'text': "On the president's orders, so Knight could pop the balloon?"},
    (395, 25): {'hash': 'b7efd55360561143', 'text': "The president's security detail was watching for anything suspect."},
    (395, 42): {'hash': '6de68e4ca2e7d79e', 'text': "One of Gumshoe's Seven Secret Weapons. Used to find metal."},
    (395, 47): {'hash': 'c21042d6db4b6506', 'text': 'Something heavier than Saint would be needed for the trick to work.'},
    (395, 54): {'hash': '95da97970395eef9', 'text': "The whipped cream is melting; it'll lose its shape at the slightest touch."},
    (395, 55): {'hash': 'f7a4273ab25b7fbd', 'text': "The candy castle's rock crystals have stands on the bottom."},
    (395, 80): {'hash': '5098ca75acade6f7', 'text': 'Did someone move the body aside to get to the blood in the chest?'},
    (395, 84): {'hash': '3f65dafd86f8b80a', 'text': "Bound got back the house and the ultimate cookbook for Tangaroa's sake."},
    (395, 97): {'hash': '3c8d43c6ac330d57', 'text': 'Someone in a red raincoat from the concession stand pushed Kay.'},
    (395, 107): {'hash': '3f9c33101a9d87f7', 'text': "The body was hidden so departing participants wouldn't spot it."},
    (395, 127): {'hash': '33094beb2037d50b', 'text': "Signs indicate Aldown's body was moved from elsewhere."},
    (432, 7): {'hash': 'e9135288f2d003b4', 'text': 'A photograph of the president at the moment the incident occurred.'},
    (432, 77): {'hash': '1bdc5bcdb7865ed4', 'text': "Used during the show to send Saint flying. The weights were replaced with the victim's body."},
    (432, 116): {'hash': '11db4a3c1f81da0f', 'text': 'Cloth that glows when linked to a full-spectrum light-emitting device.'},
    (432, 171): {'hash': 'b4a1f4399a6c757c', 'text': "A three-armed candle holder that may be the murder weapon, judging by the victim's chest wounds."},
    (432, 173): {'hash': '3ac3ea50486da535', 'text': 'A book of promises Kay made to her father as a child. What was it doing in the Committee chamber?'},
    (432, 180): {'hash': 'eb61d0c5c7002178', 'text': 'Ringleader: white jacket, white gloves, magenta flower, mask. A facial tattoo showed past the mask.'},
    (432, 207): {'hash': 'b5f2c5b18168a407', 'text': "The combination lock on the front gate was untouched, while the side gate's chain was cut last night."},
    (432, 260): {'hash': '7dab8c0bf921b6bc', 'text': "President's security second-in-command. A firearms specialist."},
    (432, 292): {'hash': 'ab530807196dc005', 'text': "Tangaroa's former assistant; owns Zodiac Hall. Loves to sing and dance."},
    (432, 295): {'hash': 'a33a343d9138f3dc', 'text': 'Confectioner of indeterminate age. Known in the U.K. as Ms. Delicious.'},
    (432, 298): {'hash': '9cd1f8abea9e3320', 'text': 'Confectioner collapsed outside the Autumn Wing after inhaling poison gas.'},
    (432, 303): {'hash': '05b68ef667f3c697', 'text': 'A nurse at Hertz Hospital. Serves as assistant to the coroner, Dr. Hertz.'},
    (432, 304): {'hash': '6cbdffaf47a7fe5f', 'text': 'Mysterious woman brought by Florence Niedler. Seems to have amnesia, but...'},
    (432, 305): {'hash': 'a1e9221ef70ca894', 'text': 'Self-styled Great Thief, the second Yatagarasu. Suffering from memory loss.'},
    (432, 314): {'hash': 'd21b6cd6dba98ba8', 'text': 'Props person at Global Studios, first to find the body: Penny Nichols.'},
    (432, 317): {'hash': '6f1e47da78928bf0', 'text': "Judge, Committee member. Suspected of involvement in the president's murder."},
    (432, 318): {'hash': 'd436a09bdce147d9', 'text': "Partner at Edgeworth and Co. Defends Fifi Laguarde in Rosie Ringer's stead."},
    (432, 322): {'hash': '2bf5a51fa2714dc0', 'text': 'Committee Chairman; ran the underground auction. Under arrest for murder.'},
    (432, 326): {'hash': 'bac5fa18663e3cb3', 'text': 'A professional killer who tried to kill President Wang at Gourd Lake.'},
    (432, 327): {'hash': '27710eddedc3ee5d', 'text': 'Action star with Global Studios. Playing Taurusaurus in the movie.'},
    (453, 2): {'hash': 'faa66c14482fbfcf', 'text': '{E04D}Are they related to our location?{E040}'},
    (453, 6): {'hash': 'a2e4903d43b79458', 'text': '{E04D}She fired at you from outside?{E040}'},
    (453, 50): {'hash': '62d5c41d0615ef93', 'text': '{E04D}You must have a record of your report!{E040}'},
    (453, 51): {'hash': 'c21b6687c1070ec4', 'text': 'I\'ll "young lady" you as often as I like!'},
    (453, 147): {'hash': '5804eabf934f1759', 'text': '"The person who found the body"?'},
    (453, 155): {'hash': '6417e79fdb51455b', 'text': 'A scream would frighten them.'},
    (453, 157): {'hash': 'eb7ebbe25de9741f', 'text': 'Someone seems to be hopping mad.'},
    (453, 159): {'hash': 'eec473d54843b3c1', 'text': "You weren't at the show, were you?"},
    (453, 162): {'hash': '3b2018e76c00383f', 'text': "It wasn't the victim who screamed?"},
    (453, 163): {'hash': '86080069d2865f06', 'text': "You're the one who found the body!"},
    (453, 242): {'hash': '4bada2c02d09a313', 'text': 'And those people have no taste.'},
    (453, 244): {'hash': '8ef3c762d59f183d', 'text': "You're here for the Gemini sculpture?"},
    (453, 247): {'hash': '4d9d70fa36fdf829', 'text': "Ms. Bound wasn't at reception?"},
    (453, 250): {'hash': '6fd8bae9c01e1c02', 'text': 'The victim stopped you from entering?'},
    (453, 252): {'hash': '73e858f768b0ee51', 'text': 'Something "totally terrifying"?'},
    (453, 288): {'hash': '6d2d114be753586e', 'text': "You couldn't do that on your own?"},
    (453, 292): {'hash': '1a04c7d11fa08d87', 'text': 'You were interested in the book, too?'},
    (453, 294): {'hash': '680df10863bf3267', 'text': "{E04D}You knew that's not what's in there!{E040}"},
    (453, 295): {'hash': 'f3308c015382542d', 'text': 'You tried to become a pharmacist!'},
    (453, 299): {'hash': '6dedaddc2e97ba06', 'text': "You cared about Mr. Tangaroa's work!"},
    (453, 385): {'hash': 'daee0f3619437fe3', 'text': "You have a scoop, don't you?"},
    (453, 386): {'hash': 'c8753b379aab512b', 'text': 'You were on your way to school?'},
    (453, 391): {'hash': '0bff9df688469e2d', 'text': 'Did you hear from Ms. Lloyd?'},
    (453, 392): {'hash': '254d17f639a84932', 'text': 'You did hear the sound of something?'},
    (453, 394): {'hash': 'b7e1a69b20605453', 'text': "You should've snuck elsewhere!"},
    (453, 398): {'hash': 'f786bb605a56bb3f', 'text': '{E04D}I thought you were "honester"?{E040}'},
    (453, 441): {'hash': '9fec98e05328c353', 'text': "I don't recall entrusting my fate to you!"},
    (453, 449): {'hash': '515ebee83297661e', 'text': '{E04D}You remembered all the evidence!{E040}'},
    (453, 454): {'hash': '0997ce7937a48b4d', 'text': "You're avoiding talking about the case."},
    (453, 455): {'hash': '71a3a8c47fc6ce8a', 'text': "You're trying to win my sympathy."},
    (453, 457): {'hash': 'e0448b3a35b950ea', 'text': 'I have the perfect explanation!'},
    (453, 458): {'hash': '2665f08c58362673', 'text': '{E04D}Yet you know every other detail!{E040}'},
    (453, 467): {'hash': 'a65ffb555fcdc426', 'text': 'Did you see where she was found?'},
    (453, 468): {'hash': '1333caa9a396fe79', 'text': 'What was the weather like that day?'},
    (453, 532): {'hash': 'd0b24a99e5089c8d', 'text': "You're worried about somebody else?"},
    (453, 536): {'hash': '1972600468259ac0', 'text': 'You call Eustace "that poor child"?'},
    (453, 538): {'hash': '84a098af8323618d', 'text': 'Is something wrong with how he died?'},
    (453, 539): {'hash': '6105ae7329db9435', 'text': 'Something wrong with where he died?'},
    (453, 541): {'hash': '77f8d1d9cc388dab', 'text': 'Worried about its box office chances?'},
    (453, 542): {'hash': '5f126ff929dbcda1', 'text': '{E04D}"That poor child" is missing, right?{E040}'},
    (453, 551): {'hash': '3c9dea53d54781cf', 'text': '{E04D}The two of you are connected!{E040}'},
    (453, 596): {'hash': '0664ef9a33b41757', 'text': 'Did somebody steal from you?'},
    (453, 606): {'hash': 'f73b1ebaa891bb13', 'text': '{E04D}Your father was behind the kidnapping!{E040}'},
    (453, 620): {'hash': '08d37e0cbc37f453', 'text': 'Because you want to help your father.'},
    (453, 631): {'hash': 'e2621d75cd5313da', 'text': 'He wanted you to be a laughingstock!'},
    (453, 633): {'hash': '942ec21e7d851dc1', 'text': '"The milk of human kindness"?'},
    (454, 147): {'hash': 'f197ed06a9ed0eb0', 'text': "You were calling the shots, weren't you?"},
    (455, 1): {'hash': '6c08ed81c9104d60', 'text': "{E04C}Why they're taking over the case{E040}"},
    (455, 2): {'hash': '303d293cfc6ecf54', 'text': '{E04C}If extraterritoriality applies{E040}'},
    (455, 21): {'hash': 'ce03b481aacf3a9c', 'text': '{E04C}What happened during the incident{E040}'},
    (455, 60): {'hash': '9d82f6cf3c2c4dd2', 'text': '{E04C}Why he collaborated with Mr. Frost{E040}'},
    (455, 91): {'hash': '6cfb8e85654f8675', 'text': '{E04C}Why he rushed to have Kay arrested{E040}'},
    (455, 92): {'hash': '11ef41ae00e7337d', 'text': '{E04C}If the investigation was sufficient{E040}'},
    (455, 110): {'hash': '2015bf198ae522c9', 'text': '{E04C}What she discussed with the president{E040}'},
}

MC_BANKS = (453, 454, 455)


def _key_units(units):
    return hashlib.sha1(struct.pack('<%dH' % len(units), *units)).hexdigest()[:16]


def _key_text(s):
    return hashlib.sha1(s.encode('utf-8')).hexdigest()[:16]


def _parse_markup(text):
    """'{E04D}text{E040}' -> flat unit list (control codes as ints, characters
    as their own codepoints) - the shape dstext.convert() consumes and the
    same shape inject.py's per-row widget loop feeds it from en[j2][3]. Plain
    ASCII in, exactly like every other row that loop measures; dstext.convert()
    does the halfwidth-to-fullwidth conversion, same as Capcom's own rows."""
    import re
    out = []
    i = 0
    for m in re.finditer(r'\{([0-9A-Fa-f]{2,4})\}', text):
        out.extend(ord(c) for c in text[i:m.start()])
        out.append(int(m.group(1), 16))
        i = m.end()
    out.extend(ord(c) for c in text[i:])
    return out


def _trailing_code_run(units):
    """(body, trailer): trailer is the maximal run of WHOLE control-code
    tokens (arity-aware, so a code's own argument units are never mistaken
    for a second code or for text) at the very end of `units`; body is
    everything before it, codes and characters flattened back to units."""
    tokens = []
    i, n = 0, len(units)
    while i < n:
        v = units[i]
        if 0xE000 <= v <= 0xF8FF:
            width = 1 + dstext.ARGS.get(v, 0)
            tokens.append(('code', list(units[i:i + width])))
            i += width
        else:
            tokens.append(('char', [v]))
            i += 1
    j = len(tokens)
    while j > 0 and tokens[j - 1][0] == 'code':
        j -= 1
    body, trailer = [], []
    for t in tokens[:j]:
        body.extend(t[1])
    for t in tokens[j:]:
        trailer.extend(t[1])
    return body, trailer


def mc_units(bank, string_index, capcom_units):
    """Approved replacement units for a Mind Chess row (banks 453/454/455), or
    None if this (bank, string_index) has no row. The approved text supplies
    the body (its own {E04D}/{E04C}/{E040} framing, exactly as reviewed); the
    row's own TRAILING control-code run (the box-end code(s) after the last
    visible character, e.g. {E106}) is taken from `capcom_units` - Capcom's
    own row - verbatim, replacing whatever trailing run (if any) the approved
    text's own markup ends on, so the shipped row's terminator is byte-for-
    byte Capcom's, never something reconstructed from the approved wording."""
    row = CONDENSE_ROWS.get((bank, string_index))
    if row is None:
        return None
    a_body, _a_trailer = _trailing_code_run(_parse_markup(row['text']))
    _c_body, c_trailer = _trailing_code_run(list(capcom_units))
    return a_body + c_trailer


def mc_source_ok(bank, string_index, capcom_units):
    """True if capcom_units (en[j2][3], the raw pre-convert Capcom units
    inject.py's widget loop already has in hand) still hashes to what this
    row's approved text was built against."""
    row = CONDENSE_ROWS.get((bank, string_index))
    if row is None:
        return False
    return _key_units(list(capcom_units)) == row['hash']


def loc_text(bank, string_index):
    """Approved replacement text for a Logic-card/description row (banks
    395/432), or None if this (bank, string_index) has no row."""
    row = CONDENSE_ROWS.get((bank, string_index))
    if row is None:
        return None
    return row['text']


def loc_source_ok(bank, string_index, capcom_eng):
    """True if capcom_eng (loc_patch.py's `eng`, the Collection's official
    string before word-wrap) still hashes to what this row's approved text
    was built against, after the same '\n'-to-space fold used to hash it."""
    row = CONDENSE_ROWS.get((bank, string_index))
    if row is None or capcom_eng is None:
        return False
    norm = capcom_eng.replace('\n', ' ')
    return _key_text(norm) == row['hash']
