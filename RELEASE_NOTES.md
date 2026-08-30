Port Capcom's official English localization of *Gyakuten Kenji 2* into the Nintendo DS ROM.

**98.4% of the script's text becomes Capcom's** (1,803,512 of 1,833,041 character
units, measured by `tools/coverage.py` — a new, reproducible counting; not directly
comparable to the old release's "85.7%", whose methodology differed). The remainder
stays in the AAI2 fan translation — see the README for exactly why, and which parts.

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

This release was verified structurally (every recovered string byte-audited against
the fan layout), independently reviewed, and exercised with roughly fifteen thousand
scripted inputs across Episode 1 and 2 chapters in melonDS with zero defects. But
the newly recovered scenes in **Episodes 2, 4 and 5 have never been played
end-to-end by a human** — true of every release of this project so far, now true of
less text than ever.

The scenes to watch, if you want to help: the *"How Knight Wound Up in the Prison
Proper"* argument and the *Kanis testimony* (Ep 2, End Part 1), the circus-performer
conversation (Ep 2), and a handful of Ep 1/4 scene transitions. If the game ever
hangs mid-scene: **your save is not damaged** — text is read-only data. Restart the
chapter, and please open an issue saying where it happened. v1.1.0 remains
downloadable if you prefer the more conservative build.

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
