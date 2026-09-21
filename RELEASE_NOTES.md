Prosecutor's Path ports Capcom's official English localization of Gyakuten Kenji 2 onto the original Nintendo DS game, layered on top of the AAI2 Final v2 fan translation. As of this release, 93.8% of the script is Capcom's own writing rather than the fan team's, with the rest staying as the fan translation for reasons explained in the README. This file covers what changed release by release, in short; for the full technical record behind each entry, see BUILD_NOTES.md.

## v1.9.1: menu buttons lettered like the fan game's

A tester pointed out that the buttons you pick answers and conversation topics from didn't look like the ones in the fan translation or in the other DS games, and he was right. Two things were wrong with them. The text was being drawn twice, one pixel apart, to thicken it, on the assumption that the fan team's lettering was that heavy; it isn't, it's lighter, so the buttons read as bolder than everything around them. And the letters didn't sit level: round letters like o and e dip very slightly below the line in this typeface, which is invisible at normal sizes but becomes a whole pixel at the size these buttons use, so the text looked like it was bouncing up and down. Both are fixed. The thickening now only applies to the seventeen buttons whose wording is long enough to need smaller text, where the thinner version was harder to read. Nothing else in the game changed, and saves carry over. The Episode 2 crash reported against an earlier build is still unexplained and is not fixed here; it's described in the README.

## v1.9.0: every line re-measured against the game's own font

The tool used to guess how wide each letter is, and it guessed narrow, so lines wrapped shorter than needed and a small number ran past the edge of the box where you couldn't read the end of them. It now reads the real letter widths straight out of your own game, so text fills the box properly. The number of lines running past the edge drops sharply; the couple that remain are queued for a future release, and one of those two is a single pixel this release introduced. Long unbroken runs of letters, like a scream with no spaces in it, used to just run off the screen; they now break across lines properly. A couple of menus, the option lists in Mind Chess and on the Logic keyword cards, got a little wider too, and are being watched. Coverage of the script by Capcom's own writing is unchanged. This release touches every line in the game, and no episode has been played start to finish yet, so if you spot a line breaking oddly, please say where.

## v1.8.6: the answer menus that froze the game

A tester hit a hard freeze in Episode 2, right after examining the crime scene and being asked what's missing from it: the answer choices appear, and then the game simply stops responding. The same kind of freeze could happen at one point in Episode 3 too. The cause was a numbering mismatch in how a chunk of the game's answer menus point at their button graphics, affecting twelve of the sixty two menus in the game, one of which pointed at something that isn't a button image at all. Five of those twelve could also have sent you down the wrong branch of dialogue without you noticing. Both problems are fixed now, and a new safety check will refuse to let a future build ship with this kind of mistake in it. If you hit a freeze at an answer screen on an earlier version, please update; your save itself was never damaged.

## v1.8.5: Logic keyword cards drawn in the fan team's own lettering

A tester pointed out that the Logic board's keyword cards and banners, which are pictures rather than text, looked noticeably different from the rest of the fan team's artwork around them: squashed sideways, flattened backgrounds, and an odd font. That's fixed here. The official keyword names are now hand-drawn using letters lifted straight from the fan team's own existing cards, so the new cards match the game's look instead of standing out. Two official names that are unusually long needed a shorter version to fit their banner; the full name still appears on the card face itself. Everywhere the official name matches what the fan team already used, the card and banner are now pixel for pixel identical to the fan originals.

## v1.8.4: talking to Ms. Bound opens her conversation, not Larry's

A Reddit tester playing Episode 3 found that choosing to talk to Ms. Bound at one specific location instead opened Larry's conversation and his topics, not hers. That's been true since the very first release of this port. The cause was one small numbering slip: the line meant to send the game to her conversation was pointing at his instead, a mistake that had gone unnoticed because most lines like it happen to point at the right place by chance. It's fixed now, confirmed against the tester's own save file at the exact spot where it happened, in the emulator, with Ms. Bound now opening her own conversation correctly. Nothing else in the script was touched by this fix.

## v1.8.3: location cards laid out the way the DS games always did it

Time and place cards, like one reading "Detention Center - Visitor's Room," were printing as a single cramped line pushed to the left instead of splitting the building and the room onto their own centered lines the way the original DS games do. Most of these cards are fixed now, splitting cleanly onto two properly centered lines. A handful with unusually long names can't split without going off the edge, so they keep the older two-line layout, just centered correctly this time instead of sitting flush left. Testimony titles that wrap onto a second line got the same centering fix.

## v1.8.2: "John Doe" is John Doe again

