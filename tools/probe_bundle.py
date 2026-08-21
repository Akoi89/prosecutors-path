import sys, UnityPy, collections
p = sys.argv[1]
env = UnityPy.load(p)
c = collections.Counter()
names = []
for obj in env.objects:
    c[obj.type.name] += 1
    if obj.type.name in ("TextAsset","MonoBehaviour","MonoScript","AssetBundle"):
        try:
            d = obj.read()
            n = getattr(d, "m_Name", None) or getattr(d, "name", None)
            names.append((obj.type.name, n, getattr(obj, "byte_size", 0)))
        except Exception as e:
            names.append((obj.type.name, "<err %s>" % e, 0))
print("types:", dict(c))
for t, n, s in names[:40]:
    print("  %-14s %-50s %d" % (t, n, s))
print("total listed:", len(names))
