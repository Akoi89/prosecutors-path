# Testing

An honest account of what has been played and what has not. The short version is that
most of this game has never been run by anyone, on any build. If you play deep into it,
what you find is the only thing that shortens this page.

## Testing status

Every release is verified structurally (every string audited against the fan layout,
seven audits covering the defect classes that have shipped before) and exercised in
melonDS by a scripted rig. What that rig has actually executed, measured: all 25 chapter
saves boot, load and advance; about 5,100 of the game's 41,706 message boxes have been
displayed, weighted toward chapter openings and finales; and on the 1.5.0 candidate an
Episode 1 run from a cold-boot New Game, following a walkthrough, has covered the opening,
the first investigation, the first Logic connections, the first Mind Chess to checkmate
and the second investigation area with zero defects. **Nobody has finished an episode
yet**, on any release. Both hangs this project ever shipped were found by playing, not by
audits, and both were in interactive scenes rather than dialogue, so that is where a
report helps most.

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
