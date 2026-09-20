# -*- coding: utf-8 -*-
"""Read the DS font's real per-glyph advances out of the player's own ROM.

The fan patch installed a variable-width font and stored its metrics in the
arm9: a table of 8-byte records, u16 UTF-16 codepoint, u16 advance in pixels,
u32 pointer to the glyph in RAM. Until now this port ESTIMATED those widths
with a narrow/wide character heuristic, which runs 12 to 14% low and forced a
conservative line budget to compensate.

The arm9 is BLZ-compressed in the ROM, which is why the table cannot be found
by searching the ROM directly. Decode first, then read.

No game data enters this repository: the table is derived at build time from
the ROM the user supplied, exactly like the harvested fonts and pictures, and
is written to dump/, which .gitignore excludes.

    widths(rom_path) -> ({codepoint: advance_px}, line_px) or (None, None)

The offsets below are AAI2 Final v2's. Every read is validated before it is
returned, so a ROM that does not match yields None and the caller falls back to
the estimate rather than wrapping text against garbage.
"""
import hashlib, json, os, struct

from paths import work

# An arm9 is about half a megabyte decompressed. This only has to be loose enough
# to never reject a real one and tight enough that a file that is not an arm9 at
# all cannot ask for an allocation that matters.
MAX_ARM9 = 8 << 20

# Main dialogue font, measured 2026-09-19 against AAI2 Final v2.
TABLE_OFF = 0x00045B4C
TABLE_N = 2012

# The widest line the FAN patch itself ships, measured across its own 72,615
# lines: the distribution has a hard cliff at 240 (157 lines at 240, 2 at 241).
# 240 = the 256px screen less an 8px margin each side.
LINE_PX = 240

CACHE = 'ds_font_widths.json'

BLZ_THRESHOLD = 2


def _blz_decode(pak):
    """Nintendo's backwards-LZ, as used for arm9 binaries (CUE's blz.c)."""
    n = len(pak)
    if n < 8:
        return None
    inc_len = struct.unpack_from('<I', pak, n - 4)[0]
    if inc_len == 0:
        return bytes(pak)                     # stored uncompressed
    hdr_len = pak[n - 5]
    if not (0x08 <= hdr_len <= 0x0B):
        return None
    enc_len = struct.unpack_from('<I', pak, n - 8)[0] & 0x00FFFFFF
    if enc_len > n or enc_len < hdr_len:
        return None
    dec_len = n - enc_len                     # raw prefix, stored as-is
    enc_only = enc_len - hdr_len
    raw_len = dec_len + enc_len + inc_len
    # inc_len is four arbitrary bytes off the end of a file we have not validated
    # yet. Unbounded, a ROM that is not this one asks for a multi-gigabyte
    # allocation before anything else gets a chance to reject it.
    if raw_len > MAX_ARM9:
        return None

    out = bytearray(raw_len)
    out[:dec_len] = pak[:dec_len]
    enc = bytearray(pak[dec_len:dec_len + enc_only])
    enc.reverse()

    buf = bytearray()
    ei, mask, flags = 0, 0, 0
    target = raw_len - dec_len
    while len(buf) < target:
        if mask == 0:
            if ei >= len(enc):
                break
            flags = enc[ei]; ei += 1
            mask = 0x80
        if not (flags & mask):
            if ei >= len(enc):
                break
            buf.append(enc[ei]); ei += 1
        else:
            if ei + 1 >= len(enc):
                break
            pos = (enc[ei] << 8) | enc[ei + 1]; ei += 2
            ln = (pos >> 12) + BLZ_THRESHOLD + 1
            pos = (pos & 0xFFF) + 3
            # A back-reference past the start of what we have decoded so far means
            # this is not the stream we think it is. Python would index from the
            # END instead of raising and quietly produce plausible garbage, which
            # is the one failure this module must never hand back.
            if pos > len(buf):
                return None
            if len(buf) + ln > target:
                ln = target - len(buf)
            for _ in range(ln):
                buf.append(buf[len(buf) - pos])
        mask >>= 1
    if len(buf) != target:
        return None
    buf.reverse()
    out[dec_len:dec_len + len(buf)] = buf
    return bytes(out)


