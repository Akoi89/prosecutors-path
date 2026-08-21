# Prosecutor's Path

**Port Capcom's official English localization of *Gyakuten Kenji 2* into the Nintendo DS ROM.**

*Gyakuten Kenji 2* (2011) never received an official English release on the DS. The
community filled the gap with the excellent **AAI2 Final v2** fan translation. Thirteen
years later, Capcom localized the game themselves for the *Ace Attorney Investigations
Collection* (2024).

This toolchain takes Capcom's script and injects it into the DS game — so you can play
the official localization on original hardware, on a flashcart, or in an emulator.

**85.7% of the on-screen text becomes Capcom's.** The remaining 14.3% stays in the fan
translation, for reasons documented in [What doesn't port, and why](#what-doesnt-port-and-why).

> **This repository contains no game data.** No ROM, no script, no extracted text — only
> the tools. You supply your own legally-obtained copy of the DS game and your own
> installation of the Collection.

---

## What you need

| | |
|---|---|
| **Gyakuten Kenji 2 (AAI2 Final v2)** | The fan-patched DS ROM. It supplies the variable-width font and English graphics — without it, nothing renders |
| **Ace Attorney Investigations Collection** | Any platform. The script lives in the Unity Addressables bundles |
| **Python 3.9+** | `pip install UnityPy Pillow` |

## Usage

Extract the Collection's script bundles into `dump/`:

```bash
python tools/dump_textassets.py "/path/to/Collection/StreamingAssets/aa" dump
```

Then build:

```bash
python tools/inject.py "Gyakuten Kenji 2 (AAI2 Final v2).nds" -o out/GK2-official.nds
```

The build prints a full audit of what it did and, crucially, what it refused to do:

```
entries replaced with official English: 404
records kept as fan - still Japanese:   347
records kept as fan - fan relaid it vs JP: 112
kept fan text - string count mismatch:   14
kept fan text - control-code shape off:  11
kept fan text - scene shifted between strings: 5
```

Every one of those counters is a guard that fired. They exist because each one, once,
broke the game.

---

## Coverage

| Episode | Official | Notes |
|---|---|---|
| 1 — *Turnabout Target* | 73.6% | Worst-aligned stretch in the game |
| 2 — *The Imprisoned Turnabout* | 82.4% | |
| 3 — *The Inherited Turnabout* | **99.9%** | Essentially pure Capcom |
| 4 — *The Forgotten Turnabout* | 74.7% | Large fan cluster in chapters 4–5 |
| 5 — *The Grand Turnabout* | 89.7% | |
| Menus & UI | 79.1% | |
| **Total** | **85.7%** | 1,657,842 of 1,934,287 characters |

Also ported: evidence and profile descriptions, Logic card text, and the Organizer
messages — none of which live in the script files at all. They come from the Collection's
Unity Localization string tables, matched through the Japanese text.

---

## How it works

### The container

Both the DS ROM and the Collection store dialogue in a ` TPS` (SPT) container — the
Collection inherited the DS format wholesale. The DS uses 16-bit fields, the Collection
32-bit. Text is UTF-16LE **XOR 0x55AA**; code points `0xE000–0xF8FF` decode as control
codes rather than characters.

Two traps cost real debugging time:

**A file holds n+1 strings, not n.** String 0 is described by the header (offset `0x0C`,
length `0x0E`); the record table covers strings 1..n. Miss it and every script file
silently truncates — the game boots, reaches the first scene, and goes black.

**The fan patch changed what offsets mean.** Retail ROMs store byte offsets. The fan
patch reads them as 16-bit *unit* offsets, doubling the addressable range from 64 KB to
128 KB. Write byte offsets into a fan ROM and it black-screens. `spt.offset_scale()`
detects which convention a file uses by checking whether the data start matches the
computed header size, or half of it.

### Reflowing the text

The DS message box is three lines of a variable-width font. Capcom's is much wider, and
their script is full of line breaks that belong to *their* box, not to the sentence.

Measured across the whole English corpus: **20,516 of 26,172 newlines end a line of
40–59 visible characters, and none ever exceeds 59** — the signature of a fixed-width
wrapper, not an author's choice. Honouring them produced messages like:

```
The moment
the phone rang, I knew it was
serious.
```

Only the **79** newlines immediately followed by `{E20D}` are structural — that code
opens a new laid-out row on a date/location card. Everything else is folded to a space
and re-wrapped by pixel width. `dstext.convert(hard_nl=...)` selects the policy.

### Aligning to the right reference

This is the subtle one, and getting it wrong hung the game.

The obvious move is to check your output against the fan ROM you're injecting into.
That's the wrong ruler — **the fan ROM is the thing that was rearranged.**

Capcom's script matches the *retail Japanese* DS script box-for-box. The fan patch
redistributed message boxes between strings in **54 of 429 entries**, always as a matched
pair: `DS[4]` moves +8 boxes into str3 and −8 out of str4; `DS[27]` is −38/+38; `DS[60]`
is +23/−23.

Swap such a string per-index and the fan shows the moved boxes, then the official text
**replays them** — and everything after shifts by 8, landing on top of whatever the DS
keeps at those indices. For `DS[4]` that's the Logic tutorial and the *Gourd Lake Park:
Stage* location card. The engine waits on them. They never arrive.

Box-count-based guards can't see this: the official string has *more* boxes (63 vs 55),
not fewer. The fix is to compare each string's box count against the **Japanese DS ROM**
and revert only the strings whose count moved. Doing this per-string rather than
per-entry is worth about ten points of coverage (76.0% → 85.7%).

### Guards

Structural failures don't show up in a format check — the file parses perfectly and the
game hangs anyway. Each guard below exists because it happened:

- **Scene redistributed across strings** — a string with >200 printable DS characters
  whose Collection counterpart has under 20% of that. Rejects the entry.
- **Message-box loss** — losing ≥2 boxes reverts that string. Losing exactly *one* is
  benign and very common (868 of 913 cases): the localization merged a pair.
- **Per-record defects** — Capcom's English bundle contains `DEMO TEXT` placeholders and
  untranslated Japanese, but *per record*, not per file. Guarding at file level threw
  away 16,780 letters of perfectly good English.
- **Control-code shape** — a wrong file match shows as near-zero overlap in the
  control-code profile against the Japanese original.

---

## What doesn't port, and why

The floor isn't laziness — it's structural, and it breaks down cleanly:

| Cause | Share |
|---|---|
| Fan-authored content, blank in the Japanese original too | 6.5% |
| Strings the fan patch relaid relative to the JP script | 3.8% |
| Individual lines inside otherwise-official scenes | 2.5% |
| Collection empty at that slot | 2.1% |
| Other | 0.4% |

DS-only content is the recurring theme. The touch-screen tutorials, the button prompts,
the Logic walkthrough — Capcom's version targets hardware without a second screen or an
L button, so no official wording has ever existed for a lot of it.

**Episode names stay the fan's.** Capcom renamed all five (*Turnabout Target* →
*Turnabout Trigger*, *The Imprisoned Turnabout* → *The Captive Turnabout*, and so on),
but those names appear on the episode-select screen as a **bitmap**, not text. Changing
only the save-slot labels would put two different names for one episode a single menu
apart. Set `RETITLE = True` in `tools/inject.py` if you disagree.

