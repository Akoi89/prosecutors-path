Port Capcom's official English localization of *Gyakuten Kenji 2* into the Nintendo DS ROM.

**93.8% of the script's text is Capcom's writing** (measured by `tools/coverage.py`;
the exact unit count is in the README). 1.5.2 said 93.9%, 1.5.1 said 94.3%: four tutorial
lines went back to the fan text in 1.5.2 and twelve description rows in 1.6.0, see below. Earlier notes said 96.5% and, before that,
98.4%; see the 1.5.0 entry for why the counting changed. The remainder stays in the AAI2
fan translation; the README says exactly why, and which parts.

## v1.6.4: a highlighted term split across two boxes keeps its colour

When a coloured term was too long for one text box, the half that landed in the second box
lost its colour and drew plain white. So a keyword the game had marked as important stopped
looking important halfway through. It showed most on the green testimony and deduction lines,
and on orange keywords like *Animal Taming Department*, where the box ends on
*"She's head of the **Animal**"* and the next one opens with a colourless *"Taming
Department."*

A box-terminating code resets the engine's inline style, the same way a thought box loses its
blue when its opening "(" is stranded on the previous page. The converter already put the
parenthesis back across a break; it never put the *style* back. It does now: whichever colour
is open is closed before the break and re-opened after it. **98 places across all five
episodes**, and 81 of them are the green style, so a fix written only for the orange keywords
would have missed five sixths of it.

Judged by the ROM rather than by the build running: the previous tools reproduce the 1.6.3
hash exactly, so this change is the only difference; every audit's output is identical, the
guard counts are unchanged, and coverage is unchanged at 93.8%. The ROM grows by 512 bytes.

Confirmed on the hardware, not on paper. The Episode 2 line above was checked in game before
and after: white, then orange. The green case was proved the same way, by changing a single
byte in a test ROM so that term used the green style instead: both halves come back green,
while a *separate* coloured term in that same second box was orange throughout. The engine
can draw colour in the second box perfectly well; what it could not do was carry one over.

## v1.6.3: long evidence titles are no longer squashed

The evidence and profile card titles are drawn strips 128 px wide, and 18 of the 119
official titles do not fit that at normal letter spacing. Through 1.6.2 the renderer
squashed those to zero letter gap before it would consider a shorter title, so cards
like *Creature Feature Flyer*, *Mr. Aldown's Final Call* and *Behind-the-Scenes Photo*
were drawn with their letters touching and were hard to read.

Now every candidate title is tried at normal spacing before any candidate is squashed,
and 17 of the 18 have a shorter form built only from words in Capcom's own title, with
the Japanese name used to decide which words carry the meaning: *Creature Flyer*,
*Gemini Results*, *Statutes Book*, *Guard Uniform*, *Poison Ingredients*, *Building
Pamphlet*, *Behind-the-Scenes*, *Rehearsal Tape*, *SS-5 Case File*, *Blood Stain*, and
the honorific dropped from *Tangaroa's Teapot*, *Scone's Statement*, *Niedler's
Statement*, *Wang's Autopsy*, *Aldown's Autopsy*, *Aldown's Photograph* and *Aldown's
Final Call* (the Japanese names carry no honorific either). *Ringleader's Appearance*
has no shorter form that keeps its meaning and still squashes. The 101 titles that
already fit are byte-identical. Nothing else in the ROM changed; all audits identical;
coverage unchanged at 93.8%.

## v1.6.2: closing quotation marks no longer draw as an apostrophe

Every closing double quote in the ported text came out as an apostrophe:
`"Taurusaurus Vs. Gourdy'.` where the script says `"Taurusaurus Vs. Gourdy".` The fan
patch's font has no separate closing-quote glyph. Its U+201D slot *is* the apostrophe
(the fan script uses it that way 16,482 times), and the fan team drew both ends of a
quotation with the same U+201C glyph, 925 times. The converter emitted U+201D for the
closing half, so every release through 1.6.1 had this: 995 places in 657 strings.

One line changed (`DQ_CLOSE` in `tools/dstext.py`). Judged by the ROM rather than by
the build running: the 1.6.1 tools reproduce the 1.6.1 hash exactly, the fixed tools
change one file in the ROM, and every one of the 657 string changes is that single
character substitution. No line re-wrapped, every audit's output is identical, coverage
is unchanged at 93.8%. Found by the rig playtest on the Creature Feature Flyer card in
Episode 5 and verified on that card with the fixed build.

