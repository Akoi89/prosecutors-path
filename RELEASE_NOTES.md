Version 1.11.2 fixes the Case 3 freeze reported in issue 3 and puts Capcom's wording on a long list of pictures, most of them found after JPScaravino's Episode 5 reports. The script is as in 1.11.1 apart from the Case 3 commands.

## What this build fixes

- **The Case 3 freeze.** After Ms. Bound's second rebuttal, Edgeworth's memory of the ice block began on a white top screen and nothing responded. Every version from 1.10.0 on had it. A command that put two characters on screen had been dropped while the commands waiting on them stayed; they now go together.
- **Bigg Building and the city map.** "Grand Tower" is gone from the city map, the cross-sections and the place cards, and the other city place names match Capcom's map.
- **Markers on maps and floor plans.** The round markers carry Capcom's letters, so the red B for Chairman Winner is a W.
- **Nameplates.** "Man in Black" no longer reads "ManinBlack", and the redrawn names are evenly spaced and centred.
- **Plans and map pieces.** The prison, detention center and Zodiac Hall plans, the Gourd Lake pieces and the leaflet map use Capcom's wording, and an office and a corridor label that were still Japanese are in English.
- **Evidence and close-ups.** A ticket, a keycard, a notebook, the Angel's Cookbook painting and its plaques, weight markings and some icon labels use Capcom's words.
- **Signs painted into backgrounds.** The prison motto, the Maximum Security door, the circus banner, the cotton candy stand, a few more signs and the nurse's cap use Capcom's lettering.
- **The Case 4 visitor log.** It is laid out like Capcom's and shows "Gavèlle" with its accent.

## Version history

- **v1.11.2** - the Case 3 freeze fixed, Bigg Building, Capcom's wording on maps, plans, signs, item pictures and nameplates.
- **v1.11.1** - screams without gaps, Rook and Knight on the purse's security plan, Capcom's names on more pictures and Logic cards.
- **v1.11.0** - Case 4 crash after Lotta fixed, Mind Chess banner redrawn, touch-tap switches, coverage 99.4%.
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

- JPScaravino has finished Episodes 1, 3 and 4 and the second half of Episode 2. Episode 5 hasn't been reported finished, and a lot of optional dialogue hasn't been played by anyone.
- I checked the Case 3 fix in the emulator from a save just before the memory scene: on 1.11.1 the screen goes white and stays that way, and with the fix the scene plays on. I haven't replayed the rebuttal leading into it, and the reporter hasn't confirmed yet.
- The new pictures were checked by decoding the built ROM. In the emulator I saw the new floor-plan marker and every evidence icon in an Episode 5 save draw correctly; the city maps and the rest haven't been seen on a running game yet.
- The 1.11.0, 1.11.1 and 1.11.2 release builds boot on a DSi through TWiLight Menu++ and on a DSPico, and 1.11.2 played the Episode 1 opening movie on both. Nothing deeper has been tried on real hardware, and no original DS at all.
- A few pictures were too faint for me to read with confidence, so a picture or two may still carry the fan's wording. If you spot one, send it.
- "Gavelle" has no accent in Organizer descriptions and in Mind Chess, where the lettering has no accented letters.
- The fan translation remains only where Capcom's Collection has no matching text (mostly DS-only save and menu messages) or its wording doesn't fit a Mind Chess row's bar. My own lines in Capcom's style are counted separately.

**How the figure is counted.** 99.4% is the share of the script's characters that are Capcom's, measured by a tool in the repository. Based on an analysis of the game's code rather than a full playthrough, about 99.8% of the text you can actually see is Capcom's official wording. The counting changed slightly: a fan row already matching Capcom's wording now counts as Capcom's, and my own lines are reported separately. 1.10.0 said 98.8%; before the 1.5.0 correction it was 96.5%.

## Files

- `gk2port-windows-x64.exe` and `gk2port-linux-x64`: the build tool, with `SHA256SUMS` alongside them. `gk2port --verify` checks a finished ROM against this version's published reference, sha256 e8d391bbe2c5fddbb5b4d871c99680b4fcd0fda43e023e45d3e2d2d423351170 (50,548,648 bytes).
- `Prosecutors-Path-1.11.2-fan-base.xdelta` (5,547,665 bytes, sha256 3f57757623376a085f12f1a9439308ef68d7a9402b4953503fd971541fa72200): the patch, uploaded separately and left out of `SHA256SUMS` because it carries Capcom's script.
- `GK2-v1.11.2.zip` (5,705,404 bytes, sha256 c09bf98d418955ab1b50b6b782d60982d5b5ef225d9b338752beaca7f52f8b16): the same patch bundled with `xdelta3.exe` and a short README.
- Apply steps, sizes, hashes and troubleshooting are in [README.md](README.md).

## Credits

Thanks to **meowcitycentral** for reporting the Case 3 freeze in issue 3 and for checking the same save on 1.9.1, which narrowed it down. Thanks to **JPScaravino** for the playtesting across several builds: his save state found the Lotta crash, his screenshot the stray Logic banner letters, and his Episode 5 reports on 1.11.1 the "Grand Tower" on the city map, the red B on a floor plan where Capcom has a W, and the run-together "Man in Black" nameplate. Thanks also to the player on Reddit whose report started 1.11.1. The AAI2 Final v2 fan translation team did the hard part: without their patch there is nothing to inject into. This project is built on their work and keeps their ATTENTION notice in every build. The tooling was written with LLM assistance, Claude, driven through Claude Code; what ships in the ROM is Capcom's own script, art and recordings plus the fan team's assets, nothing generated.
