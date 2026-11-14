"""test_stl.py - checks export_stl.py (obj -> binary stl)."""
import os, re, struct, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import export_stl

RES = []
def check(name, ok, detail=""):
    RES.append(bool(ok)); print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"   ({detail})" if detail else ""))

def read_stl(data):
    n = struct.unpack("<I", data[80:84])[0]
    tris = []
    for i in range(n):
        v = struct.unpack("<12fH", data[84 + 50 * i: 134 + 50 * i])
        tris.append((v[0:3], v[3:6], v[6:9], v[9:12], v[12]))
    return n, tris

def volume(tris):          # tris: list of (a, b, c) corner triples
    vol = 0.0
    for a, b, c in tris:
        cr = (b[1]*c[2]-b[2]*c[1], b[2]*c[0]-b[0]*c[2], b[0]*c[1]-b[1]*c[0])
        vol += (a[0]*cr[0] + a[1]*cr[1] + a[2]*cr[2]) / 6.0
    return vol

CUBE = """v 0 0 0
v 10 0 0
v 10 10 0
v 0 10 0
v 0 0 10
v 10 0 10
v 10 10 10
v 0 10 10
f 1 4 3 2
f 5 6 7 8
f 1 2 6 5
f 2 3 7 6
f 3 4 8 7
f 4 1 5 8
"""   # six QUADS, outward-facing

print("1. A CUBE OF 10 mm (six quads -> 12 triangles)")
d = export_stl.obj_to_stl(CUBE.encode())
n, tris = read_stl(d)
check("size = 84 + 50 per triangle, count 12", len(d) == 84 + 50 * 12 and n == 12, f"{len(d)} bytes")
check("header is 80 bytes of text", d[:25] == b"scanner3d binary STL (mm)" and len(d[:80]) == 80)
check("volume 1000 mm3, positive (outward)", abs(volume([t[1:4] for t in tris]) - 1000) < 1e-3,
      f"{volume([t[1:4] for t in tris]):.3f}")
check("every normal has length 1 and points away from the centre",
      all(abs(sum(x*x for x in t[0]) - 1) < 1e-5 and
          sum(t[0][i] * ((t[1][i] + t[2][i] + t[3][i]) / 3 - 5) for i in range(3)) > 0 for t in tris))
check("attribute bytes are 0", all(t[4] == 0 for t in tris))
v, f = export_stl.parse_obj("v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1/1/1 2//2 -1\n")
check("'f a/b/c' tokens and negative indices understood", f == [(0, 1, 2)], str(f))

print("2. BAD FILES")
for text, why in [("", "empty"), ("v 0 0 0\nv 1 0 0\nv 0 1 0\n", "no faces"),
                  ("v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 9\n", "face to a missing point")]:
    try:
        export_stl.obj_to_stl(text.encode()); ok = False
    except ValueError:
        ok = True
    check(f"refused: {why}", ok)

print("3. THE MODEL OF A (FAKE) SCAN")
with tempfile.TemporaryDirectory() as tmp:
    ph = os.path.join(tmp, "ph")
    subprocess.run([sys.executable, os.path.join(HERE, "capture.py"), "--dry-run", "--photos", "36",
                    "--out", ph], capture_output=True, cwd=tmp)
    obj = os.path.join(tmp, "m.obj")
    r = subprocess.run([sys.executable, os.path.join(HERE, "scan_folder.py"), ph, "--out", obj,
                        "--preview", os.path.join(tmp, "p.png")], capture_output=True, text=True, cwd=tmp)
    m = re.search(r"volume ([0-9,]+) mm3", r.stdout)
    vol_scan = float(m.group(1).replace(",", ""))
    r = subprocess.run([sys.executable, os.path.join(HERE, "export_stl.py"), obj], capture_output=True, text=True)
    stl = os.path.join(tmp, "m.stl")
    check("CLI writes m.stl next to m.obj and says how many triangles", os.path.exists(stl) and "triangles" in r.stdout, r.stdout.strip())
    data = open(stl, "rb").read()
    n, tris = read_stl(data)
    verts, faces = export_stl.parse_obj(open(obj).read())
    check("same number of triangles as faces of the .obj", n == len(faces) == len(tris), f"{n}")
    worst = max(abs(a - b) for t, (i, j, k) in zip(tris, faces) for p, q in zip(t[1:4], (verts[i], verts[j], verts[k])) for a, b in zip(p, q))
    check("corners equal the .obj points (32-bit float rounding only)", worst < 1e-3, f"largest difference {worst:.6f} mm")
    vol_stl = volume([t[1:4] for t in tris])
    check("volume of the .stl equals the volume scan_folder.py reports", abs(vol_stl - vol_scan) / vol_scan < 1e-3,
          f"{vol_stl:,.0f} against {vol_scan:,.0f} mm3")
    r = subprocess.run([sys.executable, os.path.join(HERE, "export_stl.py"), os.path.join(tmp, "nothere.obj")], capture_output=True, text=True)
    check("missing file: clear message, exit 1", r.returncode == 1 and "Error" in r.stdout)

print(f"\n  {sum(RES)} of {len(RES)} checks passed")
sys.exit(0 if all(RES) else 1)
