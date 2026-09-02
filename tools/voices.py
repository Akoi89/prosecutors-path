# -*- coding: utf-8 -*-
"""Capcom's English voice shouts, from the player's Collection into the DS sound archive.

The fan patch replaced 20 one-shot samples in com/kenji2_sound.sdat with its
own English recordings of the shouts. The Collection localises 13 of those
slots (AudioClips SE_<n>_eng in the gk2_se bundle; the SE numbering is the
same on both platforms). The other seven have no language variants in the
Collection at all, so the fan's versions stay.

Per slot this does what the retail archive did:

  SE 37-46, 221, 222   IMA ADPCM, 22050 Hz, mono   (the retail format there)
  SE 177               16-bit PCM, 32000 Hz, mono  (retail was PCM16/32k too)

The Collection clips are 44.1 kHz stereo 16-bit: downmixed by averaging,
resampled with a windowed-sinc filter, peak-normalised the way every retail
and fan shout is (peak 1.00), then encoded. SWAV headers (rate, timer,
loop length) and the SWAR/SDAT tables are all rebuilt from the actual sample
data, never patched on one side.

There is no fixed slot on the DS: SWAR entries are variable-size and the
SDAT FAT is rebuilt, and each shout's sequence is a single note of length 0
with a flat envelope, so a sample plays to its end whatever its length.
SE 177 is 0.5 s longer than the fan's; it goes in whole.

    extract(bdir, dumpdir)        Collection -> dump/voice/SE_<n>_eng.wav
    apply(dumpdir, rom_path)      rebuild the sdat in the ROM in place
    python tools/voices.py        standalone: dump/voice -> out/audit/voice/
"""
import io, os, glob, math, struct, wave
import sys
sys.path.insert(0, os.path.dirname(__file__))

SDAT_PATH = 'com/kenji2_sound.sdat'
BUNDLE_PREFIX = 'gk2_se_trial_assets_all_'
PEAK = 0.98
# SE number -> (target rate, encoding)  encoding 1 = PCM16, 2 = IMA ADPCM
SLOTS = {
    37: (22050, 2), 38: (22050, 2), 39: (22050, 2), 40: (22050, 2), 41: (22050, 2),
    42: (22050, 2), 43: (22050, 2), 44: (22050, 2), 45: (22050, 2), 46: (22050, 2),
    177: (32000, 1), 221: (22050, 2), 222: (22050, 2),
}
ARC_TIMER = 16756991


def voice_dir(dumpdir):
    return os.path.join(dumpdir, 'voice')


def required(dumpdir):
    return [os.path.join(voice_dir(dumpdir), 'SE_%d_eng.wav' % n) for n in SLOTS]


# --- Collection -> WAV ---------------------------------------------------------

def extract(bdir, dumpdir):
    import UnityPy
    out = voice_dir(dumpdir)
    os.makedirs(out, exist_ok=True)
    bundles = glob.glob(os.path.join(bdir, BUNDLE_PREFIX + '*.bundle'))
    if not bundles:
        raise SystemExit('no %s*.bundle under %s' % (BUNDLE_PREFIX, bdir))
    want = {'SE_%d_eng' % n: n for n in SLOTS}
    got = {}
    for b in bundles:
        env = UnityPy.load(b)
        for o in env.objects:
            if o.type.name != 'AudioClip':
                continue
            c = o.read()
            if c.m_Name in want and want[c.m_Name] not in got:
                for _, data in c.samples.items():
                    p = os.path.join(out, c.m_Name + '.wav')
                    with open(p, 'wb') as f:
                        f.write(data)
                    got[want[c.m_Name]] = p
                    break
    missing = sorted(set(SLOTS) - set(got))
    if missing:
        raise SystemExit('Collection has no English clip for SE %s' % missing)
    return out


# --- audio -----------------------------------------------------------------

