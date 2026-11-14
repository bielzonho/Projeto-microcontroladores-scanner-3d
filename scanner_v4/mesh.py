"""Mesh generator for a turntable + line-laser scanner.

Input : slices[i] = list of (r, z) points for platform angle i
        r = distance from the rotation axis, z = height.
        Every slice must have the same number of points.
Output: a closed triangle mesh written as a Wavefront .obj file.

Run this file directly to build a fake vase and check the result.
"""
import math


# ---------------------------------------------------------------- fake data
def fake_scan(num_angles=40, num_heights=30, height=60.0):
    """A vase-like shape with a lumpy outline, so we can see if angles are right."""
    slices = []
    for i in range(num_angles):
        theta = 2 * math.pi * i / num_angles
        profile = []
        for j in range(num_heights):
            z = height * j / (num_heights - 1)
            r = 20 + 8 * math.sin(2 * math.pi * z / height)  # vase profile
            r *= 1 + 0.15 * math.cos(3 * theta)              # 3 lobes: not round
            profile.append((r, z))
        slices.append(profile)
    return slices


# --------------------------------------------------------------- mesh build
def build_mesh(slices, scale=1.0):
    """Return (vertices, faces). Faces use 1-based indices, as .obj expects."""
    n_ang = len(slices)
    n_h = len(slices[0])
    assert all(len(s) == n_h for s in slices), "all slices need the same length"

    # 1) cylindrical (r, theta, z) -> cartesian (x, y, z)
    vertices = []
    for i, profile in enumerate(slices):
        theta = 2 * math.pi * i / n_ang
        for r, z in profile:
            vertices.append((r * scale * math.cos(theta),
                             r * scale * math.sin(theta),
                             z * scale))

    def idx(i, j):  # 1-based index of the vertex at angle i, height j
        return (i % n_ang) * n_h + j + 1  # i % n_ang closes the loop

    faces = []

    # 2) side surface: join slice i to slice i+1 (the last joins back to the first)
    for i in range(n_ang):
        for j in range(n_h - 1):
            a, b = idx(i, j), idx(i, j + 1)          # slice i   (low, high)
            d, c = idx(i + 1, j), idx(i + 1, j + 1)  # slice i+1 (low, high)
            faces.append((a, d, c))  # counter-clockwise seen from outside
            faces.append((a, c, b))

    # 3) caps: a center vertex on the axis at the bottom and top, fanned out
    z_bottom = slices[0][0][1] * scale
    z_top = slices[0][-1][1] * scale
    vertices.append((0.0, 0.0, z_bottom))
    bottom_c = len(vertices)
    vertices.append((0.0, 0.0, z_top))
    top_c = len(vertices)
    for i in range(n_ang):
        faces.append((bottom_c, idx(i + 1, 0), idx(i, 0)))
        faces.append((top_c, idx(i, n_h - 1), idx(i + 1, n_h - 1)))

    return vertices, faces


# ------------------------------------------------------------------- output
def write_obj(path, vertices, faces):
    with open(path, "w") as f:
        for x, y, z in vertices:
            f.write(f"v {x:.4f} {y:.4f} {z:.4f}\n")
        for a, b, c in faces:
            f.write(f"f {a} {b} {c}\n")


# ------------------------------------------------------------------- checks
def check_mesh(vertices, faces):
    """Closed mesh: every edge is used once in each direction.
    Outward-facing: the signed volume is positive."""
    edges = {}
    for face in faces:
        for k in range(3):
            e = (face[k], face[(k + 1) % 3])
            edges[e] = edges.get(e, 0) + 1
    closed = all(n == 1 and (e[1], e[0]) in edges for e, n in edges.items())

    volume = 0.0
    for a, b, c in faces:
        v0, v1, v2 = vertices[a - 1], vertices[b - 1], vertices[c - 1]
        cross = (v1[1] * v2[2] - v1[2] * v2[1],
                 v1[2] * v2[0] - v1[0] * v2[2],
                 v1[0] * v2[1] - v1[1] * v2[0])
        volume += (v0[0] * cross[0] + v0[1] * cross[1] + v0[2] * cross[2]) / 6.0
    return closed, volume


if __name__ == "__main__":
    slices = fake_scan()
    vertices, faces = build_mesh(slices)
    closed, volume = check_mesh(vertices, faces)
    write_obj("fake_vase.obj", vertices, faces)
    print(f"{len(vertices)} vertices, {len(faces)} faces")
    print("closed mesh:", closed)
    print(f"signed volume: {volume:.1f} ({'outward' if volume > 0 else 'INSIDE-OUT'})")
