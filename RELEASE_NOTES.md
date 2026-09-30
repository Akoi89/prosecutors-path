Version 1.11.0 fixes a Case 4 crash that 1.10.0 and earlier versions can hit after talking to Lotta. It also repairs a handful of smaller things and moves more of the script to Capcom's writing.

## What this build fixes

- **A crash in Case 4 after talking to Lotta.** Once her scene ended, opening Logic or saving froze the game on a white or black screen. Capcom's longer English had made that room's script too big for the space the game loads it into. Long conversations are now split in two with every word kept, and the same fix covers the other scenes over the limit.
- **The Mind Chess banner is in Capcom's lettering.** The title at the start of a Mind Chess and the one that ends it are drawn the way Capcom's are, and "Checkmate" is one piece, so it no longer flashes as "Chckmate" while it zooms in. It also loads with less memory.
- **The Mind Chess wait button.** It said "Wait and see", the fan's wording; it now says Capcom's "Bide my time".
- **Tapping "burn mark" in Case 4 works again.** The tap area had stayed where the Japanese lettering was, so pointing at the words themselves was rejected.
- **Stray letters on three Logic keyword banners.** "Hidden body" read "Hidden body den?", and two others carried leftovers from the fan version. They show only their own text now.
- **Scene fixes.** The fan version's touch-tap switches during scenes are back, and holding B no longer freezes a character partway through walking in.
- **Text that breaks in a better place, and more of it Capcom's.** Long lines split across two boxes now break at a sentence end. Three scenes use Capcom's words, and many descriptions, Logic cards and Mind Chess options that fell back to the fan's wording are Capcom's, shortened only where they would not fit.
- **Lines Capcom never wrote.** Save-menu messages, slot labels, some card descriptions and a few dialogue lines are in Capcom's style. Fewer than thirty lines, not counted as Capcom's own.

## Version history

- **v1.11.0** - Case 4 crash after talking to Lotta fixed, Mind Chess banner redrawn, coverage 99.4%.
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

- The tester JPScaravino has finished Episodes 1, 3 and 4 and the second half of Episode 2, across several builds (the Credits have the detail). Episode 5 hasn't been reported finished, and a lot of optional dialogue (wrong answers, side conversations) hasn't been played by anyone. The crash fix was checked by replaying his own save, and he then finished Episode 4 on a later test build. The Logic banner fix, the touch-tap switches and 1.10.0's camera and pose fixes were checked by measurement and rendering rather than on a running game.
- I booted test builds of this release into the first case on a DSi through TWiLight Menu++ and on a DSPico, and the release build boots on both too. Nothing deeper has been tried on real hardware, and no original DS has been tried at all.
- "Gavelle" has no accent on the Case 4 visitor log, in Organizer descriptions and in Mind Chess, because the lettering there has no accented letters. In dialogue it is Gavèlle as before.
- About one character in 180 is still the fan translation, where Capcom's Collection has no matching text or its wording does not fit a Mind Chess row's bar. The lines I wrote in Capcom's style are counted separately.
- Bugs listed as fixed in an earlier version have come back before. If one shows up again, please say so.

**How the figure is counted.** 99.4% is the share of the script's characters that are Capcom's, measured by a tool in the repository (the README says how to run it). The counting changed slightly: a fan row already matching Capcom's wording now counts as Capcom's, and my own lines are reported separately. 1.10.0 said 98.8%; before the 1.5.0 correction the figure was 96.5%, which counted fan-written rows as official once Capcom's names were swapped in.

## Files

- `gk2port-windows-x64.exe` and `gk2port-linux-x64`: the build tool, with `SHA256SUMS` alongside them. `gk2port --verify` checks a finished ROM against this version's published reference, sha256 fccfb88e9943c11dc7f9a00ab7c61d471c050495bcf9899aa99b021afada34f4.
- `Prosecutors-Path-1.11.0-fan-base.xdelta` (3,928,935 bytes, sha256 ab15e528aedcf684b771f1541d978384e9689da0711982c31c97f38ac5379fe8): the patch, uploaded separately and deliberately left out of `SHA256SUMS`, since it carries Capcom's script rather than just tool code.
- `GK2-v1.11.0.zip`: the same patch bundled with `xdelta3.exe` and a short README, for anyone who would rather not install a separate tool.
- Full apply steps, source and output sizes and hashes, and troubleshooting are in [README.md](README.md).

## Credits

Thanks to **JPScaravino** for the playtesting: Episodes 1, 3 and 4, and the second half of Episode 2, across several builds. His save state found the Lotta crash and his screenshot the stray Logic banner letters. The AAI2 Final v2 fan translation team did the hard part: without their patch there is nothing to inject into and no font to render the result. This project is built entirely on their work and leaves their ATTENTION notice intact in every build. The tooling was written with LLM assistance, Claude, driven through Claude Code,; what ships in the ROM is Capcom's own script, art and recordings plus the fan team's assets, nothing generated.
