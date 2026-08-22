Port Capcom's official English localization of *Gyakuten Kenji 2* into the Nintendo DS ROM.

**85.7% of on-screen text becomes Capcom's.** The remaining 14.3% stays in the AAI2 fan
translation — see the README for exactly why, and which parts.

## New in v1.1.0 — it should now be much easier to run

Nothing about the ROM changed. This release is entirely about getting to it: the output
is **byte-for-byte identical** to v1.0.1, verified by hash.

- **A Linux build**, alongside Windows. Both are built in public by GitHub Actions and
  self-tested before upload.
- **Run it with no arguments** — on Windows, just double-click it. It finds your ROM,
  searches your Steam libraries for the Collection, shows you what it found, and asks
  before doing anything.
- **Steam auto-detection**, across every library folder, not just the default one. You
  should not have to go hunting for an install path.
- **Your ROM is verified by hash** before anything happens. Pointing this at the wrong
  ROM used to produce a file that boots to a black screen with no explanation.
- **The window stays open** when it was double-clicked, so error messages can actually
  be read.
- Drag the `.nds` onto the program, if that's easier than typing a path.
- It refuses to overwrite its own input, which is easy to do by accident.

## Downloads

| Platform | File |
|---|---|
| Windows | `gk2port-windows-x64.exe` |
| Linux (glibc 2.35+) | `gk2port-linux-x64` |

Checksums are in `SHA256SUMS`. On Linux, `chmod +x` it first. Windows SmartScreen will
warn about an unrecognised publisher, because the binary is unsigned and certificates
cost money - check the hash, or build from source. `gk2port --selftest` confirms your
download is complete.

Only the Windows binary has been used to build a ROM that was then played. The Linux one
passes the self-test in CI; if it misbehaves, please open an issue.

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
  there is nothing to inject into and no font to render the result. Their ATTENTION
  notice is left intact in every build. If you haven't played their translation, play it.
- The tooling was written with **LLM assistance** (Claude Opus 5, via Claude Code). The
  measurements and format work are reproducible by running the tools; the bugs that
  mattered were found by a human playing the game. See the README for the full note.
- Tested in melonDS. Episode 1 plays through to free roam; later episodes are less
  exercised, so please open an issue if you hit anything.
