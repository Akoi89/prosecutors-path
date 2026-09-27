# Testing

A plain account of what has been played and what has not. The short version is that
most of this game has never been run by anyone, on any build. If you play deep into it,
what you find is the only thing that shortens this page.

## Testing status

Every release is verified structurally (every string audited against the fan layout,
13 audits covering the defect classes that have shipped before) and exercised in
melonDS by a scripted rig. What that rig has actually executed, measured: all 25 chapter
saves boot, load and advance; about 5,100 of the game's 41,706 message boxes have been
displayed, weighted toward chapter openings and finales; and on the 1.5.0 candidate an
Episode 1 run from a cold-boot New Game, following a walkthrough, has covered the opening,
the first investigation, the first Logic connections, the first Mind Chess to checkmate
and the second investigation area with zero defects. **The rig itself has finished
nothing.** Episodes 1 and 3, and the second half of Episode 2, have been finished by a
tester, across several builds: Episode 1 on v1.8.5, Episode 2's second half (from
Gavèlle's rebuttal to the end) on the 1.10.0 candidate, and Episode 3 on v1.9.0 or v1.9.1
(the tester isn't sure which). Episodes 4 and 5 haven't been reported finished, and most
optional dialogue everywhere has never been run. Every hang a player actually hit was
found by playing, not by audits. The one hang found another way is the Case 4 freeze
fixed in 1.10.0, found by searching every scene for the cause of one a tester hit in
Case 2, not by anyone hitting it.

On hardware, 1.4.4 booted and reached gameplay from a DSPico flashcart on a 3DS; nothing
deeper has been tried on real hardware, and no original DS has been tried at all.

If the game ever hangs mid-scene: **your save is not damaged**, text is read-only data.
Restart the chapter and open an issue saying where it happened. Issue #1 is the thread
for playtest reports.

## If you find something

Report it in the [issues](../../issues) tab. Don't check first to see whether it's
already known. A duplicate costs me nothing and something you talked yourself out of
reporting costs me a defect.

The full technical record of every release, including the detail behind these figures,
is in [BUILD_NOTES.md](BUILD_NOTES.md).
