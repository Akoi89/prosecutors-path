Version 1.11.1 fixes what a player reported, gaps inside long screams and the fan translation's names on the purse's security plan, then a few more fan names I found by checking every picture the fan translation edited. Everything else is as in 1.11.0; saves carry over.

## What this build fixes

- **Gaps inside long screams.** Long breakdowns, such as the two ending Episode 1, showed a small gap mid-row ("AAAAAAA AAAAAAA"). Screams now run on without a gap, including ones with no line break in Capcom's script.
- **Fan names on the purse's security plan.** The security plan you pull out of the purse in the Episode 1 trash can still carried the fan translation's names, Rooke and Knightley. It now reads Rook and Knight.
- **Stray spaces after hyphens.** A few words showed "long- standing" or "muddle- headed". They no longer have a stray space after the hyphen, and one very long phrase no longer breaks mid-word.
- **Fan names left in pictures.** The Episode 3 opening card's cake-show logo now reads Capcom's "Samson & Judy's Bake 'n' Bop!", the cake-contest maps say Gusto's, Scone's, Tangaroa's and Frost's Room, and the victim's letter in the Court Record reads Ms. Rosie Ringer. I didn't find any other pictures with fan names.
- **Six Logic keyword cards.** "Simon's stunt" now reads Capcom's "Mr. Saint's big moment". Five more that kept the fan's wording now read "Bloody lamp", "Lack of knowledge", "Scone's rulebreaking", "Vehicle activity" and "No Shaun".
- **A Court Record title.** One title that was still in Japanese now reads Capcom's "Promise Notebook".

## Version history

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

- The tester JPScaravino has finished Episodes 1, 3 and 4 and the second half of Episode 2. Episode 5 hasn't been reported finished, and a lot of optional dialogue hasn't been played by anyone. The Lotta crash fix (1.11.0) was checked by replaying his own save, and he then finished Episode 4 on a later build. The Logic banner fix, the touch-tap switches and 1.10.0's camera and pose fixes were checked by measurement and rendering, not on a running game. For 1.11.1, on a running game I checked the purse paper, Wang's scream at the end of Episode 1 (on a build from just before the last scream change), the Episode 3 opening card and the victim's letter in the Court Record, and two of the cake-contest room maps. The rest I checked by decoding the built ROM and by renders.
- I booted test builds of 1.11.0 into the first case on a DSi through TWiLight Menu++ and on a DSPico, and the 1.11.0 release build boots on both too. The 1.11.1 release build boots on both as well. Nothing deeper has been tried on real hardware, and no original DS has been tried at all.
- "Gavelle" has no accent on the Case 4 visitor log, in Organizer descriptions and in Mind Chess, where the lettering has no accented letters. In dialogue it is Gavèlle.
- The fan translation remains only where Capcom's Collection has no matching text (mostly DS-only save and menu messages) or its wording doesn't fit a Mind Chess row's bar. My own lines in Capcom's style are counted separately.
- Two pieces of a map in a later chapter, an office label and a corridor label, are still in Japanese: the fan patch never translated them, and Capcom's Collection has no English version of that map.

**How the figure is counted.** 99.4% is the share of the script's characters that are Capcom's, measured by a tool in the repository. Based on an analysis of the game's code rather than a full playthrough, about 99.8% of the text you can actually see is Capcom's official wording. The counting changed slightly: a fan row already matching Capcom's wording now counts as Capcom's, and my own lines are reported separately. 1.10.0 said 98.8%; before the 1.5.0 correction it was 96.5%.

## Files

- `gk2port-windows-x64.exe` and `gk2port-linux-x64`: the build tool, with `SHA256SUMS` alongside them. `gk2port --verify` checks a finished ROM against this version's published reference, sha256 a411e3f08019e6227aa30fd4188f3ab26f9b67aebea24f001965bb7f1875d35a.
- `Prosecutors-Path-1.11.1-fan-base.xdelta` (3,937,394 bytes, sha256 17e5e8120db58339d5475b8f5362ed5b2f7f466a5596f3c9b06e726f4a138cc4): the patch, uploaded separately and left out of `SHA256SUMS` because it carries Capcom's script.
- `GK2-v1.11.1.zip` (4,094,338 bytes, sha256 4f935a4188dd903e257f57b7a95b38d4037de5b800f23ba2a0d2a8dde1270be9): the same patch bundled with `xdelta3.exe` and a short README.
- Apply steps, sizes, hashes and troubleshooting are in [README.md](README.md).

## Credits

Thanks to **JPScaravino** for the playtesting across several builds. His save state found the Lotta crash and his screenshot the stray Logic banner letters. Thanks also to the player on Reddit whose report started 1.11.1. The AAI2 Final v2 fan translation team did the hard part: without their patch there is nothing to inject into. This project is built on their work and keeps their ATTENTION notice in every build. The tooling was written with LLM assistance, Claude, driven through Claude Code; what ships in the ROM is Capcom's own script, art and recordings plus the fan team's assets, nothing generated.
