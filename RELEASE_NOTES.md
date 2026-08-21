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
sha256: f5f44aeb9f52fe634a1768b16717f8982c213cf5e21233f248e608b20ba3a1a3
size:   26M
```

Windows SmartScreen will warn about an unrecognised publisher. The binary is unsigned
because certificates cost money — check the hash above, or build from source, which is
four files and a `pip install`.

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

