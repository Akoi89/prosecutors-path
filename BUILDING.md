# Building

Everything here is optional. Ordinary use needs only the release binary or
`python tools/build.py` — see the [README](README.md).

This file covers the two things that aren't reproducible from a plain checkout:
rebuilding `gk2port.exe`, and regenerating the three metadata files that ship in
`dump/`.

---

## Verify before you trust

Any change to the tools should be judged by whether the built ROM changes, not by
whether the build ran. Keep a known-good ROM and compare:

```bash
python tools/build.py --fan-rom "GK2 (AAI2 Final v2).nds" --skip-extract -o out/check.nds
sha256sum out/check.nds
```

Every refactor in this repo's history was gated on that hash staying put. For
v1.3.1 the reference is
`176ea39fa62df6c9d115f7200ffdba231601cfd639d04b7ad226d0e41ebdad8a`
(v1.3.0's was `50e6af8f…`, v1.2.1's `ee2098ba…` - each move intentional and released)
(v1.2.0's was `c97635faefda1f131ec33a0c3e15d3fc6f9159dfbc0367d958d75f086643e661`)
(v1.1.0's was `76a5d740268e914f5cdacf1cb7c7362e500bf3db02c4af3db821242ffb9bdb02`;
it moved intentionally, and only, with the v1.2.0 text recoveries). If yours moves,
you changed behaviour — find out why before committing.

---

## Rebuilding the binaries

Normally you don't: [`.github/workflows/build.yml`](.github/workflows/build.yml) builds
Windows and Linux on every push and attaches them to the release on a tag.
**PyInstaller cannot cross-compile** — each binary has to be produced on its own OS —
so CI is the only way to ship the non-Windows ones at all.

macOS is commented out of the matrix rather than absent. An arm64 binary builds and
passes `--selftest` in about 40 seconds; what is missing is anyone running it on a real
Mac. Intel is a separate problem: `macos-13` is being retired and its runners now sit in
the queue indefinitely instead of failing, which stalls the whole release, so
`macos-15-intel` is the label to use when it comes back.

To build one by hand:

```bash
pip install pyinstaller UnityPy Pillow

python -m PyInstaller --onefile --name gk2port \
  --add-data "$PWD/dump/ctrl_args.json;dump" \
  --add-data "$PWD/dump/ds_to_collection_final.json;dump" \
  --add-data "$PWD/dump/jp_structure.json;dump" \
  --add-data "$PWD/tools/desc_font.json;." \
  --add-data "$PWD/tools/select_strips.json;." \
  --add-data "$PWD/tools/txtcut_font.json;." \
  --add-data "$PWD/tools/txtcut_condensed.json;." \
  --add-data "$PWD/tools/map_font.json;." \
  --paths "$PWD/tools" --collect-all UnityPy \
  --exclude-module tkinter --exclude-module matplotlib --exclude-module numpy \
  tools/build.py

dist/gk2port --selftest
```

Three things that cost time if you don't know them:

- **`--add-data` paths must be absolute.** They resolve relative to `--specpath`, not
  the working directory, so a relative path silently fails to find the file.
- **Do not exclude PIL.** UnityPy imports it internally
  (`UnityPy/classes/legacy_patch/Texture2D.py`); excluding it builds fine and then
  dies at extraction time.
- **`--selftest` is the check that catches both.** It verifies the three bundled JSON
  files and imports what extraction actually needs — including `UnityPy.UnityPyBoost`,
  a C extension, and `lz4.block`, which is how Addressables bundles are compressed.
  None of that is exercised by `--help`, and a bundle missing any of it looks perfectly
  healthy until someone points it at the game. CI runs it on every binary before it is
  uploaded.

On Linux/macOS the `;` in `--add-data` becomes `:`.

The Linux binary is built on `ubuntu-22.04` deliberately: a PyInstaller binary needs the
glibc it was linked against or newer, so building on the newest image would silently
drop older distros.

The binaries are unsigned. Windows SmartScreen warns; macOS Gatekeeper refuses outright
until the user runs `xattr -d com.apple.quarantine`. Signing certificates cost money —
the release carries a `SHA256SUMS` file and a public build log instead.

---

## Regenerating the shipped metadata

Three files under `dump/` are tracked in git because they contain no game text —
only integers and filenames — and shipping them saves every user a lot of work.
Regenerating any of them needs source data the repo does not contain.

| File | Regenerate with | Needs |
|---|---|---|
| `ctrl_args.json` | `tools/ctrl_args.py` | `dump/eng`, `dump/eng_trial` |
| `ds_to_collection_final.json` | `tools/build_map.py` | the above plus `dump/jpn`, `dump/jpn_trial`, `dump/ds_jp` |
| `jp_structure.json` | `tools/jp_profile.py` | `dump/ds_jp` |

`dump/eng*` and `dump/jpn*` come from a normal extraction run (`build.py` without
`--skip-extract`). `dump/ds_jp` does not — it is the **retail Japanese DS ROM**'s
filesystem, which the build itself no longer needs:

```bash
python tools/ndsx.py "Gyakuten Kenji 2 (Japan).nds" dump/ds_jp
python tools/jp_profile.py dump/ds_jp/jpn/spt.bin dump/jp_structure.json
```

That ROM is required only to regenerate these files, never to build.

---

## Fixed: nine control codes that were missing arities

`dump/ctrl_args.json` originally held 325 codes. The corpus contains nine more that
plainly take arguments, and because they were absent, `dstext.DEFAULT_ARGS` treated
them as arity 0 and sent 1,498 argument bytes down the text path — where 39 of them
(in `E0B0`, `E162`, `E16E`, `E183`) fell in `0x21`–`0x7E` and were rewritten to
fullwidth, so the engine received altered argument values.

The table now has all 342. What made the fix safe to apply:

- **Zero variance in run length.** All 52 occurrences of `E0B0` are followed by
  exactly 8 non-control units; all 245 of `E145` by exactly 3. Not a minimum — an
  invariant. Arity-0 codes sitting in prose produce wildly varying run lengths.
- **The arguments are small binary values** (`0x00`–`0x1B` mostly), never letters.
- **All nine occur only at the tail of a string**, after the final message box:
  `{E243}<01><02><03>` is the last four units, `{E0B0}<01><14>…` is a nine-unit
  string. So the over-estimation failure mode that once made `{E04C}` swallow words
  is structurally impossible here — there is no dialogue after them to swallow.
- **Verified by diffing rendered text** between the two tables: 10,697 strings
  identical, 8 changed, and every change is the removal of stray argument bytes that
  had been leaking into view (`' !!'` → `'!!'`, `'2 2 2 2'` → `'2222'`). No dialogue
  was lost.

At the time of that fix every guard count was unchanged (then 404 entries, 112
relaid strings, 11 shape rejections) and all six structural checks still passed.
The counts have since moved for good reasons - v1.2.0's structural recoveries -
and the current audit is printed by every build; `tools/coverage.py` computes the
coverage figure.

`tools/ctrl_args.py --check` now reports no gap. If it ever reports one again, the
same evidence gate applies: demand zero run-length variance, binary-looking arguments,
and a rendered-text diff that loses nothing.

---

## The xdelta patch

The exact flags matter and were not written down until 1.6.4, when they had to be
rediscovered by matching a re-encode against the shipped 1.6.3 patch byte for byte:

```bash
xdelta3 -e -9 -A \
  -s "Gyakuten Kenji 2 (AAI2 Final v2).nds" \
  "out/GK2 (Official English, DS port).nds" \
  "xdelta/Prosecutors-Path-X.Y.Z-fan-base.xdelta"
```

`-9` is the compression level and **`-A` disables the application header**, which otherwise
embeds the local output filename in the patch. Without `-A` the patch is ~206 bytes larger
and differs on every machine; with it, the same inputs give a byte-identical patch anywhere.
Dropping `-9` costs ~200 KB; `-S lzma` makes no difference; `-N` makes it much worse.

Then decode-verify before shipping - the patch, not the build log, is what users apply:

```bash
xdelta3 -d -s "Gyakuten Kenji 2 (AAI2 Final v2).nds" xdelta/...xdelta /tmp/check.nds
sha256sum /tmp/check.nds     # must equal REFERENCE_ROM_SHA256
```

---

## Releasing

Update `RELEASE_NOTES.md` and `VERSION` in `tools/build.py`, then:

```bash
git tag vX.Y.Z && git push origin vX.Y.Z
```

CI builds all four binaries from that exact commit, self-tests each one, and publishes
them with a `SHA256SUMS` file. Nothing is uploaded from a local machine, and the release
is created with `--target $GITHUB_SHA` so the tag and the assets cannot drift apart — an
earlier release had a tag three commits behind its own binary, which is impossible to
audit.

The `.xdelta` is the one asset CI does not produce, because it needs the fan ROM and the
built output, and neither of those may live on a runner. Encode it locally with the flags
in [The xdelta patch](#the-xdelta-patch), decode-verify it against `REFERENCE_ROM_SHA256`,
and attach it by hand once CI has finished:

```bash
gh release upload vX.Y.Z "xdelta/Prosecutors-Path-X.Y.Z-fan-base.xdelta"
```

It is deliberately absent from `SHA256SUMS`, which CI writes from `dist/` before the
upload happens; GitHub's own digest on the asset row is what a downloader checks. The
patch is also outside the "no game data" claim in NOTICE, for the reason set out under
[The patch file](README.md#the-patch-file) - encode it knowing that, or skip it.
