Version 1.10.0 fixes a game freeze at the start of a Case 2 rebuttal and a possible one in Case 4, along with several lines and testimony questions that were only showing half their text. It also lets a lot more of the script through as Capcom's own writing, since a safety check that had been holding back dozens of unrelated lines turned out to be guarding against a different, already-fixed bug.

## What this build fixes

- **A freeze in Case 2, when Gavelle's rebuttal starts.** The rebuttal opened with no statement on screen, and no button did anything from then on.
- **A possible freeze in a Case 4 rebuttal.** It had the same error as the Case 2 freeze. I found it by checking every scene for that cause, and nobody has reported hitting it.
- **Questions cut in half while you choose.** When the game asks you to present evidence, the question stays on screen while you pick. Winner's question about the murder weapon leaving the prison, and several others like it, used to show only their second half.
- **Several testimony statements only showed half their text too.** The game gives each one a single box to work with, and some ran long enough that the rest of the statement never appeared.
- **Lines that carried on after a pause stopped cutting off mid-word.** A line of Eddie Fender's, for one, used to run straight into the next sentence and chop off partway through a word.
- **Tutorial lines that mention a controller button now use Capcom's own wording.** They used to fall back to the fan translation entirely, because the DS doesn't understand the picture of a button that Capcom's script points at instead.
- **More of the script is Capcom's own writing than before.** A safety check meant to stop a different, already-fixed freeze was holding back dozens of unrelated lines; narrowed to the actual danger, coverage climbs from the mid-90s to 98.9%, and two of the five episodes are now entirely Capcom's wording.

## Version history

- **v1.10.0** - two game freezes fixed in Case 2 and Case 4, cut-off testimony lines and questions repaired, tutorial button wording restored, coverage up to 98.9%.
- **v1.9.1** - menu buttons lettered like the fan game's own lettering.
- **v1.9.0** - every line re-measured against the game's own font.
- **v1.8.6** - the answer menus that froze the game.
- **v1.8.5** - Logic keyword cards drawn in the fan team's own lettering.
- **v1.8.4** - talking to Ms. Bound opens her conversation, not Larry's.
- **v1.8.3** - location cards laid out the way the DS games always did it.
- **v1.8.2** - "John Doe" is John Doe again.
- **v1.8.1** - silent boxes no longer move the speaker's mouth.
- **v1.8.0** - six hand-lettered pictures now carry Capcom's official names.
- **v1.7.0** - close-up document screens now use Capcom's official wording.
- **v1.6.4** - a highlighted term keeps its color when split across two boxes.
- **v1.6.3** - long evidence and profile titles are no longer squashed.
- **v1.6.2** - closing quotation marks no longer look like an apostrophe.
- **v1.6.1** - the 1.6.0 downloads were missing files and would crash.
- **v1.6.0** - choice buttons speak Capcom's words, descriptions stop losing their last letter.
- **v1.5.2** - a hang in Episode 1 that every earlier release had.
- **v1.5.1** - the last five lines with a fan character name.
- **v1.5.0** - official titles everywhere, Capcom's own shout recordings, and an honest coverage number.
- **v1.4.4** - ten lines that shipped visibly cut off.
- **v1.4.3** - Episode 1 freezes at the Gourd Lake scene. Update before playing.
- **v1.4.2** - an early Episode 1 freeze, found by a player.
- **v1.4.1** - one renamed line was too wide for its menu.
- **v1.4.0** - Capcom's character names, everywhere.
- **v1.3.4** - one description stops contradicting itself about a room's name.
- **v1.3.3** - a permanent freeze during the Little Thief scenes, fixed.
- **v1.3.2** - no game changes, just easier setup and troubleshooting.
- **v1.3.1** - three autopsy descriptions stop contradicting the trial testimony.
- **v1.3.0** - the last big chunks of missing text are recovered.
- **v1.2.1** - one missing line restored.
- **v1.2.0** - most of the previously missing text is recovered.

## Known problems

- One tester finished Episode 1 on an older build (v1.8.5), and testers have got through a few rebuttals in later cases, but none of that was on this build, and most of the game has never been run. Testing happens scene by scene, mostly through a rig that can only press confirm and tap, with some scenes played by hand.
- The Case 2 fix was checked by replaying the tester's own save: the rebuttal now opens with all five statements and the game keeps responding. Nobody has played that rebuttal through yet. The Case 4 fix is the identical mistake in a different rebuttal, but no save has reached that scene yet, so it has only been checked against the game's own data, not watched running.
- The Winner's testimony fix has not been rephotographed since the last merge. The same underlying code change was proven on a different line in the same episode, and the new wording was reviewed before use, but nobody has watched that exact line on screen yet.
- About one line in ninety is still the fan translation rather than Capcom's, in spots where Capcom's Collection has no matching text at all. That is not a defect, just a gap Capcom's own script does not cover.
- Bugs listed as fixed in an earlier version have come back before. If something here shows up again, say so. That matters more than this note saying it is handled.

## Files

- `gk2port-windows-x64.exe` and `gk2port-linux-x64`: the build tool, with `SHA256SUMS` alongside them. `gk2port --verify` checks a finished ROM against this version's published reference, `02a48ecf4126175ca9cc8fa309ec26208d22b2086b720068de46e3e87962a779`.
- `Prosecutors-Path-1.10.0-fan-base.xdelta` (4,392,762 bytes bytes): the patch, uploaded separately and deliberately left out of `SHA256SUMS`, since it carries Capcom's script rather than just tool code.
- `GK2-v1.10.0.zip`: the same patch bundled with `xdelta3.exe` and a short README, for anyone who would rather not install a separate tool.
- Full apply steps, source and output sizes and hashes, and troubleshooting are in [README.md](README.md).

## Credits

The AAI2 Final v2 fan translation team did the hard part: without their patch there is nothing to inject into and no font to render the result. This project is built entirely on top of their work and leaves their ATTENTION notice intact in every build. The tooling was written with LLM assistance, Claude, driven through Claude Code, over a series of sessions; what ships in the ROM is Capcom's own script, art and recordings plus the fan team's assets, nothing generated.
