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

**99.4% of the script's text is Capcom's writing**, measured by `tools/coverage.py`, so you
can recompute it yourself. Earlier releases said 96.5%; that counted fan-written rows as
official once Capcom's names had been swapped in, which isn't the same thing. The counting
changed slightly again in 1.11.0: a fan row that already reads exactly as Capcom's wording
now counts as Capcom's (it doesn't move the figure at this precision), and the lines I wrote
in Capcom's style, where Capcom had nothing that fit, are reported on their own line and
counted as neither. 1.10.0 said 98.8%.

The cast uses Capcom's names throughout, including the ones that are graphics: the
nameplates, the evidence and profile cards, the episode-select buttons, the splash cards
and the title screen are all redrawn at build time.

> ### Playtesters wanted
>
> **Episode 1 has been finished, on an older build (v1.8.5).** The second half of Episode 2,
> from Gavèlle's rebuttal to the end, has been finished on the 1.10.0 candidate, Episode 3
> was finished on v1.9.0 or v1.9.1 (the tester isn't sure which), and Episode 4 was finished
> on the 1.11 test builds (started on the first, finished on the third, "works perfectly
> from start to finish"). Episode 5 hasn't been reported finished, and the automated rig
> hasn't finished any of them. Of
> the game's ~41,700 message boxes, about 5,100 have been run by a script
> that can only press A and tap, and several hundred more by hand: Episode 1 chapter 1 end
> to end, Episode 2 chapters 1 and 2, part of chapter 3 and chapter 4's opening, and
> Episode 5 chapter 4's opening. Episode 3's fourth chapter went through the rig instead,
> about 1,000 boxes with no hangs, which is where the accented nameplate was first
> confirmed in-game. Episode 1's complete Organizer and Episode 4's complete evidence list
> were read card by card on the shipped build. Every hang a player actually hit was found
> by playing, not by an offline check.
>
> **[Report anything wrong in issue #1](../../issues/1)**, not just things that stop.
> Wrong or odd wording, text that runs past its box, a name that changes between screens,
> a mouth that moves on a silent line, a card that reads differently from the dialogue:
> all of it is worth sending. Which episode and chapter is enough, and a photo beats a
> description. Your save is never at risk; the text is read-only data, so a hang costs you
> the chapter and nothing else.
>
> Don't check first to see whether I already know. A duplicate costs me nothing and a
> report somebody talked themselves out of costs me a bug.

> **This repository contains no game data, with one exception**: the six close-up pictures
> added in 1.8.0, set out in [Legal](#legal). You supply your own legally-obtained copy of
> the DS game, and, if you build rather than patch, your own installation of the
> Collection.

---

## Already known

Context, not a filter. If you're looking at something and can't tell which side of this
list it falls on, send it anyway.

- **Some of the script is still the fan translation.** About one character in 180.
  Capcom never localised this game officially on the DS, so where their Collection text
  has no counterpart here the AAI2 fan translation stays. Those lines are not wrong, they
  are just not Capcom's, and they can read slightly differently in tone.
- **Most of this game has never been run.** Episodes 1, 3 and 4, and the second half of
  Episode 2, have now been finished by a tester, across several builds (the Playtesters
  box above has the detail), but Episode 5, and most optional dialogue everywhere,
  hasn't been. That is the single biggest thing wrong with this release, and it is why the invitation
  above is so broad. [TESTING.md](TESTING.md) has the detail.
- **"Gavelle" has no accent in a few places.** The Case 4 visitor log, Organizer
  descriptions and Mind Chess spell it without the grave, because the lettering there has no
  accented letters. In dialogue it is Gavèlle as before.
- **Some Mind Chess rows still show the fan's own wording.** Capcom's text is measured
  against the game's own font now, but a few rows still don't fit the bar even at the
  right size, and those keep the fan's wording rather than being cut off.
- **Bugs fixed in an earlier version can come back.** Several problems listed as fixed in
  the release notes, a hang in Episode 1, a mouth moving on a silent line, quotation marks
  drawing wrong, were each found by one person playing. If you see one of them now, that
  matters more than the release note saying it was handled, so please say so.
- **On real hardware, dialogue that turns into strings of accented letters is the game's
  anti-piracy check.** Current versions of TWiLight Menu++ and the DSpico's Pico Loader
  handle it for this patch, and I tested both. If you see it, update your loader or switch
  to one of those. I also booted test builds of 1.11.0 into the first case on a DSi (through
  TWiLight Menu++) and on a DSPico, and the release build boots on both; nothing deeper has been tried on hardware, and no
  original DS has been tried at all.

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
xdelta3 -d -s "Gyakuten Kenji 2 (AAI2 Final v2).nds" "Prosecutors-Path-1.11.0-fan-base.xdelta" "GK2 (Official English, DS port).nds"
```

On Windows, DeltaPatcher asks for the same two files and writes the same output. The source
has to be the AAI2 Final v2 ROM exactly (`sha256 08e1f7af...`, 45,165,392 bytes). Anything
else either fails to decode or boots to a black screen. Check the result:

```
gk2port-windows-x64.exe --verify "GK2 (Official English, DS port).nds"
```

A correct output ROM is 50,597,852 bytes, sha256
fccfb88e9943c11dc7f9a00ab7c61d471c050495bcf9899aa99b021afada34f4. The patch itself is
3,928,935 bytes, sha256 ab15e528aedcf684b771f1541d978384e9689da0711982c31c97f38ac5379fe8.

**Or build it yourself** from your own copy of the Collection, if you'd rather the
localization came out of your files than out of one someone uploaded. Full steps are in
[DETAILS.md](DETAILS.md), along with how coverage is counted, how the names and episode
titles are redrawn, what doesn't port and why, and the tool inventory.

## Credits

**JPScaravino** has done the most playtesting of any tester so far, finishing Episodes 1,
3 and 4 and the second half of Episode 2, across several builds. His save state found the
Case 4 crash that 1.11.0 fixes.

The **AAI2 fan translation team** did the hard part:
**[Gyakuten Kenji 2: AAI2 Final v2](https://www.romhacking.net/translations/2260/)**.

This is built entirely on top of their work: their variable-width font engine, most of
their English graphics, their menus, their ROM. Without the Final v2 patch there's nothing
to inject *into*, and no font capable of rendering the result. They also solved problems
this project simply inherits, like fitting English into a script laid out for Japanese.

If you haven't played their translation, play it. It stood alone for over a decade and it's
genuinely good. This is a different thing, not a better one: it swaps in Capcom's wording,
titles and voices for people who want the official script on hardware.

Their ATTENTION notice is left intact in every build, and should stay that way.

*Gyakuten Kenji 2* and the *Ace Attorney Investigations Collection* are © Capcom.

## How this was built

[RELEASE_NOTES.md](RELEASE_NOTES.md) has a short entry for every version, newest first.
[TESTING.md](TESTING.md) says what has actually been played and what has not, and
[BUILD_NOTES.md](BUILD_NOTES.md) is the full technical record behind both.

**Nothing here asks to be taken on trust.** Almost every figure on this page is reproducible
by running the tools on your own files. `tools/coverage.py` computes the coverage table, and
`--verify` hashes a finished build against the release's published reference, so a ROM can
be trusted without trusting whoever built it. The two exceptions are the message box counts
above, the ~41,700 total and the ~5,100 run by script. Those came from counts made during
the work and no shipped tool reproduces them, which is why they carry a tilde. Read the
coverage figure as measured and the box figures as estimates.

The 14 audits in [`audits/`](audits) guard the structural failure classes, and every one
but the typography shape check is tested against a deliberately corrupted input. An audit that has never failed hasn't
been tested, it's only been run.

The tooling was written with **LLM assistance**: Claude, driven through Claude Code, over a
series of sessions. That's stated plainly rather than buried. What ships is Capcom's own
script, art and recordings plus the fan team's assets; nothing in the ROM is generated
text. The code is about 18,390 lines across 67 modules, plus 15 audit scripts (the 14 audits and the harness that tests them), MIT licensed, and it ships as source
precisely so you don't have to take any of that on faith.

Because every hang but one was found by **playing the game**, not by an offline check (the
Case 4 freeze fixed in 1.10.0 was found by searching for the cause of the Case 2 one). Three
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
of their fonts and twenty of their audio clips, alongside the fan translation's
assets.

The releases also carry an `.xdelta` from the fan ROM to the built one, and that delta *is*
Capcom's script, which is what makes it nearly 4 MB. The trade is written down rather than
left implied, in [DETAILS.md](DETAILS.md).

**If you want Capcom's translation, buy the Collection.** It's very good, and it's the
reason this project can exist at all.

## License

MIT for the tools. See [LICENSE](LICENSE). That covers the code only; the game data it
operates on isn't mine to license, and none of it is distributed here apart from the six
pictures noted above. See [NOTICE](NOTICE) for the exact scope.