def read_wav_mono(path):
    w = wave.open(path, 'rb')
    n, rate, ch, sw = w.getnframes(), w.getframerate(), w.getnchannels(), w.getsampwidth()
    raw = w.readframes(n)
    w.close()
    if sw != 2:
        raise ValueError('%s: %d-bit, expected 16' % (path, sw * 8))
    s = struct.unpack('<%dh' % (len(raw) // 2), raw)
    if ch == 1:
        mono = [float(v) for v in s]
    else:
        mono = [sum(s[i * ch:(i + 1) * ch]) / float(ch) for i in range(n)]
    return mono, rate


def resample(x, src, dst, half=24):
    """Windowed-sinc resampling (Blackman window, half-width `half` output taps).
    Pure Python and deterministic, which the reference hash depends on."""
    if src == dst:
        return list(x)
    ratio = float(src) / dst
    fc = min(1.0, 1.0 / ratio)                     # low-pass at the lower Nyquist
    span = half * max(1.0, ratio)                  # input samples covered per side
    n_out = int(len(x) * dst / src)
    out = []
    N = len(x)
    for n in range(n_out):
        t = n * ratio
        k0, k1 = int(math.floor(t - span)), int(math.ceil(t + span))
        acc, wsum = 0.0, 0.0
        for k in range(max(0, k0), min(N - 1, k1) + 1):
            d = (t - k)
            if abs(d) >= span:
                continue
            w = 0.42 + 0.5 * math.cos(math.pi * d / span) + 0.08 * math.cos(2 * math.pi * d / span)
            s = fc if d == 0 else math.sin(math.pi * d * fc) / (math.pi * d)
            c = w * s
            acc += x[k] * c
            wsum += c
        out.append(acc / wsum if wsum else 0.0)
    return out


def normalise(x, peak=PEAK):
    m = max(abs(v) for v in x) or 1.0
    g = peak * 32767.0 / m
    return [max(-32768, min(32767, int(round(v * g)))) for v in x]


STEP = [7, 8, 9, 10, 11, 12, 13, 14, 16, 17, 19, 21, 23, 25, 28, 31, 34, 37, 41, 45, 50, 55, 60, 66, 73, 80, 88,
        97, 107, 118, 130, 143, 157, 173, 190, 209, 230, 253, 279, 307, 337, 371, 408, 449, 494, 544, 598, 658,
        724, 796, 876, 963, 1060, 1166, 1282, 1411, 1552, 1707, 1878, 2066, 2272, 2499, 2749, 3024, 3327, 3660,
        4026, 4428, 4871, 5358, 5894, 6484, 7132, 7845, 8630, 9493, 10442, 11487, 12635, 13899, 15289, 16818,
        18500, 20350, 22385, 24623, 27086, 29794, 32767]
IDX = [-1, -1, -1, -1, 2, 4, 6, 8]


def ima_encode(samples):
    """IMA ADPCM as the DS decodes it: 4-byte header (predictor s16, step
    index u16), then low nibble first."""
    pred, idx = samples[0], 0
    out = bytearray(struct.pack('<hH', pred, idx))
    nibs = []
    for s in samples:
        step = STEP[idx]
        delta = s - pred
        code = 0
        if delta < 0:
            code = 8
            delta = -delta
        diff = step >> 3
        if delta >= step:
            code |= 4; delta -= step; diff += step
        if delta >= (step >> 1):
            code |= 2; delta -= step >> 1; diff += step >> 1
        if delta >= (step >> 2):
            code |= 1; diff += step >> 2
        pred = pred - diff if code & 8 else pred + diff
        pred = max(-32768, min(32767, pred))
        idx = max(0, min(88, idx + IDX[code & 7]))
        nibs.append(code)
    if len(nibs) % 2:
        nibs.append(0)
    for i in range(0, len(nibs), 2):
        out.append(nibs[i] | (nibs[i + 1] << 4))
    while len(out) % 4:
        out.append(0)
    return bytes(out)


def swav(samples, rate, enc):
    if enc == 1:
        data = struct.pack('<%dh' % len(samples), *samples)
        while len(data) % 4:
            data += b'\x00'
        ls = 0
    else:
        data = ima_encode(samples)
        ls = 1
    ll = len(data) // 4 - ls
    hdr = struct.pack('<BBHHHI', enc, 0, rate, ARC_TIMER // rate, ls, ll)
    return hdr + data


def swar(swavs):
    n = len(swavs)
    table_end = 0x3C + 4 * n
    offs, body = [], bytearray()
    for s in swavs:
        offs.append(table_end + len(body))
        body += s
    size = table_end + len(body)
    out = bytearray(b'SWAR' + struct.pack('<HHIHH', 0xFEFF, 0x0100, size, 0x10, 1))
    out += b'DATA' + struct.pack('<I', size - 0x10) + bytes(32)
    out += struct.pack('<I', n) + b''.join(struct.pack('<I', o) for o in offs) + body
    assert len(out) == size
    return bytes(out)


# --- SDAT ------------------------------------------------------------------

def sdat_parts(d):
    symb_off, symb_sz, info_off, info_sz, fat_off, fat_sz, file_off, file_sz = struct.unpack_from('<8I', d, 0x10)
    nf = struct.unpack_from('<I', d, fat_off + 8)[0]
    fat = [struct.unpack_from('<II', d, fat_off + 12 + 16 * i) for i in range(nf)]
    files = [d[o:o + s] for o, s in fat]
    return (symb_off, info_off, fat_off, file_off), fat, files


def sdat_names(d, kind):
    symb_off = struct.unpack_from('<I', d, 0x10)[0]
    recs = struct.unpack_from('<8I', d, symb_off + 8)
    off = recs[kind]
    n = struct.unpack_from('<I', d, symb_off + off)[0]
    out = []
    for i in range(n):
        o = struct.unpack_from('<I', d, symb_off + off + 4 * i + 4)[0]
        out.append(d[symb_off + o:d.index(b'\x00', symb_off + o)].decode('ascii') if o else None)
    return out


def wavearc_files(d):
    """wavearc name -> FAT file id, from the INFO block."""
    info_off = struct.unpack_from('<I', d, 0x18)[0]
    recs = struct.unpack_from('<8I', d, info_off + 8)
    off = recs[3]
    n = struct.unpack_from('<I', d, info_off + off)[0]
    names = sdat_names(d, 3)
    out = {}
    for i in range(n):
        o = struct.unpack_from('<I', d, info_off + off + 4 * i + 4)[0]
        if o and names[i]:
            out[names[i]] = struct.unpack_from('<H', d, info_off + o)[0]
    return out


def rebuild_sdat(d, repl):
    """Return the sdat with FAT files in `repl` (file id -> bytes) replaced;
    the FILE block is re-laid back to back, exactly as the original was."""
    (symb_off, info_off, fat_off, file_off), fat, files = sdat_parts(d)
    for i in range(1, len(fat)):
        assert fat[i][0] == fat[i - 1][0] + fat[i - 1][1], 'FILE block is not back to back'
    files = [repl.get(i, f) for i, f in enumerate(files)]
    out = bytearray(d[:file_off + 16])
    pos = file_off + 16
    for i, f in enumerate(files):
        struct.pack_into('<II', out, fat_off + 12 + 16 * i, pos, len(f))
        pos += len(f)
    body = b''.join(files)
    out += body
    struct.pack_into('<I', out, 0x08, len(out))                 # file size
    struct.pack_into('<I', out, 0x2C, len(out) - file_off)      # FILE block size (header field)
    struct.pack_into('<I', out, file_off + 4, len(out) - file_off)
    return bytes(out)


def build(dumpdir, log=None):
    """-> (new sdat bytes, report lines)."""
    log = log if log is not None else []
    sdat = open(os.path.join(dumpdir, 'ds_fan', *SDAT_PATH.split('/')), 'rb').read()
    wa = wavearc_files(sdat)
    repl = {}
    for n, (rate, enc) in sorted(SLOTS.items()):
        name = 'wav_se%03d' % n if n >= 100 else 'wav_se%03d' % n
        # retail names: wav_se037..046, wav_se177, wav_se221, wav_se222
        fid = wa.get(name)
        if fid is None:
            raise SystemExit('sdat has no wave archive %s' % name)
        mono, src = read_wav_mono(os.path.join(voice_dir(dumpdir), 'SE_%d_eng.wav' % n))
        pcm = normalise(resample(mono, src, rate))
        repl[fid] = swar([swav(pcm, rate, enc)])
        log.append('SE %3d -> %-10s %s %5d Hz %6d samples %.2fs  %6d B' % (
            n, name, 'pcm16' if enc == 1 else 'adpcm', rate, len(pcm), len(pcm) / float(rate), len(repl[fid])))
    return rebuild_sdat(sdat, repl), log


def apply(dumpdir, rom_path, log=print):
    from title_logo import splice
    new, lines = build(dumpdir)
    rom = open(rom_path, 'rb').read()
    rom = splice(rom, SDAT_PATH, new)
    open(rom_path, 'wb').write(rom)
    for l in lines:
        log(l)
    log('voices: %d shouts in Capcom\'s English, sound archive %d -> %d bytes' % (
        len(SLOTS), os.path.getsize(os.path.join(dumpdir, 'ds_fan', *SDAT_PATH.split('/'))), len(new)))


if __name__ == '__main__':
    from paths import work
    dumpdir = work('dump')
    outdir = os.path.join(work('out'), 'audit', 'voice')
    os.makedirs(outdir, exist_ok=True)
    new, lines = build(dumpdir)
    print('\n'.join(lines))
    p = os.path.join(outdir, 'kenji2_sound.sdat')
    open(p, 'wb').write(new)
    print('wrote', p, len(new), 'bytes')
    if '--rom' in sys.argv:
        from title_logo import splice
        i = sys.argv.index('--rom')
        rom = splice(open(sys.argv[i + 1], 'rb').read(), SDAT_PATH, new)
        open(sys.argv[i + 2], 'wb').write(rom)
        print('wrote', sys.argv[i + 2])
