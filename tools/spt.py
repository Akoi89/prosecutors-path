import struct, os, collections

def offset_scale(d, ds=False):
    """Offsets are byte offsets in the retail ROMs, but the AAI2 fan patch modified
    the engine to read them as 16-bit UNIT offsets, doubling the addressable range
    from 64 KB to 128 KB so longer English text would fit. Detect which is in use by
    checking where the record table must end."""
    ncnt = struct.unpack_from('<H', d, 6)[0]
    n = ncnt - 1
    exp = (16 + n * 8 + 4) if ds else (18 + n * 10 + 4)
    dstart = struct.unpack_from('<H', d, 12)[0] if ds else struct.unpack_from('<I', d, 12)[0]
    if dstart == exp: return 1
    if dstart * 2 == exp: return 2
    return 1

def parse(d, ds=False, scale=None):
    """Parse an SPT file. Returns (hdr, records). ds=True for the 16-bit DS variant.
    scale=2 means offsets are stored as 16-bit units (fan-patched engine)."""
    if scale is None: scale = offset_scale(d, ds)
    assert d[:4] == b' TPS', d[:4]
    ver   = struct.unpack_from('<H', d, 4)[0]
    ncnt  = struct.unpack_from('<H', d, 6)[0]
    last  = struct.unpack_from('<H', d, 8)[0]
    mark  = struct.unpack_from('<H', d, 10)[0]
    if ds:
        dstart = struct.unpack_from('<H', d, 12)[0]
        lead   = struct.unpack_from('<H', d, 14)[0]
        p = 16; fmt = '<IHH'; rsz = 8
    else:
        dstart = struct.unpack_from('<I', d, 12)[0]
        lead   = struct.unpack_from('<H', d, 16)[0]
        p = 18; fmt = '<IIH'; rsz = 10
    recs = []
    n = ncnt - 1
    for i in range(n):
        a, b, c = struct.unpack_from(fmt, d, p); p += rsz
        recs.append((a, b, c))
    term = struct.unpack_from('<I', d, p)[0]
    dstart *= scale
    recs = [(a, b * scale, c) for a, b, c in recs]
    return dict(ver=ver, ncnt=ncnt, last=last, mark=mark, dstart=dstart, scale=scale,
                lead=lead, term=term, recend=p+4), recs

KEY = 0x55AA

def units(raw, n=None):
    """Decode a record's raw bytes into plaintext UTF-16 code units."""
    u = [int.from_bytes(raw[k:k+2],'little') ^ KEY for k in range(0, len(raw)-1, 2)]
    if n is not None:
        u = u[:n]
    return u

def render(u):
    s = ''
    for v in u:
        if 0xE000 <= v <= 0xF8FF:
            s += '{%04X}' % v
        elif v == 0:
            s += '{00}'
        elif v == 0x0A:
            s += '\n'
        else:
            s += chr(v)
    return s

def strings(d, ds=False):
    h, recs = parse(d, ds)
    bs = [x[1] for x in recs] + [len(d)]
    for i, (a, b, c) in enumerate(recs):
        yield i, a, c, units(d[b:bs[i+1]], c)

def all_strings(d, ds=False, scale=None):
    """Yield (i, A, length, units) for every string, INCLUDING string 0.

    String 0 is described by the header (offset 0x0C, length 0x0E), not by the
    record table; the record table covers strings 1..n. Missing it silently
    truncates every script file.
    """
    h, recs = parse(d, ds, scale)
    bounds = [h['dstart']] + [r[1] for r in recs] + [len(d)]
    yield 0, None, h['lead'], units(d[bounds[0]:bounds[1]], h['lead'])
    for i, (a, b, c) in enumerate(recs):
        yield i + 1, a, c, units(d[b:bounds[i+2]], c)
