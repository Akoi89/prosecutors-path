Version 1.11.1 fixes two things a player reported: small gaps inside long screams, and the fan translation's names on the security plan you pull out of the purse. Everything else in the text and the game is as it was in 1.11.0, and saves carry over.

## What this build fixes

- **Gaps inside long screams.** The long breakdowns, such as the two at the end of Episode 1, showed a small gap in the middle of a row, like "AAAAAAA AAAAAAA". Capcom's script breaks a long scream across lines to suit the Switch's wider text box, and the conversion had turned each of those breaks into a space. The scream now runs on with no gap and is laid out in even rows. Every other text box is unchanged.
- **Rooke and Knightley on the security plan in the purse.** The plan you pull out of the purse in the Episode 1 trash can is a 3D paper in the examine view, and it still carried the fan translation's names on its handwriting and legend. It now reads Rook and Knight, matching the dialogue and the flat Security Plan picture that 1.8.0 fixed. I checked it in the game.

## Version history

- **v1.11.1** - gaps inside long screams closed, Rook and Knight on the purse's security plan.
- **v1.11.0** - Case 4 crash after talking to Lotta fixed, Mind Chess banner redrawn, "Bide my time" button, burn-mark tap, Logic banner leftovers, touch-tap switches, coverage 99.4%.
- **v1.10.0** - two rebuttal freezes, cut-off text, DS staging, accents.
- **v1.9.1** - menu button lettering.
- **v1.9.0** - every line re-measured.
- **v1.8.6** - answer menus that froze.
- **v1.8.5** - Logic keyword cards relettered.
- **v1.8.4** - Ms. Bound's talk opens hers, not Larry's.
- **v1.8.3** - location cards laid out the DS way.
- **v1.8.2** - "John Doe" is John Doe again.
- **v1.8.1** - silent boxes stop moving mouths.
- **v1.8.0** - six pictures carry Capcom's names.
- **v1.7.0** - close-up documents use Capcom's wording.
- **v1.6.4** - highlighted terms keep color across boxes.
- **v1.6.3** - long titles no longer squashed.
- **v1.6.2** - closing quotes no longer look like apostrophes.
- **v1.6.1** - the 1.6.0 downloads were missing files.
- **v1.6.0** - Capcom's choice buttons; descriptions keep their last letter.
- **v1.5.2** - an Episode 1 hang.
- **v1.5.1** - last five fan character names.
- **v1.5.0** - official titles, Capcom's shouts, stricter coverage count.
- **v1.4.4** - ten lines that shipped cut off.
- **v1.4.3** - Episode 1 freezes at the Gourd Lake scene. Update before playing.
- **v1.4.2** - an Episode 1 freeze.
- **v1.4.1** - one line too wide for its menu.
- **v1.4.0** - Capcom's character names, everywhere.
- **v1.3.4** - a description contradicted a room's name.
- **v1.3.3** - a freeze in the Little Thief scenes.
- **v1.3.2** - setup help, no game changes.
- **v1.3.1** - three autopsy descriptions fixed.
- **v1.3.0** - last big chunks of missing text.
- **v1.2.1** - one missing line restored.
- **v1.2.0** - most missing text recovered.

## Known problems

- The tester JPScaravino has finished Episodes 1, 3 and 4 and the second half of Episode 2, across several builds (the Credits have the detail). Episode 5 hasn't been reported finished, and a lot of optional dialogue (wrong answers, side conversations) hasn't been played by anyone. The Lotta crash fix (1.11.0) was checked by replaying his own save, and he then finished Episode 4 on a later test build. The Logic banner fix, the touch-tap switches and 1.10.0's camera and pose fixes were checked by measurement and rendering rather than on a running game. For 1.11.1, the purse paper was checked on a running game, from a new game to the trash can, and the scream rows were measured against the text box. The scream screens in the emulator: {{SCREAM_RIG}}
- I booted test builds of 1.11.0 into the first case on a DSi through TWiLight Menu++ and on a DSPico, and the 1.11.0 release build boots on both too. {{HW_BOOT}} Nothing deeper has been tried on real hardware, and no original DS has been tried at all.
- "Gavelle" has no accent on the Case 4 visitor log, in Organizer descriptions and in Mind Chess, because the lettering there has no accented letters. In dialogue it is Gavèlle as before.
- The fan translation remains only where Capcom's Collection has no matching text, mostly DS-only save and menu messages, or where its wording does not fit a Mind Chess row's bar. The lines I wrote in Capcom's style are counted separately.

**How the figure is counted.** 99.4% is the share of the script's characters that are Capcom's, measured by a tool in the repository (the README says how to run it). Based on an analysis of the game's code rather than a full playthrough, about 99.8% of the text you can actually see in the game is Capcom's official wording. The counting changed slightly: a fan row already matching Capcom's wording now counts as Capcom's, and my own lines are reported separately. 1.10.0 said 98.8%; before the 1.5.0 correction the figure was 96.5%, which counted fan-written rows as official once Capcom's names were swapped in.

## Files

- `gk2port-windows-x64.exe` and `gk2port-linux-x64`: the build tool, with `SHA256SUMS` alongside them. `gk2port --verify` checks a finished ROM against this version's published reference, sha256 {{ROM_SHA256}}.
- `Prosecutors-Path-1.11.1-fan-base.xdelta` ({{XDELTA_SIZE}} bytes, sha256 {{XDELTA_SHA256}}): the patch, uploaded separately and deliberately left out of `SHA256SUMS`, since it carries Capcom's script rather than just tool code.
- `GK2-v1.11.1.zip` ({{ZIP_SIZE}} bytes, sha256 {{ZIP_SHA256}}): the same patch bundled with `xdelta3.exe` and a short README, for anyone who would rather not install a separate tool.
- Full apply steps, source and output sizes and hashes, and troubleshooting are in [README.md](README.md).

## Credits

Thanks to **JPScaravino** for the playtesting: Episodes 1, 3 and 4, and the second half of Episode 2, across several builds. His save state found the Lotta crash and his screenshot the stray Logic banner letters. Thanks also to the player on Reddit whose report turned up both things fixed in 1.11.1. The AAI2 Final v2 fan translation team did the hard part: without their patch there is nothing to inject into and no font to render the result. This project is built entirely on their work and leaves their ATTENTION notice intact in every build. The tooling was written with LLM assistance, Claude, driven through Claude Code,; what ships in the ROM is Capcom's own script, art and recordings plus the fan team's assets, nothing generated.