---

## Tools

| | |
|---|---|
| `spt.py` | SPT container parser, both variants, with offset-scale detection |
| `build_spt.py` | SPT writer |
| `dstext.py` | Text conversion: fullwidth mapping, pixel wrapping, page breaks, control-code arity |
| `inject.py` | End-to-end build — mapping, guards, ROM rebuild |
| `loc_patch.py` | Evidence, profiles and Logic cards from the Unity Localization tables |
| `build_map.py` / `map_ids.py` | Fuzzy n-gram matching of DS entries to Collection files |
| `lz11.py` / `nitro.py` | Nintendo LZ11 and NCGR/NCLR/NSCR/NCER/NANR |
| `episode_titles.py` | Optional official episode names |

---

## Credits

The **AAI2 fan translation team** did the hard part. This project is built entirely on
top of their work — their variable-width font engine, their English graphics, their
menus, their ROM. Without the Final v2 patch there is nothing to inject *into*, and no
font capable of rendering the result.

Their ATTENTION notice is left intact in every build, and should stay that way.

*Gyakuten Kenji 2* and the *Ace Attorney Investigations Collection* are © Capcom.

## Legal

This repository distributes **no copyrighted material** — no ROM, no script, no extracted
text, no graphics. It is a set of tools that operate on files you already own.

Building requires your own legally-obtained copy of both games. Do not redistribute the
output: it contains both Capcom's copyrighted localization and the fan translation's
assets. **If you want Capcom's translation, buy the Collection — it is very good, and it
is the reason this project can exist at all.**
