# Prosecutor's Path

**Port Capcom's official English localization of *Gyakuten Kenji 2* into the Nintendo DS ROM:
the script, the title logo, the episode titles, the Logic keyword cards and the voice clips.**

*Gyakuten Kenji 2* (2011) never received an official English release on the DS. The
community filled the gap with the excellent **AAI2 Final v2** fan translation. Thirteen
years later, Capcom localized the game themselves for the *Ace Attorney Investigations
Collection* (2024).

This toolchain takes Capcom's own script, art and voice recordings and injects them into
the DS game, so you can play the official localization on original hardware, on a
flashcart, or in an emulator.

**93.8% of the script's text is Capcom's writing**, measured by `tools/coverage.py`, so
you can recompute it. Earlier releases said 96.5%; that figure counted fan-written rows
as official once Capcom's character names had been swapped into them, which is not the
same thing. The remainder stays in the fan translation, for reasons documented in
[What doesn't port, and why](#what-doesnt-port-and-why).

> ### Playtesters wanted
>
> Nobody has finished an episode, and solving a rebuttal has never been tested by
> anyone. Of the game's ~41,700 message boxes, about 5,100 have been executed by a
> script that can only press A and tap, and several hundred more by hand: Episode 1
> chapter 1 end to end, Episode 2 chapters 1 and 2, and part of chapter 3. Every bug
> this project has had was found by a person playing, and none by an offline check,
> including the two most recent.
>
> **[Report anything that stops in issue #1](../../issues/1)**, which episode and
> chapter is enough. Your save is never at risk; the text is read-only data, so a
> hang costs you the chapter and nothing else.

**The cast uses Capcom's names throughout**, not just in dialogue: the nameplates above
the text box and the evidence and profile cards are *graphics*, and they are redrawn at
build time in the fan patch's own pixel font. Five individual lines in the whole game
still carry a fan name because even Capcom's surname is wider than the line the fan
drew; they are listed in the release notes. See
[Names](#names-are-capcoms-including-the-ones-that-are-graphics).

**The title screen, the episode-select buttons, the episode splash cards and the save
screen all carry Capcom's titles** as of 1.5.0: the official logo and the two fonts are
read out of your own Collection at build time and rendered into the DS graphics. See
[Episode titles and the title screen](#episode-titles-and-the-title-screen).

> **This repository contains no game data.** No ROM, no script, no extracted text: only
> the tools. You supply your own legally-obtained copy of the DS game and your own
> installation of the Collection.

---

## What you need

| | |
|---|---|
| **Gyakuten Kenji 2 (AAI2 Final v2)** | The fan-patched DS ROM. It supplies the variable-width font and English graphics, without it, nothing renders |
| **Ace Attorney Investigations Collection** | The **PC** build, tested on Steam. The script lives in the Unity Addressables bundles under `GK12_Data/StreamingAssets/aa/` |
| **Python 3.9+** | Only if building from source. `pip install UnityPy Pillow` |

## Usage

Download the build for your platform from
[Releases](https://github.com/Akoi89/prosecutors-path/releases). No Python, and nothing
else to install.

| | |
|---|---|
| Windows | `gk2port-windows-x64.exe` |
| Linux (glibc 2.35+) | `gk2port-linux-x64` |

**macOS: build from source for now.** A macOS binary compiles and self-tests fine in
CI, but nobody has run one on an actual Mac yet, and shipping a binary no one has
executed is not much of a favour. `pip install UnityPy Pillow` and use `tools/build.py`
instead, which works the same way.

### The short version

Put it in a folder of its own **next to your fan ROM** and run it with no arguments.
On Windows that means double-clicking it. It finds the ROM, searches your Steam
libraries for the Collection, shows you what it found, and asks before doing anything:

```
  fan ROM     Gyakuten Kenji 2 (AAI2 Final v2).nds   [verified AAI2 Final v2]
  Collection  D:\Steam Games\steamapps\common\Ace Attorney Investigations Collection
  output      C:\gk2\out\GK2 (Official English, DS port).nds

  Build? [Y/n]
```

It extracts what it needs into `dump/` beside itself and writes the ROM to `out/`.
Takes a couple of minutes.

You can also drag the `.nds` onto the program, or pass paths yourself:

```
gk2port-windows-x64.exe --fan-rom "GK2 (AAI2 Final v2).nds" --collection "C:\Program Files (x86)\Steam\steamapps\common\Ace Attorney Investigations Collection"
```

`--collection` accepts the game folder, the `StreamingAssets/aa` folder, or the platform
folder inside it, and is only needed when auto-detection fails: a non-Steam copy, or a
console dump you extracted yourself.

### Linux

It's a terminal program. Mark it executable and run it:

```bash
chmod +x gk2port-linux-x64
./gk2port-linux-x64
```

Steam auto-detection knows the usual locations, including Flatpak's. The Collection is a
Windows game, so it will be a Proton install, which lives in an ordinary Steam library
and is found the same way.

The binary is built on Ubuntu 22.04, so it needs glibc 2.35 or newer. On anything older,
build from source.

> **Console builds are untested.** The bundle lookup matches by name prefix and does
> not care which platform folder it finds, so a Switch or PS4 dump you have already
> extracted yourself may well work. Point `--collection` at the extracted folder. But
> nothing here has been run against one, so treat it as unknown rather than supported.

The binaries are unsigned, so Windows SmartScreen will complain. Certificates cost
money. Every release ships a `SHA256SUMS` file, the binaries are built in public by
[GitHub Actions](.github/workflows/build.yml) rather than on someone's desktop, and
`gk2port --selftest` checks that the one you downloaded is complete.

### Checks before it builds

- **The fan ROM is verified by hash.** Point it at a raw Japanese cart or a different
  patch and it stops and says so, instead of producing a ROM that boots to a black
  screen with no explanation. `--any-rom` overrides it, but expect the black screen.
- **It refuses to overwrite its own input**, which is easy to do by accident once a
  previous output is sitting next to the fan ROM.

### Checking a build

`gk2port --verify` hashes a built ROM and checks it against the version's published
reference. A MATCH means it is the genuine, unmodified output of the tool, so you can
trust a ROM without trusting whoever built it. Pass a path to check a specific file:
`gk2port --verify "path\to\rom.nds"`. Something going wrong? See
[TROUBLESHOOTING.md](TROUBLESHOOTING.md).

### From source

```bash
pip install UnityPy Pillow
python tools/build.py --fan-rom "...nds" --collection "..."
```

See [BUILDING.md](BUILDING.md) to rebuild `gk2port.exe`, to regenerate the metadata
files that ship in `dump/`, or for the one known gap in the control-code table.

### Rebuilding without the Collection installed

The Collection is only read during *extraction*. Once `dump/` exists it holds everything
the injection needs, so you can free the 7 GB install and still rebuild forever:

```
gk2port-windows-x64.exe --fan-rom "GK2 (AAI2 Final v2).nds" --skip-extract
```

The wizard notices this by itself: if `dump/` is already there and the Collection isn't
installed any more, it says so and carries on.

That needs the fan ROM and `dump/` (~70 MB: the script dumps plus the title assets and
voice clips pulled from the Collection) and nothing else. Verified byte-identical to
a full run.

Or run the injection alone:

```bash
python tools/inject.py "Gyakuten Kenji 2 (AAI2 Final v2).nds" -o out/GK2-official.nds
```

The build prints a full audit of what it did and, crucially, what it refused to do:

```
strings patched from localization tables:  343
episode titles switched to official names:   27
kept-fan strings renamed to official names:  64
entries replaced with official English: 423
entries where a joined string was split back: 11
relaid strings rebuilt in the fan layout:   74
hollow official strings kept as fan:       36
rows kept as fan to keep their message box: 4
rows kept as fan to keep a DS-only command:  105  (in 67 script banks)
sparse official banks swapped row-by-row: 2 (853 rows kept fan)
records kept as fan - still Japanese:       347
records kept as fan - fan relaid it vs JP:    38
records kept as fan - would lose a message box: 3
records kept as fan - official-only control code: 21
kept fan text - string count mismatch:  3
kept fan text - control-code shape off:  8
nameplates redrawn with official names:      147
title screen: official logo 248x116 at (4,30), 439/768 tiles, 222 colours
logic keyword cards: 97 of 133 slots named officially, 194 card images rewritten
choice strips redrawn with official text: 297 (48 condensed, 20 at a smaller size, 0 without English)
voices: 13 shouts in Capcom's English, sound archive 11066644 -> 11282047 bytes
```

Every one of those counters is a guard that fired. They exist because each one, once,
broke the game. The three at the bottom of the guard list were each added after a
specific hang, and the last two lines of the injection report exist because a player
hit the thing they now prevent.

---

## Coverage

| Episode | Official | character units |
|---|---|---|
| 1. *Turnabout Trigger* | 86.4% | 155,050 / 179,474 |
| 2. *The Captive Turnabout* | 91.0% | 335,523 / 368,696 |
| 3. *Turnabout Legacy* | 97.6% | 368,827 / 377,751 |
| 4. *A Turnabout Forsaken* | 95.9% | 285,437 / 297,663 |
| 5. *Turnabout for the Ages* | 96.1% | 478,208 / 497,811 |
| Menus & UI | 86.9% | 96,934 / 111,588 |
| **Total** | **93.8%** | 1,719,979 / 1,832,983 |

**These are lower than the 96.5% every release since v1.4.0 quoted, and the ROM did not
get worse; the counting got honest.** `tools/coverage.py` used to call a string official
whenever its bytes differed from the fan ROM's, on the premise that the injector only
replaces whole strings. That stopped being true in v1.4.0, when the rename pass started
swapping Capcom's character names into fan-written rows: 84 long conversations
were counted as official because a name in them had changed. As of 1.5.0 a row counts as
official only if it differs from the fan row *after* that row has been given the official
names and episode titles, so a fan-written line with "Bronco Knight" in it is fan text,
which is what it is. Measured this way v1.4.4 was 93.8%, not 96.5%.

Two figures in this file have been wrong before, both remembered rather than measured;
this third one was measured, by a rule that had quietly stopped meaning what it said.
Every number in this table is what `tools/coverage.py` printed for the ROM whose hash
`--verify` checks. If you build it yourself and get different numbers, the README is the
thing that is wrong.

The counting is `tools/coverage.py`: character units (everything that is not a control
code or one of its arguments) in strings whose bytes differ from the fan ROM after names
and titles, over all character units. Earlier releases quoted "85.7%" from a methodology
that did not survive; the two numbers are not directly comparable.

Also ported: evidence and profile descriptions, Logic card text, and the Organizer
messages, none of which live in the script files at all. They come from the Collection's
Unity Localization string tables, matched through the Japanese text.

---

## Names are Capcom's, including the ones that are graphics

Capcom renamed most of the cast. With the dialogue in their words, the fan's names had
become the inconsistency rather than the tradition: the text said *Fender* while the
nameplate above it said *Ray* and the Organizer said *Raymond Shields*.

All three now agree. The text is the easy part; the other two are **graphics**:

- **28 dialogue nameplates**: `jpn/idlocal.bin` entries 27-86, one LZ11'd 144×8 tile
  strip each, with a 43-pixel text field.
- **119 evidence and profile title cards**: 128×16 strips inside that same file's
  sprite bundles, drawn as four 32×16 OAM objects.
- **297 choice and topic buttons**: the option plates of every choice menu and
  talk-topic list, entries 364-670 of the same file (224×32 and 144×32 sprite bundles).
  These are where a fan name could still reach the screen after 1.5.1: one Episode 1
  choice offered *Nicole Swift* as an option while the script around it said *Tabby
  Lloyd*.

Neither can be swapped as text, so they are **redrawn at build time in the fan patch's
own pixel font**, which the tool recovers from your own ROM, by cutting the letters out
of the cards whose wording it already knows. Nothing but Capcom's names and a handful of
hand-drawn glyphs for letters the fan set never used ships in this repository.

The fan→official mapping was derived from the two scripts rather than from memory: for
every line present in both translations, fan names were paired with the official names in
the same line. That caught what recall would have missed: *Nicole Swift* is officially
*Tabby Lloyd*, the monster *Moozilla* is *Taurusaurus*, and the chairman's nickname
*Blaisie* is *Celsius*.

The choice buttons are different again: their wording is Capcom's option text, not a
name, so each plate had to be paired with its Collection string first. That pairing was
made from the retail Japanese ROM, whose plates sit at the same entries: the Japanese
lettering on each was matched glyph by glyph to the Collection's own Japanese select
tables, and the English follows from the id, never from guessing which English sentence
"means the same" as the fan's. `tools/select_strips.json` ships that pairing as numbers
only; the text is read from your Collection at build time and set in its UD Kakugo M
face on the fan's plates (`tools/choice_strips.py`). Long options condense by up to 12%
and then step down a size, as the episode titles do.

`tools/names.py` holds the map and rewrites only strings that are byte-identical to the
fan ROM's, so official text is never touched: 64 whole rows in the current build, more
rows renamed line by line where a whole-row rename would not fit, plus 147 nameplates
redrawn. Since 1.5.1 no line in the game keeps a fan character name: the five that the
official name pushed past their box carry hand-shortened lines (`ROWFIX` in `names.py`),
and a scan of the built ROM finds zero fan names in kept-fan text. See the width guard
under [Guards](#guards). `tools/plates.py` does the graphics.

---

## How it works

### The container

Both the DS ROM and the Collection store dialogue in a ` TPS` (SPT) container, the
Collection inherited the DS format wholesale. The DS uses 16-bit fields, the Collection
32-bit. Text is UTF-16LE **XOR 0x55AA**; code points `0xE000-0xF8FF` decode as control
codes rather than characters.

Two traps cost real debugging time:

**A file holds n+1 strings, not n.** String 0 is described by the header (offset `0x0C`,
length `0x0E`); the record table covers strings 1..n. Miss it and every script file
silently truncates: the game boots, reaches the first scene, and goes black.

**The fan patch changed what offsets mean.** Retail ROMs store byte offsets. The fan
patch reads them as 16-bit *unit* offsets, doubling the addressable range from 64 KB to
128 KB. Write byte offsets into a fan ROM and it black-screens. `spt.offset_scale()`
detects which convention a file uses by checking whether the data start matches the
computed header size, or half of it.

### Reflowing the text

The DS message box is three lines of a variable-width font. Capcom's is much wider, and
their script is full of line breaks that belong to *their* box, not to the sentence.

Measured across the whole English corpus: **20,516 of 26,172 newlines end a line of
40-59 visible characters, and none ever exceeds 59**: the signature of a fixed-width
wrapper, not an author's choice. Honouring them produced messages like:

```
The moment
the phone rang, I knew it was
serious.
```

Only the **79** newlines immediately followed by `{E20D}` are structural, because that code
opens a new laid-out row on a date/location card. Everything else is folded to a space
and re-wrapped by pixel width. `dstext.convert(hard_nl=...)` selects the policy.

### Aligning to the right reference

This is the subtle one, and getting it wrong hung the game.

The obvious move is to check your output against the fan ROM you're injecting into.
That's the wrong ruler: **the fan ROM is the thing that was rearranged.**

Capcom's script matches the *retail Japanese* DS script box-for-box. The fan patch
redistributed message boxes between strings in **54 of 429 entries**, always as a matched
pair: `DS[4]` moves +8 boxes into str3 and −8 out of str4; `DS[27]` is −38/+38; `DS[60]`
is +23/−23.

Swap such a string per-index and the fan shows the moved boxes, then the official text
**replays them**, and everything after shifts by 8, landing on top of whatever the DS
keeps at those indices. For `DS[4]` that's the Logic tutorial and the *Gourd Lake Park:
Stage* location card. The engine waits on them. They never arrive.

Box-count-based guards can't see this: the official string has *more* boxes (63 vs 55),
not fewer. The fix is to compare each string's box count against the **Japanese DS ROM**
and revert only the strings whose count moved. Doing this per-string rather than
per-entry was worth about ten points of coverage on its own. v1.2.0 goes further:
where a whole RUN of neighbouring strings was relaid with its box total conserved, the
official strings are joined and re-cut at the fan's own boundaries, the layout the
engine was built against, with strict per-string box-code equality as the gate. The
same trick inverts the fan's habit of splitting one long retail string into two
(the retail JP and the Collection both hold the joined form; the split point is
recovered from three independent structural fingerprints). What used to be reverted
wholesale is now mostly rebuilt.

You don't need that ROM, though. The guards want *counts*, never text: message boxes per
string, and a control-code histogram per entry. Those are integers, facts about the file's
structure rather than its content, so they ship as `dump/jp_structure.json` (214 KB) and
the retail Japanese cart drops off the requirements list entirely.
`tools/jp_profile.py` regenerates it if it ever needs updating.

### Guards

Structural failures don't show up in a format check: the file parses perfectly and the
game hangs anyway. Each guard below exists because it happened:

- **Scene redistributed across strings**: a string with >200 printable DS characters
  whose Collection counterpart has under 20% of that. Rejects the entry.
- **Message-box loss**: losing ≥2 boxes reverts that string. Losing exactly *one* is
  benign and very common (868 of 913 cases, measured before the v1.2.0 rebuilds):
  the localization merged a pair.
- **A row that loses its box entirely** (v1.4.2): if the Collection has nothing for a
  row, the replacement has no message box at all, and a box that opens with nothing in
  it never closes. Such a row keeps the fan's, *in any language*: untranslated text is a
  blemish, a lost box is a lock.
- **Official-only control codes** (v1.5.2): the Collection's script carries two codes the
  DS engine has never seen, `E2A0` (its form of the DS `E10D`, the opener of the
  `E10D`/`E10E` scripted-wait pair) and `E2B0` (an inline button icon). The engine skips a
  code it does not know and then reads the code's arguments as text; a `0` argument ends
  the string, `E10E` is left orphaned, and the scene stops with the music playing and no
  input accepted. Every release through 1.5.1 hung there, 15 sites in 12 strings, the first
  one in Episode 1 right after the bodyguard's introduction. `dstext.OFFICIAL_TO_DS`
  translates `E2A0`; the injector keeps the fan's string whenever a converted string still
  carries any code absent from the fan script (`records kept as fan - official-only
  control code`), which is what handles the five `E2B0` tutorial lines.
- **DS-only engine commands** (v1.4.3): the guard that matters most, and the one that
  took three tries to get right. See below.
- **Option-widget width**: the confrontation and Logic Chess widgets have no measured
  width, so the budget is the widest line the fan ever displayed in that widget. Anything
  wider keeps the fan's line rather than risk a clipped word.
- **A renamed line that no longer fits** (v1.4.4): Capcom's names are often longer than
  the fan's, so substituting one into a kept-fan row can push a line past the edge of its
  box. The build re-breaks the row to fit. When it can't, usually because the over-wide
  line ends a box, leaving nowhere to push the word, that row keeps the fan's name. Ten
  rows do. A single line still reading the fan's name costs less than a clipped one.
  This guard is why the previous release shipped ten clipped lines and this one doesn't:
  v1.4.3's DS-only revert handed the rename pass many more rows to work on (84, up from
  45), and some of them didn't fit.
- **Per-record defects**: Capcom's English bundle contains `DEMO TEXT` placeholders and
  untranslated Japanese, but *per record*, not per file. Guarding at file level threw
  away 16,780 letters of perfectly good English.
- **Control-code shape**: a wrong file match shows as near-zero overlap in the
  control-code profile against the Japanese original.

### Counting boxes is not enough

This section used to end here, and the game hung anyway.

Capcom's script has no touch-screen, A-Button or Logic tutorials, because those are
DS-only. Converting it can therefore drop the engine commands that drive them. The guard
above tried to catch that by counting message boxes, on the reasonable-sounding logic
that missing content means missing boxes.

It does not. Capcom's prose is **longer**, so the converted string ends up with *more*
boxes than the fan's while the command inside it is gone. `DS[4]` str3 came out with 18
boxes against the fan's 16 (a healthy-looking number) and Episode 1 never handed the
player control at the Gourd Lake stage. Nameplate over an empty box, music playing,
nothing to press.

So the guard now compares the **commands**, not the boxes: a string that would drop an
`E041`/`E042` pair keeps the fan's line. That is 105 rows across 67 script banks,
living in the partner-conversation, examine-check and NPC entries where DS-only
interaction sits throughout the game. Worth stating plainly, because the first
announcement of this fix got it wrong: these are *not* concentrated in Episode 1's
tutorial opening. Episode 1 is where one of them happened to lock the game.

`rig`-side, `audit_cmdloss.py` answers the obvious follow-up (*is another command being
dropped the same way?*) by computing, for every control code, how often the fan string
carries it against how often ours drops it. A ratio near 1.0 means the official script
essentially never has that code, which is the signature of DS-only content. The highest
ratio in the current build is 0.28, on a formatting code the official script uses 62,000
times. Nothing is hiding.

---

## What doesn't port, and why

The floor isn't laziness. It's structural, and it breaks down cleanly:

What remains fan (~5.7% of the script):

- **DS-only tutorial and interaction strings**: 105 rows whose official replacement
  drops an engine command the DS build needs. The largest single category, and the newest:
  see [Counting boxes is not enough](#counting-boxes-is-not-enough).

- **Relaid strings with no rebuildable partner**: 38 strings whose box counts moved
  against the retail layout in ways the run-rebuild cannot verify (lone strings, or
  runs where the official uses a different box-end variant, e.g. `DS[236]`).
- **Evidence descriptions and Logic cards that overflow their box**: official English
  exists for 108 of them but does not fit the DS's 4-line description box (or the 3-line
  Logic card). Until 1.5.0 those rows kept the fan's text. **As of 1.5.0 they carry Capcom's
  wording, condensed to fit**: the Japanese source says what must survive, Capcom's English
  supplies the words, and the fan line proves what fits. Nothing is paraphrased where a
  deletion will do, names and facts are kept, and hedges are kept ("appears to", "I have my
  doubts"). The edits ship as word-index operations over the official text
  (`tools/condense_generated.py`, produced by `rig/desc_fit.py` from a reviewed list), so no
  Capcom text sits in the repo, and each entry carries a result hash: a Collection whose
  wording differs falls back to the fan line instead of applying a stale edit. To check
  them, `python tools/desc_overflow.py OUT.txt` lists every affected row four ways
  (Japanese, Capcom, condensed, fan) from your own extracted data. Together with the earlier exceptions that makes **126
  rows where Capcom's wording is edited**: these 108, 3 hand-condensed descriptions in
  `tools/condense.py`, 8 over-wide card titles in `tools/plates.py` (`TRIMS`), and 7 renamed
  rows in `tools/names.py` (`ROWFIX`).
- **Hollow official strings**: a few strings are empty or `DEMO TEXT` in the
  Collection's own files.
- **Menus & UI residue**: DS-only interface text with no official counterpart.

DS-only content is the recurring theme. The touch-screen tutorials, the button prompts,
the Logic walkthrough, because Capcom's version targets hardware without a second screen or an
L button, so no official wording has ever existed for a lot of it.

## Episode titles and the title screen

Capcom renamed all five episodes (*Turnabout Target* → *Turnabout Trigger*, *The
Imprisoned Turnabout* → *The Captive Turnabout*, *The Inherited Turnabout* → *Turnabout
Legacy*, *The Forgotten Turnabout* → *A Turnabout Forsaken*, *The Grand Turnabout* →
*Turnabout for the Ages*). The names live in four places, and since 1.5.0 all four say the
same thing:

- **Save screen text**: 27 strings in `DS[460]`, switched by `tools/episode_titles.py`.
- **Episode-select buttons** and **episode splash cards**: sprite graphics in
  `jpn/save_local.bin` and `jpn/opening_local.bin`. `tools/title_text.py` renders the
  official names into the existing sprites using two fonts pulled from *your* Collection
  at build time: Modé Mina B for the splash cards, which turns out to be the very face the
  fan team was imitating by hand, and UD Kakugo M for the buttons. Nothing is drawn
  outside the sprites the game already draws.
- **Title screen**: the official English logo sprite (`GK2_Logo_R_eng`) is read from the
  Collection, laid out over the fan's copyright line, and written into `jpn/title_local.bin`
  by `tools/extract_logo.py` and `tools/title_logo.py`. The build's version number is painted into the
  empty top-right corner of that picture (`tools/title_version.py`), so any screenshot says
  which build it came from.
- **Logic keyword cards**: the 133 keyword cards on the Logic board (and the banner each one
  shows above its description) are images in `jpn/logic_keyword_local.bin`, lettered by the
  fan team in their own words ("Ruptured balloon" where Capcom wrote "Popped balloon"). The
  DS never stores those names as text, only each keyword's Japanese description, so
  `tools/logic_names.py` joins the DS description to the Collection's description table and
  from there to the official name table, and `tools/logic_cards.py` repaints the card interior
  and renders the official name in UD Kakugo M, two lines on the card and one on the banner.
  97 of the 133 slots have an official name; the rest (30 unused dummies, 6 real keywords
  with no Collection counterpart) keep the fan lettering.

- **Voices**: thirteen of the shouts ("Objection!" and friends) are Capcom's 2024 English
  recordings, pulled from the Collection's sound bundle by `tools/voices.py`, resampled to
  each slot's retail format and rebuilt into `com/kenji2_sound.sdat`. The seven shout
  samples the Collection does not localise stay as the fan team recorded them.

No artwork, font or audio ships with the tool; like the script, all of it comes out of the
player's own install. `tools/ncer.py` is the cell-bank reader that made the sprite work
possible, and `tools/title_art.py` exports the pieces for inspection.

The game's title screen therefore reads *Prosecutor's Gambit*, Capcom's title, while this
project keeps the name it started with.

---

## Tools

Everything under `tools/` builds the ROM. Everything under `audits/` checks one after
the fact. Each takes an optional ROM path, so you can point one at any build:

```bash
python audits/audit_boxes.py            # did any string lose a message box?
python audits/audit_fixtures.py         # prove the audits can actually fail
```

| | |
|---|---|
| `audits/audit_boxes.py` | Any string with fewer message boxes than the fan's (the v1.4.2 hang) |
| `audits/audit_empty.py` | Strings emptied of text that the fan ROM had |
| `audits/audit_arity.py` | Control-code arguments corrupted into text (the v1.3.3 hang) |
| `audits/audit_cmdloss.py` | Is another DS-only engine command being dropped? (the v1.4.3 hang) |
| `audits/audit_widgets.py` | Option lines wider than the fan ever proved that widget can draw |
| `audits/audit_titles.py` | Every redrawn card keyed off the right source title |
| `audits/audit_hint.py` | Any SPT buffer hint too small for its own data |
| `audits/audit_fixtures.py` | Breaks a copy of your build four ways and checks the audits notice |
| `spt.py` | SPT container parser, both variants, with offset-scale detection |
| `build_spt.py` | SPT writer |
| `dstext.py` | Text conversion: fullwidth mapping, pixel wrapping, page breaks, control-code arity |
| `build.py` | One-shot entry point: extract everything, then inject. This is what the released binaries run |
| `locate.py` | Finds the fan ROM and the Collection, and verifies the ROM by hash |
| `jp_profile.py` | Regenerates `dump/jp_structure.json`, the shipped structural counts from the JP script |
| `ctrl_args.py` | Regenerates `dump/ctrl_args.json`; `--check` diffs a fresh derivation against it |
| `inject.py` | Mapping, structural guards, ROM rebuild |
| `loc_patch.py` | Evidence, profiles and Logic cards from the Unity Localization tables |
| `logic_names.py` | Maps each DS Logic keyword slot to Capcom's official short name |
| `logic_cards.py` | Renders those names into the Logic card and banner images |
| `voices.py` | Capcom's English shouts from the Collection into the DS sound archive |
| `names.py` | The fan→official character-name map, applied only to strings that kept fan text |
| `plates.py` | Redraws the nameplate and title-card graphics in the fan's own pixel font |
| `choice_strips.py` | Sets Capcom's option text on the 297 choice/topic button plates; `select_strips.json` is the plate→string pairing |
| `build_map.py` / `map_ids.py` | Fuzzy n-gram matching of DS entries to Collection files |
| `lz11.py` / `nitro.py` | Nintendo LZ11 and NCGR/NCLR/NSCR/NCER/NANR |
| `episode_titles.py` | The official episode names in the save-screen strings (on since 1.5.0) |
| `title_assets.py` | Title logo, episode-title sprites and Logic cards: pulls the assets from the Collection and applies `extract_logo` / `title_logo` / `title_text` / `logic_cards` |
| `title_version.py` | Paints the build's version into the title screen's empty corner |
| `condense.py` / `condense_generated.py` | The word-index edits that fit 111 official descriptions into the DS box (result-hashed, no Capcom text) |
| `coverage.py` | The coverage figures above, recomputed from a built ROM |
| `desc_overflow.py` | Lists every condensed description four ways from your own extracted data |

---

## Credits

The **AAI2 fan translation team** did the hard part:

> **[Gyakuten Kenji 2: AAI2 Final v2](https://www.romhacking.net/translations/2260/)**
> on romhacking.net

This project is built entirely on top of their work: their variable-width font engine,
most of their English graphics, their voice recordings for the shouts Capcom never
localised, their menus, their ROM. Without the Final v2 patch there is nothing to inject
*into*, and no font capable of rendering the result. They also solved
problems this project simply inherits, like fitting English into a script laid out for
Japanese, and reworking the engine's string offsets to buy back address space.

If you have not played their translation, play it. It stood alone for over a decade and
it is genuinely good. This project is a different thing, not a better one: it swaps in
Capcom's wording, titles and voices for people who want the official script on hardware.

Their ATTENTION notice is left intact in every build, and should stay that way.

*Gyakuten Kenji 2* and the *Ace Attorney Investigations Collection* are © Capcom.

## How this was built

**Nothing here asks to be taken on trust.** Every figure in this README is reproducible
by running the tools on your own files: `tools/coverage.py` computes the coverage table,
and the format work behind it (20,516 of 26,172 newlines, 54 of 429 relaid entries) is
grounded in measurements over the real files rather than in anyone's recollection.
`--verify` hashes a finished build against the release's published reference, so a ROM can
be trusted without trusting whoever built it, and the published binary has been confirmed
to reproduce that hash byte-for-byte.

The seven audits in [`audits/`](audits) guard the structural failure classes, and **four
of them are tested against deliberately corrupted ROMs**. `audits/audit_fixtures.py`
breaks a copy of your build in exactly the way each one claims to detect and checks it
notices. Run it yourself; it never touches `out/`. One of those fixtures immediately
exposed a defect class that had no audit at all, which is why `audit_boxes.py` exists.
An audit that has never failed has not been tested, it has only been run.

Each audit also carries a `# SCOPE` block stating what it does **not** look at, because a
check with an unstated scope is how something goes unexamined without anyone being wrong
about anything.

The tooling was written with **LLM assistance**: Claude, driven through Claude Code, over
a series of sessions. That is stated plainly rather than buried, and so is the rest of the
record, including the parts that do not flatter it.

Because every hang this project has ever had was found by **playing the game**, and none
by any offline check, including checks written specifically to catch the previous one.
Three of them:

- a mode launcher whose argument had been converted into a letter, because the
  argument's constant value *was* the letter `D`;
- seven examine rows emptied so completely they lost their message box;
- Episode 1 refusing to hand over control, while the guard meant to prevent exactly that
  counted boxes and saw a healthy number.

Each was invisible to a format check: the file parses, the structure verifies, the game
stops anyway. Two of the three were found by a person who simply started playing and left
the emulator running when it froze, which turned out to be worth more than any audit run
that day.

The build's own output did catch one thing, though not a hang: v1.4.4's ten clipped lines
were sitting in a warning that v1.4.3 printed and nobody read, because the release was
already tagged by the time it scrolled past. A guard that reports into a wall of counters
only works if someone reads the wall.

So treat the guards as a record of what has actually gone wrong rather than proof that
nothing else will, and treat the code as reviewable rather than authoritative. It is about
3,500 lines across 28 modules, MIT licensed, and it ships as source precisely so you do
not have to take any of the above on faith. Read it before you trust it with a ROM you
care about, and recompute anything here that matters to you.

That is also why this is offered as a **test build** rather than a finished one, and why
[issue #1](../../issues/1) asks for players rather than for approval. Nobody has finished
an episode yet.

## Legal

This repository distributes **no copyrighted material**: no ROM, no script, no extracted
text, no graphics. It is a set of tools that operate on files you already own.

Building requires your own legally-obtained copy of both games. Do not redistribute the
output: it contains Capcom's copyrighted localization, and since 1.5.0 Capcom's logo
art, two of their fonts and thirteen of their voice recordings, alongside the fan
translation's assets. **If you want Capcom's translation, buy the Collection. It is very good, and it
is the reason this project can exist at all.**

### Why there is no patch file

The obvious way to make this easier would be an xdelta or IPS patch, so nobody needs the
Collection at all. That patch would *be* Capcom's script: a delta from the fan ROM to
the ported one contains the entire localization as its payload, which is the thing being
avoided, not a way around it. The same goes for the extracted `dump/` tree: the three
`.json` files in it are integers and filenames and do ship here, but `dump/eng` is
Capcom's text, and `dump/title` and `dump/voice` are Capcom's logo, fonts and audio.

Owning the Collection isn't a hurdle this project failed to remove. It's the reason the
project is allowed to exist.

## License

MIT for the tools. See [LICENSE](LICENSE). That covers the code only; the game data
it operates on is not ours to license, and none of it is distributed here. See
[NOTICE](NOTICE) for the exact scope.
