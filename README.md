# Prosecutor's Path

**Port Capcom's official English localization of *Gyakuten Kenji 2* into the Nintendo DS ROM.**

*Gyakuten Kenji 2* (2011) never received an official English release on the DS. The
community filled the gap with the excellent **AAI2 Final v2** fan translation. Thirteen
years later, Capcom localized the game themselves for the *Ace Attorney Investigations
Collection* (2024).

This toolchain takes Capcom's script and injects it into the DS game — so you can play
the official localization on original hardware, on a flashcart, or in an emulator.

**98.4% of the script's text becomes Capcom's** — measured by `tools/coverage.py`, so
you can recompute it. The remainder stays in the fan translation, for reasons documented
in [What doesn't port, and why](#what-doesnt-port-and-why).

> **This repository contains no game data.** No ROM, no script, no extracted text — only
> the tools. You supply your own legally-obtained copy of the DS game and your own
> installation of the Collection.

---

## What you need

| | |
|---|---|
| **Gyakuten Kenji 2 (AAI2 Final v2)** | The fan-patched DS ROM. It supplies the variable-width font and English graphics — without it, nothing renders |
| **Ace Attorney Investigations Collection** | The **PC** build — tested on Steam. The script lives in the Unity Addressables bundles under `GK12_Data/StreamingAssets/aa/` |
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
— it works the same way.

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
folder inside it, and is only needed when auto-detection fails — a non-Steam copy, or a
console dump you extracted yourself.

### Linux

It's a terminal program — mark it executable and run it:

```bash
chmod +x gk2port-linux-x64
./gk2port-linux-x64
```

Steam auto-detection knows the usual locations, including Flatpak's. The Collection is a
Windows game, so it will be a Proton install — that lives in an ordinary Steam library
and is found the same way.

The binary is built on Ubuntu 22.04, so it needs glibc 2.35 or newer. On anything older,
build from source.

> **Console builds are untested.** The bundle lookup matches by name prefix and does
> not care which platform folder it finds, so a Switch or PS4 dump you have already
> extracted yourself may well work — point `--collection` at the extracted folder. But
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

That needs the fan ROM and `dump/` (~55 MB) and nothing else. Verified byte-identical to
a full run.

Or run the injection alone:

```bash
python tools/inject.py "Gyakuten Kenji 2 (AAI2 Final v2).nds" -o out/GK2-official.nds
```

The build prints a full audit of what it did and, crucially, what it refused to do:

```
entries replaced with official English: 422
entries re-aligned to the fan string layout: 11
sparse official banks swapped row-by-row: 2
relaid strings rebuilt in the fan layout:   74
hollow official strings kept as fan:       8
records kept as fan - still Japanese:   347
records kept as fan - fan relaid it vs JP: 38
kept fan text - string count mismatch:   3
kept fan text - control-code shape off:  9
```

Every one of those counters is a guard that fired. They exist because each one, once,
broke the game.

---

## Coverage

| Episode | Official | character units |
|---|---|---|
| 1 — *Turnabout Target* | 97.7% | 175,426 / 179,476 |
| 2 — *The Imprisoned Turnabout* | 99.9% | 368,376 / 368,710 |
| 3 — *The Inherited Turnabout* | **100%** | 377,753 / 377,753 |
| 4 — *The Forgotten Turnabout* | 98.4% | 292,972 / 297,665 |
| 5 — *The Grand Turnabout* | **100%** | 497,837 / 497,837 |
| Menus & UI | 81.7% | 91,148 / 111,600 |
| **Total** | **98.4%** | 1,803,512 / 1,833,041 |

The counting is `tools/coverage.py`: character units (everything that is not a control
code or one of its arguments) in strings whose bytes differ from the fan ROM, over all
character units. Earlier releases quoted "85.7%" from a methodology that did not
survive; the two numbers are not directly comparable.

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
per-entry was worth about ten points of coverage on its own. v1.2.0 goes further:
where a whole RUN of neighbouring strings was relaid with its box total conserved, the
official strings are joined and re-cut at the fan's own boundaries — the layout the
engine was built against — with strict per-string box-code equality as the gate. The
same trick inverts the fan's habit of splitting one long retail string into two
(the retail JP and the Collection both hold the joined form; the split point is
recovered from three independent structural fingerprints). What used to be reverted
wholesale is now mostly rebuilt.

You don't need that ROM, though. The guards want *counts*, never text — message boxes per
string, and a control-code histogram per entry. Those are integers, facts about the file's
structure rather than its content, so they ship as `dump/jp_structure.json` (214 KB) and
the retail Japanese cart drops off the requirements list entirely.
`tools/jp_profile.py` regenerates it if it ever needs updating.

### Guards

Structural failures don't show up in a format check — the file parses perfectly and the
game hangs anyway. Each guard below exists because it happened:

- **Scene redistributed across strings** — a string with >200 printable DS characters
  whose Collection counterpart has under 20% of that. Rejects the entry.
- **Message-box loss** — losing ≥2 boxes reverts that string. Losing exactly *one* is
  benign and very common (868 of 913 cases, measured before the v1.2.0 rebuilds):
  the localization merged a pair.
- **Per-record defects** — Capcom's English bundle contains `DEMO TEXT` placeholders and
  untranslated Japanese, but *per record*, not per file. Guarding at file level threw
  away 16,780 letters of perfectly good English.
- **Control-code shape** — a wrong file match shows as near-zero overlap in the
  control-code profile against the Japanese original.

---

## What doesn't port, and why

The floor isn't laziness — it's structural, and it breaks down cleanly:

What remains fan, as of v1.2.0 (~3.1% of the script):

- **Relaid strings with no rebuildable partner** — 38 strings whose box counts moved
  against the retail layout in ways the run-rebuild cannot verify (lone strings, or
  runs where the official uses a different box-end variant, e.g. `DS[236]`).
- **Evidence descriptions that overflow their box** — official English exists for
  ~111 of them but does not fit the DS's 4-line description box, and editing Capcom's
  wording to fit was ruled out (evidence text is contradiction material; a dropped
  hedge changes the game). The fan's descriptions fit because they were written for
  this box.
- **Hollow official strings** — a few strings are empty or `DEMO TEXT` in the
  Collection's own files.
- **Menus & UI residue** — DS-only interface text with no official counterpart.

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
| `build.py` | One-shot entry point: extract everything, then inject. This is what the released binaries run |
| `locate.py` | Finds the fan ROM and the Collection, and verifies the ROM by hash |
| `jp_profile.py` | Regenerates `dump/jp_structure.json`, the shipped structural counts from the JP script |
| `ctrl_args.py` | Regenerates `dump/ctrl_args.json`; `--check` diffs a fresh derivation against it |
| `inject.py` | Mapping, structural guards, ROM rebuild |
| `loc_patch.py` | Evidence, profiles and Logic cards from the Unity Localization tables |
| `build_map.py` / `map_ids.py` | Fuzzy n-gram matching of DS entries to Collection files |
| `lz11.py` / `nitro.py` | Nintendo LZ11 and NCGR/NCLR/NSCR/NCER/NANR |
| `episode_titles.py` | Optional official episode names |

---

## Credits

The **AAI2 fan translation team** did the hard part:

> **[Gyakuten Kenji 2 — AAI2 Final v2](https://www.romhacking.net/translations/2260/)**
> on romhacking.net

This project is built entirely on top of their work — their variable-width font engine,
their English graphics, their menus, their ROM. Without the Final v2 patch there is
nothing to inject *into*, and no font capable of rendering the result. They also solved
problems this project simply inherits, like fitting English into a script laid out for
Japanese, and reworking the engine's string offsets to buy back address space.

If you have not played their translation, play it. It stood alone for over a decade and
it is genuinely good. This project is a different thing, not a better one — it swaps in
Capcom's wording for people who want to read the official script on hardware.

Their ATTENTION notice is left intact in every build, and should stay that way.

*Gyakuten Kenji 2* and the *Ace Attorney Investigations Collection* are © Capcom.

## How this was built

The tooling in this repository was written with **LLM assistance** — specifically Claude
(Opus 5), driven through Claude Code, over a series of sessions.

That is worth stating plainly, because it shapes what you should trust here. The format
reverse-engineering is grounded in measurements over the real files rather than in
recollection, and the numbers quoted throughout — 20,516 of 26,172 newlines, 54 of 429
relaid entries, 96.9% coverage — are all reproducible by running the tools
(`tools/coverage.py` computes the coverage figure). Every build
is verified byte-for-byte against previous ones.

But the bugs that mattered were found by **playing the game**, not by the model. The
freeze in Episode 1, the ragged line wrapping, the clipped text, the duplicated
conversation — each surfaced from a human sitting in front of an emulator with a
screenshot, and several of them contradicted what the model believed at the time. The
project's own history is a decent argument for that division of labour.

Treat the code as reviewable rather than authoritative. It is 1,400 lines and MIT
licensed; read it before you trust it with a ROM you care about.

## Legal

This repository distributes **no copyrighted material** — no ROM, no script, no extracted
text, no graphics. It is a set of tools that operate on files you already own.

Building requires your own legally-obtained copy of both games. Do not redistribute the
output: it contains both Capcom's copyrighted localization and the fan translation's
assets. **If you want Capcom's translation, buy the Collection — it is very good, and it
is the reason this project can exist at all.**

### Why there is no patch file

The obvious way to make this easier would be an xdelta or IPS patch, so nobody needs the
Collection at all. That patch would *be* Capcom's script — a delta from the fan ROM to
the ported one contains the entire localization as its payload, which is the thing being
avoided, not a way around it. The same goes for the extracted `dump/` tree: the three
`.json` files in it are integers and filenames and do ship here, but `dump/eng` is
Capcom's text.

Owning the Collection isn't a hurdle this project failed to remove. It's the reason the
project is allowed to exist.

## License

MIT for the tools — see [LICENSE](LICENSE). That covers the code only; the game data
it operates on is not ours to license, and none of it is distributed here. See
[NOTICE](NOTICE) for the exact scope.
