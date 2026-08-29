Port Capcom's official English localization of *Gyakuten Kenji 2* into the Nintendo DS ROM.

**98.4% of the script's text becomes Capcom's** (1,803,512 of 1,833,041 character
units, measured by `tools/coverage.py` — a new, reproducible counting; not directly
comparable to the old release's "85.7%", whose methodology differed). The remainder
stays in the AAI2 fan translation — see the README for exactly why, and which parts.

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
