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
`22f93c96415516c926beb1857c5ee26eca3f7f93337c0fabcc5b0ec8a4d76ab3`. If yours moves,
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

## Known gap: nine control codes

`tools/ctrl_args.py --check` reports this, so it is worth explaining rather than
leaving as a surprise:

```
shipped 325 codes, derived 342, 325 in common
disagreements on shared codes: 0
codes with arguments that the shipped table omits: 9
  E0B0:8, E145:3, E162:1, E16E:1, E183:1, E192:2, E193:2, E1C2:1, E243:3
```

The derivation reproduces the shipped table exactly on every code they share. But
the corpus contains nine further codes that clearly take arguments —
`{E0B0}<01><18><01><19>…` is not text — which the shipped table omits, so
`dstext.DEFAULT_ARGS` treats them as arity 0 and their arguments fall through the
text path.

Measured consequences, across every entry the injector touches:

- **1,498 argument bytes are treated as text.** They still reach the ROM in the
  right order, so the engine reads them correctly, but they occupy pixel width in
  the line-wrapping model. Lines containing these codes wrap earlier than they
  should.
- **39 of those bytes (2.6%, in `E0B0`, `E162`, `E16E`, `E183`) fall in `0x21`–`0x7E`
  and are rewritten to fullwidth** by `dstext._fw()`. Those arguments reach the
  engine with altered values.
- **No argument run is ever split by a line or page break** — 0 of 575. Breaks are
  only inserted at word boundaries, and an argument run forms a single atomic token,
  so this failure mode is structurally impossible rather than merely unobserved.

Correcting it is a one-line change (regenerate the table), and it **does** change the
built ROM. The shipped table is deliberately frozen at the state that has been played
and verified in-game. Treat fixing this as a real change: regenerate, rebuild, and
play through Episode 1 before trusting it.

The risk on the other side is not zero either. Arity is inferred from a minimum, and
a minimum can over-estimate — that is exactly how `{E04C}` and `{E04D}` once came out
as 9 and 20 and started swallowing words. The 85% letter test guards against it, but
a code with few occurrences could still slip through.

---

## Releasing

```bash
gh release create vX.Y.Z "dist/gk2port.exe#gk2port.exe (Windows x64, standalone)" \
  --target main --title "vX.Y.Z — Prosecutor's Path" --notes-file RELEASE_NOTES.md
```

Tag from `main` so the binary and the source that produced it agree — an earlier
release had a tag three commits behind its own asset, which is confusing for anyone
auditing. Put the SHA-256 of the exe in the notes.
