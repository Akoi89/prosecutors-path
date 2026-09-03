# Troubleshooting

Most problems are one of a few things. Run `gk2port --selftest` first if the tool
itself seems broken, and `gk2port --verify` to check a ROM you already built.

## The two files you need

| | What it is | Where it comes from |
|---|---|---|
| **AAI2 Final v2 ROM** | the fan-patched DS ROM, `sha256 08e1f7af…`, 45,165,392 bytes | the AAI2 Final v2 patch applied to your own DS ROM (romhacking.net) |
| **AA Investigations Collection** | the **PC** build (Steam tested) | your own install; the tool reads it, nothing is copied out |

The tool ships **no game data** — both inputs are files you already own.

If you applied the release `.xdelta` instead of building, only the first row applies; the
Collection is never read on that route. Everything below about builds can be skipped, but
`--verify` and the hang advice still apply, because the ROM is the same one.

## Common problems

**"this is not the AAI2 Final v2 ROM"**
You pointed it at the wrong ROM — a raw Japanese cart, a different patch, or an
already-built output. It must be the AAI2 Final v2 fan ROM, hash above. Building on
anything else produces a ROM that boots to a black screen, which is why the check
exists. If you are certain, `--any-rom` overrides it (expect the black screen).

**"could not find the Ace Attorney Investigations Collection"**
Auto-detection scans your Steam libraries. If your copy is elsewhere (non-Steam, or a
console dump you extracted), pass it: `--collection "<the folder containing GK12_Data>"`.
It accepts the game folder, the `StreamingAssets/aa` folder, or the platform folder
inside it.

**It ran once; can I delete the 7 GB Collection now?**
Yes. `gk2port --fan-rom "…nds" --skip-extract` rebuilds forever from the ~55 MB `dump/`
folder the first run left behind. The wizard does this automatically if it finds `dump/`
and no Collection.

**The window closes instantly (Windows)**
Run it from a terminal, or just double-click — recent versions keep the window open when
double-clicked so you can read any message. `gk2port --selftest` confirms the download
is intact.

**The patch fails to apply, or the patched ROM boots to a black screen**
The source ROM was wrong. `xdelta3` needs the AAI2 Final v2 ROM exactly (hash above): a
raw Japanese cart, a different fan patch, or an already-built output will either be
rejected outright or decode into something that will not boot. Hash your source before
blaming the patch, and hash the output afterwards with `gk2port --verify`.

**Windows SmartScreen / macOS Gatekeeper warns**
The binaries are unsigned (certificates cost money). Verify the SHA-256 on the release
page, or build from source. On macOS also `xattr -d com.apple.quarantine <file>`.

**Is my built ROM the real thing?**
`gk2port --verify` (or `--verify "path\to\rom.nds"`) hashes it and checks it against the
version's published reference. MATCH means it is the genuine, unmodified output of this
tool — no need to trust whoever built it.

**A scene hangs mid-dialogue while playing**
Your save is not damaged — the text is read-only data. Restart the chapter and please
[open an issue](https://github.com/Akoi89/prosecutors-path/issues) with where it
happened. The newly recovered scenes in Episodes 2/4/5 are the least play-tested; see
the release notes. v1.1.0 remains downloadable if you want the most conservative build.

**In-game issues inherited from the fan translation**
The voice-command shout ("Objection!"/"Hold It!" into the mic) and the occasional empty
text box on save-load are known AAI2 fan-patch issues, not caused by this tool.

## Still stuck?

Open an issue with: `gk2port --version`, your OS, the full output (or a screenshot of
the error), and — for a build failure — the SHA-256 of your fan ROM
(`certutil -hashfile "your.nds" SHA256` on Windows).