def _read_table(arm9):
    """-> {codepoint: advance}, or None if this does not look like the table.

    Range checks alone are not enough: a table shifted by a few records in some
    other build would still be full of plausible-looking values. These checks are
    structural, so they fail on a shift rather than on a different set of widths.
    """
    if TABLE_OFF + (TABLE_N + 1) * 8 > len(arm9):
        return None
    w, prev = {}, -1
    for i in range(TABLE_N):
        cp, adv, ptr = struct.unpack_from('<HHI', arm9, TABLE_OFF + i * 8)
        if not (0x0020 <= cp <= 0xFFFD and 0 < adv <= 32
                and 0x02000000 <= ptr < 0x02400000):
            return None                        # a correct read is 100%, not 99%
        if cp <= prev:
            return None                        # the real table ascends strictly
        prev = cp
        w[cp] = adv
    # The record just past the end bounds the table; a shifted read runs into
    # real records here instead of the zero sentinel.
    if struct.unpack_from('<HHI', arm9, TABLE_OFF + TABLE_N * 8) != (0, 0, 0):
        return None
    # The whole fullwidth Latin alphabet is contiguous in the real table. A slice
    # taken from the wrong place will be missing part of it.
    for lo, hi in ((0xFF21, 0xFF3A), (0xFF41, 0xFF5A)):
        if any(cp not in w for cp in range(lo, hi + 1)):
            return None
    return w


def _arm9_slice(rom_path):
    """The compressed arm9 exactly as the ROM stores it, plus its sha256."""
    rom = open(rom_path, 'rb').read()
    off, _entry, _ram, size = struct.unpack_from('<IIII', rom, 0x20)
    if off + size > len(rom) or size > MAX_ARM9:
        return None, None
    blob = rom[off:off + size]
    return blob, hashlib.sha256(blob).hexdigest()


def from_rom(rom_path):
    """Pull the advances straight out of a ROM. -> dict or None."""
    try:
        blob, _digest = _arm9_slice(rom_path)
        if blob is None:
            return None
        arm9 = _blz_decode(blob)
        if arm9 is None:
            return None
        return _read_table(arm9)
    except Exception:
        return None


def widths(rom_path=None):
    """Cached advances for the dialogue font.

    Returns ({codepoint: advance_px}, LINE_PX), or (None, None) when the ROM is
    not available or does not match, so the caller keeps the old estimate.

    The cache is only honoured when it carries the sha256 of the arm9 in the ROM
    being built. Without that check, building once on this ROM and then on any
    other silently applies the first ROM's metrics to the second - exactly the
    "wrong table rather than no table" failure this module exists to avoid.
    """
    if not rom_path or not os.path.exists(rom_path):
        return None, None
    try:
        blob, digest = _arm9_slice(rom_path)
    except Exception:
        return None, None
    if blob is None:
        return None, None

    cache = work('dump', CACHE)
    if os.path.exists(cache):
        try:
            d = json.load(open(cache))
            if d.get('arm9_sha256') == digest and d.get('table_offset') == TABLE_OFF:
                return {int(k): v for k, v in d['widths'].items()}, int(d['line_px'])
        except Exception:
            pass                               # unreadable or stale: re-derive below

    arm9 = _blz_decode(blob)
    w = _read_table(arm9) if arm9 is not None else None
    if not w:
        return None, None
    try:
        os.makedirs(os.path.dirname(cache), exist_ok=True)
        json.dump({'line_px': LINE_PX,
                   'source': os.path.basename(rom_path),
                   'arm9_sha256': digest,
                   'table_offset': TABLE_OFF,
                   'glyphs': len(w),
                   'widths': {str(k): v for k, v in sorted(w.items())}},
                  open(cache, 'w'), indent=0)
    except Exception:
        pass                                   # a cache we cannot write is not fatal
    return w, LINE_PX
