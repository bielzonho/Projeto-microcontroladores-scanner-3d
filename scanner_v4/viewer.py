"""Minimal .obj viewer (numpy + matplotlib only).

  python3 viewer.py fake_vase.obj            -> opens a window you can rotate with the mouse
  python3 viewer.py fake_vase.obj --save a.png   -> saves a picture instead (no window)
"""
import argparse
import numpy as np
import matplotlib

parser = argparse.ArgumentParser()
parser.add_argument("obj")
parser.add_argument("--save", help="write a PNG instead of opening a window")
parser.add_argument("--elev", type=float, default=20)
parser.add_argument("--azim", type=float, default=-60)
args = parser.parse_args()

if args.save:
    matplotlib.use("Agg")  # no display needed
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection


def load_obj(path):
    verts, faces = [], []
    with open(path) as f:
        for line in f:
            p = line.split()
            if not p:
                continue
            if p[0] == "v":
                verts.append([float(x) for x in p[1:4]])
            elif p[0] == "f":
                # "f 1 2 3" or "f 1/1/1 2/2/2 3/3/3": keep only the vertex index
                faces.append([int(t.split("/")[0]) - 1 for t in p[1:4]])
    return np.array(verts), np.array(faces)


verts, faces = load_obj(args.obj)
tris = verts[faces]  # (n_faces, 3, 3)

# simple lighting: brightness from the angle between face normal and a light direction
normals = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
normals /= np.linalg.norm(normals, axis=1, keepdims=True) + 1e-12
light = np.array([0.4, -0.5, 0.8])
light /= np.linalg.norm(light)
shade = 0.25 + 0.75 * np.clip(normals @ light, 0, 1)
colors = np.outer(shade, [0.35, 0.6, 0.9])

fig = plt.figure(figsize=(7, 7))
ax = fig.add_subplot(111, projection="3d")
ax.add_collection3d(Poly3DCollection(tris, facecolors=colors, edgecolor="none"))

# equal axes so the object is not stretched
mid = (verts.max(0) + verts.min(0)) / 2
half = (verts.max(0) - verts.min(0)).max() / 2
ax.set_xlim(mid[0] - half, mid[0] + half)
ax.set_ylim(mid[1] - half, mid[1] + half)
ax.set_zlim(mid[2] - half, mid[2] + half)
ax.set_box_aspect((1, 1, 1))
ax.view_init(elev=args.elev, azim=args.azim)
ax.set_title(f"{args.obj}: {len(verts)} vertices, {len(faces)} faces")

if args.save:
    fig.savefig(args.save, dpi=120)
    print("saved", args.save)
else:
    plt.show()