## v1.6.1: the 1.6.0 downloads were incomplete

The 1.6.0 executables crashed before finishing: two data files the tools read from
beside their own code (`desc_font.json`, the measured description-card font, and
`select_strips.json`, the choice-button pairing) were not bundled into the frozen
build. Building from source was unaffected. 1.6.1 is the same tools with both files
bundled, the self-test now checks for them, and the version stamp on the title screen
reads 1.6.1, which is the only reason the ROM hash differs from 1.6.0.

## New in v1.6.0: the choice buttons are in Capcom's words, and descriptions no longer clip

The option plates of every choice menu and talk-topic list were still the fan's
lettering, and one of them put a fan character name on screen: in Episode 1 the
choice "the owner of the red raincoat" offered *Nicole Swift* while the script
around it said *Tabby Lloyd*. The 297 plates (`jpn/idlocal.bin` 364-670, all of
them graphics) are now redrawn with the official option text, read from your
Collection at build time and set in its UD Kakugo M face.

Each plate was paired with its Collection string through the retail Japanese ROM,
whose plates sit at the same entries: the Japanese lettering was matched glyph by
glyph to Capcom's own Japanese select tables, and the English follows from the id.
Nothing was matched by meaning. Nine strings Capcom lists twice with different
English are resolved by episode; three plates Capcom's own data labels with debug
text ("Her position aaaaaa") take their twin's clean line. 48 long options are
condensed by up to 12% and 20 step down a size to fit, the way the episode titles do.

