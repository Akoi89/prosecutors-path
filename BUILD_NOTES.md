# Build Notes

This file is the full technical record of every release: the exact defects found, how they
were measured, what changed byte for byte, and the coverage figures behind each version. It
exists because RELEASE_NOTES.md is now written for players, in short entries. Everything that
used to live there is kept here in full.

Port Capcom's official English localization of *Gyakuten Kenji 2* into the Nintendo DS ROM.

**99.4% of the script's text is Capcom's writing** (measured by `tools/coverage.py`;
the exact unit count is in the v1.11.0 entry below). 1.10.0 said 98.8%, 1.5.2 said 93.9%, 1.5.1 said 94.3%: four tutorial
lines went back to the fan text in 1.5.2 and twelve description rows in 1.6.0, see below. Earlier notes said 96.5% and, before that,
98.4%; see the 1.5.0 entry for why the counting changed. The remainder stays in the AAI2
fan translation; the README says exactly why, and which parts.

## v1.11.0: the Case 4 crash after talking to Lotta, long script rows split to fit the engine's load buffer, the fan's touch-tap switches restored, the Mind Chess banner in Capcom's lettering, the burn-mark tap, Logic banner tails, held-B entrances, sentence-end box breaks, and more of the script in Capcom's words

This release is the `next` branch of `port`: 27 commits after the v1.10.0 tag, ending with the 1.11.0 version commit. The DS program code (arm9 and every overlay) is byte-identical to 1.10.0 and to the fan ROM; four files in the ROM differ from 1.10.0 (`jpn/spt.bin`, `jpn/idlocal.bin`, `jpn/logic_keyword_local.bin`, `com/cutdata.bin`), read back with `python audits/romdiff.py` on the 1.10.0 output against the release candidate. Coverage, measured with `python tools/coverage.py` on the release ROM:

    python tools/coverage.py out/GK2-v1.11.0-official-english.nds
                  official   char units
    Episode 1        97.7%  175,424 / 179,474
    Episode 2       100.0%  368,696 / 368,696
    Episode 3       100.0%  377,751 / 377,751
    Episode 4       100.0%  297,663 / 297,663
    Episode 5       100.0%  497,811 / 497,811
    Menus & UI       94.5%  105,423 / 111,588
    TOTAL            99.4%  1,822,768 / 1,832,983
    TOTAL (without the identical-wording counter fix):  99.4%  1,822,573 / 1,832,983
    identical-wording counter fix adds: 10 rows / 195 char units
    rows rewritten in Capcom's style: 29 rows, replacing 1,783 fan units

1.10.0 measured 98.8% (1,810,475 / 1,832,983; rerun today on the released 1.10.0 ROM, sha256 d6f3891a..., with the same counting), so the official-text total is up by 12,098 units counted the same way, or 12,293 with the counter fix's 195. The remaining 10,215 units (0.6%) are fan text or rows I wrote (see the counting note below).

### The Case 4 crash after talking to Lotta (commits 2e474d1 and 912ae1b)

A tester reported that in early Case 4, after talking to Lotta, the Logic, Organizer and Save menus failed: Logic showed a white screen forever, Save a black one, Organizer still worked. His melonDS save state from that point reproduced it at once on 1.10.0 (the public release) and on the release candidates of the time, and did not reproduce on the fan ROM. Entry 230's load size was then measured on 1.8.4, 1.8.5, 1.8.6, 1.9.0, 1.9.1 and 1.10.0, and it is over 0x2000 in all six, so the public docs say 1.10.0 and earlier versions are affected; earlier than 1.8.4 was not measured. A snapshot of the frozen state showed an ARM9 data abort in the heap's free routine, on the block right after the overrun one (the field object keeps five 0x31C-byte script records, each with its own 0x2000-byte buffer).

Cause. The field engine loads the current map's NPC or check script (an entry of `jpn/spt.bin`) into a fixed 0x2000-byte heap buffer. It sizes the read as the 12-byte header plus 8 bytes per row-table entry plus two bytes per unit of the longest row, and it reads that many bytes straight into the buffer with no comparison against 0x2000 (arm9 0200d9ac computes the size, 0200d974 does the read, overlay 7 020b6444 is the slot loader). In this port entry 230 (the Case 4 storeroom talk script) needs 0x2400 to 0x2408 bytes, because its longest row, row 82, the auction conversation with Lotta, is 4,205 units against the fan's 3,551. The extra bytes land on the next record's heap header, and the next Logic or Save teardown frees that block and aborts. The fan has no NPC or check script over the limit; the port had exactly this one.

A second family, the chapter scene scripts loaded into the fifth record, also runs past 0x2000 in both ROMs (27 in the port, 11 in the fan). Those spill into free heap rather than a live header, which is why they had never crashed.

Fix (`tools/rowsplit.py`, runs after `sentence_breaks` and the tap-switch pass, before the archive is built). Every field-slot entry is now held to a need of 0x2000 or less: 29 entries were over it, and 33 rows in them were split, with every word kept. A cut is allowed only after an `{E102}` (box end) that is followed by `{E100}` or `{E101}`. The first piece ends in a jump to the appended row (`{E081:n}`, a plain jump within the same entry, checked in the arm9 handler), and the new row's read mark is the original row's mark plus the boxes before the cut, so the game's read-flag bookkeeping is unchanged. No words are cut and no code is dropped. Entry 230's row 82 is cut at unit 2,048 into pieces of 2,050 and 2,157 units, as new row 99, and the entry's need falls from 0x2400 to 0x17e2. Across the whole ROM the largest field-slot need is now 0x1e30 (entry 290, slot 3, the NPC and check scripts) and 0x1fd4 (entry 334, slot 4, the chapter scene scripts); the only entry still over 0x2000 is 342, a Logic/trial script loaded another way, and it is byte-identical to the fan's.

Checks run. A verifier with its own copy of the arity table checked all 33 rows: pieces rejoin to the original row, every cut sits after `{E102}` before `{E100}`/`{E101}`, every jump targets the new row, every read mark matches. The 421 rows in those entries that were not split are identical to the baseline. Only `jpn/spt.bin` differs from the previous candidate. `coverage.py` and the per-index audits fold the appended rows back through the build's split manifest (`tools/rowfold.py`), so coverage is unchanged by the split (the figure above). On the rig, replaying the tester's crash recipe (examine the statue, watch the Lotta scene, walk left and Talk, then open Save and Logic) now shows the Save prompt and opens Logic, and the split auction conversation plays the same as before the split. The tester then finished Episode 4 on a later test build that carries this fix.

Predictive checks after the fix, because this is a class of bug and not one row (`tools/bufcheck.py`, now run by every build right after the last writer of the affected files, and covered by `tools/test_bufcheck.py` negative tests): (a) every script entry's load need against its buffer, (b) the longest text box in units, (c) the longest examine row, (d) every idlocal entry against the fan's size, (e) the cutdata slot in use, and (f) the Logic banner tails below. A static search (disassembly and data, not run on an emulator) of every other loader of `spt`, `idlocal` or `cutdata` into a fixed buffer found none that can overflow: every other loader sizes its buffer from the entry's own header, and compressed graphics are decompressed through temporary buffers sized from the archive table.

### The Mind Chess banner file is stored properly compressed (commit 912ae1b)

The Mind Chess banner graphic (`jpn/idlocal.bin` entry 25) had been stored as literal-only LZ11, bigger than its own raw data. Nothing overflowed, but the banner needed far more temporary memory while loading than the fan's did. It now uses a real LZ11 encoder (`tools/lz11.py`, optimal parse, window 0x1000, minimum displacement 2 like every stream in the fan's file), which brings the load much closer to what the fan's needed. The decoded bytes are identical to before (compared with two independent decoders), so nothing on screen changes; only this one entry's stored bytes differ, and the ROM file is about 36 KB smaller.

### The fan's touch-tap switches restored (commit 0363089)

`{E11C:n}` sets or clears one bit in the main game-state block. Its only reader is the per-frame tap test of the field's tappable hotspots (overlay 7 020BC8DC), which honours a stylus tap inside a hotspot only while the bit is 1, so it is an on/off switch for taps during scripted scenes. The fan script has 91 of them; 1.10.0 had 79. Fifteen of the fan's switches were missing, in 12 rows (16/6, 16/33, 16/34, 89/1, 89/2, 101/5, 177/5, 231/48, 264/0, 277/1, 310/17, 310/23), and three rows (22/0, 293/9, 387/1) carried an off-switch the fan never had. `tools/e11c.py` puts back the fifteen and removes the three, each guarded by the hash of the row it expects; afterwards every row's ordered list of these commands equals the fan's (91 against 91). This was not the cause of the Lotta crash (reading the code shows a missing switch only leaves taps live during a scene), and no report traces back to it; it restores the fan's behaviour.

### The Mind Chess banner in Capcom's lettering (commit 27fdd2f)

The banner that flies in at the start of a Mind Chess and the one that ends it now use Capcom's own lettering for "Mind", "Chess", "Checkmate" and "Commence", laid out the way Capcom's banner is. "Checkmate" is drawn as one piece instead of pieces that grew separately, which removes the 1.10.0 frame sequence "Clckmate", "Chckmate", "Chickmate" while it zooms in. On the rig every zoom step reads "Checkmate" whole. One thing remains and was accepted: for a single frame a 1 to 2 pixel hairline can show between the e and the c, because the seam runs through outline ink; 1.10.0 had the same hairline at one zoom scale. The tester's comment on the first candidate was that the lettering looks great.

### The Logic keyword banner tails (commit 532583e)

The tester found the Logic keyword banner "Hidden body" reading "Hidden body den?". Cause: `jpn/logic_keyword_local.bin` banners 242, 244 and 246 ("Hidden body", "Was he stomped on?", "Side gate chain cut") span six sprites (192 px wide) but their graphic header declares 1,280 bytes, while the fan stored 256 more bytes after the declared data (fragments of the fan's own text: "den?", "r", "en"). `logic_cards.py` rewrote only the declared 1,280 bytes, so the fan's leftover tails showed beside the new lettering. This has been so since 1.8.5. Fix: the builder now reads the cell's full extent, redraws exactly as before, writes back the whole extent, and reads each rewritten card back as the display sees it, raising if it differs from what was drawn. In the three banners the leftover ink bytes go from 56, 31 and 37 to 0, 3 and 0 (the 3 in banner 244 is the port's own question mark). A scan of every graphic file the build writes (Logic cards, plates, strips, Mind Chess, close-ups, title, opening and save screens) found no other entry with the quirk. Only those three entries differ from the previous candidate, only in the tail bytes. This is checked by rendering the built graphics and by the build's own read-back, not yet on a running game.

### Known limit: "Gavelle" without its accent

