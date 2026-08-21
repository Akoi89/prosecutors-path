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

Every refactor in this repo's history was gated on that hash staying at
`76a5d740268e914f5cdacf1cb7c7362e500bf3db02c4af3db821242ffb9bdb02`. If yours moves,
you changed behaviour — find out why before committing.

---

## Rebuilding `gk2port.exe`

```bash
pip install pyinstaller UnityPy Pillow

python -m PyInstaller --onefile --name gk2port \
  --add-data "$PWD/dump/ctrl_args.json;dump" \
  --add-data "$PWD/dump/ds_to_collection_final.json;dump" \
  --add-data "$PWD/dump/jp_structure.json;dump" \
  --paths "$PWD/tools" --collect-all UnityPy \
  --exclude-module tkinter --exclude-module matplotlib --exclude-module numpy \
  tools/build.py
```

Two things that cost time if you don't know them:

- **`--add-data` paths must be absolute.** They resolve relative to `--specpath`, not
  the working directory, so a relative path silently fails to find the file.
- **Do not exclude PIL.** UnityPy imports it internally
  (`UnityPy/classes/legacy_patch/Texture2D.py`); excluding it builds fine and then
  dies at extraction time.

On Linux/macOS the `;` in `--add-data` becomes `:`.

The binary is unsigned, so Windows SmartScreen warns about it. Signing certificates
cost money; the release notes carry a SHA-256 instead.

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

Every guard count is unchanged (404 entries, 112 relaid strings, 11 shape rejections),
all six structural checks still pass, and coverage stays at 85.7%.

`tools/ctrl_args.py --check` now reports no gap. If it ever reports one again, the
same evidence gate applies: demand zero run-length variance, binary-looking arguments,
and a rendered-text diff that loses nothing.

---

## Releasing

```bash
gh release create vX.Y.Z "dist/gk2port.exe#gk2port.exe (Windows x64, standalone)" \
  --target main --title "vX.Y.Z — Prosecutor's Path" --notes-file RELEASE_NOTES.md
```

Tag from `main` so the binary and the source that produced it agree — an earlier
release had a tag three commits behind its own asset, which is confusing for anyone
auditing. Put the SHA-256 of the exe in the notes.