**Evidence and profile descriptions no longer lose their last letter.** The
description card draws a smaller font than the dialogue box, but the fitter had been
using the dialogue box's budget for it, so lines near the top of the range ran off the
140-pixel field and the game cut the final glyph ("outside the Autumn Wing afte[r]" on
Carmelo Gusto's profile, "Jammin' Ninja's face. Made o[f]" on the mask). Every release
through 1.5.2 had this. The card font was measured in game (per-glyph advances fitted
from 58 rendered lines on 18 cards, `tools/desc_font.json`) and 84 description rows are
re-wrapped against it; twelve more rows stay on the fan's text because the official
wording needs a fifth line the card does not have (rows kept as fan: 78 -> 90). Verified
on the chapter saves: Fender, Gusto, Deauxnim and the mask card all read complete.
Coverage is 93.8% (was 93.9%).

## New in v1.5.2: a hang in Episode 1 that every release had

Every release through 1.5.1 could stop dead in Episode 1, in the audience area, right
after the bodyguard introduces himself: the music keeps playing, the text box never
comes back, and no button or tap does anything. It was found by a scripted playthrough
of the build, not by a report, and it is a bug in this port, not in the fan patch.

The cause is one control code. Capcom's script uses a code the DS engine has never seen,
where the DS script uses its own equivalent (the pair that opens and closes a scripted
wait). The converter passed the unknown code through unchanged. The engine skips a code
it does not know and then reads the code's arguments as text; one of them is zero, which
ends the string early, and the closing half of the pair is left waiting forever. There
are 15 such sites in 12 strings across the game, all with the same shape, plus five
sites of a second unknown code (the Collection's inline button icon, in tutorial lines).

The fix does two things. The converter now translates that code to its DS equivalent,
and the injector keeps the fan's string whenever a converted string still carries any
code the fan script never uses, so the five button-icon lines fall back to the fan text
rather than gamble. That guard is now part of the build report
(`records kept as fan - official-only control code`). Exactly 14 strings differ from
1.5.1; every audit passes; the first chapter of Episode 1 was replayed on the fixed build
and runs clean. Coverage moves from 94.3% to 93.9% because those four tutorial lines are
fan text again.

If you built 1.5.1 or earlier, rebuild.

```
sha256  d9d27354ecbd734cc4d01683d57f51a0a447e6c0ed826318baa76b776a899047
```

## New in v1.5.1: the last five fan-named lines

1.5.0 left five dialogue lines with a fan character name because the official name pushed
each one past its box and re-breaking had nowhere to put the extra word. They now carry
the official names, each with the smallest edit the width allows: a title or an
honorific dropped, or a contraction, never a changed meaning. Measured in the game's own
font against the 216 px line budget (`rig/measure_lines.py` in the private notes). The
per-line renamer now applies these hand fixes too; before, a row with a second over-wide
line silently discarded them. A full scan of the built ROM finds no fan character name
left in any kept-fan row. Coverage is unchanged at 94.3%: renamed fan rows count as fan.

```
sha256  2f5ba692e0c0bc2c45ab3c88dced781b8800bd117503dd69f5eca7a7873f1a61
```

## New in v1.5.0: Capcom's titles everywhere, and an honest coverage number

**The last fan names are gone from the screens you see most.** The title screen now shows
Capcom's *Ace Attorney Investigations 2: Prosecutor's Gambit* logo; the episode-select
buttons, the splash card at the start of each episode and the save screen all carry the
official episode titles. The logo sprite and the two fonts (Modé Mina B, UD Kakugo M) are
read from your own Collection at build time and rendered into the DS graphics; nothing
Capcom-owned ships with the tool. The splash-card face the fan team hand-drew turned out
to be Modé Mina, so those cards read as the same design with the official words.

Verified in melonDS on a cleared save: title screen, save panel ("Turnabout for the
Ages"), episode select and splash card ("Turnabout Trigger"), all at 60/60.

### The shouts, in Capcom's English voices

The fan patch recorded its own English "Objection!", "Hold it!", "Take that!" and the
rest over the Japanese samples. The Collection carries Capcom's 2024 English recordings
under the same sound-effect numbers, and thirteen of the twenty samples the fan team
replaced have one. Those thirteen now play Capcom's takes: read from your Collection at
build time, downmixed and resampled to the retail format of each slot (IMA ADPCM at
22 kHz; 16-bit PCM at 32 kHz for the long one), and written back into the sound archive
with every header rebuilt from the sample data. The DS plays each shout to the end of its
sample, so nothing is time-compressed or cut; the one take that runs half a second longer
than the fan's goes in whole. The seven samples the Collection does not localise keep the
fan's recordings. The rebuilt archive boots and plays in melonDS, and every new sample was
decoded back out of it to confirm length, rate and level.

### Logic keyword cards in Capcom's words

The cards on the Logic board were the last large fan-lettered surface. They are images,
not text, and the fan team drew their own English into 206 of them. 194 of those images
(97 keywords, card plus banner) now carry the official short names, rendered in UD Kakugo M
from your Collection over a cleaned card face; the six keywords the Collection has no name
for, and the unused dummy slots, keep the fan's lettering. Verified in melonDS on the
Episode 1 Logic board ("Assassination attempt", "Six-shot revolver").

### Character names: line by line

v1.4.4 left ten whole conversations in the fan's names because one line in each could not
take the longer official name. The rename now works line by line: the official name where
it fits, Capcom's surname where only that fits, the fan line only if even that is too wide.
Hyphenated forms ("Courtney-pie") rename too; they were being skipped. Result: 94 rows
renamed (was 84), and **five lines in the whole game still carry a fan name** (resolved in 1.5.1), each because
the fan drew that line already at the edge of the box:

- `DS[29]` str 14: "Swift will be cleared of suspicion!"
- `DS[76]` str 7: "You didn't know either, Uncle Ray?"
- `DS[94]` str 2: "escaped prisoner, Jay Elbird"
- `DS[99]` str 4: "Mr. Elbird would have seen it"
- `DS[117]` str 28: "(The true killer is Warden Roland.)"

### 108 descriptions and Logic cards, condensed to fit

Official English existed for 108 evidence descriptions, profiles and Logic cards but did not
fit the DS box, so every release until now showed the fan's text there. They now carry
Capcom's wording, condensed: deletions first, names and facts kept, hedges kept. The
Japanese line was the guide for what had to survive and the fan line for what fits. The
edits are word-index operations with result hashes (no Capcom text in the repo), and all
108 can be listed Japanese / Capcom / condensed / fan with `tools/desc_overflow.py`. Menus &
UI coverage rises from 81.1% to 90.2%; total from 93.7% to 94.3%.

### One evidence description, one hedge

The Episode 2 autopsy description used to say "Death was instant." Capcom wrote "would
have been instant" and the Japanese hedges too; in a game where autopsies get overturned
that is not a decoration. It now reads "Death was likely instant," paid for by dropping
"to the head" after "scalp", which says the same thing. Still exactly four lines.

### Coverage: 93.7%, not 96.5%

`tools/coverage.py` counted a string as official whenever its bytes differed from the fan
ROM's. Since v1.4.0 the rename pass has been swapping Capcom's character names into
fan-written rows, and every one of those rows was being counted as official. It now counts
a row as official only if it differs from the fan row *after* names and titles are applied.
By that rule v1.4.4 was **93.8%**, and 1.5.0 is **94.3%** (93.7% before the 108 condensed rows). The ROM did not get worse; the
number got honest. Per-episode figures are in the README.

### Also

- `tools/nitro.py`: the palette reader started four bytes late (no visible effect on the
  nameplates, wrong colours on every 8bpp screen). Fixed; a rebuild of 1.4.4 hashed
  identically.
- New tools, all build-time, none shipping game data: `ncer.py`, `title_art.py`,
  `title_logo.py`, `extract_logo.py`, `title_text.py`, `title_assets.py`,
  `logic_names.py`, `logic_cards.py`, `voices.py`.
- The build now has five steps; the Collection is needed for the title assets as well as
  the script, and `--skip-extract` checks for them.
- The splash-card episode titles are now anti-aliased in the same grey steps as the fan's
  "Episode N" line above them, and drawn at the same weight, so the two rows read as one
  piece of lettering (edge pixels used to be thresholded, which left the second line
  harder-edged and lighter than the first).
- The title screen now shows the build's version ("v1.5.0") in small white digits in its
  top-right corner, so a screenshot or a bug report says which build it came from. Painted
  into the composed picture by `tools/title_version.py`; no artwork is covered.

```
sha256  689c599401d3f5221fc71a778d53217649cc0af941db28514f503f8576c46263
```

```bash
python tools/build.py --verify
```

## New in v1.4.4: ten lines that shipped clipped, and two corrected claims

**Ten lines in v1.4.3 shipped clipped at the right edge of their box.** If you
are already playing v1.4.3 this is cosmetic: no hangs, no save incompatibility.
Rebuilding is optional but recommended.

v1.4.3 reverted 105 rows to fan text so they would keep the engine commands the
DS-only tutorials need. That had a side effect nobody looked for: the
name-substitution pass only touches rows byte-identical to the fan ROM, so
handing it 105 more such rows gave it **84 rows to rename, up from 45**.

Capcom's names are often longer than the fan's, and ten of those rows ended up
wider than the box they draw into. The build re-breaks a row to make it fit, but
it cannot when the over-wide line is the *last* line of a box, because there is
nowhere to push the word to. Those ten now keep the fan's name instead. A single
line still reading *Fender* costs less than a line running off the screen.

The build had printed a warning about this. It scrolled past in a wall of thirty
counters, after the tag was already cut.

### Corrections to the v1.4.3 notes

The v1.4.3 release said the revert was "93 strings, nearly all in Episode 1's
tutorial-heavy opening." Both halves were wrong, and it is now measured rather
than recalled:

- It is **105 rows, across 67 script banks.**
- They are spread across the whole game: partner conversations, examine checks
  and NPC entries, wherever DS-only interaction sits. Episode 1 is not where they
  cluster, it is where one of them locked the game.

The README also claimed **97.5% coverage**. Re-measured with `tools/coverage.py`:
**96.5%**. That figure had been written from memory instead of from the tool.

### Also in this release

- `inject.py` reports how many script banks the DS-only revert touched.
- The over-wide report is no longer phrased as a `WARNING`, since those rows are
  reverted rather than shipped.
- README: refreshed per-episode coverage and the new guard documented.

```
sha256  8ab40704f4abed647ec1fe602dd8f8cb92b6b25ee38ba2abc8af74a4b744fa6e
```

## New in v1.4.3 — Episode 1 hands you the controls again. Update before playing.

**Every release from v1.2.0 to v1.4.2 hangs in Episode 1**, at the exact moment the
game stops talking and gives you control at the Gourd Lake stage. A speaker's
nameplate sits over an empty message box, the scene keeps animating, the music keeps
playing, and nothing advances. Reproduced from a cold boot, and confirmed against the
fan translation, which reaches free roam at the same point.

The cause is a guard that was measuring the wrong thing. The Collection's script has
no touch-screen, A-Button or Logic tutorials — they are DS-only — so converting it can
silently drop the engine commands that drive them. The existing guard caught that by
counting **message boxes**, on the reasoning that missing content means missing boxes.
It does not: Capcom's prose is longer, so the converted string ended up with *more*
boxes than the fan's (18 against 16) while the tutorial command pair inside it was
gone. The box count looked healthy and the scene hung anyway.

The guard now compares the **engine commands** rather than the boxes, and any string
that would drop one keeps the fan's line.

That turned out to be bigger than the one scene. **93 strings across all five
episodes** were dropping a DS-only command — 34 in Episode 1, 27 in Episode 2, 16 in
Episode 5, 9 in Episode 3, 4 in Episode 4. They sit in the partner-conversation,
examine-check and NPC entries, which is where DS-only interaction lives throughout the
game, not just in the tutorial. Only the Episode 1 one is known to hang, because it is
the only one anybody has reached and stopped at; the rest were the same defect waiting
in the same kind of place.

That costs real coverage, and it is worth being plain about it: **the total falls from
98.4% to 97.5%**, with Episode 1 taking most of it (97.7% to 91.8%) and every other
episode giving up a little. Those strings are the DS-only content Capcom never wrote,
so they were always the least translatable part of the game, and the alternative is a
scene that stops. A scene that plays in the fan's words beats a scene that does not
play at all.

This is the third hang found by someone actually playing rather than by any offline
check, and the second in Episode 1's opening — which had never been played on a build
this recent. If you are on any earlier release, update before starting.

## New in v1.4.2 — an Episode 1 hang, found by a player. Update if you are playing.

**Every release from v1.3.0 to v1.4.1 can lock up early in Episode 1**, while you
are examining the scene. The screen keeps animating and the music keeps playing,
but a speaker's nameplate sits over an empty message box and no button advances it.
Your save is not damaged — text is read-only data — but the only way out is to
restart the chapter on this build.

Seven rows of the examine-response bank had been emptied outright. The Collection
has no text for them (the fan patch left them untranslated), and when a row is
replaced by nothing it loses its **message box** along with its words. A box that
opens with nothing inside never closes, so the scene simply stops.

There was already a net for this: a row the Collection empties keeps the fan's row
instead. It only ran when the fan's row was in English, which is why these seven —
Japanese in the fan patch — fell straight through it. The net is now split in two.
The old English rule still governs *wording*. A second, stricter rule governs
*structure*: **a row whose replacement has no message box at all keeps the fan's
row, whatever language it is in.** Untranslated text is a blemish; a lost box is a
lock, and structure now wins. A whole-ROM check confirms no string anywhere is
missing a box any more, and the fix touches that one bank and nothing else.

Thanks to the player who hit it and left the game running — a live lock is worth
far more than a bug report, and this was found and fixed from that one screen.

## New in v1.4.1 — one renamed line brought back inside its widget

An audit of v1.4.0 against the injector's own rules found a single line that broke
one. The confrontation and Logic Chess option widgets have no measured width in
the game; what the tool trusts instead is **the widest line the fan translation
ever displayed in that widget** — anything wider keeps the fan's line rather than
risk a clipped word. v1.4.0's rename pass did not apply that rule to its own
output, and one line, where a shorter surname became a longer official one, ended
up 8 pixels past the widest that widget has ever been proven to draw.

The line now drops an honorific to fit (243px against a 262px budget), and the
rename pass enforces the same per-widget budget the injector does, so a future
name can't quietly overrun one: any renamed row wider than the fan proved simply
keeps the fan line and says so at build time. No other line in the game was
affected — the other renamed banks came in at or under budget.

Also in this release: the guard meant to stop a title card being redrawn with the
wrong item's name was a no-op, and is now real. It never mattered — every one of
the 177 fan titles was independently re-read and confirmed, and all 119 official
names were checked to exist verbatim in Capcom's own tables — but the check now
actually runs.

## New in v1.4.0 — Capcom's character names, everywhere

The fan translation named this cast years before Capcom did, and until now the
port wore both sets at once: the dialogue (98.4% Capcom's) said *Fender*,
*Saint* and *Laguarde* while the nameplate above it still said *Ray*, *Simon*
and *Roland*, and the Organizer agreed with neither. This release retires the
fan names entirely — the official localization is the canon this port follows.

- **All 28 dialogue nameplates whose names Capcom changed are redrawn**
  (Ray→Fender, Simon→Saint, Courtney→Gavèlle, Debeste→Eustace, Roland→Laguarde,
  Dogen→Kanis, Knightley→Knight, MIB→Man in Black, and twenty more). Nameplates
  are graphics, not text: the tool decodes them from your fan ROM, harvests the
  fan patch's own pixel font from the plates themselves, and re-renders the
  official names in it — so the plates still look exactly like the fan patch drew
  them, and no fan-drawn graphics ship with this tool.
- **All 119 evidence and profile title cards with outdated names or titles are
  redrawn the same way** — profile cards now read *Eddie Fender* and *Simeon
  Saint*, and evidence titles use Capcom's item names (*Ms. Lloyd's Tape*,
  *Pocket Chess Set*, *Mr. Kanis's Bells*, *Taurusaurus Head*, ...). A few
  official titles are wider than the DS card and drop one filler word, built
  only from the official title's own words. One card the fan patch left in
  Japanese (約束ノート) is now *Promise Notebook*.
- **Every kept-fan text string is renamed to match** — 45 strings (Organizer
  descriptions, Logic cards, DS-only tutorials and the fan-kept scenes) now use
  the official names, verified string-by-string against the fan ROM first so
  official text is never touched, with line widths re-checked and re-wrapped
  where a longer name needed it. The mapping was derived from the two scripts
  themselves: for every line that exists in both translations, fan names were
  paired with the official names appearing in the same line (139 co-occurrences
  for Knightley→Knight alone), then spot-checked in context.
- The pairing also covers the non-people: *Moozilla* is officially
  *Taurusaurus*, the elephant *Astique* is *Azea*, the chairman's nickname
  *Blaisie* is *Celsius*, the masked *Conductor* is the *Ringleader*, and the
  *Dye-Young Hospital* is *Hertz Hospital*.

The episode titles on the save screen already used Capcom's names (since
v1.1.0); the episode-select artwork remains the fan's bitmap, as before. The
reference hash for `--verify` moves; coverage counts are unchanged (titles and
nameplates are graphics, not counted text).

## New in v1.3.4 — one description stops disagreeing about a room's name

The Rubber Glove's updated Court Record description — one of the ~100 over-long
descriptions that keep the fan's fitting text — called the crime scene
"workroom A", while every official line around it (including the same item's own
earlier description) says "workshop". The playtest that found the v1.3.3 hang
also caught this. An audit of every kept-fan row against the official vocabulary
found **exactly one such location-term conflict in the whole game**; the rest of
the fan-vocabulary differences are character names, which stay untouched until
nameplates can change with them.

The fix substitutes that one word at build time in the description/Logic banks
only — same letter count, measurably narrower, so nothing re-wraps. The ROM
changes by exactly 3 character units; full fan scenes keep their own vocabulary.
The reference hash for `--verify` moves accordingly.

## New in v1.3.3 — a hang in the Little Thief scenes, found by playtest, fixed

**Every earlier release hangs — permanently, music still playing — the moment Kay
deploys Little Thief in Episode 2's final chapter.** The first hands-on playtest of
the recovered scenes hit it within the hour, on the first Little Thief scene it
reached. If you played v1.3.2 or earlier past that point, this is the fix; your
save is fine (text is read-only data — restart the chapter on a v1.3.3 ROM).

The cause is almost funny. The converter knows how many argument units follow each
control code from a statistically derived table, and that table treats any code
"followed by a letter in >85% of cases" as inline markup with no arguments. Code
`E1E2` — Little Thief's projector command — takes three arguments, and the first is
always the value 68… which is the letter **`D`**. A constant argument that spells a
letter defeated the letter test, the converter fullwidth-converted the 68 into a
`Ｄ`, and the DS engine hung on the garbage value. Two more codes fell into the same
trap: `E19D` (argument 100 = `d`) and `E1E5` (argument 115 = `s`), corrupted at 16
further sites — no confirmed symptom, but the same class of wrong.

The fix corrects those three arities (the deriver now refuses to force arity 0 when
the "prose" after a code is the same value every time — prose varies, arguments
don't), which repairs **exactly 32 units across 20 script entries and changes
nothing else** — verified by byte-diff against the v1.3.2 ROM, and every repaired
argument is now byte-identical to the fan ROM's own engine-proven value. Verified
in-game: the Episode 2 scene that hung now plays through its full Little Thief
re-creation in Capcom's text (that entire ~4,400-unit recovered scene was also
box-by-box reviewed on screen — zero text defects). The other affected scenes
(Episodes 2/4/5) are verified structurally by the same byte-comparison.

The reference hash for `--verify` moves accordingly. Coverage is unchanged.

## New in v1.3.2 — checking, and clearer help

No change to the ROM (still verifies to the same hash as v1.3.1). This release makes
the tool easier to trust and to get working:

- **`gk2port --verify`** hashes a built ROM and confirms it against this version's
  published reference. A MATCH means it is the genuine, unmodified output of the tool —
  so a ROM can be trusted without trusting whoever built it. Pass a path to check any
  file: `gk2port --verify "your.nds"`.
- **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** — the handful of things that actually go
  wrong (wrong ROM, Collection not found, freeing the 7 GB install, unsigned-binary
  warnings) and how to fix each.

## New in v1.3.1 — three autopsy descriptions stop contradicting the testimony

The Episode 2 rebuttal cites the autopsy report's *stab wound* — official dialogue
in this ROM — while the Court Record description of the body still said the fan's
*"single blow to base of neck"*, because Capcom's wording didn't fit the DS's
4-line description box. In a series about spotting contradictions, the game
contradicting itself is the one thing text must never do.

Those three descriptions (and only those — the ~100 other over-long descriptions
keep the fan's fitting text, which agrees with the dialogue) are now Capcom's
wording, lightly condensed to fit. The condensations live in the repository as
word-index edit operations with a result checksum — no game text — applied at
build time to the text you extract from your own Collection, and falling back to
the fan line if your Collection's wording ever differs.

## New in v1.3.0 — the last big recoveries, and a jump-index repair

- **The confrontation line banks are official now.** The "argument" lines you pick
  during rebuttals and Logic Chess (236 rows, e.g. *"Yet, I will be heard!"*) were at
  0% because their file only exists in the Collection's trial bundle. They now swap
  row-by-row, each line verified single-line and no wider than the widest line the
  fan translation ever displayed in that widget.
- **The two biggest fan-kept scenes are recovered** — a courtroom stretch of Episode 4
  and an Episode 2 investigation scene (~12k characters) whose restructuring was
  beyond the previous release's tools: the region aligner now handles multiple joins
  in one entry and regions re-cut into a different number of strings, under the same
  strict structural verification as everything else.
- **A latent v1.2.1 defect is repaired.** In five recovered entries, the jump index
  carried at the end of some strings (which string the engine plays next) was copied
  from the official layout's numbering, off by the recovery's own re-cutting — 33
  strings in Episodes 2/4/5, including two that jumped to themselves. All jump
  indices are now taken from the fan layout, and a whole-ROM scan verifies zero
  divergence. These scenes had never been played on any build; if you hit an odd
  text loop there on v1.2.x, this was it.
- Coverage: **96.9% → 98.4%**. Episode 2 is 99.9%, Episode 4 98.4%, Episodes 3 and 5
  stay 100%.

| Episode | Official | character units |
|---|---|---|
| 1 — Turnabout Target | 97.7% | 175,426 / 179,476 |
| 2 — The Imprisoned Turnabout | 99.9% | 368,376 / 368,710 |
| 3 — The Inherited Turnabout | **100%** | 377,753 / 377,753 |
| 4 — The Forgotten Turnabout | 98.4% | 292,972 / 297,665 |
| 5 — The Grand Turnabout | **100%** | 497,837 / 497,837 |
| Menus & UI | 81.7% | 91,148 / 111,600 |
| **Total** | **98.4%** | 1,803,512 / 1,833,041 |

## New in v1.2.1 — one restored NPC line

A post-release audit of every string in the ROM against the fan original found
exactly one real text loss: an Episode 1 free-roam NPC line ("Thank you for
waiting! There's nothing unusual here!") that the Collection's own files leave
empty, small enough to slip between two guards' thresholds. It could have shown
an empty box — or hung — if examined. A final safety net now restores any short
English fan line whose official replacement is empty; audited ROM-wide, it
changes exactly that one string.

The same audit settled a long-standing unknown: the argument on the string
terminator is the index of the next string to jump to, which proves the
v1.2.0 seam rebuilds carry the correct value by construction.

## New in v1.2.0 — most of what was missing is recovered

The fan patch restructured the script in ways that used to force whole scenes back to
fan text. This release understands and inverts that restructuring, always verified
structurally before a single string is touched:

- **9 entries** where the fan split one long retail string into two are split back at
  the fan's own cut point — three independent sources (fan layout, Collection script,
  retail-JP structural profile) must agree on the fingerprint first.
- **74 strings across 33 entries** where the fan moved message boxes between
  neighbouring strings are rebuilt in the fan's layout by re-cutting the official
  text at the fan's own boundaries. The gate is strict per-string box-code equality;
  anything that doesn't reproduce the fan structure exactly stays fan.
- **5 Episode 1 entries** (46k characters) were being rejected wholesale because one
  to three strings each are empty or `DEMO TEXT` in the Collection's files. Those
  hollow strings now revert individually; the rest of each entry is official.
- **25 more evidence descriptions** fit their box after the DS-only "see the detail
  view" tail (this project's own wording, not Capcom's) was shortened to one line.

Zero message boxes are lost anywhere: across all 931 strings of the 48 entries that
changed since v1.1.0, every string's box structure matches the fan layout the engine
was built against, verified mechanically at build time.

## Testing status — read this if you play deep into the game

Every release is verified structurally (every string audited against the fan layout,
seven audits covering the defect classes that have shipped before) and exercised in
melonDS by a scripted rig. What that rig has actually executed, measured: all 25 chapter
saves boot, load and advance; about 5,100 of the game's 41,706 message boxes have been
displayed, weighted toward chapter openings and finales; and on the 1.5.0 candidate an
Episode 1 run from a cold-boot New Game, following a walkthrough, has covered the opening,
the first investigation, the first Logic connections, the first Mind Chess to checkmate
and the second investigation area with zero defects. **Nobody has finished an episode
yet**, on any release. Both hangs this project ever shipped were found by playing, not by
audits, and both were in interactive scenes rather than dialogue, so that is where a
report helps most.

On hardware, 1.4.4 booted and reached gameplay from a DSPico flashcart on a 3DS; nothing
deeper has been tried on real hardware, and no original DS has been tried at all.

If the game ever hangs mid-scene: **your save is not damaged**, text is read-only data.
Restart the chapter and open an issue saying where it happened. Issue #1 is the thread
for playtest reports.

## Downloads

| Platform | File |
|---|---|
| Windows | `gk2port-windows-x64.exe` |
| Linux (glibc 2.35+) | `gk2port-linux-x64` |

Checksums are in `SHA256SUMS`. On Linux, `chmod +x` it first. Windows SmartScreen will
warn about an unrecognised publisher, because the binary is unsigned and certificates
cost money - check the hash, or build from source. `gk2port --selftest` confirms your
download is complete.

**macOS: build from source for now.** A macOS binary compiles and self-tests fine in CI,
but nobody has run one on an actual Mac, and shipping a binary no one has executed is
not much of a favour.

## You need to supply

| | |
|---|---|
| **Gyakuten Kenji 2 (AAI2 Final v2)** | The fan-patched DS ROM — supplies the variable-width font and English graphics |
| **Ace Attorney Investigations Collection** | The **PC** build — tested on Steam |

**No game data is included in this download.** Both inputs are files you own.

There is deliberately no patch file. A delta from the fan ROM to the ported one *is*
Capcom's script, so distributing one would distribute the localization — the thing this
project is built to avoid. Owning the Collection is the reason this can exist.

Console builds are untested. The bundle lookup matches by name prefix and ignores the
platform folder name, so an already-extracted Switch or PS4 dump may work — but nothing
here has been run against one.

## Rebuilding without the Collection installed

The Collection is only read during extraction. Once `dump/` exists it holds everything
the injection needs, so you can free the ~7 GB install and still rebuild:

```
gk2port --fan-rom "GK2 (AAI2 Final v2).nds" --skip-extract
```

That needs the fan ROM and `dump/` (~55 MB) and nothing else. Verified byte-identical
to a full run. The wizard does this by itself if it finds `dump/` and no Collection.

## Notes

- The output ROM is **not redistributable**: it contains Capcom's copyrighted
  localization and the fan translation's assets. Build your own.
- Episode names stay the fan's. Capcom renamed all five, but those appear on the
  episode-select screen as a bitmap, so changing only the save-slot text would show two
  names for one episode a menu apart.
- The **[AAI2 Final v2 fan translation](https://www.romhacking.net/translations/2260/)**
  team did the hard part — this is built entirely on top of their patch, and without it
  there is nothing to inject into, no font to render the result, and no English voice
  clips (theirs stay, and they recorded them). Their ATTENTION notice is left intact in
  every build. If you haven't played their translation, play it.
- The tooling was written with **LLM assistance** (Claude Opus 5, via Claude Code). The
  measurements and format work are reproducible by running the tools; the bugs that
  mattered were found by humans and emulator testing. See the README for the full note.