The Case 4 visitor log (`upcut_local` entry 242, drawn by `tools/cg_names.py` in the fan's close-up face, `txtcut_font.json`) has no accented glyphs, so it reads "Gavelle". Organizer descriptions and Mind Chess use the small font, which has no accent slot, so the same. No glyph was drawn by hand. In dialogue the accent shows (1.10.0).

### The burn-mark tap (commit cac8385)

In Case 4's Coroner's Findings you are asked to point at the burn mark on the document. The close-up screen carries Capcom's English wording, but the tap rectangle in `com/cutdata.bin` (slot 47, for cut 208) still sat where the Japanese lettering was, so in 1.10.0 it covered the words "of victim's" instead of "burn" and "mark", and the right answer was rejected. `tools/cutdata_hotfix.py` derives the rectangle from the text renderer's own line layout (no typed coordinates), guarded by the hashes of the row text and of the fan's `cutdata.bin`. `audits/audit_hotspots.py` (new) decodes the ROM's image and slot and checks that every "burn" and "mark" pixel is real ink inside an accepted rectangle and that no other lit pixel is; for the other point-at prompts (photos and maps, no phrase) it checks that image and slot are byte-identical to the fan's. On the rig a tap on "burn" was accepted and a tap on "of victim's" rejected. The audit covers only this prompt's text; the other 23 point-at prompts show pictures the build does not modify.

### Held B and the entrances that froze mid-move (commit 3348857)

An animated entrance (`{E111 a,...}`) is normally followed by `{E112 a}`, which waits for that actor's move to finish; 4,188 of the game's 4,221 entrances have it. The other 33 are Capcom's own script, identical in the fan ROM. With B held to skip, the next box's `{E12F ...}` overwrites the actor's single task slot and the move stops where it stands: entry 119, string 3, box 1 leaves Edgeworth at about x = -100 with only a sleeve on screen. `tools/skipguard.py` inserts `{E112 a}` after the `{E111}` at 13 of those entrances, each guarded by the hash of its string; the rest are left alone. Only those strings change, by one command each. On the rig, the Edgeworth scene with B held is now whole.

### Box breaks moved to sentence ends (commit 1c24721)

When Capcom's text does not fit one box, the port splits it, and a scan found 432 dialogue messages where that split fell mid-sentence although a sentence end fit. A three-tier rule classified them (266 automatic, 47 flagged, 119 kept as they were, 60 of those because an animation or sound code blocks the move); I reviewed the flagged tier and approved 46 of the 47. That made 312 breaks to move; 15 were dropped because the new break would cross an animation or sound code, leaving 297. `tools/sentence_breaks.py` moves them. Words, their order and every control code are unchanged, and each moved box is laid out again by the port's own layout and checked against the recorded widths.

### Scenes laid into the fan's box structure, condensed rows, and more Capcom rows

- **Relaid scenes** (a81e78f). Three scenes had stayed the fan's wording because the fan's boxes are laid out differently from Capcom's: entry 93 (Episode 2), entry 236 (Episode 4) and entry 340 (Episode 1, a Logic scene). `tools/relaid_rows.py` keeps the fan's box skeleton byte for byte and lays Capcom's converted words into it, guarded by hashes of the fan strings, Capcom's source strings and the result. In 10 of 101 boxes Capcom's words need a fourth line at 240 px and become two boxes, as the port already does elsewhere.
- **Condensed rows** (425feff, f343782). 89 small-font rows (Mind Chess options in banks 453 to 455, Logic cards and item descriptions in banks 395 and 432) whose Capcom text overflows now carry shorter wording that keeps Capcom's words, each wording approved before it was built; the last four descriptions (tunnel photo, bouquet, shoes, nurse profile) were added in f343782. 89 applied, 0 fell back to the fan.
- **Tolerant lookup** (513b197). 23 descriptions and Logic cards whose Japanese differs from Capcom's only by a comma or the DS-only details suffix now match Capcom's row.
- **Last rows** (7813789). Capcom's line for the Episode 4 gift refusal is ported; one candidate row (DS[36] string 37) was dropped as unreachable. The coverage counter now credits fan rows that already read exactly as Capcom's (see the counting note).

### Rows Capcom never wrote (commits 77fd6b5 and 0064f36)

29 rows had no Capcom counterpart that fit: two guard conversations (13/1, 13/3), the red-dot line (37/9), three organizer descriptions (432/245, 312, 333), 14 save-system prompts (bank 460) and nine save-slot labels ("End" became "Latter"). I wrote them in Capcom's style in `tools/rewrite.py`, each guarded by the hash of the fan row it replaces and each control code checked against the fan row's own. They are measured against their boxes (dialogue in the main font at 240 px and three lines, descriptions in a 140.5 px field of at most four lines, save prompts in a 181 px budget) and are excluded from the official-text count, which reports them on a separate line. The rewritten wording was approved before it was built; six of the save-menu rows (delete confirmation, saving, two load errors, new episode, and the matching dots) were added in 0064f36 so they sit in the same style as the first eight prompts.

### Counting note

Three things about the coverage counter changed in this release, and none of them changes the 99.4%. First, a fan row that already reads exactly as Capcom's own wording (for example a few Mind Chess lines such as "Objection!" and "Hold it!") is now counted as Capcom's; before, it counted as fan text because the bytes matched the fan row. It adds 10 rows and 195 units, and the total is 99.4% with or without it. Second, the rows I wrote in Capcom's style are not counted as Capcom's, and are reported on their own line (29 rows replacing 1,783 fan units). Third, the rows appended by the buffer split are folded back into their original rows through the build's split manifest before rows are compared, so the split does not affect the count. The method for everything else (a row is official when its bytes differ from the fan row after names and titles are applied) is the one set in 1.5.0. The figure is from `python tools/coverage.py`, run against the current build.

### The Mind Chess wait button reads "Bide my time"

The Mind Chess "wait" button showed the fan's "Wait and see", drawn as a picture, where Capcom's Collection says "Bide my time". A tester pointed it out. It is redrawn in Capcom's wording.

### Also in this release

- Every `assert` in the tools became an explicit raise (b34c96b, 86a9172), so a check can no longer be switched off by running Python with `-O`. The output ROM is byte-identical before and after.
- The index-argument guard also restores the string indices of six more codes (`E200`, `E1FD`, `E20A`, `E17E`, `E17F`, `E180`) from the fan (19791cd). A whole-script comparison found all 1,114 occurrences in 1.10.0 already identical to the fan's, so nothing changed in the ROM; it is a guard with an audit fixture.
- `audits/measure_linewidth.py` now measures every dialogue-font line, narration included (8c5aa8a).
- Workflow actions moved to their Node 24 versions (a8f5b5b); saves, zips and 7z archives are ignored by git (0c2e623).

### Testing for this release

The rig replayed the crash recipe and the split conversation (above), the burn-mark tap, the held-B Edgeworth scene, the save and delete prompts, and the Mind Chess banner at start and end. The tester, JPScaravino, finished Episode 4 on the 1.11 test builds (started on the first, finished on the third, "works perfectly from start to finish"); Episode 5 has not been reported finished on any build. I booted test builds of this release on a DSi through TWiLight Menu++ and on a DSPico, into the first case on both. Not seen on the rig: the two guard lines (13/1, 13/3), the red-dot line (37/9), card 432/245 (the last two have no route the scripts could find, so they were checked in the data), the officers' cards, the episode-clear prompts, and the erase-all screen reached by holding B, X and Select at power-on. The Logic banner fix and the tap-switch restoration have been checked in the data and by rendering, not on a running game.

## v1.10.0: the Case 2 rebuttal freeze and its Case 4 twin, four box-boundary defects, the DS-only gate lifted, restored DS staging, Mind Chess fixes, accents, louder shouts and ROM compaction

This release closes out the `fix-string-index-args` branch (commits 180ddaff through 50d11fa
on `port`, ahead of the v1.9.1 tag) plus the earlier button-glyph work. Coverage is
character units of official text over total; the counting method itself has not changed
since it was corrected in 1.5.0 (see that entry above), only the amount of text that
qualifies. Measured today with `python tools/coverage.py "out/GK2 (Official English, DS port).nds"`:

    Episode 1        97.7%  175,424 / 179,474
    Episode 2        99.9%  368,362 / 368,696
    Episode 3       100.0%  377,751 / 377,751
    Episode 4        98.4%  292,970 / 297,663
    Episode 5       100.0%  497,811 / 497,811
    Menus & UI       88.0%  98,157 / 111,588
    TOTAL            98.8%  1,810,475 / 1,832,983

The Menus & UI and total figures are below the 89.3%/98.9% an earlier 1.10.0 candidate measured,
because the Mind Chess font-measurement fix below reverts some rows to the fan's wording
where Capcom's does not fit the bar (723 character units), partly offset by more official
text elsewhere. sha256 of the release build is
`d6f3891ab53609cfff938adb2c79d4bc3f26a6d86697b5167db8f864da0a4a51` (VERSION and
REFERENCE_ROM_SHA256, commit 757baf3), 50,627,184 bytes; two identical builds and a
clean-clone executable doing a full extraction reproduce it.

### The Case 2 and Case 4 rebuttal freezes (entries 92 and 248)

A tester's report of a freeze in Case 2, right at Gavelle's prison rebuttal, reproduced on
the rig from his own save: the rebuttal setup ({E11F} x5, {E120}) points each of the five
statements at a string in the same entry by index, and every one of those indices was one
string early, because `dstext.py` copies the Collection's argument units through unchanged
while the region aligner's re-cutting (`RECUT_SHIFTED`) skews them. Statement 0 landed on an
empty stub, no statement box was drawn, the next menu handler dereferenced a widget that was
never made, and the ARM9 data-aborted and parked in the BIOS. `sweep/GK2_e92_B7.nds`, a
proof build with only entry 92's index arguments corrected, opened the rebuttal clean: five
correct statements in order, on-topic Press reply, no crash, verified by eye.

The toolchain already copied {E187}'s arguments from the fan ROM (the 1.8.6 fix) and
`region_align` rewrote {E081}'s. Commit 0548c257 extends that same copy, gated on equal
argument counts per string, to every other code whose arguments are string indices:

    E187 (both, unchanged)  E11F 1-3  E120 1  E080 0  E0B0 1,3,5,7
    E1C1 0  E164 1  E161 1  E162 0  E1A6 1-3  E1E9 0  E11B 1  E160 0

90 argument units change across 12 entries in Cases 2, 4 and 5; nothing else in the ROM
moves. Entry 248, a Case 4 rebuttal (Gramma's report), carried the identical fault, with one
of its strings pointing at itself. `audits/audit_indexargs.py` (new) fails any build whose
index arguments disagree with the fan ROM's; its fixture checks exit codes clean 0 / broken
1, and the pre-fix release output fails the new audit as expected.

Entry 248 has not been reached on the rig: no known save sits close enough, and it needs
three earlier rebuttals solved first. It is verified only at the data level, the same way
every other entry the rig has not reached is verified: its argument units now match the fan
ROM's exactly, gated the same way as entry 92's.

### Seam cues and the map value (entries 95, 221, 259, 411)

At a re-cut seam the fan ROM keeps some cue commands between a string's last box and its
jump tail; the converter had been moving the Collection's equivalents to the head of the
next string instead. Of five seams flagged by a 2026-08-23 review, three remain in the
current script: entries 95, 221 and 259. Entry 95 is Dogen's testimony in Case 2, a few
scenes after the Gavelle rebuttal: {E11B}<55,18> is a conditional jump (flag 55 -> string
18), and in the fan ROM it is checked at the end of string 16, just before the jump back to
string 8. Mine ended string 16 with that jump and put the check at the head of string 17
instead, so after string 16 the flag was never tested and the testimony could loop forever.
Commit aa605a8 restores each seam's run to match the fan unit for unit, gated so the commands
removed from the next string's head must equal the commands copied into the previous one
(a first cut of this change lost entry 95's {E100}<01>{E121}, which is what that gate now
catches). Entry 411's map list ({E131}) held 3 where the fan and the Japanese retail hold 2;
`DS_VALUE_ARGS` restores it and `audit_indexargs` checks it, the same way the 1.8.6 strip ids
are protected.

### 16 prompt questions and 28 testimony statements trimmed to fit

The DS engine shows each testimony or rebuttal statement in exactly one message box, three
lines; all 262 statements in the fan patch and the Japanese retail fit one box. Capcom's
English for 28 of them needs four lines, so the converter had been spreading them across two
boxes, and the engine only ever shows the first. This was watched on the rig in Case 2:
Gavelle's third statement never showed its second half. Each of the 28 now gives up a word or
two, chosen with the rule that no time, place or detail a contradiction could hinge on is
dropped, reviewed with Gemini before use (`GEMINI_statement_trims.md`) and signed off by the
user.

Separately, when the game asks you to present evidence, point at a spot or press a statement,
the question stays on screen in the box that ends the previous utterance while you choose.
Capcom's English for 16 of these prompts runs to four lines, so the same two-box split
happened, and only the second box stayed up during the choice. A tester's screenshot of
Winner's confrontation ("...couldn't possibly have taken the weapon out of the prison with
them!") showed exactly that, the question missing its first half. Each of the 16 now gives up
a word or two the same way; the Winner line drops the standalone word "possibly"
(`GEMINI_prompt_trims.md`, option B).

Both sets of edits are stored the way `tools/condense.py` already stores condensed
descriptions: keyed by entry and string, a hash of the source text, word positions to delete
or replace, and a hash of the result. No Capcom or fan text is stored in the repository; a
Collection whose wording does not match the hash is left untrimmed (the old two-box behaviour,
not a hang). `tools/stmt_trim.py` was also rewritten so every unit outside an edited word
passes through exactly as it was; the previous version treated the zero-space seam between two
messages in one string as a single word and moved its control codes, which shifted every
message's first word into the box before it on a first build. The generator now refuses any
edit that touches a seam or a box end.

Measured on the merged output: 44 trims (16 prompt, 28 statement) are byte-identical across
every later build in the branch; prompt questions split across boxes go from 9 (the
pre-existing, structurally necessary ones) to the same 9, with three further {E106}
continuations that genuinely need two boxes (Fender's line, and two others).

### The {E106} box-boundary fix

{E106} does not end a message box. Its handler, overlay 7 address 0x020ACEB0, does the
engine's read-mark bookkeeping and returns; only {E102} and {E104} clear the render buffer and
canvas. The converter had been treating {E106} as a box boundary and laying out the text on
each side independently, so where the two sides met on one line the renderer cut the line off
mid-word at the box edge. Eddie Fender's line in Episode 2 ("...I do remember?" / "You
betraying everything you were supposed to stand for") rendered as one run, "remember?You
betraying everythin" with "g you were" lost, photographed at
`rig/proof/e107/CUTOFF_fender_everythin_box.png`.

Correcting the instruments to measure this properly first (commit 3c1fdee) found the true
count of dialogue lines wider than the 240px box was 278 (worst 473px), not the 2 the old,
buggy instrument reported; the fan ROM itself measures 278 the same way, so this is an
inherited defect the tooling could not previously see, not a regression. The fix
(`dstext.e106_clears()`, merged as fa3edcb) keeps buffering both sides of an {E106} as one run
except where a prompt or popup code (one of {E163} {E1CF} {E198} {E160} {E113} {E234} {E19C})
follows before the next text; there, the Japanese retail script shows the box does clear, and
210 of 283 such cases already ran more than 3 lines without clearing, against 0 of 27 on the
other side of the rule. The same helper is shared by `audits/audit_typography.py` and
`audits/measure_linewidth.py` so the instruments and the converter agree.

A rescue pass in the same merge also moves where an over-long message breaks between boxes,
towards a comma or dash instead of mid-phrase, changing 137 strings with every word, control
code and glyph colour unchanged. Measured on the merged output against the pre-merge build:
lines over the 240px box width go from 26 to 2 (widest 469px to 253px), the 44 statement and
prompt trims stay byte-identical, and coverage is unchanged. Verified on the rig:
`fan_tone/RIG_FENDER_D7B.md`, two complete boxes with the arrow visible on
`sweep/GK2_d7b.nds` (sha256 52ca3e4e...), matching the earlier proof at
`fan_tone/RIG_FENDER_E106.md` against the pre-merge candidate.

### DS button glyphs get Capcom's wording and the real DS button name (commit 180ddaff)

Capcom's how-to-play lines carry {E2B0}, an inline picture of the controller button being
described, which the DS engine does not know; `inject.py`'s foreign-code gate discarded the
whole string and the fan translation's version survived instead. Measured on the pre-fix
build, this cost 20 strings and 15,212 character units, almost entirely tutorial material.
`tools/buttons.py` substitutes the DS button's name for the glyph before conversion, from a
20-row, 40-glyph table in `tools/button_icons.json`, every icon id verified against the real
Collection strings. Which button to name comes from the fan row for that same scene, never a
global table, because the same icon means Rewind in one scene and the information list in
another. The inserted name is wrapped in the keyword colour the fan used for the same picture.
18 of the 20 rows now pass the DS-only-command gate on their own; coverage moves from 93.8% to
94.6% (Episode 1 86.4% to 90.3%). The two rows that still fall back to fan text are the
Gumshoe partner-topic rows, where the fan highlights eleven words against Capcom's six.

Commit 2e3d11d closes the last of the 21 button rows: entry 106 string 0, the Episode 2
re-creation switch, names no button in the fan row at all ("select Little Thief on the bottom
screen"). Three independent sources agree it is the Y button: Episode 5's own fan wording for
the same action, Episode 1's fan line naming Y as the partner button, and StrategyWiki's DS
walkthrough for the same scene. 19 of the 21 rows land with this table complete; the injector
reports zero records kept as fan for an official-only control code, where it reported three.

### Zero-unit audit (commit 7e60963, on top of 66ee62d)

The DS engine walks a string with its own arity table, and a zero unit in text position ends
the string there; anything after it never runs. The gate change below already guards the main
conversion path against this. `audits/audit_zeros.py` (new) additionally walks every shipped
string, arity-aware, on whichever path produced it (including the row-by-row menu-bank path
and the localisation-table patches, which bypass the per-string guard) and fails on any
text-position zero except the one the fan ROM itself carries at entry 95 string 16, after
{E121}, in the same place in both scripts. On the current output: 10,705 strings, one zero,
allowed as the fan's.

### The DS-only gate lifted (commit 66ee62d): coverage 94.6% to 98.9% (98.8% after the Mind Chess fix)

A block in the converter kept the fan's line whenever Capcom's version carried fewer
{E041}/{E042} codes than the fan's, added for the v1.4.2 hang at the Episode 1 Gourd Lake
handoff. Re-analysis showed both codes are plain colour setters (orange keyword text, blue
monologue text), not something the engine waits on, and that the v1.4.2 hang was really an
unmapped {E2B0} button-glyph code passing through, which `_has_foreign` and `tools/buttons.py`
already stop. A throwaway build with the gate off ran Episode 1 past the Gourd Lake handoff
twice on the rig with no freeze, plus a six-attack adversarial review pass.

The gate is now `KEEP_DSONLY_GATE = False` (code kept, not deleted), replaced by the guard
that matches the real hang: a converted string with a zero unit in text position before its
end keeps the fan's version instead. This refused two menu strings in entry 460, which is
rejected as a whole by a separate control-code profile check anyway. 77 of the 90 rows the old
gate held back are now Capcom's; 13 stay fan text for other reasons (a per-row menu pixel-width
budget in three menu banks, a box-loss safety net, and entry 460's rejection). Verified on the
rig: Episode 1 reaches the Gourd Lake handoff live with the gate off, captures in
`rig/caps/d5gl_*.png`.

### Coverage-counting note

As stated in the intro above, the method by which a row counts as "official" (bytes differ
from the fan row after names and titles are applied) has not changed since the correction
made in 1.5.0. Every percentage in this entry comes from `python tools/coverage.py` run
against the current build, quoted with that context so it is not mistaken for a new counting
change.

### All 20 shout slots are Capcom's audio (commit e67c26b)

The fan patch re-recorded 20 samples in `com/kenji2_sound.sdat`. `tools/voices.py` had imported
Capcom's English for 13 of them and said the Collection had no language variants for the other
seven. It did, for five of them: the tool matched wave archives by name, and on the DS the name is
not the SE number (SE 31 is `wav_se_013`, SE 33 `wav_se_019`, and so on). It now resolves every slot
through the `seq_se` sequence archive's records and the bank table, and imports all 20: eighteen of
Capcom's English shouts and, for SE 32 and SE 102, which are plain sound effects with no language
variants, Capcom's base clips. The seven new slots are IMA ADPCM at 22 kHz like the other ADPCM
shouts. The thirteen slots imported before come out byte-identical; only the sound archive changes,
and every sample decodes back and correlates 0.990 to 1.000 with Capcom's clip. Ten of Capcom's
clips stop at about 1.3% of full scale rather than at silence, where every retail DS shout ends at
zero, so every clip now gets an 8 ms half-cosine fade at its end; all 20 decode to a final sample of
exactly 0.

A pre-compaction candidate (sha256 `cf361075...`, superseded, sent to a tester before the fixes
below landed) booted on melonDS to a title screen reading v1.10.0 and played from a chapter save.
The rig's emulator runs without an audio device, so the shouts were checked by decoding them, not
by ear on the rig; I approved the loudness stage below by ear from the decoded clips before
turning it on.

### The DS camera, character positions and poses restored (commit 149a0db)

The Collection re-tuned camera framing, character positions and poses for its own wider screen,
and dropped some poses outright. On the DS that showed up as the camera stopping short of its
mark, an officer or Edgeworth left out of frame, or a character standing in the wrong pose for
the line. Each string's sequence of position, camera and pose commands now matches the fan ROM's,
placed in the same box and on the same side of the text, the same copy-from-the-fan approach used
for the string-index arguments above. `audits/audit_staging.py` (new) checks this, with three
fixtures: the Case 2 camera argument that motivated the fix, a staging command moved into the
wrong box in a string whose box-end count still matches the fan's, and a staging command moved
from after some text to before any text in the same box. The same commit prices the two accent
slots below like a plain "e" in the sparse-bank width check, so an accented row is priced
normally instead of being forced wide as unpriceable.

### Mind Chess measured in the font it is actually drawn in (commit 90fe921)

A text-box sweep found Mind Chess banks had been measured against the dialogue font's widths,
although the game draws Mind Chess topic banners and option rows in its own smaller face. That
mismatch was losing the second line of a topic banner and the last letter of an option row
("hopping ma."). Those banks are now measured in the small font against limits taken from what
the game actually shows on screen; a row that still does not fit keeps the fan's own wording
rather than being cut, and the accented "e" below, which that small font does not have, falls
back to a plain "e" only in this font. The wrap now counts a closing parenthesis added at a box
break, one fan line gets a guarded line-break move, and `audits/audit_widgets.py` and
`audits/measure_linewidth.py` both fail on any Mind Chess overflow left after the fix.

### Accented letters in dialogue, and which fan font slot is which (commits 1b41147, c363ee6)

The fan font already draws e-grave and e-acute, in two slots the fan translation never used;
dialogue now uses them instead of the plain letter, so "Gavèlle" and "attaché" show their
accents. The smaller description and Logic card face's accent slots are unverified, so it
keeps the plain letter there. Trim tables (`stmt_trim.py`
and `txtcut_trim.py`) hash accent-insensitively, so an accent does not break a trim keyed to
the unaccented text.

The first reading of the font data had the two slots backwards: the glyph rows are stored least
significant bit first, and reading them most-significant-bit first mirrors and swaps the pair, so
the judge's surname rendered with an acute accent instead of a grave one. Corrected: e-grave is
the fan font's U+30A7 slot, e-acute is U+0415. Seen on the rig as "Judge Gavèlle!", the accent
correct. Mind Chess banks carry no accents (see above).

### Two-line titles break at a natural phrase (commit 1b41147)

A testimony or rebuttal title too long for one line used to break wherever the wrap fell, which
could strand a single word alone on the second line. The title composer now looks for a
preposition to break before when one is available, and keeps a title's closing dashes together on
the second line rather than splitting them from the word before.

### The Mind Chess banner reads "Mind Chess" (commit 040d68f)

The animated Mind Chess banner still read "Logic Chess", the older working name, where
Capcom's script calls it "Mind Chess" and ends its win screen on "Checkmate" rather than the
fan's wording. Both are now drawn from the player's own Collection install into the fan's
existing banner pieces: only tile pixels and each piece's horizontal offset change, the animation
itself is untouched. Rendered from the ROM with the game's own animation positions.

A tester's video of the first candidate showed three problems, all fixed in commit a8ac8a4:
"Mind" and "Checkmate" were drawn in two colours only, next to the fan's "Chess", which shades
from blue to white through the banner's 11-step palette ramp (idlocal entry 26, bank 0). All
redrawn letters now use that ramp. "Checkmate" was upright; it now has the same lean as "Mind".
And the cut between its first sprite piece (cell 9) and the rest (cell 10) ran through the "e";
it now falls in the gap between "e" and "c", with the word narrowed slightly (183 of 192 px) and
re-centred so the cut lands on the piece boundary. The build stops if no clean cut exists.

Checked on the rig on 2026-09-27 at 60 fps, Case 4's Mind Chess against Excelsius Winner: both
banners are right at rest. During the end banner's zoom-in, the first three frames still hide part
of "Checkmate" ("Clckmate", "Chckmate", "Ch|ckmate"), as the earlier build did. Cells 9 and 10
scale about their own anchors and overlap while enlarged; the seam inside cell 10's two objects
never breaks. The fix is to carry the whole word in one cell, which means adding an OAM entry to
the cell data, the same change "Commence" needs for Capcom's name-on-top layout. Both are planned
for the next release.

### Louder shouts (commits e688f39, f0c37be)

The shouts imported from the Collection peak-normalise quieter than the DS mix expects, so
Capcom's English sat several dB under the Japanese level and under the music once played. Each
of the 20 imported clips is now gained toward its Japanese counterpart's loudness for
that slot and peak-limited afterward, closing most of that gap; a few shouts are still 1 to 4 dB
under the Japanese level on purpose, to avoid squashing them against the music bed. The 20 gain
targets are stored as plain numbers in the tool, so every player's build applies the same values
without needing a copy of the Japanese ROM to measure them from. The stage was optional and off
by default in the first commit; the second turns it on for every build. I approved the loudness
by ear from the decoded clips before turning it on.

### The output ROM packs smaller (commit 5750653)

Earlier builds left the old copy of a file behind inside the ROM's filesystem whenever a later
pass replaced it, since nothing ever reclaimed that space. The build now packs the output so a
replaced file's old copy is not carried along; every file that ships is byte-identical to before,
but the file offsets, the FAT, the header's size and capacity fields, its CRC, and the padding
between files all change to match the tighter layout. The ROM drops from about 72.7 MB to
50.6 MB, and the patch built against it from about 4.3 MB to 3.9 MB.

### Also in this release

- `225b325` and `b33a9f8` (internal only, no ROM change): the public repository no longer
  stores lines of Capcom's or the fan's dialogue, narration or document text in comments or
  review tables (`tools/txtcut_trim.py`, hash-and-edit-ops the same way `stmt_trim.py` does).
  Names, titles and UI labels the build needs are unaffected. The output ROM is byte-identical
  before and after (`52ca3e4e...`).

## v1.9.0: every line re-measured against the game's own font

Short version: the tool had been guessing how wide each letter is, and guessing narrow. It
now reads the real width of every character out of your own ROM, so the text fills the box
the way it should and stops running off the right edge.

Here's what was wrong. To decide where to break a line, the injector has to know how wide
the line is so far. It never had the real numbers, so it used a rough model: this class of
character is about this wide. That model ran narrow, and two things followed from it. Lines
came out shorter than they needed to be, which wasted space in every box. And 59 lines in
the shipped script were actually wider than the box, so their last word or two ran off the
edge of the screen where you can't read it.

The real widths were there the whole time. The fan patch keeps a table of 2,012 characters
inside the DS's own code, each with the exact number of pixels the game moves along after
drawing it. That code is compressed, which is why nothing had ever read it.
`tools/fontwidths.py` decompresses it at build time and lifts the table straight out of the
ROM you supply. As with everything else here, nothing ships with the tool.

The worst offenders were the long shouts. A scream with no spaces in it can't be broken at a
space, and the old code just let it overflow. A word too long for the box is now split
across lines instead.

Measured on the actual release build:

    python audits/measure_linewidth.py "GK2_186.nds" "GK2 (Official English, DS port).nds"
    1.8.6   59 lines wider than the 240px box, widest 335px
    1.9.0    2 lines wider than the 240px box, widest 253px

The two that are left aren't the same story, so here's both. The first is a tutorial line
that opens with a round bracket and overhangs by 13 pixels. It does exactly that in 1.8.6
too, and this release neither causes it nor fixes it. The second one I did cause. It ends a
thought, and when a thought runs over a box the closing bracket gets added afterwards
without being charged against the line's width. That gap has always been there; the old
wrapping just left enough slack that it never showed. Now that lines fill the box properly
it tips one line one pixel over. One pixel of a bracket, on one line, and the fix belongs
with the wider rework rather than bolted on here.

One audit came out worse, and I'd rather say so here than have you find it.
`audits/audit_widgets.py` checks the option widgets, meaning the lists of questions you pick
from in Mind Chess and the Logic keyword cards, against the widest line the fan patch ever
put in that same widget.
Those lists are wrapped by the same code as the dialogue, so widening the dialogue budget
widened them too:

    python audits/audit_widgets.py "GK2 (Official English, DS port).nds"
    1.8.6   68 rows over      1.9.0   94 rows over

Nearly all of that is two of the nine banks, 456 and 457, where the fan patch left the
widget almost empty. The "widest line the fan ever put there" is therefore drawn from a
handful of Japanese rows and doesn't bound much: 227 pixels for one and 172 for the other.
The sibling widgets show the strip is a good deal wider than that, since the fan patch
itself draws a 340 pixel line in one of them, and nothing I write into these two goes past
240. Of the other seven banks, one improved and six didn't move.

I did finally get one of these widgets on screen, in the first Mind Chess of Episode 1, and
it says something useful about that count. The option strip is about 238 pixels of the
256 pixel screen, and the question drawn in it measures 179 pixels on screen against the
263 the audit credits it with. So this widget draws in a smaller face than the dialogue
box does, and the audit is pricing it in the dialogue font's pixels, which overstates the
real width by roughly a third. Nothing in these banks is close to the edge of the strip,
and the only widget where anything comes near it is one where the fan patch's own longest
line is still longer than mine.

That doesn't make the count meaningless, since both sides of it are measured the same way,
but it does mean the right fix is to give these widgets their own font rather than to
narrow the text, and that's a job for after this release. Bank 457 in particular still has
not been seen drawing anywhere: the menu I captured turned out to come from a different
bank. I'd rather say that than leave you with the impression it's all been watched.

Coverage hasn't changed: 93.8% of the script is Capcom's writing, Menus and UI 86.9%, the
same figures 1.8.6 carried. This release rewraps text rather than adding any.

It does move characters around, though, and in one way that's worth calling out because you
might notice it. When a thought is too long for one box, the game has to close the bracket,
turn the page and open it again. Because lines now hold more, 136 thoughts that used to be
split across two boxes fit in one, so that break and its brackets are simply gone.

Character names are decided by a separate set of budgets that were cut against the old
model, so those are pinned to the old model on purpose rather than quietly re-measured
against numbers nothing has verified. The 73 rows that take Capcom's name and the 1 that
keeps the fan's are exactly what 1.8.6 shipped.

One warning worth reading. This moves every line in the game, and only one episode of this
port has been played through to the end, on an older build. If you find a line broken in a
strange place, or text sitting oddly in a box, please open an issue and say where.

## v1.8.6: the answer menus that froze the game

A tester playing 1.8.5 hit a hard freeze in Episode 2, right after the crime scene has been
examined. Edgeworth asks what's missing from it, the red "Select your answer" bar comes up,
and then nothing. No buttons, no input, the game is gone. The same thing happened in Episode
3, at the second rebuttal against Gusto.

It's my bug, and it has been in every release since 1.4.4. When the game builds an answer
menu it names the button image to use for each option. Those numbers come from Capcom's
script, and Capcom's numbering is not the DS's. Fifty of the game's sixty two answer menus
happened to line up anyway. Twelve did not. The Episode 3 one pointed at a colour palette
instead of a button image, which is the kind of thing that stops a game dead.

Five of the twelve had a second problem: the number saying which line an answer continues
from was one too low, which would have sent you down the wrong branch. The build already
fixed exactly that for another command, and simply wasn't doing it here.

Both are fixed the same way now, by taking those numbers from the fan patch, which has the
DS's own numbering. Twenty five of them were corrected in this build. Nothing else in the
script moved: the read back against 1.8.5 shows the script file and the title screen's
version stamp, and nothing else.

There's also a new build check, `audits/audit_choicearg.py`, which refuses a build whose
answer menus name a button image that isn't there. It's the ninth audit, and like the others
it's tested against a deliberately broken copy of the build so I know it can actually fail.

Proof: the tester's own save file, on the 1.8.6 ROM, at the exact spot that froze. The three
answers appear, the scene plays on.

## v1.8.5: the Logic keyword cards in the fan patch's own lettering

The same tester who found the Episode 3 talk bug said the Logic keyword graphics I edit
looked a bit odd. They did. Those cards and the banner above each keyword's description are
images, not text, so the official name has to be drawn into them. Until now it was drawn in
the Collection's own font squashed down to the DS size and forced to one bit per pixel, on a
card interior wiped to flat bands, and long names were squeezed sideways until the letters
touched. Next to an untouched fan card it stood out immediately.

They are now drawn in the fan team's own pixel lettering. Nothing ships with the tool: every
letter, the spacing between letters and words, and a clean copy of the card with no text on
it are all cut out of your own ROM at build time by `tools/logic_font.py`, from the fan's 133
cards and banners. What the repository holds is the fan's own card text, so the harvester
knows which shape is which letter.

Proof, since none of that is worth anything unless it reproduces the fan's work: redrawing
the fan's own card text with the finished pipeline gives back 75 of its 101 cards and 83 of
its 93 banners pixel for pixel, whole images, background and the dark outline under the white
letters included. Of the 26 cards that differ, 10 come out exact once the block of text moves
the one row the fan moved it by hand (the fan used two heights for a two-line card with
nothing in the text to tell them apart, and I use the one it used more often), 14 differ
where the fan tightened a line by hand, and for 2 my record of the fan's text only holds the
first line, so they were never a fair comparison. Where Capcom's name for a keyword is the
same as the fan's, my card and banner come out byte-identical to the fan's: 17 cards and 18
banners.

97 of the 133 keywords have an official name, and all 194 of their images are redrawn. Two
names are wider than any banner can hold even with the spaces narrowed, so their banner
carries a shorter form while the card keeps Capcom's full name on three lines: "Sound of
something breaking" becomes "Something breaking" above its description, and "Festival at
Sunshine Coliseum" becomes "Festival at the Coliseum". Four characters the fan never drew are
built out of ones it did: the double quote, the digit zero, a lowercase z, and a capital I on
banners. Read back against 1.8.4, one file changes, the Logic image bank, plus the version
number painted on the title screen. The eight audits are identical to 1.8.4's output.

Reference sha256 for 1.8.5 is `d2f7988c...`.

## v1.8.4: talking to Ms. Bound opens her conversation, not Larry's

A Reddit tester playing Episode 3 found that at the Zodiac Art Gallery's Fountain Patio, choosing Talk on Ms. Bound opened Larry's scene and his topics instead of hers. He sent his save. It reproduced on 1.8.3 in the emulator, and the same save on the fan ROM talks to her correctly, so it was mine.

The cause was one unit. The talk script for that area holds a four-unit string that is nothing but a command sending the game to the string with her conversation. The command's last argument, that string's number, sits just past the string's declared length, in the slot where a string normally ends with a zero. The fan ROM keeps it there and the engine reads it. The injector rebuilt the entry from the declared lengths and wrote a zero in that slot, which pointed the talk at string 0: Larry's scene. Every release I could still check has it, 1.4.4 and 1.7.0 included.

The rebuild now keeps whatever the fan ROM stores after a string's declared end whenever the string itself is unchanged. Across the whole script the fan ROM stores something there in 11 places. Nine were already kept, one is a stray newline after text I replace, which the game doesn't read, and this was the one I lost. Only two strings in the fan ROM have a command whose arguments run past their declared end, and the other one has a zero there anyway. Read back against 1.8.3, one unit in one file changes.

None of the seven audits could see this: they all read strings up to their declared length and stop. A new one, `audits/audit_tails.py`, compares those slots with the fan ROM and reports 1.8.3's lost unit; its fixture in `audit_fixtures.py` proves it can fail. Checked in the emulator with the tester's own save: talking to Ms. Bound now opens her conversation in Capcom's words.

Reference sha256 for 1.8.4 is `3bcd80c0...`.

## v1.8.3: location cards laid out the DS way

A Reddit tester playing Episode 3 pointed out that the time and place cards read "Detention Center - Visitor's Room" on one line, where the DS games give the building and the room a line each. Checking every card showed it was worse than a style difference. Capcom's script puts the whole place on one line because the Collection's box is wide. On the DS that line often didn't fit, the converter wrapped it with a plain line break, and the wrapped part printed flush left under the centred text, so "Room" sat on its own at the left edge. Every line of a card has to start with the engine's centring code, and the wrapped part didn't have one.

`tools/dstext.py` now moves the part after a place's " - " onto its own centred line when both halves fit and the card still fits the box, which is how the fan translation lays out its own cards. That covers 64 of the 70 date cards that change and 12 of the 13 place labels. The Committee for Prosecutorial Excellence cards (six of them, plus one label) can't split cleanly, because the committee's name alone is wider than the box, so they keep Capcom's two lines and the wrapped line is centred instead. The same centring now applies to the 18 testimony titles that wrap onto a second line, and to one narrated box in Episode 3; those were flush left too. Seven of those titles used to wrap so that the second line held nothing but the closing "--", so the closing "--" now stays with the word before it: "-- President Wang's" over "Testimony --". Same words, one wrap point moved.

Read back against 1.8.2, only the script bank changes, and inside it only line breaks, centring codes and the " - " separators moved: 87 entries, no other character touched. The audits match their 1.8.2 output except audit_cmdloss, where the centring code now goes missing 5 times against the fan ROM's 385 uses, down from 88. Checked in the emulator: the Episode 2 chapter 3 Visitor's Room card and the Episode 4 chapter 2 Committee card. The testimony titles haven't been seen in game yet.

Reference sha256 for 1.8.3 is `8eff2315...`.

## v1.8.2: "John Doe" is John Doe again, and two more names come out right

The same tester, an hour after 1.8.1: the unidentified man in Episode 1 was being introduced as "Shaun Doe". The rename table has always carried a protection pair for "John Doe" so that the given-name swap for the character whose fan name is John cannot touch it. The protection never worked, and neither did any other pair with a space in it. The renamer projects the fan text to ASCII before matching, and the fan ROM's space glyph sits inside the fullwidth range it tests first, so every space became an underscore and "John Doe" could never equal "John Doe". Single-word pairs did all the work, which is why nobody noticed: given name plus surname usually adds up to the same result as the full-name pair.

Testing the space first changes exactly three strings in the whole ROM, read back against 1.8.1: the Episode 1 introduction says John Doe again; an Episode 3 line that named the blind assassin twice over ("Kanis Kanis") now names him once; and a nurse's profile that called the coroner "Hilda Young" now says Hilda Hertz, which is what the Collection calls her. The seven audits are unchanged apart from the first of those strings dropping out of the "swapped" count, because it is now byte-identical to the fan ROM's.

Not checked in the emulator this time: the change is three text strings, the read-back is exact, and nothing else in the ROM moved.

Reference sha256 for 1.8.2 is `ff5b6ea2...`.

## v1.8.1: silent boxes no longer move the speaker's mouth

A Reddit tester playing 1.7.0 noticed that in the first Logic Chess of Episode 1, choosing to wait made Edgeworth's mouth move as if he were talking through a box that holds nothing but dots. He was right, and it was mine: every release so far did it, in every silent box in the game and, less visibly, on every ellipsis inside a line.

The cause is a glyph, not a control code. The fan translation prints its ellipses with the two-dot leader character (U+2025), and the DS engine treats that character as silence: the mouth stays still while it prints. Capcom's script writes ellipses as ordinary periods, and the converter carried them across as fullwidth periods, which draw the identical dot but count as letters, so the engine animates the mouth for each one. The print-mode argument that precedes an ellipsis (7 in the Collection's script, 8 in the DS original) turned out not to matter: with the periods kept, both values flap; with the fan's glyph, neither does. This was settled in the emulator from one save state at the wait move, with three builds differing only in those two things, thirty-odd frames each at 60 ms.

The fix in `tools/dstext.py` swaps every run of three or more periods for the same number of U+2025 after the line layout is done, so nothing re-wraps and no page break moves: the glyph has the same advance as a period in both the dialogue and description fonts. Read back from the built ROM against 1.8.0, exactly one file differs, the script bank, and inside it exactly one kind of change: 14,213 ellipsis runs in 2,894 strings, each period replaced one for one, no string changing length. The seven audits are identical to their 1.8.0 output. Checked in game at the reported site: the wait move now prints its dots with the mouth shut on all twenty printing frames, and the opponent's next line still animates.

A lone period is still a period, and so is a pair.

Reference sha256 for 1.8.1 is `7050029a...`. The six pictures, the coverage figure and everything else are as in 1.8.0.

## v1.8.0: the six pictures with lettering drawn into the artwork carry Capcom's names

Six close-up pictures in the fan translation had English drawn straight into real artwork rather than onto a flat page: the two Secret Service briefing diagrams, the three placards on the cake-contest table, the logo of the TV baking show (one drawing shown across 61 pictures as the camera pulls back from the screen), the monster movie poster, and the magazine cover with the child actor. All six still carried the fan translation's character names and titles, which contradicted the dialogue around them. This release replaces them.

For four of the six, Capcom's Collection contains its own English version of the same picture, re-lettered by Capcom's artists with the official names: the placards read Scone, Frost and Gusto; the show is Samson & Judy's Bake 'n' Bop; the poster is The Legendary Taurusaurus vs. Gourdy; the magazine headline names Shaun Fenn. The new placards and TV logo are Capcom's lettering set onto the fan patch's DS pictures. The poster and the magazine are Capcom's own pictures reframed to the DS screen, since Capcom recomposed both for widescreen. The two briefing diagrams have no Collection counterpart; every official name there is shorter than the fan one (Rook for Rooke, Knight for Knightley), so the trailing letters were removed from the fan's own lettering and the rest of each handwritten line slid along its baseline to close the gap.

Unlike every other graphic in this port, these six are not composed by the build. Composing them at build time gave visibly worse results than preparing them once by hand, so they were prepared outside the build, checked at DS size, and ship as six 256x192 pictures in the repository under tools/cg_art_final. The build writes them into the ROM as they are. That is a change of policy for the repository, which until now carried tools and no game-derived art; the README's legal section says so plainly. The 60 zoom frames of the TV logo are still derived by the build: each frame's screen glass is filled with the logo at that frame's scale, measured against Capcom's picture, and softened to match the fan's own frame.

Each of these pictures carries its own 256-colour palette in the ROM, so every one is re-quantised with a fresh palette. The 60 zoom frames share one palette with the in-room view and are quantised together. Translation coverage is unchanged: pictures were never counted as script.

A look over every other redrawn graphic (28 nameplates, 119 title cards, 297 option strips, 39 text screens, all compared against the fan pictures at 2x and 3x) found one cosmetic fault, fixed here: the four option strips that carry quotation marks ("Kay", "scoop" twice, "Non-standard means") drew the ASCII quote as a small raised tick in Capcom's face. They now use the face's own curly quotes.

Building from source now needs numpy as well as UnityPy and Pillow, and the frozen executables no longer exclude it. The Collection is not needed for the shipped pictures.

The executables attached to 1.7.0 could not build from a Collection at all: they passed their self-test and then stopped at the logo extraction step, because the packaging did not carry the native libraries UnityPy's sprite export loads. Nobody reported it, which suggests everyone used the patch. The 1.8.0 executables carry those libraries, and the Windows one was downloaded from the release page and run through a full extraction and build to confirm it reproduces the reference hash.

## v1.7.0: the close-up text screens use Capcom's official words

The game displays 39 documents as full-screen pictures on the bottom screen when you press Check in the Organizer: autopsy reports, case files, letters, notes, and the tape transcripts. The fan translation team drew every one of those by hand in their own pixel lettering. Capcom's Collection provides the official text for the same screens, so 1.7.0 renders Capcom's exact wording into the pictures, in the fan team's own face (harvested from their screens, so the letters are theirs) and with their margins and spacing. 38 Capcom text rows cover all 39 screens. Three more pictures contain no Capcom text but carried fan character names in their artwork, a room map and two log tables. Those names are re-lettered in place with the official ones using the fan team's map lettering, and the room names follow Capcom's official English map.

Because Capcom set these text rows for a wide card, the text is re-flowed for the DS screen. Six rows carry a minor edit so they fit. All of them use Capcom's own vocabulary and were checked against the original Japanese: a label Capcom uses elsewhere, two line breaks inside a date, two dropped articles, and four short phrases cut from the letter and the contest rules. Those cuts were necessary because the text could not fit under the Organizer's Back button at any legible line spacing. The rest of the text is verbatim. Thirteen screens sit at a slightly tighter line spacing than the fan team used.

Verified in the game rather than on paper: the Interim Autopsy Report was opened on the real engine and matched the render. The patched ROM grows by about 6 MB because the rewritten container is stored uncompressed and the old copy remains in the file. Translation coverage is unchanged, since these screens were never counted as script.

## v1.6.4: a highlighted term split across two boxes keeps its colour

When a coloured term was too long for one text box, the half that landed in the second box
lost its colour and drew plain white. So a keyword the game had marked as important stopped
looking important halfway through. It showed most on the green testimony and deduction lines,
and on orange keywords like *Animal Taming Department*, where the term itself splits
across the box break, the first half keeping its colour and the second opening the
next box in plain white.

A box-terminating code resets the engine's inline style, the same way a thought box loses its
blue when its opening "(" is stranded on the previous page. The converter already put the
parenthesis back across a break; it never put the *style* back. It does now: whichever colour
is open is closed before the break and re-opened after it. **98 places across all five
episodes**, and 81 of them are the green style, so a fix written only for the orange keywords
would have missed five sixths of it.

Judged by the ROM rather than by the build running: the previous tools reproduce the 1.6.3
hash exactly, so this change is the only difference; every audit's output is identical, the
guard counts are unchanged, and coverage is unchanged at 93.8%. The ROM grows by 512 bytes.

Confirmed on the hardware, not on paper. The Episode 2 line above was checked in game before
and after: white, then orange. The green case was proved the same way, by changing a single
byte in a test ROM so that term used the green style instead: both halves come back green,
while a *separate* coloured term in that same second box was orange throughout. The engine
can draw colour in the second box perfectly well; what it could not do was carry one over.

The green case is now confirmed in the wild as well, on the shipped ROM with nothing patched:
a phone call in Episode 2 chapter 2 whose coloured span runs past the end of a box comes back
green in the next box, from its first character, reached by ordinary play from a chapter save.
And the colour is not a per-speaker or per-scene effect: elsewhere a single line turns from
white to green and back within one box, exactly where the style opens and closes.

## v1.6.3: long evidence titles are no longer squashed

The evidence and profile card titles are drawn strips 128 px wide, and 18 of the 119
official titles do not fit that at normal letter spacing. Through 1.6.2 the renderer
squashed those to zero letter gap before it would consider a shorter title, so cards
like *Creature Feature Flyer*, *Mr. Aldown's Final Call* and *Behind-the-Scenes Photo*
were drawn with their letters touching and were hard to read.

Now every candidate title is tried at normal spacing before any candidate is squashed,
and 17 of the 18 have a shorter form built only from words in Capcom's own title, with
the Japanese name used to decide which words carry the meaning: *Creature Flyer*,
*Gemini Results*, *Statutes Book*, *Guard Uniform*, *Poison Ingredients*, *Building
Pamphlet*, *Behind-the-Scenes*, *Rehearsal Tape*, *SS-5 Case File*, *Blood Stain*, and
the honorific dropped from *Tangaroa's Teapot*, *Scone's Statement*, *Niedler's
Statement*, *Wang's Autopsy*, *Aldown's Autopsy*, *Aldown's Photograph* and *Aldown's
Final Call* (the Japanese names carry no honorific either). *Ringleader's Appearance*
has no shorter form that keeps its meaning and still squashes. The 101 titles that
already fit are byte-identical. Nothing else in the ROM changed; all audits identical;
coverage unchanged at 93.8%.

## v1.6.2: closing quotation marks no longer draw as an apostrophe

Every closing double quote in the ported text came out as an apostrophe:
`"Taurusaurus Vs. Gourdy'.` where the script says `"Taurusaurus Vs. Gourdy".` The fan
patch's font has no separate closing-quote glyph. Its U+201D slot *is* the apostrophe
(the fan script uses it that way 16,482 times), and the fan team drew both ends of a
quotation with the same U+201C glyph, 925 times. The converter emitted U+201D for the
closing half, so every release through 1.6.1 had this: 995 places in 657 strings.

One line changed (`DQ_CLOSE` in `tools/dstext.py`). Judged by the ROM rather than by
the build running: the 1.6.1 tools reproduce the 1.6.1 hash exactly, the fixed tools
change one file in the ROM, and every one of the 657 string changes is that single
character substitution. No line re-wrapped, every audit's output is identical, coverage
is unchanged at 93.8%. Found by the rig playtest on the Creature Feature Flyer card in
Episode 5 and verified on that card with the fixed build.

## v1.6.1: the 1.6.0 downloads were incomplete

The 1.6.0 executables crashed before finishing: two data files the tools read from
beside their own code (`desc_font.json`, the measured description-card font, and
`select_strips.json`, the choice-button pairing) were not bundled into the frozen
build. Building from source was unaffected. 1.6.1 is the same tools with both files
bundled, the self-test now checks for them, and the version stamp on the title screen
reads 1.6.1, which is the only reason the ROM hash differs from 1.6.0.

## New in v1.6.0: the choice buttons are in Capcom's words, and descriptions no longer clip

The option plates of every choice menu and talk-topic list were still the fan's
lettering, and one of them put a fan character name on screen: in Episode 1 one
choice, naming a character by a distinguishing feature, offered *Nicole Swift*
while the script around it said *Tabby Lloyd*. The 297 plates (`jpn/idlocal.bin` 364-670, all of
them graphics) are now redrawn with the official option text, read from your
Collection at build time and set in its UD Kakugo M face.

Each plate was paired with its Collection string through the retail Japanese ROM,
whose plates sit at the same entries: the Japanese lettering was matched glyph by
glyph to Capcom's own Japanese select tables, and the English follows from the id.
Nothing was matched by meaning. Nine strings Capcom lists twice with different
English are resolved by episode; three plates Capcom's own data labels with debug
text ("Her position aaaaaa") take their twin's clean line. 48 long options are
condensed by up to 12% and 20 step down a size to fit, the way the episode titles do.

**Evidence and profile descriptions no longer lose their last letter.** The
description card draws a smaller font than the dialogue box, but the fitter had been
using the dialogue box's budget for it, so lines near the top of the range ran off the
140-pixel field and the game cut the final glyph (a place name on Carmelo Gusto's
profile, a descriptive line on the mask, each losing their last letter). Every release
through 1.5.2 had this. The card font was measured in game (per-glyph advances fitted
from lines rendered on 18 cards, kept in `tools/desc_font.json`) and 84 description rows are
re-wrapped against it; twelve more rows stay on the fan's text because the official
wording needs a fifth line the card does not have (rows kept as fan: 78 -> 90). Verified
on the chapter saves: Fender, Gusto, Deauxnim and the mask card all read complete.
Coverage is 93.8% (was 93.9%).

## New in v1.5.2: a hang in Episode 1 that every release had

Every release through 1.5.1 could stop dead in Episode 1, in the audience area, right
after the bodyguard introduces himself: the music keeps playing, the text box never
comes back, and no button or tap does anything. It was found by a scripted playthrough
of the build, not by a report, and it is a bug in this port, not in the fan patch.

The cause is one control code. Capcom's script uses a code the DS engine has never seen,
where the DS script uses its own equivalent (the pair that opens and closes a scripted
wait). The converter passed the unknown code through unchanged. The engine skips a code
it does not know and then reads the code's arguments as text; one of them is zero, which
ends the string early, and the closing half of the pair is left waiting forever. There
are 15 such sites in 12 strings across the game, all with the same shape, plus five
sites of a second unknown code (the Collection's inline button icon, in tutorial lines).

The fix does two things. The converter now translates that code to its DS equivalent,
and the injector keeps the fan's string whenever a converted string still carries any
code the fan script never uses, so the five button-icon lines fall back to the fan text
rather than gamble. That guard is now part of the build report
(`records kept as fan - official-only control code`). Exactly 14 strings differ from
1.5.1; every audit passes; the first chapter of Episode 1 was replayed on the fixed build
and runs clean. Coverage moves from 94.3% to 93.9% because those four tutorial lines are
fan text again.

If you built 1.5.1 or earlier, rebuild.

```
sha256  d9d27354ecbd734cc4d01683d57f51a0a447e6c0ed826318baa76b776a899047
```

## New in v1.5.1: the last five fan-named lines

1.5.0 left five dialogue lines with a fan character name because the official name pushed
each one past its box and re-breaking had nowhere to put the extra word. They now carry
the official names, each with the smallest edit the width allows: a title or an
honorific dropped, or a contraction, never a changed meaning. Measured in the game's own
font against the 216 px line budget (`rig/measure_lines.py` in the private notes). The
per-line renamer now applies these hand fixes too; before, a row with a second over-wide
line silently discarded them. A full scan of the built ROM finds no fan character name
left in any kept-fan row. Coverage is unchanged at 94.3%: renamed fan rows count as fan.

```
sha256  2f5ba692e0c0bc2c45ab3c88dced781b8800bd117503dd69f5eca7a7873f1a61
```

## New in v1.5.0: Capcom's titles everywhere, and a stricter coverage count

**The last fan names are gone from the screens you see most.** The title screen now shows
Capcom's *Ace Attorney Investigations 2: Prosecutor's Gambit* logo; the episode-select
buttons, the splash card at the start of each episode and the save screen all carry the
official episode titles. The logo sprite and the two fonts (Modé Mina B, UD Kakugo M) are
read from your own Collection at build time and rendered into the DS graphics; nothing
Capcom-owned ships with the tool. The splash-card face the fan team hand-drew turned out
to be Modé Mina, so those cards read as the same design with the official words.

Verified in melonDS on a cleared save: title screen, save panel ("Turnabout for the
Ages"), episode select and splash card ("Turnabout Trigger"), all at 60/60.

### The shouts, in Capcom's English voices

The fan patch recorded its own English "Objection!", "Hold it!", "Take that!" and the
rest over the Japanese samples. The Collection carries Capcom's 2024 audio for all twenty
of the sound-effect slots the fan team replaced: eighteen are Capcom's English lines, and
the other two (SE 32, SE 102) are plain sound effects with no dialogue in the Collection at
all, so Capcom's base clip goes in instead of an English take. All twenty now play Capcom's
takes: read from your Collection at build time, downmixed and resampled (IMA ADPCM at
22 kHz; 16-bit PCM at 32 kHz for the long one), and written back into the sound archive
with every header rebuilt from the sample data. The DS plays each shout to the end of its
sample, so nothing is time-compressed or cut; takes that run longer than the fan's (by up to
half a second) go in whole. None of the fan team's shout recordings remain in the build.
Every new sample was decoded back out of the rebuilt archive to confirm length, rate and
level, and correlated against Capcom's own clip.

### Logic keyword cards in Capcom's words

The cards on the Logic board were the last large fan-lettered surface. They are images,
not text, and the fan team drew their own English into 206 of them. 194 of those images
(97 keywords, card plus banner) now carry the official short names, rendered in UD Kakugo M
from your Collection over a cleaned card face; the six keywords the Collection has no name
for, and the unused dummy slots, keep the fan's lettering. Verified in melonDS on the
Episode 1 Logic board ("Assassination attempt", "Six-shot revolver").

### Character names: line by line

v1.4.4 left ten whole conversations in the fan's names because one line in each could not
take the longer official name. The rename now works line by line: the official name where
it fits, Capcom's surname where only that fits, the fan line only if even that is too wide.
Hyphenated forms ("Courtney-pie") rename too; they were being skipped. Result: 94 rows
renamed (was 84), and **five lines in the whole game still carry a fan name** (resolved in 1.5.1), each because
the fan drew that line already at the edge of the box:

- `DS[29]` str 14: a one-line declaration ending in the character's surname
- `DS[76]` str 7: a two-clause question addressed to a character by title and name
- `DS[94]` str 2: a short noun phrase naming an escaped character by name
- `DS[99]` str 4: a short clause naming a character before its verb
- `DS[117]` str 28: a parenthetical naming the true culprit by title and surname

### 108 descriptions and Logic cards, condensed to fit

Official English existed for 108 evidence descriptions, profiles and Logic cards but did not
fit the DS box, so every release until now showed the fan's text there. They now carry
Capcom's wording, condensed: deletions first, names and facts kept, hedges kept. The
Japanese line was the guide for what had to survive and the fan line for what fits. The
edits are word-index operations with result hashes (no Capcom text in the repo), and all
108 can be listed Japanese / Capcom / condensed / fan with `tools/desc_overflow.py`. Menus &
UI coverage rises from 81.1% to 90.2%; total from 93.7% to 94.3%.

### One evidence description, one hedge

The Episode 2 autopsy description used to state the time of death as flat fact. Capcom's
line hedges it, and the Japanese hedges too; in a game where autopsies get overturned
that is not a decoration. The hedge is restored, paid for by dropping a redundant
location phrase that repeats what the wound description already says. Still exactly
four lines.

### Coverage: 93.7%, not 96.5%

`tools/coverage.py` counted a string as official whenever its bytes differed from the fan
ROM's. Since v1.4.0 the rename pass has been swapping Capcom's character names into
fan-written rows, and every one of those rows was being counted as official. It now counts
a row as official only if it differs from the fan row *after* names and titles are applied.
By that rule v1.4.4 was **93.8%**, and 1.5.0 is **94.3%** (93.7% before the 108 condensed rows). The ROM did not get worse; the
count got stricter. Per-episode figures are in the README.

### Also

- `tools/nitro.py`: the palette reader started four bytes late (no visible effect on the
  nameplates, wrong colours on every 8bpp screen). Fixed; a rebuild of 1.4.4 hashed
  identically.
- New tools, all build-time, none shipping game data: `ncer.py`, `title_art.py`,
  `title_logo.py`, `extract_logo.py`, `title_text.py`, `title_assets.py`,
  `logic_names.py`, `logic_cards.py`, `voices.py`.
- The build now has five steps; the Collection is needed for the title assets as well as
  the script, and `--skip-extract` checks for them.
- The splash-card episode titles are now anti-aliased in the same grey steps as the fan's
  "Episode N" line above them, and drawn at the same weight, so the two rows read as one
  piece of lettering (edge pixels used to be thresholded, which left the second line
  harder-edged and lighter than the first).
- The title screen now shows the build's version ("v1.5.0") in small white digits in its
  top-right corner, so a screenshot or a bug report says which build it came from. Painted
  into the composed picture by `tools/title_version.py`; no artwork is covered.

```
sha256  689c599401d3f5221fc71a778d53217649cc0af941db28514f503f8576c46263
```

```bash
python tools/build.py --verify
```

## New in v1.4.4: ten lines that shipped clipped, and two corrected claims

**Ten lines in v1.4.3 shipped clipped at the right edge of their box.** If you
are already playing v1.4.3 this is cosmetic: no hangs, no save incompatibility.
Rebuilding is optional but recommended.

v1.4.3 reverted 105 rows to fan text so they would keep the engine commands the
DS-only tutorials need. That had a side effect nobody looked for: the
name-substitution pass only touches rows byte-identical to the fan ROM, so
handing it 105 more such rows gave it **84 rows to rename, up from 45**.

Capcom's names are often longer than the fan's, and ten of those rows ended up
wider than the box they draw into. The build re-breaks a row to make it fit, but
it cannot when the over-wide line is the *last* line of a box, because there is
nowhere to push the word to. Those ten now keep the fan's name instead. A single
line still reading *Fender* costs less than a line running off the screen.

The build had printed a warning about this. It scrolled past in a wall of thirty
counters, after the tag was already cut.

### Corrections to the v1.4.3 notes

The v1.4.3 release said the revert was "93 strings, nearly all in Episode 1's
tutorial-heavy opening." Both halves were wrong, and it is now measured rather
than recalled:

- It is **105 rows, across 67 script banks.**
- They are spread across the whole game: partner conversations, examine checks
  and NPC entries, wherever DS-only interaction sits. Episode 1 is not where they
  cluster, it is where one of them locked the game.

The README also claimed **97.5% coverage**. Re-measured with `tools/coverage.py`:
**96.5%**. That figure had been written from memory instead of from the tool.

### Also in this release

- `inject.py` reports how many script banks the DS-only revert touched.
- The over-wide report is no longer phrased as a `WARNING`, since those rows are
  reverted rather than shipped.
- README: refreshed per-episode coverage and the new guard documented.

```
sha256  8ab40704f4abed647ec1fe602dd8f8cb92b6b25ee38ba2abc8af74a4b744fa6e
```

## New in v1.4.3: Episode 1 hands you the controls again. Update before playing.

**Every release from v1.2.0 to v1.4.2 hangs in Episode 1**, at the exact moment the
game stops talking and gives you control at the Gourd Lake stage. A speaker's
nameplate sits over an empty message box, the scene keeps animating, the music keeps
playing, and nothing advances. Reproduced from a cold boot, and confirmed against the
fan translation, which reaches free roam at the same point.

The cause is a guard that was measuring the wrong thing. The Collection's script has
no touch-screen, A-Button or Logic tutorials, they are DS-only, so converting it can
silently drop the engine commands that drive them. The existing guard caught that by
counting **message boxes**, on the reasoning that missing content means missing boxes.
It does not: Capcom's prose is longer, so the converted string ended up with *more*
boxes than the fan's (18 against 16) while the tutorial command pair inside it was
gone. The box count looked healthy and the scene hung anyway.

The guard now compares the **engine commands** rather than the boxes, and any string
that would drop one keeps the fan's line.

That turned out to be bigger than the one scene. **93 strings across all five
episodes** were dropping a DS-only command, 34 in Episode 1, 27 in Episode 2, 16 in
Episode 5, 9 in Episode 3, 4 in Episode 4. They sit in the partner-conversation,
examine-check and NPC entries, which is where DS-only interaction lives throughout the
game, not just in the tutorial. Only the Episode 1 one is known to hang, because it is
the only one anybody has reached and stopped at; the rest were the same defect waiting
in the same kind of place.

That costs real coverage, and it is worth being plain about it: **the total falls from
98.4% to 97.5%**, with Episode 1 taking most of it (97.7% to 91.8%) and every other
episode giving up a little. Those strings are the DS-only content Capcom never wrote,
so they were always the least translatable part of the game, and the alternative is a
scene that stops. A scene that plays in the fan's words beats a scene that does not
play at all.

This is the third hang found by someone actually playing rather than by any offline
check, and the second in Episode 1's opening, which had never been played on a build
this recent. If you are on any earlier release, update before starting.

## New in v1.4.2: an Episode 1 hang, found by a player. Update if you are playing.

**Every release from v1.3.0 to v1.4.1 can lock up early in Episode 1**, while you
are examining the scene. The screen keeps animating and the music keeps playing,
but a speaker's nameplate sits over an empty message box and no button advances it.
Your save is not damaged, text is read-only data, but the only way out is to
restart the chapter on this build.

Seven rows of the examine-response bank had been emptied outright. The Collection
has no text for them (the fan patch left them untranslated), and when a row is
replaced by nothing it loses its **message box** along with its words. A box that
opens with nothing inside never closes, so the scene simply stops.

There was already a net for this: a row the Collection empties keeps the fan's row
instead. It only ran when the fan's row was in English, which is why these seven, 
Japanese in the fan patch, fell straight through it. The net is now split in two.
The old English rule still governs *wording*. A second, stricter rule governs
*structure*: **a row whose replacement has no message box at all keeps the fan's
row, whatever language it is in.** Untranslated text is a blemish; a lost box is a
lock, and structure now wins. A whole-ROM check confirms no string anywhere is
missing a box any more, and the fix touches that one bank and nothing else.

Thanks to the player who hit it and left the game running, a live lock is worth
far more than a bug report, and this was found and fixed from that one screen.

## New in v1.4.1: one renamed line brought back inside its widget

An audit of v1.4.0 against the injector's own rules found a single line that broke
one. The confrontation and Logic Chess option widgets have no measured width in
the game; what the tool trusts instead is **the widest line the fan translation
ever displayed in that widget**, anything wider keeps the fan's line rather than
risk a clipped word. v1.4.0's rename pass did not apply that rule to its own
output, and one line, where a shorter surname became a longer official one, ended
up 8 pixels past the widest that widget has ever been proven to draw.

The line now drops an honorific to fit (243px against a 262px budget), and the
rename pass enforces the same per-widget budget the injector does, so a future
name can't quietly overrun one: any renamed row wider than the fan proved simply
keeps the fan line and says so at build time. No other line in the game was
affected, the other renamed banks came in at or under budget.

Also in this release: the guard meant to stop a title card being redrawn with the
wrong item's name was a no-op, and is now real. It never mattered, every one of
the 177 fan titles was independently re-read and confirmed, and all 119 official
names were checked to exist verbatim in Capcom's own tables, but the check now
actually runs.

## New in v1.4.0: Capcom's character names, everywhere

The fan translation named this cast years before Capcom did, and until now the
port wore both sets at once: the dialogue (98.4% Capcom's) said *Fender*,
*Saint* and *Laguarde* while the nameplate above it still said *Ray*, *Simon*
and *Roland*, and the Organizer agreed with neither. This release retires the
fan names entirely, the official localization is the canon this port follows.

- **All 28 dialogue nameplates whose names Capcom changed are redrawn**
  (Ray→Fender, Simon→Saint, Courtney→Gavèlle, Debeste→Eustace, Roland→Laguarde,
  Dogen→Kanis, Knightley→Knight, MIB→Man in Black, and twenty more). Nameplates
  are graphics, not text: the tool decodes them from your fan ROM, harvests the
  fan patch's own pixel font from the plates themselves, and re-renders the
  official names in it, so the plates still look exactly like the fan patch drew
  them, and no fan-drawn graphics ship with this tool.
- **All 119 evidence and profile title cards with outdated names or titles are
  redrawn the same way**, profile cards now read *Eddie Fender* and *Simeon
  Saint*, and evidence titles use Capcom's item names (*Ms. Lloyd's Tape*,
  *Pocket Chess Set*, *Mr. Kanis's Bells*, *Taurusaurus Head*, ...). A few
  official titles are wider than the DS card and drop one filler word, built
  only from the official title's own words. One card the fan patch left in
  Japanese (約束ノート) is now *Promise Notebook*.
- **Every kept-fan text string is renamed to match**, 45 strings (Organizer
  descriptions, Logic cards, DS-only tutorials and the fan-kept scenes) now use
  the official names, verified string-by-string against the fan ROM first so
  official text is never touched, with line widths re-checked and re-wrapped
  where a longer name needed it. The mapping was derived from the two scripts
  themselves: for every line that exists in both translations, fan names were
  paired with the official names appearing in the same line (139 co-occurrences
  for Knightley→Knight alone), then spot-checked in context.
- The pairing also covers the non-people: *Moozilla* is officially
  *Taurusaurus*, the elephant *Astique* is *Azea*, the chairman's nickname
  *Blaisie* is *Celsius*, the masked *Conductor* is the *Ringleader*, and the
  *Dye-Young Hospital* is *Hertz Hospital*.

The episode titles on the save screen already used Capcom's names (since
v1.1.0); the episode-select artwork remains the fan's bitmap, as before. The
reference hash for `--verify` moves; coverage counts are unchanged (titles and
nameplates are graphics, not counted text).

## New in v1.3.4: one description stops disagreeing about a room's name

The Rubber Glove's updated Court Record description, one of the ~100 over-long
descriptions that keep the fan's fitting text, called the crime scene
"workroom A", while every official line around it (including the same item's own
earlier description) says "workshop". The playtest that found the v1.3.3 hang
also caught this. An audit of every kept-fan row against the official vocabulary
found **exactly one such location-term conflict in the whole game**; the rest of
the fan-vocabulary differences are character names, which stay untouched until
nameplates can change with them.

The fix substitutes that one word at build time in the description/Logic banks
only, same letter count, measurably narrower, so nothing re-wraps. The ROM
changes by exactly 3 character units; full fan scenes keep their own vocabulary.
The reference hash for `--verify` moves accordingly.

## New in v1.3.3: a hang in the Little Thief scenes, found by playtest, fixed

**Every earlier release hangs, permanently, music still playing, the moment Kay
deploys Little Thief in Episode 2's final chapter.** The first hands-on playtest of
the recovered scenes hit it within the hour, on the first Little Thief scene it
reached. If you played v1.3.2 or earlier past that point, this is the fix; your
save is fine (text is read-only data, restart the chapter on a v1.3.3 ROM).

The cause is almost funny. The converter knows how many argument units follow each
control code from a statistically derived table, and that table treats any code
"followed by a letter in >85% of cases" as inline markup with no arguments. Code
`E1E2`, Little Thief's projector command, takes three arguments, and the first is
always the value 68… which is the letter **`D`**. A constant argument that spells a
letter defeated the letter test, the converter fullwidth-converted the 68 into a
`Ｄ`, and the DS engine hung on the garbage value. Two more codes fell into the same
trap: `E19D` (argument 100 = `d`) and `E1E5` (argument 115 = `s`), corrupted at 16
further sites, no confirmed symptom, but the same class of wrong.

The fix corrects those three arities (the deriver now refuses to force arity 0 when
the "prose" after a code is the same value every time, prose varies, arguments
don't), which repairs **exactly 32 units across 20 script entries and changes
nothing else**, verified by byte-diff against the v1.3.2 ROM, and every repaired
argument is now byte-identical to the fan ROM's own engine-proven value. Verified
in-game: the Episode 2 scene that hung now plays through its full Little Thief
re-creation in Capcom's text (that entire ~4,400-unit recovered scene was also
box-by-box reviewed on screen, zero text defects). The other affected scenes
(Episodes 2/4/5) are verified structurally by the same byte-comparison.

The reference hash for `--verify` moves accordingly. Coverage is unchanged.

## New in v1.3.2: checking, and clearer help

No change to the ROM (still verifies to the same hash as v1.3.1). This release makes
the tool easier to trust and to get working:

- **`gk2port --verify`** hashes a built ROM and confirms it against this version's
  published reference. A MATCH means it is the genuine, unmodified output of the tool, 
  so a ROM can be trusted without trusting whoever built it. Pass a path to check any
  file: `gk2port --verify "your.nds"`.
- **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)**, the handful of things that actually go
  wrong (wrong ROM, Collection not found, freeing the 7 GB install, unsigned-binary
  warnings) and how to fix each.

## New in v1.3.1: three autopsy descriptions stop contradicting the testimony

The Episode 2 rebuttal cites the autopsy report's *stab wound*, official dialogue
in this ROM, while the Court Record description of the body still described a
single blunt-force impact in the fan's own words, because Capcom's wording didn't
fit the DS's 4-line description box. In a series about spotting contradictions, the
game contradicting itself is the one thing text must never do.

Those three descriptions (and only those, the ~100 other over-long descriptions
keep the fan's fitting text, which agrees with the dialogue) are now Capcom's
wording, lightly condensed to fit. The condensations live in the repository as
word-index edit operations with a result checksum, no game text, applied at
build time to the text you extract from your own Collection, and falling back to
the fan line if your Collection's wording ever differs.

## New in v1.3.0: the last big recoveries, and a jump-index repair

- **The confrontation line banks are official now.** The "argument" lines you pick
  during rebuttals and Logic Chess (236 rows, one-line declarations and exclamations)
  were at 0% because their file only exists in the Collection's trial bundle. They now swap
  row-by-row, each line verified single-line and no wider than the widest line the
  fan translation ever displayed in that widget.
- **The two biggest fan-kept scenes are recovered**, a courtroom stretch of Episode 4
  and an Episode 2 investigation scene (~12k characters) whose restructuring was
  beyond the previous release's tools: the region aligner now handles multiple joins
  in one entry and regions re-cut into a different number of strings, under the same
  strict structural verification as everything else.
- **A latent v1.2.1 defect is repaired.** In five recovered entries, the jump index
  carried at the end of some strings (which string the engine plays next) was copied
  from the official layout's numbering, off by the recovery's own re-cutting, 33
  strings in Episodes 2/4/5, including two that jumped to themselves. All jump
  indices are now taken from the fan layout, and a whole-ROM scan verifies zero
  divergence. These scenes had never been played on any build; if you hit an odd
  text loop there on v1.2.x, this was it.
- Coverage: **96.9% → 98.4%**. Episode 2 is 99.9%, Episode 4 98.4%, Episodes 3 and 5
  stay 100%.

| Episode | Official | character units |
|---|---|---|
| 1, Turnabout Target | 97.7% | 175,426 / 179,476 |
| 2, The Imprisoned Turnabout | 99.9% | 368,376 / 368,710 |
| 3, The Inherited Turnabout | **100%** | 377,753 / 377,753 |
| 4, The Forgotten Turnabout | 98.4% | 292,972 / 297,665 |
| 5, The Grand Turnabout | **100%** | 497,837 / 497,837 |
| Menus & UI | 81.7% | 91,148 / 111,600 |
| **Total** | **98.4%** | 1,803,512 / 1,833,041 |

## New in v1.2.1: one restored NPC line

A post-release audit of every string in the ROM against the fan original found
exactly one real text loss: an Episode 1 free-roam NPC line ("Thank you for
waiting! There's nothing unusual here!") that the Collection's own files leave
empty, small enough to slip between two guards' thresholds. It could have shown
an empty box, or hung, if examined. A final safety net now restores any short
English fan line whose official replacement is empty; audited ROM-wide, it
changes exactly that one string.

The same audit settled a long-standing unknown: the argument on the string
terminator is the index of the next string to jump to, which proves the
v1.2.0 seam rebuilds carry the correct value by construction.

## New in v1.2.0: most of what was missing is recovered

The fan patch restructured the script in ways that used to force whole scenes back to
fan text. This release understands and inverts that restructuring, always verified
structurally before a single string is touched:

- **9 entries** where the fan split one long retail string into two are split back at
  the fan's own cut point, three independent sources (fan layout, Collection script,
  retail-JP structural profile) must agree on the fingerprint first.
- **74 strings across 33 entries** where the fan moved message boxes between
  neighbouring strings are rebuilt in the fan's layout by re-cutting the official
  text at the fan's own boundaries. The gate is strict per-string box-code equality;
  anything that doesn't reproduce the fan structure exactly stays fan.
- **5 Episode 1 entries** (46k characters) were being rejected wholesale because one
  to three strings each are empty or `DEMO TEXT` in the Collection's files. Those
  hollow strings now revert individually; the rest of each entry is official.
- **25 more evidence descriptions** fit their box after the DS-only "see the detail
  view" tail (this project's own wording, not Capcom's) was shortened to one line.

Zero message boxes are lost anywhere: across all 931 strings of the 48 entries that
changed since v1.1.0, every string's box structure matches the fan layout the engine
was built against, verified mechanically at build time.

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
hang found another way is the Case 4 freeze fixed in 1.10.0, found by searching every scene
for the cause of one a tester hit in Case 2, not by anyone hitting it. The Lotta crash fixed
in 1.11.0 was hit by the tester; his emulator save state reproduced it, and a snapshot of
the frozen state found the cause.

On hardware, 1.4.4 booted and reached gameplay from a DSPico flashcart on a 3DS. Test builds
of 1.11.0 booted into the first case on a DSi through TWiLight Menu++ and on a DSPico.
The release build itself boots on both too. Nothing deeper has been tried on real hardware, and no original DS has been tried at all.

If the game ever hangs mid-scene, your save isn't damaged, since text is read-only data.
Restart the chapter and open an issue saying where it happened. Issue #1 is the thread
for playtest reports.

## Downloads

| Platform | File |
|---|---|
| Windows | `gk2port-windows-x64.exe` |
| Linux (glibc 2.35+) | `gk2port-linux-x64` |

Checksums are in `SHA256SUMS`. On Linux, `chmod +x` it first. Windows SmartScreen will
warn about an unrecognised publisher, because the binary is unsigned and certificates
cost money - check the hash, or build from source. `gk2port --selftest` confirms your
download is complete.

**macOS: build from source for now.** A macOS binary compiles and self-tests fine in CI,
but nobody has run one on an actual Mac, and shipping a binary no one has executed is
not much of a favour.

## You need to supply

| | |
|---|---|
| **Gyakuten Kenji 2 (AAI2 Final v2)** | The fan-patched DS ROM, supplies the variable-width font and English graphics |
| **Ace Attorney Investigations Collection** | The **PC** build, tested on Steam |

**No game data is included in this download.** Both inputs are files you own.

There is deliberately no patch file. A delta from the fan ROM to the ported one *is*
Capcom's script, so distributing one would distribute the localization, the thing this
project is built to avoid. Owning the Collection is the reason this can exist.

Console builds are untested. The bundle lookup matches by name prefix and ignores the
platform folder name, so an already-extracted Switch or PS4 dump may work, but nothing
here has been run against one.

## Rebuilding without the Collection installed

The Collection is only read during extraction. Once `dump/` exists it holds everything
the injection needs, so you can free the ~7 GB install and still rebuild:

```
gk2port --fan-rom "GK2 (AAI2 Final v2).nds" --skip-extract
```

That needs the fan ROM and `dump/` (~55 MB) and nothing else. Verified byte-identical
to a full run. The wizard does this by itself if it finds `dump/` and no Collection.

## Notes

- The output ROM is **not redistributable**: it contains Capcom's copyrighted
  localization and the fan translation's assets. Build your own.
- Episode names stay the fan's. Capcom renamed all five, but those appear on the
  episode-select screen as a bitmap, so changing only the save-slot text would show two
  names for one episode a menu apart.
- The **[AAI2 Final v2 fan translation](https://www.romhacking.net/translations/2260/)**
  team did the hard part, this is built entirely on top of their patch, and without it
  there is nothing to inject into, no font to render the result, and no English voice
  clips (theirs stay, and they recorded them). Their ATTENTION notice is left intact in
  every build. If you haven't played their translation, play it.
- The tooling was written with **LLM assistance** (Claude Opus 5, via Claude Code). The
  measurements and format work are reproducible by running the tools; the bugs that
  mattered were found by humans and emulator testing. See the README for the full note.