A bug in how the game swaps in character names was turning the unidentified man in Episode 1 into "Shaun Doe" instead of "John Doe," because a name containing a space wasn't being compared correctly behind the scenes, so the safeguard meant to protect that exact name never actually worked. That's fixed now, and while fixing it two more names that had the same silent problem also came out correct: a name that used to repeat itself oddly in an Episode 3 line, and the coroner's name in a nurse's profile, which now matches what the Collection calls her. Only three lines in the entire game were affected, and nothing else in the script changed as a result.

## v1.8.1: silent boxes no longer move the speaker's mouth

A Reddit tester playing an earlier build noticed that in a silent, dots-only message box, meant to show a character pausing without speaking, the character's mouth was still animating as if they were talking. This happened throughout the whole game, in every silent box and on ordinary ellipses inside regular lines too, in every release so far. The cause was a mismatch between the punctuation mark used for these dots and what the game's engine recognizes as silent. The fix swaps in the correct character wherever three or more dots appear in a row, so pauses and silent moments now actually look silent, without changing how any line wraps or breaks. Checked in the emulator at the spot the tester reported: the mouth now stays shut through the whole pause.

## v1.8.0: six hand-lettered pictures now carry Capcom's official names

Six close-up pictures have English lettering drawn directly into the artwork itself rather than sitting in a text box: a couple of briefing diagrams, some contest table signs, a TV show logo, a movie poster, and a magazine cover. All six still used the fan team's original names, which no longer matched the official names used everywhere else in the game. This release replaces all six with versions carrying the official wording. Four come from official artwork included with the Collection itself; the other two are the fan team's own art, hand-edited to swap in the correct, and shorter, official names. These six were prepared carefully by hand ahead of time rather than generated automatically, since that gave a noticeably better result.

## v1.7.0: close-up document screens now use Capcom's official wording

The full-screen documents you can view through the Organizer, autopsy reports, case files, letters, notes, and tape transcripts, were entirely hand-lettered by the fan team. All of them are now redrawn using the official English wording instead, in a style matched to the fan team's own handwriting so they still fit the game's look and feel. A small number of lines needed a light edit to fit the space available under the Organizer's back button; everything else uses the official text exactly as written. Because of how this had to be stored, the game file grows noticeably in size, which is expected and not a sign of a problem.

## v1.6.4: a highlighted term keeps its color when split across two boxes

When an important colored word or phrase, like a highlighted testimony line or keyword, was too long to fit in one message box, the part that spilled into the next box used to lose its color and print as plain white, making it look less important than it actually was, especially on green testimony and deduction lines. That's fixed across the whole game now: the color correctly carries over into the second box, wherever it happens. This was confirmed both in a controlled test built specifically to trigger it and on an ordinary spot reached through normal play, with nothing else in the game affected by the change.

## v1.6.3: long evidence and profile titles are no longer squashed

Evidence and profile card titles that were too long to fit in their space used to have every letter squeezed together with no spacing at all, which made titles like "Creature Feature Flyer" or "Mr. Aldown's Final Call" genuinely hard to read, with the letters touching each other. Now the game tries a shorter version of the title first, built only from words already in the official wording, before it resorts to squashing anything at all. Most previously squashed titles now display at normal, readable spacing; one title has no workable shorter form that keeps its meaning, so it still gets squashed as before. Nothing else about the game changed with this release, and every other card title is unaffected.

## v1.6.2: closing quotation marks no longer look like an apostrophe

A closing double quote mark was printing as a plain apostrophe throughout the whole game, so a title like "Taurusaurus Vs. Gourdy" showed with a stray apostrophe at the end instead of a proper closing quote, the same problem everywhere a quotation ended in the script. This touched several hundred places across the whole game, in every release up to this one. It's fixed now with a single corrected character, found during a scripted playthrough on an evidence card in Episode 5 and then confirmed by checking that exact card again on the fixed build. No line re-wraps and nothing else about the text changed.

## v1.6.1: the 1.6.0 downloads were missing files and would crash

The ready-to-run downloads for version 1.6.0 were missing a couple of small data files the tool needs while it works, so instead of finishing the build they crashed partway through every time. If you built the game from source rather than using the ready-made download, this never affected you at all. This release is exactly the same tool as 1.6.0, with the missing files properly included this time, plus a new check that makes sure they're always bundled going forward so this kind of thing can't slip through silently again in a future download. The only other difference is the version number shown on the title screen, which is why the game file's checksum changes even though nothing about the actual translation moved.

## v1.6.0: choice buttons speak Capcom's words, descriptions stop losing their last letter

