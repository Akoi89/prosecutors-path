# Testing

A plain account of what has been played and what has not. The tester JPScaravino has
finished Episodes 1, 3 and 4 and the second half of Episode 2. Reports from Episode 5 and
from optional dialogue help most.

## Testing status

Every release is verified structurally (every string audited against the fan layout,
14 audits covering the defect classes that have shipped before) and exercised in
melonDS by a scripted rig. What that rig has actually executed, measured: all 25 chapter
saves boot, load and advance; about 5,100 of the game's 41,706 message boxes have been
displayed, weighted toward chapter openings and finales; and on the 1.5.0 candidate an
Episode 1 run from a cold-boot New Game, following a walkthrough, has covered the opening,
the first investigation, the first Logic connections, the first Mind Chess to checkmate
and the second investigation area with zero defects. The rig itself has not finished
an episode or solved a rebuttal. The tester JPScaravino finished Episode 1 on
v1.8.5, Episode 3 on v1.9.0 or v1.9.1, the second half of Episode 2 (from Gavèlle's
rebuttal to the end) on the 1.10.0 candidate, and Episode 4 on the 1.11 test builds
(started on the first, finished on the third, "works perfectly from start to finish").
Episode 5 has not been reported finished on any build, and a lot of optional dialogue
(wrong answers, side conversations) hasn't been played. Every hang a player actually hit was found by playing, not by audits. The one
hang found another way is the Case 4 freeze fixed in 1.10.0, found by searching every
scene for the cause of one a tester hit in Case 2, not by anyone hitting it. The Case 4
crash fixed in 1.11.0, after talking to Lotta, was hit by the tester; his emulator save
state reproduced it, and the rig then replayed it and confirmed the fix.

On hardware, 1.4.4 booted and reached gameplay from a DSPico flashcart on a 3DS, and test
builds of 1.11.0 booted into the first case on a DSi through TWiLight Menu++ and on a
DSPico, and the release build boots on both. Nothing deeper has been tried on real hardware,
and no original DS has been tried at all.

If the game ever hangs mid-scene, your save isn't damaged, since text is read-only data.
Restart the chapter and open an issue saying where it happened. Issue #1 is the thread
for playtest reports.

## If you find something

Report it in the [issues](../../issues) tab. Don't check first to see whether it's
already known. A duplicate costs me nothing and something you talked yourself out of
reporting costs me a defect.

The full technical record of every release, including the detail behind these figures,
is in [BUILD_NOTES.md](BUILD_NOTES.md).
