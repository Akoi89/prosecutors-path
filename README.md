# Prosecutor's Path

**Capcom's official English localization of *Gyakuten Kenji 2* ported into the Nintendo DS
ROM: the script, the title logo, the episode titles, the Logic keyword cards and the voice
clips.**

*Gyakuten Kenji 2* (2011) never got an official English release on the DS. The community
filled the gap with the **AAI2 Final v2** fan translation. Thirteen years later Capcom
localized the game themselves for the *Ace Attorney Investigations Collection* (2024).

This toolchain takes Capcom's own script, art and voice recordings and injects them into
the DS game, so you can play the official localization on original hardware, on a
flashcart, or in an emulator.

**93.8% of the script's text is Capcom's writing**, measured by `tools/coverage.py`, so you
can recompute it yourself. Earlier releases said 96.5%; that counted fan-written rows as
official once Capcom's names had been swapped in, which isn't the same thing.

The cast uses Capcom's names throughout, including the ones that are graphics: the
nameplates, the evidence and profile cards, the episode-select buttons, the splash cards
and the title screen are all redrawn at build time.

> ### Playtesters wanted
>
> **Nobody has finished an episode, and solving a rebuttal has never been tested by
> anyone.** Of the game's ~41,700 message boxes, about 5,100 have been run by a script
> that can only press A and tap, and several hundred more by hand. Every bug this project
> has had was found by a person playing, and none by an offline check.
>
> **[Report anything that stops in issue #1](../../issues/1)**, which episode and chapter
> is enough. Your save is never at risk; the text is read-only data, so a hang costs you
> the chapter and nothing else.

> **This repository contains no game data, with one exception**: the six close-up pictures
> added in 1.8.0, set out in [Legal](#legal). You supply your own legally-obtained copy of
> the DS game, and, if you build rather than patch, your own installation of the
> Collection.

---

## What you need

| | |
|---|---|
| **Gyakuten Kenji 2 (AAI2 Final v2)** | The fan-patched DS ROM. It supplies the variable-width font and the English graphics. Without it nothing renders. Needed either way |
| **Ace Attorney Investigations Collection** | Only if you build. The PC build, tested on Steam |
| **xdelta3, or DeltaPatcher** | Only if you patch |
| **Python 3.9+** | Only if building from source. `pip install UnityPy Pillow numpy` |

## Usage

Two ways in, ending at the same ROM, and `--verify` confirms it either way.

**Apply the patch** if you have the fan ROM and want it done in seconds:

```bash
xdelta3 -d -s "Gyakuten Kenji 2 (AAI2 Final v2).nds" "Prosecutors-Path-1.8.2-fan-base.xdelta" "GK2 (Official English, DS port).nds"
```

On Windows, DeltaPatcher asks for the same two files and writes the same output. The source
has to be the AAI2 Final v2 ROM exactly (`sha256 08e1f7af...`, 45,165,392 bytes). Anything
else either fails to decode or boots to a black screen. Check the result:

```
gk2port-windows-x64.exe --verify "GK2 (Official English, DS port).nds"
```

**Or build it yourself** from your own copy of the Collection, if you'd rather the
localization came out of your files than out of one someone uploaded. Full steps are in
[DETAILS.md](DETAILS.md), along with how coverage is counted, how the names and episode
titles are redrawn, what doesn't port and why, and the tool inventory.

## Credits

The **AAI2 fan translation team** did the hard part:
**[Gyakuten Kenji 2: AAI2 Final v2](https://www.romhacking.net/translations/2260/)**.

This is built entirely on top of their work: their variable-width font engine, most of
their English graphics, their voice recordings for the shouts Capcom never localised, their
menus, their ROM. Without the Final v2 patch there's nothing to inject *into*, and no font
capable of rendering the result. They also solved problems this project simply inherits,
like fitting English into a script laid out for Japanese.

If you haven't played their translation, play it. It stood alone for over a decade and it's
genuinely good. This is a different thing, not a better one: it swaps in Capcom's wording,
titles and voices for people who want the official script on hardware.

Their ATTENTION notice is left intact in every build, and should stay that way.

*Gyakuten Kenji 2* and the *Ace Attorney Investigations Collection* are © Capcom.

## How this was built

**Nothing here asks to be taken on trust.** Every figure on this page is reproducible by
running the tools on your own files. `tools/coverage.py` computes the coverage table, and
`--verify` hashes a finished build against the release's published reference, so a ROM can
be trusted without trusting whoever built it.

The seven audits in [`audits/`](audits) guard the structural failure classes, and every one
is tested against a deliberately corrupted input. An audit that has never failed hasn't
been tested, it's only been run.

The tooling was written with **LLM assistance**: Claude, driven through Claude Code, over a
series of sessions. That's stated plainly rather than buried. What ships is Capcom's own
script, art and recordings plus the fan team's assets; nothing in the ROM is generated
text. The code is about 3,500 lines across 28 modules, MIT licensed, and it ships as source
precisely so you don't have to take any of that on faith.

Because every hang this project has ever had was found by **playing the game**, and none by
any offline check, including checks written specifically to catch the previous one. Three
examples, and what they say about the guards, are in [DETAILS.md](DETAILS.md).

So treat the guards as a record of what has actually gone wrong rather than proof that
nothing else will, and treat the code as reviewable rather than authoritative. That's also
why this is a **test build**, and why [issue #1](../../issues/1) asks for players rather
than for approval.

## Legal

This repository distributes **no copyrighted material, with one exception**: no ROM, no
script, no extracted text. It's a set of tools that operate on files you already own.

The exception, since 1.8.0, is `tools/cg_art_final/`: six 256x192 close-up pictures whose
lettering is drawn into the artwork, prepared from Capcom's Collection art and the fan
patch's pictures with the official names on them. They ship as finished files because
composing them at build time gave worse results. If that's a line you'd rather this project
hadn't crossed, the 1.7.0 tag is the last one before it.

Building requires your own legally-obtained copy of both games. Don't redistribute the
output: it contains Capcom's copyrighted localization, and since 1.5.0 their logo art, two
of their fonts and thirteen of their voice recordings, alongside the fan translation's
assets.

The releases also carry an `.xdelta` from the fan ROM to the built one, and that delta *is*
Capcom's script, which is what makes it over 4 MB. The trade is written down rather than
left implied, in [DETAILS.md](DETAILS.md).

**If you want Capcom's translation, buy the Collection.** It's very good, and it's the
reason this project can exist at all.

## License

MIT for the tools. See [LICENSE](LICENSE). That covers the code only; the game data it
operates on isn't ours to license, and none of it is distributed here apart from the six
pictures noted above. See [NOTICE](NOTICE) for the exact scope.
