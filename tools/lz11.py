# -*- coding: utf-8 -*-
"""Nintendo LZ11 (0x11) decompressor - used by GK2's graphic archives."""
def decompress(d):
    if not d[0] == 0x11:
        raise ValueError('expected LZ11 tag 0x11, got %s' % hex(d[0]))
    size = int.from_bytes(d[1:4], 'little')
    if size == 0:
        size = int.from_bytes(d[4:8], 'little'); p = 8
    else:
        p = 4
    out = bytearray()
    while len(out) < size and p < len(d):
        flags = d[p]; p += 1
        for bit in range(8):
            if len(out) >= size: break
            if not (flags & (0x80 >> bit)):
                out.append(d[p]); p += 1
                continue
            a = d[p]; p += 1
            kind = a >> 4
            if kind == 0:
                b = d[p]; p += 1; c = d[p]; p += 1
                cnt = ((a & 0xF) << 4 | b >> 4) + 0x11
                disp = ((b & 0xF) << 8 | c) + 1
            elif kind == 1:
                b = d[p]; p += 1; c = d[p]; p += 1; e = d[p]; p += 1
                cnt = ((a & 0xF) << 12 | b << 4 | c >> 4) + 0x111
                disp = ((c & 0xF) << 8 | e) + 1
            else:
                b = d[p]; p += 1
                cnt = kind + 1
                disp = ((a & 0xF) << 8 | b) + 1
            for _ in range(cnt):
                out.append(out[-disp])
    return bytes(out)


# ---------------------------------------------------------------------------
# Compressor. Standard LZ11 as the DS BIOS/arm9 decoder and the fan's own
# idlocal entries use it: tag 0x11 and a 24-bit size (the engine's decoder
# at arm9 0202bd7c reads size = header >> 8, so the 0 plus 32-bit form the
# reader above accepts is never produced),
# flag bytes read from the top bit down, a set bit meaning a back-reference in
# one of three length classes:
#   2 bytes  length 3..0x10      (kind nibble = length - 1, 2..15)
#   3 bytes  length 0x11..0x110  (kind nibble 0)
#   4 bytes  length 0x111..0x10110 (kind nibble 1)
# with a 12-bit displacement (window 0x1000). The parse is optimal for the
# cost model below (bit cost: 9 per literal, 1 + 8 * bytes per match), using
# the longest match found at each position. Matches never use displacement 1:
# the fan's 671 compressed idlocal entries all have a minimum displacement of
# 2 or more, which is also what the BIOS needs for VRAM-safe output.
WINDOW = 0x1000
MIN_MATCH = 3
MAX_MATCH = 0x10110


def _match_len(d, j, i, limit):
    """Length of the common run of d[j:] and d[i:], at most `limit`. Reads the
    input only, so an overlapping match (j + length > i) is measured correctly."""
    n = 0
    step = 64
    while n < limit:
        s = min(step, limit - n)
        if d[j + n:j + n + s] == d[i + n:i + n + s]:
            n += s
            step = min(step * 2, 4096)
            continue
        while n < limit and d[j + n] == d[i + n]:
            n += 1
        break
    return n


def _longest(d, i, chains, min_disp, depth):
    """(length, displacement) of the longest match at i within the window, or (0, 0)."""
    limit = min(MAX_MATCH, len(d) - i)
    if limit < MIN_MATCH:
        return 0, 0
    cand = chains.get(d[i:i + 3])
    if not cand:
        return 0, 0
    best, bdisp = 0, 0
    tried = 0
    for k in range(len(cand) - 1, -1, -1):
        j = cand[k]
        disp = i - j
        if disp > WINDOW:
            break
        if disp < min_disp:
            continue
        tried += 1
        if tried > depth:
            break
        if best and best < limit and d[j + best] != d[i + best]:
            continue
        n = _match_len(d, j, i, limit)
        if n > best:
            best, bdisp = n, disp
            if best >= limit:
                break
    if best < MIN_MATCH:
        return 0, 0
    return best, bdisp


def _cost(n):
    return 17 if n <= 0x10 else (25 if n <= 0x110 else 33)


def compress(data, min_disp=2, depth=256):
    """LZ11 stream for `data` (bytes-like). Deterministic. Raises ValueError for
    a size of 16 MB or more or a bad min_disp."""
    d = bytes(data)
    n = len(d)
    if not 1 <= min_disp <= WINDOW:
        raise ValueError('min_disp must be 1..%d, got %r' % (WINDOW, min_disp))
    if n >= 1 << 24:
        raise ValueError('input of %d bytes does not fit the 24-bit size of an LZ11 header '
                         '(the engine\'s decoder reads size = header >> 8)' % n)
    chains = {}
    INF = 1 << 60
    cost = [INF] * (n + 1)
    step = [None] * (n + 1)          # (kind, length, disp) that reached this position
    cost[0] = 0
    for i in range(n):
        ci = cost[i]
        if ci + 9 < cost[i + 1]:
            cost[i + 1] = ci + 9
            step[i + 1] = (0, 1, 0, i)
        L, disp = _longest(d, i, chains, min_disp, depth)
        if L:
            lens = set(range(MIN_MATCH, min(L, 0x12) + 1))
            for e in (0x10, 0x11, 0x110, 0x111, L):
                if MIN_MATCH <= e <= L:
                    lens.add(e)
            for m in lens:
                c = ci + _cost(m)
                if c < cost[i + m]:
                    cost[i + m] = c
                    step[i + m] = (1, m, disp, i)
        if i + 3 <= n:
            chains.setdefault(d[i:i + 3], []).append(i)
    # walk back from the end, then emit forwards
    toks = []
    p = n
    while p > 0:
        t = step[p]
        toks.append(t)
        p = t[3]
    toks.reverse()
    out = bytearray(b'\x11')
    out += n.to_bytes(3, 'little')
    for g in range(0, len(toks), 8):
        group = toks[g:g + 8]
        flags = 0
        body = bytearray()
        for k, (kind, m, disp, pos) in enumerate(group):
            if not kind:
                body.append(d[pos])
                continue
            flags |= 0x80 >> k
            dd = disp - 1
            if m <= 0x10:
                body.append(((m - 1) << 4) | (dd >> 8))
                body.append(dd & 0xFF)
            elif m <= 0x110:
                v = m - 0x11
                body.append(v >> 4)
                body.append(((v & 0xF) << 4) | (dd >> 8))
                body.append(dd & 0xFF)
            else:
                v = m - 0x111
                body.append(0x10 | (v >> 12))
                body.append((v >> 4) & 0xFF)
                body.append(((v & 0xF) << 4) | (dd >> 8))
                body.append(dd & 0xFF)
        out.append(flags)
        out += body
    return bytes(out)
