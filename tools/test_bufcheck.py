# -*- coding: utf-8 -*-
"""Negative tests for bufcheck. Run from the port folder:
    python tools/test_bufcheck.py <built rom> [dump folder]

Reads the three built files out of the ROM, shows the unmodified blobs pass,
then feeds each of checks a-e a mutated copy (in memory only) and requires a
BufCheckError. Prints the message of each. Raises if any mutation is accepted
or the clean blobs are refused.
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bufcheck
import lz11
from bufcheck import BufCheckError
from build_spt import build_ds, build_archive
from spt import all_strings, parse, tails as spt_tails


def replace_row(ent, row, fn):
    """Rebuild an SPT entry with row `row` replaced by fn(units)."""
    h = parse(ent, True)[0]
    S = list(all_strings(ent, True))
    rows = [list(t[3]) for t in S]
    ncnt = len(rows)
    rows[row] = fn(rows[row])
    marks = [struct.unpack_from('<I', ent, 0x10 + 8 * r)[0] for r in range(ncnt)]
    tl = spt_tails(ent, True)
    keep = [t if t != [0] else None for t in tl]
    recs = [(S[i][1], rows[i]) for i in range(1, ncnt)]
    return build_ds(rows[0], recs, marks[-1], h['scale'], 0, keep)


def swap_entry(spt, i, new):
    ents = bufcheck.spt_entries(spt)
    ents[i] = new
    return build_archive(ents)


def must_raise(name, fn):
    try:
        fn()
    except BufCheckError as e:
        print('  RAISED  %-46s %s' % (name, e))
        return
    raise SystemExit('FAILED: %s was accepted' % name)


def cut_with(cd, blob):
    """cutdata.bin with slot 47 replaced by `blob` (literal-only stream, appended)."""
    t = bufcheck._table(cd)
    n = len(t)
    table = bytearray(cd[:n * 8])
    body = bytearray(cd[n * 8:])
    off = n * 8 + len(body)
    body += lz11.compress(blob)
    while len(body) % 4:
        body += b'\x00'
    struct.pack_into('<II', table, bufcheck.CUT_SLOT * 8, off, 0x80000000 | len(blob))
    struct.pack_into('<II', table, (n - 1) * 8, n * 8 + len(body), 0)
    return bytes(table) + bytes(body)


def main(rom_path, dumpdir='dump'):
    rom = open(rom_path, 'rb').read()
    fan = open(os.path.join(dumpdir, 'ds_fan', 'jpn', 'idlocal.bin'), 'rb').read()
    spt, idl, cut = bufcheck.rom_files(rom)
    print(bufcheck.check_blobs(spt, idl, cut, fan))
    ents = bufcheck.spt_entries(spt)

    print('a. spt need')
    e = bytearray(ents[5])
    h = struct.unpack_from('<H', e, 8)[0]
    struct.pack_into('<H', e, 8, 0x1000)                      # header hint of entry 5 -> 0x1000
    must_raise('entry 5 header longest %d -> 4096' % h, lambda: bufcheck.check_blobs(swap_entry(spt, 5, bytes(e)), idl, cut, fan))
    e = bytearray(ents[7])
    ncnt = struct.unpack_from('<H', e, 6)[0]
    struct.pack_into('<H', e, 0xC + 8 * (ncnt - 1) + 2, 0x0FFF)   # last row's length in the row table
    must_raise('entry 7 last row length -> 4095 (hint stays)', lambda: bufcheck.check_blobs(swap_entry(spt, 7, bytes(e)), idl, cut, fan))
    e = bytearray(ents[342])                                   # the exemption itself must still pass
    struct.pack_into('<H', e, 8, 4059)
    bufcheck.check_blobs(swap_entry(spt, 342, bytes(e)), idl, cut, fan)
    print('  PASSED  entry 342 (exempt) with its real header longest 4059')

    print('b. text box length')
    def add_box_units(u, n=250):
        i = next(k for k, v in enumerate(u) if v == 0xE100 or v == 0xE101)
        return u[:i + 1 + bufcheck.ARITY.get(u[i], 0)] + [0x41] * n + u[i + 1 + bufcheck.ARITY.get(u[i], 0):]
    src = ents[76]
    m = replace_row(src, 4, add_box_units)
    must_raise('entry 76 row 4: 250 units added to a box', lambda: bufcheck.check_blobs(swap_entry(spt, 76, m), idl, cut, fan))

    loose = replace_row(ents[76], 4, lambda u: u + [0xE102] + [0x41] * 500)
    print('  b2. a 500-unit loose run after a close code is reported, not failed:')
    print('   ', bufcheck.check_blobs(swap_entry(spt, 76, loose), idl, cut, fan).split('(b)')[1].split('; (c)')[0].strip())

    print('c. exam rows')
    for i, r in ((453, 629), (458, 21)):
        m = replace_row(ents[i], r, lambda u: [0x41] * 64)
        must_raise('entry %d row %d: 64 plain units' % (i, r), lambda: bufcheck.check_blobs(swap_entry(spt, i, m), idl, cut, fan))
    m = replace_row(ents[453], 629, lambda u: [0x41] * 63)
    bufcheck.check_blobs(swap_entry(spt, 453, m), idl, cut, fan)
    print('  PASSED  entry 453 row 629 with exactly 63 plain units')

    print('d. idlocal sizes')
    t = bufcheck._table(idl)
    bad = bytearray(idl)
    struct.pack_into('<I', bad, 100 * 8 + 4, (t[100][1] & 0x80000000) | ((t[100][1] & 0x7FFFFFFF) + 4))
    must_raise('entry 100 table size +4', lambda: bufcheck.check_blobs(spt, bytes(bad), cut, fan))
    bad = bytearray(idl)
    o = t[100][0]
    bad[o + 1:o + 4] = ((t[100][1] & 0x7FFFFFFF) + 4).to_bytes(3, 'little')
    must_raise('entry 100 stream header size +4 (table kept)', lambda: bufcheck.check_blobs(spt, bytes(bad), cut, fan))
    bad = bytearray(idl)
    o = t[25][0]
    bad[o + 1:o + 4] = ((t[25][1] & 0x7FFFFFFF) + 4).to_bytes(3, 'little')
    struct.pack_into('<I', bad, 25 * 8 + 4, 0x80000000 | ((t[25][1] & 0x7FFFFFFF) + 4))
    must_raise('entry 25 table and header +4 (stream too short)', lambda: bufcheck.check_blobs(spt, bytes(bad), cut, fan))
    bad = bytearray(idl)                                      # reaches the size-against-fan branch
    struct.pack_into('<I', bad, 100 * 8 + 4, (t[100][1] & 0x80000000) | ((t[100][1] & 0x7FFFFFFF) + 4))
    o = t[100][0]
    bad[o + 1:o + 4] = ((t[100][1] & 0x7FFFFFFF) + 4).to_bytes(3, 'little')
    must_raise('entry 100 table and header both +4 (vs fan)', lambda: bufcheck.check_blobs(spt, bytes(bad), cut, fan))
    from choice_strips import rebuild, Idlocal                          # entry 25 back to literal-only storage
    lit = rebuild(idl, {25: Idlocal(idl).blob(25)})
    must_raise('entry 25 stored literal-only', lambda: bufcheck.check_blobs(spt, lit, cut, fan))
    must_raise('idlocal one entry short', lambda: bufcheck.check_idlocal(idl[:0] + struct.pack('<I', 8 * (len(t) - 1)) + idl[4:(len(t) - 1) * 8] + idl[len(t) * 8:], fan))

    print('e. cutdata slot 47')
    tc = bufcheck._table(cut)
    o, s = tc[bufcheck.CUT_SLOT]
    live = sorted(q for q, _z in tc if q > o)
    blob = bytearray(lz11.decompress(cut[o:live[0]]))
    b17 = bytearray(blob)
    struct.pack_into('<H', b17, 4, 17)
    must_raise('slot 47 records 2 -> 17', lambda: bufcheck.check_blobs(spt, idl, cut_with(cut, bytes(b17)), fan))
    big = bytes(blob) + bytes(1700 - len(blob))
    must_raise('slot 47 decoded size %d -> 1700' % len(blob), lambda: bufcheck.check_blobs(spt, idl, cut_with(cut, big), fan))
    b16 = bytearray(blob)
    struct.pack_into('<H', b16, 4, 16)
    b16 = bytes(b16) + bytes(1604 - len(b16))
    bufcheck.check_blobs(spt, idl, cut_with(cut, b16), fan)
    print('  PASSED  slot 47 at exactly 16 records and 1604 bytes')
    print('f. logic keyword cards')
    import logic_cards as L
    built = bufcheck.rom_file(rom, 'jpn/logic_keyword_local.bin')
    fan_l = open(os.path.join(dumpdir, 'ds_fan', 'jpn', 'logic_keyword_local.bin'), 'rb').read()
    print('  clean:', bufcheck.check_logic_cards(built, fan_l))

    def _swap(data, e, sub):
        """logic_keyword_local.bin with entry e replaced by sub (appended, table repointed)."""
        out = bytearray(data)
        while len(out) % 4:
            out += bytes(1)
        off = len(out)
        out += sub
        struct.pack_into('<II', out, e * 8, off, len(sub))
        return bytes(out)

    print('  fan file as built (fan cards kept whole pass):', bufcheck.check_logic_cards(fan_l, fan_l))
    must_raise('a card with no fan counterpart', lambda: bufcheck.check_logic_cards(_swap(built, 242, L.table(fan_l)[242]), fan_l))
    parts = L.sub_split(L.table(built)[244])
    g = bytearray(parts[2])
    fg = L.sub_split(L.table(fan_l)[244])[2]
    g[0x530:0x630] = fg[0x530:0x630]
    parts[2] = bytes(g)
    must_raise('card 244 rewritten but the fan tail bytes put back', lambda: bufcheck.check_logic_cards(_swap(built, 244, L.sub_join(parts)), fan_l))
    parts = L.sub_split(L.table(built)[243])
    parts[2] = parts[2][:0x30 + 1280]
    must_raise('card 243 RGCN part cut to 1280 tile bytes (OBJs reach 1536)', lambda: bufcheck.check_logic_cards(_swap(built, 243, L.sub_join(parts)), fan_l))
    print('  sizes and names of the rewritten cards (clean):', bufcheck.check_logic_sizes(built, fan_l),
          'rewritten,', bufcheck.check_logic_names(built, fan_l), 'punctuation-matched cards named')
    from title_text import repack
    from title_version import _store
    tb = L.table(built)
    must_raise('card 41 decodes 4 bytes longer than the fan card',
               lambda: bufcheck.check_logic_sizes(repack(built, {41: tb[41] + bytes(4)}), fan_l))
    pt = bufcheck._table(built)
    ext = bufcheck._extents(pt, len(built))

    def _relay(e, stored, size):
        """logic_keyword_local.bin laid out afresh with slot e holding `stored` and size field `size`
        (every other slot keeps its own bytes and size field, so no neighbour's extent is disturbed)."""
        n = len(pt); table = bytearray(n * 8); body = bytearray()
        for i, (o, z) in enumerate(pt):
            if not o:
                struct.pack_into('<II', table, i * 8, 0, z)
                continue
            raw = stored if i == e else built[ext[i][0]:ext[i][1]]
            while (n * 8 + len(body)) % 4:
                body += bytes(1)
            struct.pack_into('<II', table, i * 8, n * 8 + len(body), size if i == e else z)
            body += raw
        return bytes(table + body)

    must_raise('card 41 stored raw, the fan card compressed',
               lambda: bufcheck.check_logic_sizes(_relay(41, tb[41], len(tb[41])), fan_l))
    must_raise('card 41 stored 64 bytes over the literal-only form',
               lambda: bufcheck.check_logic_sizes(_relay(41, _store(tb[41]) + bytes(64), pt[41][1]), fan_l))
    boundary = bufcheck.check_logic_sizes(_relay(41, _store(tb[41]), pt[41][1]), fan_l)
    print('  PASSED  card 41 re-laid out at the literal-only size (%d rewritten)' % boundary)
    bad = bytearray(built)
    struct.pack_into('<II', bad, 41 * 8, pt[41][0], (pt[41][1] & 0x80000000) | (pt[41][1] & 0x7FFFFFFF) + 4)
    must_raise('card 41 table size field +4', lambda: bufcheck.check_logic_sizes(bytes(bad), fan_l))
    for e in (41, 175, 61, 255):
        must_raise('card %d put back to the fan drawing (a name that stopped matching)' % e,
                   lambda e=e: bufcheck.check_logic_names(repack(built, {e: L.table(fan_l)[e]}), fan_l))
    must_raise('the fan file as built has none of the six named', lambda: bufcheck.check_logic_names(fan_l, fan_l))
    print('g. bag model texture (jpn/modelitemlocal.bin entry 1)')
    from choice_strips import rebuild
    built_m = bufcheck.rom_file(rom, 'jpn/modelitemlocal.bin')
    fan_m = open(os.path.join(dumpdir, 'ds_fan', 'jpn', 'modelitemlocal.bin'), 'rb').read()
    print('  clean:', bufcheck.check_model_item(built_m, fan_m))
    print('  fan file as it is:', bufcheck.check_model_item(fan_m, fan_m))
    tm = bufcheck._table(fan_m)
    blob1 = lz11.decompress(fan_m[tm[1][0]:bufcheck._extents(tm, len(fan_m))[1][1]])
    must_raise('entry 1 stored literal-only (bigger than the fan\'s)',
               lambda: bufcheck.check_model_item(rebuild(fan_m, {1: blob1}), fan_m))
    must_raise('entry 1 decoded one byte longer',
               lambda: bufcheck.check_model_item(rebuild(fan_m, {1: blob1 + b'\0'}, lz=(1,)), fan_m))
    bad = bytearray(blob1)
    bad[0:4] = b'XXXX'
    must_raise('entry 1 no longer a BTX0', lambda: bufcheck.check_model_item(rebuild(fan_m, {1: bytes(bad)}, lz=(1,)), fan_m))
    blob0 = lz11.decompress(fan_m[tm[0][0]:bufcheck._extents(tm, len(fan_m))[0][1]])
    must_raise('entry 0 changed', lambda: bufcheck.check_model_item(rebuild(fan_m, {0: blob0[:-1] + b'\x01'}, lz=(0,)), fan_m))
    bad = bytearray(fan_m)
    struct.pack_into('<I', bad, 8 + 4, tm[1][1] + 4)
    must_raise('entry 1 table size +4', lambda: bufcheck.check_model_item(bytes(bad), fan_m))
    must_raise('one entry short', lambda: bufcheck.check_model_item(
        struct.pack('<I', 8 * (len(tm) - 1)) + fan_m[4:(len(tm) - 1) * 8] + fan_m[len(tm) * 8:], fan_m))
    print('h. room names (jpn/idlocal.bin 321 324 327, jpn/cutobj_local.bin 10)')
    from choice_strips import Idlocal
    built_i = bufcheck.rom_file(rom, 'jpn/idlocal.bin')
    built_c = bufcheck.rom_file(rom, 'jpn/cutobj_local.bin')
    fan_c = open(os.path.join(dumpdir, 'ds_fan', 'jpn', 'cutobj_local.bin'), 'rb').read()
    print('  clean:', bufcheck.check_rooms(built_i, fan, built_c, fan_c))
    print('  fan files as they are:', bufcheck.check_rooms(fan, fan, fan_c, fan_c))
    bi, ci = Idlocal(built_i), Idlocal(built_c)
    for e in bufcheck.ROOM_IDLOCAL:
        raw = bi.blob(e)
        must_raise('idlocal %d stored literal-only (bigger than the fan\'s)' % e,
                   lambda: bufcheck.check_rooms(rebuild(built_i, {e: raw}), fan, built_c, fan_c))
        must_raise('idlocal %d decoded one byte longer' % e,
                   lambda: bufcheck.check_rooms(rebuild(built_i, {e: raw + b'\0'}, lz=(e,)), fan, built_c, fan_c))
    bad = bytearray(built_i)
    ti = bufcheck._table(built_i)
    struct.pack_into('<I', bad, 321 * 8 + 4, ti[321][1] & 0x7FFFFFFF)      # compressed flag cleared
    must_raise('idlocal 321 table says stored raw', lambda: bufcheck.check_rooms(bytes(bad), fan, built_c, fan_c))
    raw = ci.blob(bufcheck.ROOM_CUTOBJ)
    must_raise('cutobj_local 10 stored literal-only', lambda: bufcheck.check_rooms(built_i, fan, rebuild(built_c, {10: raw}), fan_c))
    must_raise('cutobj_local 10 decoded one byte longer',
               lambda: bufcheck.check_rooms(built_i, fan, rebuild(built_c, {10: raw + b'\0'}, lz=(10,)), fan_c))
    tcc = bufcheck._table(built_c)
    other = ci.blob(0)
    must_raise('cutobj_local entry 0 changed',
               lambda: bufcheck.check_rooms(built_i, fan, rebuild(built_c, {0: other[:-1] + bytes([other[-1] ^ 1])}, lz=(0,)), fan_c))
    bad = bytearray(built_c)
    struct.pack_into('<I', bad, 10 * 8 + 4, tcc[10][1] + 4)
    must_raise('cutobj_local 10 table size +4', lambda: bufcheck.check_rooms(built_i, fan, bytes(bad), fan_c))
    must_raise('cutobj_local one entry short', lambda: bufcheck.check_rooms(
        built_i, fan, struct.pack('<I', 8 * (len(tcc) - 1)) + built_c[4:(len(tcc) - 1) * 8] + built_c[len(tcc) * 8:], fan_c))
    print('i. opening card (jpn/opening_local.bin entries 13/14)')
    import opening_card as oc
    built_o = bufcheck.rom_file(rom, 'jpn/opening_local.bin')
    fan_o = open(os.path.join(dumpdir, 'ds_fan', 'jpn', 'opening_local.bin'), 'rb').read()
    print('  clean:', bufcheck.check_opening_card(built_o, fan_o))
    print('  fan file as it is:', bufcheck.check_opening_card(fan_o, fan_o))
    g13, s13, _c = oc.entry(built_o, 13)
    fan_s13 = len(oc.entry(fan_o, 13)[1])
    lit = bytearray(b'\x11' + len(g13).to_bytes(3, 'little'))
    for p in range(0, len(g13), 8):
        lit.append(0); lit += g13[p:p + 8]

    def with13(stored13):
        """built_o with entry 13 replaced by the given stored bytes, table field kept."""
        t = bufcheck._table(built_o)
        ext = bufcheck._extents(t, len(built_o))
        a, b = ext[13]
        out = bytearray(built_o[:a]) + stored13
        shift = len(out) - b
        out += built_o[b:]
        for i, (o, s) in enumerate(t):
            if o > a:
                struct.pack_into('<I', out, i * 8, o + shift)
        return bytes(out)

    must_raise('entry 13 stored literal-only (%d bytes, fan %d)' % (len(lit), fan_s13), lambda: bufcheck.check_opening_card(with13(bytes(lit)), fan_o))
    real = lz11.compress(g13)
    print('  entry 13 padded to exactly the fan\'s stored size passes:',
          bufcheck.check_opening_card(with13(real + bytes(fan_s13 - len(real))), fan_o))
    must_raise('entry 13 one byte over the fan\'s stored size',
               lambda: bufcheck.check_opening_card(with13(real + bytes(fan_s13 - len(real) + 1)), fan_o))
    must_raise('entry 13 decoded one byte longer', lambda: bufcheck.check_opening_card(
        oc.rebuild(built_o, {13: g13 + b'\0'}, lz=(13,)), fan_o))
    bad = bytearray(g13)
    bad[0:4] = b'XXXX'
    must_raise('entry 13 no longer an RGCN', lambda: bufcheck.check_opening_card(oc.rebuild(built_o, {13: bytes(bad)}, lz=(13,)), fan_o))
    must_raise('entry 13 stored uncompressed', lambda: bufcheck.check_opening_card(oc.rebuild(built_o, {13: g13}), fan_o))
    p14 = oc.entry(built_o, 14)[0]
    must_raise('entry 14 stored as LZ11', lambda: bufcheck.check_opening_card(oc.rebuild(built_o, {14: p14}, lz=(14,)), fan_o))
    c12 = bytearray(oc.entry(built_o, 12)[0])
    c12[-1] ^= 1
    must_raise('entry 12 (cells) changed', lambda: bufcheck.check_opening_card(oc.rebuild(built_o, {12: bytes(c12)}, lz=(12,)), fan_o))
    a11 = bytearray(oc.entry(built_o, 11)[0])
    a11[-1] ^= 1
    must_raise('entry 11 (animation) changed', lambda: bufcheck.check_opening_card(oc.rebuild(built_o, {11: bytes(a11)}, lz=(11,)), fan_o))
    to = bufcheck._table(built_o)
    bad = bytearray(built_o)
    struct.pack_into('<I', bad, 13 * 8 + 4, to[13][1] + 4)
    must_raise('entry 13 table size +4', lambda: bufcheck.check_opening_card(bytes(bad), fan_o))
    print('all negative tests raised, boundary cases passed')


if __name__ == '__main__':
    sys.exit(main(*sys.argv[1:3]))