The buttons you pick between in conversations, rebuttals, and Logic Chess were still using the fan team's own lettering, and one of them was accidentally showing a fan-only character name in a place where the surrounding dialogue already used the official one. All of these buttons are now redrawn using the official wording instead, matched carefully to the game's own choice lists so the right English goes with the right option. Separately, evidence and profile descriptions were sometimes losing their very last letter off the edge of the box, because the tool had been using the wrong size setting for that smaller font. That's fixed too, so descriptions now display in full, confirmed by checking several affected cards directly.

## v1.5.2: a hang in Episode 1 that every earlier release had

Every release before this one could freeze completely in Episode 1, shortly after the bodyguard introduces himself: the music kept playing, but the game stopped responding to any input at all, with no way forward. This was caught by testing the build directly rather than by a player report, but it's a real bug in this port and not something the fan translation itself has. It was caused by an official script instruction the game's engine had never been built to handle, which threw off everything read after it and left part of the game waiting forever. It's fixed now. A handful of tutorial-only lines fall back to the fan team's original wording as a safety measure in the couple of spots where the fix can't fully apply cleanly. If you built any earlier version than this one, please rebuild before continuing to play.

## v1.5.1: the last five lines with a fan character name

Five specific dialogue lines were still showing a fan-made character name rather than the official one, because the official name was too long to fit the box and there was nowhere left to break the line to make room for it. Each of those five now carries the official name, using the smallest possible adjustment to make it fit, like dropping a title or honorific, or using a contraction, so the wording changes as little as possible while still saying the right name. Every other line in the entire game already used the official names before this release, and a full check of the finished build confirms no fan-made character name is left anywhere in the script.

## v1.5.0: official titles everywhere, Capcom's own shout recordings, and an honest coverage number

This is a big one. The title screen, episode select, save screen, and each episode's opening splash card now all show Capcom's actual official titles and logo rather than the fan team's own versions. The "Objection!", "Hold It!," "Take That!," and other shout effects now play Capcom's real English voice recordings wherever the Collection provides one, thirteen out of the twenty replaced by the fan team; the rest keep the fan team's own recordings. Most of the Logic board's keyword cards switch over to official names too. Character renaming also got smarter, correctly renaming ten more lines that had been stuck with fan names, with five holdouts left to fix in the next release. About a hundred evidence descriptions and profile cards that were previously too long to fit now show Capcom's real wording, carefully trimmed to fit without losing meaning. The previously reported figure for how much of the script is Capcom's own writing was measured incorrectly, and is corrected here to a more honest, and lower, number.

## v1.4.4: ten lines that shipped visibly cut off

A side effect of the previous release left ten dialogue lines wider than the box they're drawn in, so the last part of a word got cut off at the edge of the screen. This was cosmetic only, nothing hung or broke a save. Those ten lines now keep their shorter, fan-made name instead of running off the edge. This release also corrects two numbers published in the previous release's notes that turned out to be wrong: how many lines were actually affected by an earlier fallback to fan text, and the real percentage of the script that's Capcom's own official writing.

## v1.4.3: Episode 1 freezes at the Gourd Lake scene. Update before playing.

Every release from 1.2.0 through 1.4.2 hangs at one specific point early in Episode 1, right after the game hands you control near the lake, and never recovers. The cause was a safety check that wasn't actually checking the right thing, so it let some broken lines through undetected. The fix catches this properly, and doing so revealed the same underlying issue was quietly affecting close to a hundred lines scattered across all five episodes, not just that one spot. Those lines now fall back to the fan team's original wording rather than risk more freezes elsewhere; this costs a small amount of overall coverage by Capcom's writing, but a scene that plays beats one that doesn't. If you're on any earlier version, please update before you start playing.

## v1.4.2: an early Episode 1 freeze, found by a player

A player reported a freeze early in Episode 1 while examining the crime scene, where the screen kept animating but the game never responded again. The cause was that a small number of lines the Collection leaves completely blank were being replaced with nothing at all, which wiped out message box structure the game actually needs to keep working. It's fixed now: a blank replacement line falls back to the fan team's original text instead of leaving nothing behind. Your save was never at risk, since the game's text lives separately from your save data; if you hit this before, just update and restart the chapter.

## v1.4.1: one renamed line was too wide for its menu

A check run against the previous release found one line, in a menu with a strict but unmeasured width limit, that had been renamed to a longer official name and ended up wider than anything ever safely shown in that spot before, in any release. That single line now drops a title to fit properly again, comfortably inside the space that menu has ever used. This release also makes sure this kind of overflow gets caught automatically from now on, so a future name change can't quietly break a menu without anyone noticing before it ships. A separate check that was supposed to confirm card titles use the right item's name, but wasn't actually running, has also been turned on properly; nothing was actually wrong there, but it's now genuinely being checked. No other line in the game was affected.

