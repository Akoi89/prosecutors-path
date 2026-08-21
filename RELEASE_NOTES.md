Port Capcom's official English localization of *Gyakuten Kenji 2* into the Nintendo DS ROM.

**85.7% of on-screen text becomes Capcom's.** The remaining 14.3% stays in the AAI2 fan
translation — see the README for exactly why, and which parts.

## Quick start (Windows, no Python needed)

Put `gk2port.exe` in a folder of its own and run it from a terminal:

```
gk2port.exe --fan-rom "GK2 (AAI2 Final v2).nds" --collection "C:\Program Files (x86)\Steam\steamapps\common\Ace Attorney Investigations Collection"
```

It extracts what it needs into `dump/` beside itself and writes the ROM to `out/`.
Takes a couple of minutes.

## You need to supply

| | |
|---|---|
| **Gyakuten Kenji 2 (AAI2 Final v2)** | The fan-patched DS ROM — supplies the variable-width font and English graphics |
| **Ace Attorney Investigations Collection** | The **PC** build — tested on Steam |

**No game data is included in this download.** All three inputs are files you own.

Console builds are untested. The bundle lookup matches by name prefix and ignores the
platform folder name, so an already-extracted Switch or PS4 dump may work — but nothing
here has been run against one.

## Coverage

| Episode | Official |
|---|---|
| 1 — Turnabout Target | 73.6% |
| 2 — The Imprisoned Turnabout | 82.4% |
| 3 — The Inherited Turnabout | **99.9%** |
| 4 — The Forgotten Turnabout | 74.7% |
| 5 — The Grand Turnabout | 89.7% |

Evidence and profile descriptions, Logic card text and the Organizer messages are ported
too — those live in the Collection's Unity Localization tables rather than the script.

## Rebuilding without the Collection installed

The Collection is only read during extraction. Once `dump/` exists it holds everything
the injection needs, so you can free the ~7 GB install and still rebuild:

```
gk2port.exe --fan-rom "GK2 (AAI2 Final v2).nds" --skip-extract
```

That needs the fan ROM and `dump/` (~55 MB) and nothing else. Verified byte-identical
to a full run.

## Verify the download

```
sha256: c8f656a4de5a5ad610db33f1b3121f64b5b8773f261afe0ac1d4eb2d1752b008
size:   26M
```

Windows SmartScreen will warn about an unrecognised publisher. The binary is unsigned
because certificates cost money — check the hash above, or build from source, which is
four files and a `pip install`.

## Changed in v1.0.1

Nine control codes were missing from the argument-count table, so 1,498 argument bytes
were being treated as dialogue text — and 39 of them reached the engine with altered
values after being converted to fullwidth. The table now covers all 342 codes.

Verified by diffing rendered text against the previous build: 10,697 strings identical,
8 changed, and every change removes stray argument bytes that had been leaking into
view. No dialogue was lost, every structural guard count is unchanged, and coverage
stays at 85.7%. See BUILDING.md for the evidence.

## Notes

- The output ROM is **not redistributable**: it contains Capcom's copyrighted
  localization and the fan translation's assets. Build your own.
- Episode names stay the fan's. Capcom renamed all five, but those appear on the
  episode-select screen as a bitmap, so changing only the save-slot text would show two
  names for one episode a menu apart.
- The **[AAI2 Final v2 fan translation](https://www.romhacking.net/translations/2260/)**
  team did the hard part — this is built entirely on top of their patch, and without it
  there is nothing to inject into and no font to render the result. Their ATTENTION
  notice is left intact in every build. If you haven't played their translation, play it.
- The tooling was written with **LLM assistance** (Claude Opus 5, via Claude Code). The
  measurements and format work are reproducible by running the tools; the bugs that
  mattered were found by a human playing the game. See the README for the full note.
- Tested in melonDS. Episode 1 plays through to free roam; later episodes are less
  exercised, so please open an issue if you hit anything.

