import sys, os, UnityPy
src, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
env = UnityPy.load(src)
n = 0
for obj in env.objects:
    if obj.type.name != "TextAsset":
        continue
    d = obj.read()
    name = d.m_Name
    data = d.m_Script
    if isinstance(data, str):
        data = data.encode("utf-8", "surrogateescape")
    open(os.path.join(out, name + ".bin"), "wb").write(data)
    n += 1
print("wrote", n, "files to", out)
