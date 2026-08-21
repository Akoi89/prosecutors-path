import struct, sys, os
def extract(path, out):
    d = open(path,'rb').read()
    fnt = struct.unpack_from('<I', d, 0x40)[0]
    fat = struct.unpack_from('<I', d, 0x48)[0]
    def dirents(dirid):
        off = fnt + (dirid & 0xFFF) * 8
        suboff, firstid, parent = struct.unpack_from('<IHH', d, off)
        p = fnt + suboff; fid = firstid; res = []
        while True:
            t = d[p]; p += 1
            if t == 0: break
            ln = t & 0x7F; name = d[p:p+ln].decode('shift_jis','replace'); p += ln
            if t & 0x80:
                sub = struct.unpack_from('<H', d, p)[0]; p += 2
                res.append(('D', name, sub))
            else:
                res.append(('F', name, fid)); fid += 1
        return res
    def walk(dirid, prefix=''):
        for t, name, i in dirents(dirid):
            if t == 'D':
                walk(i, prefix + name + '/')
            else:
                s, e = struct.unpack_from('<II', d, fat + i*8)
                fp = os.path.join(out, prefix + name)
                os.makedirs(os.path.dirname(fp), exist_ok=True)
                open(fp,'wb').write(d[s:e])
    walk(0xF000)
if __name__ == '__main__':
    extract(sys.argv[1], sys.argv[2])
    print("extracted ->", sys.argv[2])
