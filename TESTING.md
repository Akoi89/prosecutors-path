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

For 1.11.1, the purse paper was checked on a running game: the rig played a new game
through the first investigation to the Episode 1 trash can, opened the purse and looked
at the paper in the examine view, and its legend and handwriting read Rook and Knight
with no Rooke or Knightley left. The handwriting is small and soft at DS size, so a few
words were settled by their length against the 1.11.0 texture, side by side. That check was
repeated on a release candidate whose paper data is the same as the shipped one (title v1.11.1): the legend and handwriting
read Rook and Knight, nothing of the old names is left, and the erased spots look like the
paper around them.

The scream rows were measured: every row of the changed strings is within the 240-pixel
box (the widest is 226), no row of one or two letters is left in the boxes that were
re-laid, and the audits give the same results as on 1.11.0. The last scream change covers
long screams that had no line break in Capcom's script: 17 boxes in 12 strings, such as
one in Wang's breakdown that showed a row of 21 letters over a row of 7 and now shows two
rows of 14. In the emulator, Wang's breakdown at the end of Episode 1 was recorded on an
earlier 1.11.1 candidate: all eight scream boxes showed even rows with no gaps, matching
the expected layout. The last change re-laid three of those eight boxes afterwards, so
those three were checked by decoding the built ROM and by rendering them with the game's
font, not by a new recording. The four strings with joined hyphen words were checked by
rendering their boxes with the game's font, not in the emulator.

The picture fixes were checked this way. On a running game, from saves and with the title
reading v1.11.1, I checked the purse paper, Wang's breakdown (on the earlier candidate
above), the Episode 3 opening card and the victim's letter in the Court Record, and two of the
cake-contest room maps (Tangaroa's Room and Scone's Room). The four-room map and one
cutscene label set were not reached and were checked by decoding.
The opening card shows "Samson & Judy's", "Bake 'n' Bop!" and "Your 3 PM Cakestravaganza"
in Capcom's lettering, with the fan's characters, cake and whisk as expected; at DS size
"PM" reads close to "DM", as it does in Capcom's own picture. In the Court Record the title
bar reads "Victim's Letter" and the card in the picture reads roughly "Ms. Rosie Ringer",
a smudge at DS size, as the fan's picture was. Not seen on a running game: the business
card and the Promise Notebook title (as far as decoding goes, no script on the DS adds
either one to the Court Record, so they may never appear) and the Logic card "Mr. Saint's
big moment" (the right chapter was reached, the card was not). The rest I checked by
decoding the built ROM entry by entry against the fan's and against what the build
produced, and by rendering each changed picture beside the fan's.

On hardware, 1.4.4 booted and reached gameplay from a DSPico flashcart on a 3DS, and test
builds of 1.11.0 booted into the first case on a DSi through TWiLight Menu++ and on a
DSPico, and the 1.11.0 release build boots on both. For 1.11.1: The 1.11.1 release build boots on both as well. Nothing deeper
has been tried on real hardware, and no original DS has been tried at all.

If the game ever hangs mid-scene, your save isn't damaged, since text is read-only data.
Restart the chapter and open an issue saying where it happened. Issue #1 is the thread
for playtest reports.

## If you find something

Report it in the [issues](../../issues) tab. Don't check first to see whether it's
already known. A duplicate costs me nothing and something you talked yourself out of
reporting costs me a defect.

The full technical record of every release, including the detail behind these figures,
is in [BUILD_NOTES.md](BUILD_NOTES.md).
