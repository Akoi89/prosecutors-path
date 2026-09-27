Version 1.10.0 fixes a Case 2 rebuttal freeze and the same fault in Case 4, several lines and testimony that were cutting off partway through, and staging the newer game had re-tuned. It also adds accents, gives Mind Chess its real name, and moves more of the script to Capcom's writing in a smaller ROM.

## What this build fixes

- **A freeze in Case 2, right when Gavèlle's rebuttal starts.** No statement showed up and no button did anything from there.
- **A possible freeze in a Case 4 rebuttal.** The exact same cause as Case 2's, found by checking every scene rather than waiting for a report; nobody has hit it.
- **Lines, prompts and testimony that used to cut off partway through.** A line after a pause ran into the next sentence and stopped mid-word, a question during evidence choice showed only half, and testimony statements lost their ending. All now show in full.
- **The camera, character positions and poses are back to how the DS always showed them**, instead of the newer game's re-tuned staging: a camera stopping short, someone left out of frame, or a character in the wrong pose, all fixed scene by scene.
- **Logic cards and Mind Chess text fit their space, and the Mind Chess banner has its real name.** Card descriptions ran into the frame, and Mind Chess banners and option rows lost text; all now measured in the right font, and the banner reads "Mind Chess", ending on "Checkmate".
- **Accented letters, and two-line titles that break in a better place.** Words like Gavèlle's name and "attaché" now show their accents in dialogue, and a too-long title breaks before a natural word instead of stranding one alone.
- **Every shout the fan patch had re-recorded is Capcom's audio now, and louder.** They had been quieter than the music since the swap; a few stay slightly under the Japanese level on purpose, so they aren't squashed flat to get there.
- **More of the script is Capcom's writing, and the files are smaller.** Tutorial lines naming a DS button now use Capcom's wording, and the ROM drops from about 72.7 MB to 50.6 MB, the patch from about 4.3 MB to 3.9 MB.

## Version history

- **v1.10.0** - two rebuttal freezes fixed, cut-off lines and testimony repaired, DS staging restored, Mind Chess fixed and renamed, accents added, coverage up to 98.8%.
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
- **v1.5.0** - official titles everywhere, Capcom's own shout recordings, and a stricter coverage count.
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

- Most of the game still hasn't been run by anyone; see the Credits below for what has been finished. The Case 2 fix was checked by replaying the tester's own save: the rebuttal opens with all five statements, the game keeps responding, and he played it through to the end. The Case 4 fix is the identical mistake in a different rebuttal, but no save has reached that scene yet, so it has only been checked against the game's own data, not watched running.
- The camera and pose fixes were checked by measurement and by rendering the scenes, not by watching them run on the rig. The Mind Chess banner hasn't been seen on screen yet either; it's rendered from the ROM using the game's own animation positions.
- About one character in eighty is still the fan translation rather than Capcom's, in spots where Capcom's Collection has no matching text at all, or where its wording does not fit a Mind Chess row's bar.
- Bugs listed as fixed in an earlier version have come back before. If something here shows up again, say so. That matters more than this note saying it is handled.

## Files

- `gk2port-windows-x64.exe` and `gk2port-linux-x64`: the build tool, with `SHA256SUMS` alongside them. `gk2port --verify` checks a finished ROM against this version's published reference, `b92d69fa0f91b049071fed7337f4031cce0ed884c0b15b366cae4ee92f512446`.
- `Prosecutors-Path-1.10.0-fan-base.xdelta` (3,922,382 bytes, sha256 `521a11aa848efd67f07fa1c57b8adb7fcd62c780546fee7c6170e14686741358`): the patch, uploaded separately and deliberately left out of `SHA256SUMS`, since it carries Capcom's script rather than just tool code.
- `GK2-v1.10.0.zip`: the same patch bundled with `xdelta3.exe` and a short README, for anyone who would rather not install a separate tool.
- Full apply steps, source and output sizes and hashes, and troubleshooting are in [README.md](README.md).

## Credits

Thanks to **JPScaravino** for the playtesting: Episodes 1 and 3, and the second half of Episode 2, across several builds. The AAI2 Final v2 fan translation team did the hard part: without their patch there is nothing to inject into and no font to render the result. This project is built entirely on top of their work and leaves their ATTENTION notice intact in every build. The tooling was written with LLM assistance, Claude, driven through Claude Code, over a series of sessions; what ships in the ROM is Capcom's own script, art and recordings plus the fan team's assets, nothing generated.
