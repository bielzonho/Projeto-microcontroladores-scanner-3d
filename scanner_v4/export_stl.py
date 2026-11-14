"""
export_stl.py - turns the .obj of the scanner into a binary .stl (for 3D printing).

    python export_stl.py model.obj              writes model.stl next to it
    python export_stl.py model.obj out.stl

The numbers are NOT changed: the .obj of this scanner is in millimetres, and so
is the .stl (slicer programs read STL numbers as millimetres). Only triangles
are written (the scanner's .obj has only triangles; faces with more corners are
split). Binary STL: 80-byte header, a 32-bit count, then per triangle the
normal and the three corners as 32-bit floats and 2 bytes of attributes.

What the .stl is NOT: a guarantee that it prints well. It is exactly as good as
the scan (see the limits in the guide, Part H and the README).
"""

import math
import struct
import sys


def parse_obj(text):
    """(vertices, triangles) from the text of an .obj; triangles use 0-based indices."""
    verts, tris = [], []
    for line in text.splitlines():
        if line.startswith("v "):
            p = line.split()
            verts.append((float(p[1]), float(p[2]), float(p[3])))
        elif line.startswith("f "):
            idx = [int(tok.split("/")[0]) for tok in line.split()[1:]]
            idx = [i - 1 if i > 0 else len(verts) + i for i in idx]       # "-1" = last vertex
            for k in range(1, len(idx) - 1):                              # split a bigger face
                tris.append((idx[0], idx[k], idx[k + 1]))
    return verts, tris


def triangle_normal(a, b, c):
    ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
    nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
    n = math.sqrt(nx * nx + ny * ny + nz * nz)
    return (0.0, 0.0, 0.0) if n == 0 else (nx / n, ny / n, nz / n)


def obj_to_stl(obj_bytes):
    """bytes of an .obj -> bytes of a binary .stl. Raises ValueError for an unusable file."""
    verts, tris = parse_obj(obj_bytes.decode("utf-8", errors="replace"))
    if not verts or not tris:
        raise ValueError("the .obj has no points or no faces")
    for t in tris:
        for i in t:
            if not 0 <= i < len(verts):
                raise ValueError("a face points to a point that does not exist")
    out = bytearray()
    header = b"scanner3d binary STL (mm)"
    out += header.ljust(80, b" ")
    out += struct.pack("<I", len(tris))
    for ia, ib, ic in tris:
        a, b, c = verts[ia], verts[ib], verts[ic]
        out += struct.pack("<12fH", *triangle_normal(a, b, c), *a, *b, *c, 0)
    return bytes(out)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    src = argv[0]
    dst = argv[1] if len(argv) > 1 else (src[:-4] if src.lower().endswith(".obj") else src) + ".stl"
    try:
        with open(src, "rb") as f:
            data = obj_to_stl(f.read())
    except (OSError, ValueError) as e:
        print("Error:", e)
        return 1
    with open(dst, "wb") as f:
        f.write(data)
    print(f"{dst}: {(len(data) - 84) // 50} triangles, {len(data) / 1024:.0f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