## v1.4.0: Capcom's character names, everywhere

Until now, the game's dialogue used Capcom's official character names while the nameplates above the text box, and the evidence and profile cards, still showed the fan team's original names, so the game was inconsistent about what to call people. This release switches everything over to match: nameplates, evidence and profile titles, and any remaining lines that were still using the fan team's names. The nameplates are redrawn using the fan team's own lettering style, so they still look like they belong in the game, just with the correct names on them now. A few location and object names also change to match, like the monster "Moozilla" becoming "Taurusaurus."

## v1.3.4: one description stops contradicting itself about a room's name

One evidence description, for the Rubber Glove, called a location "workroom A," while every other official reference to that same room, including that same item's own earlier description elsewhere in the game, called it "workshop." This was caught during testing for the previous release. A full check of every other line still using older wording found this was the only such conflict left anywhere in the game, aside from character names, which are handled separately and change together with the nameplates. It's fixed here with a small wording swap in the description itself, so it now agrees with everything else around it, and nothing else in the game was touched by this change.

## v1.3.3: a permanent freeze during the Little Thief scenes, fixed

Every release before this one would hang permanently, with the music still playing, at the exact moment Kay deploys her Little Thief gadget in a specific late Episode 2 scene. This was found during actual hands-on play testing, within the first hour of trying. The cause was the tool misreading how many extra values followed a couple of specific game commands, which corrupted values those scenes depended on. It's fixed now, verified by playing the affected scene through from start to finish with no problems, and the same kind of fix was applied everywhere else the same mistake could have caused trouble. Your save is fine either way; just update and replay the chapter if you'd hit this before.

## v1.3.2: no game changes, just easier setup and troubleshooting

This release doesn't change anything in the game itself; a copy built with this version's tool still checks out identical to the one before it. What it adds is a way to trust the tool more easily. You can now hash a finished ROM and have the tool confirm it against the version it published, so you can tell whether a file really is the genuine, unmodified result of a normal build without having to trust whoever handed it to you. There's also a new troubleshooting guide covering the handful of things that actually tend to go wrong: an outdated fan ROM, the Collection not being found, freeing up the disk space its install takes, and the unsigned-program warning Windows shows when you run the tool for the first time.

## v1.3.1: three autopsy descriptions stop contradicting the trial testimony

In one case, courtroom testimony referred to a stab wound using the official wording, while the matching evidence description back in the Court Record still described the same injury differently, using older fan wording, because the real official wording hadn't originally fit the space available in the description box. In a game built entirely around catching contradictions in front of you, the game contradicting itself is exactly the one thing the text should never do. Those three specific descriptions, and only those three, now use the official wording instead, trimmed carefully to fit the space without losing what it actually says. Every other description in the game that's still too long for the box keeps the fan team's original wording, since it already agrees with the dialogue around it.

## v1.3.0: the last big chunks of missing text are recovered

This release recovers several large sections of the game that had been falling back to fan text because they were too structurally different from the DS original to convert safely before now: the answer options you pick during rebuttals and Logic Chess, and two of the largest individual scenes in the whole game, a courtroom stretch in Episode 4 and an investigation scene in Episode 2. It also fixes a numbering mistake from the previous release that could, in a handful of recovered scenes, have sent the game to the wrong follow-up line. Overall, the share of the script using Capcom's official writing jumps by well over a percentage point with this release.

## v1.2.1: one missing line restored

A full check of every single line in the game against the original fan version turned up exactly one real loss: a short, free-roam line in Episode 1, where an NPC thanks you for waiting and says there's nothing unusual to see, that the Collection's own files leave completely empty. That could have shown a blank message box, or worse, if you'd happened to examine that exact spot while playing. It's restored now, and a permanent safeguard was added so a short line left accidentally empty like this always falls back to the fan team's original wording instead of showing nothing at all, checked against the whole game to confirm this was the only place it happened.

## v1.2.0: most of the previously missing text is recovered

The fan translation had restructured parts of the original DS script in ways that made a lot of content impossible to safely swap over before now: whole scenes, lines split apart or merged together, message boxes moved between neighboring lines. This release understands that restructuring and reverses it, and only makes a change once independent checks confirm it will reproduce the correct on-screen structure exactly. As a result, a large amount of previously fan-only text throughout the game now shows Capcom's official wording instead, with no message boxes lost anywhere along the way.

For the full technical record behind every release, including exact measurements and file-level detail, see BUILD_NOTES.md.
