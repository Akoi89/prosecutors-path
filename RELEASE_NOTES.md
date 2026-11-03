Version 1.11.5 changes the game's title in the DS menu to "Prosecutor's Gambit" and puts Capcom's newspaper name on the Newspaper Clipping and two other Episode 1 newspaper pages. Nothing else in the game changed apart from the version text on the title screen, and the script's wording is as in 1.11.4.

## What this build fixes

- **Menu title.** The title line the DS menu shows for the game read "Prosecutor's Path", which could be mistaken for the fan ROM there. It now reads "Prosecutor's Gambit".
- **Newspaper Clipping.** In the Court Record the clipping carried the fan translation's paper name, "Daily Express", with its own headline. It now shows Capcom's: "Mercurial News", "Evening Edition" and "President of Zheng Fa to Visit". The small icon of the clipping matches.
- **Two more newspapers.** Two other newspaper front pages in Episode 1 also said "Daily Express" and now say "Mercurial News" across the top.

## Version history

- **v1.11.5** - the DS menu title reads "Prosecutor's Gambit", and the Newspaper Clipping, its icon and two more Episode 1 newspapers carry Capcom's paper name.
- **v1.11.4** - 17 long topic buttons no longer look bold.
- **v1.11.3** - two testimony titles (Episode 5 and the last chapter of Episode 3) centred, and the Episode 3 cooking-show line that never appeared.
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

- JPScaravino has finished Episodes 1, 3, 4 and 5 (Episode 5 on 1.11.1) and the second half of Episode 2. JuanCraft_yt played all of Episode 2 on 1.11.4 and reported that everything works and looks good. He also said Episode 3 worked from start to finish, without saying which build. A lot of optional dialogue hasn't been played by anyone.
- I checked every topic button by its rendered picture, and all of them fit their boxes, but I haven't checked each one in a running game. JuanCraft_yt looked at renders of the 17 new buttons and called them significantly better.
- I checked the Case 3 fix in the emulator from a save just before the memory scene: on 1.11.1 the screen goes white and stays that way, and with the fix the scene plays on. I haven't replayed the rebuttal leading into it, and the reporter hasn't confirmed yet.
- I checked the centring fix in the emulator on test lines of several widths, and on the cooking-show box, where the third line now prints. A title that was already centred, "-- President Wang's Testimony --", still is. I haven't seen the two fixed testimony titles in their own scenes, because the tester's save brings back the old box from the save file.
- The new pictures were checked by decoding the built ROM. In the emulator I saw the new floor-plan marker and every evidence icon in an Episode 5 save draw correctly; the city maps and the rest haven't been seen on a running game yet.
- The 1.11.0, 1.11.1 and 1.11.2 release builds boot on a DSi through TWiLight Menu++ and on a DSPico, and 1.11.2 played the Episode 1 opening movie on both. The 1.11.3 release build went further on both: past the opening movie and into play in Episode 1. Nothing deeper has been tried on real hardware, and no original DS at all. I haven't booted the 1.11.5 build on a DSi or a DSPico yet.
- I checked the four newspaper pictures and the new menu title by decoding the built ROM. In the emulator I saw the Newspaper Clipping in the Court Record of an Episode 1 save with Capcom's wording and played about five minutes on without a problem. I haven't seen the other three pictures in a running game, or the new title in a DS menu, yet.
- A few pictures were too faint for me to read with confidence, so a picture or two may still carry the fan's wording. If you spot one, send it.
- "Gavelle" has no accent in Organizer descriptions and in Mind Chess, where the lettering has no accented letters.
- The fan translation remains only where Capcom's Collection has no matching text (mostly DS-only save and menu messages) or its wording doesn't fit a Mind Chess row's bar. My own lines in Capcom's style are counted separately.

**How the figure is counted.** 99.4% is the share of the script's characters that are Capcom's, measured by a tool in the repository. Based on an analysis of the game's code rather than a full playthrough, about 99.8% of the text you can actually see is Capcom's official wording. The counting changed slightly: a fan row already matching Capcom's wording now counts as Capcom's, and my own lines are reported separately. 1.10.0 said 98.8%; before the 1.5.0 correction it was 96.5%.

## Files

- `gk2port-windows-x64.exe` and `gk2port-linux-x64`: the build tool, with `SHA256SUMS` alongside them. `gk2port --verify` checks a finished ROM against this version's published reference, sha256 e0eb68c5f84673e517212b790706f2523ed244bd35e4372f388fcd8d6139f83b (50,547,084 bytes).
- `Prosecutors-Path-1.11.5-fan-base.xdelta` (5,636,960 bytes, sha256 dba091055ffbc5f8fa07c01ef13a2a81c8998465485f8c54cb12bb6f5dea27a9): the patch, uploaded separately and left out of `SHA256SUMS` because it carries Capcom's script.
- `GK2-v1.11.5.zip` (5,794,726 bytes, sha256 f72717d361f74ffbdcdbac506d2c884eb21f073a5c85e9adc8351803562efefb): the same patch bundled with `xdelta3.exe` and a short README.
- Apply steps, sizes, hashes and troubleshooting are in [README.md](README.md).

## Credits

Thanks to **JuanCraft_yt** for pointing out the bold-looking topic buttons with a screenshot, for checking renders of the new ones, and for playing all of Episode 2 on 1.11.4. Thanks to **meowcitycentral** for reporting the Case 3 freeze in issue 3 and for checking the same save on 1.9.1, which narrowed it down. Thanks to **JPScaravino** for the playtesting across several builds: his save state found the Lotta crash, his screenshot the stray Logic banner letters, and his Episode 5 reports on 1.11.1 the "Grand Tower" on the city map, the red B on a floor plan where Capcom has a W, the run-together "Man in Black" nameplate and the testimony title whose second line sat against the left edge. He has also played Episode 5 start to finish on 1.11.1. Thanks also to the player on Reddit whose report started 1.11.1. The AAI2 Final v2 fan translation team did the hard part: without their patch there is nothing to inject into. This project is built on their work and keeps their ATTENTION notice in every build. The tooling was written with LLM assistance, Claude, driven through Claude Code; what ships in the ROM is Capcom's own script, art and recordings plus the fan team's assets, nothing generated.
