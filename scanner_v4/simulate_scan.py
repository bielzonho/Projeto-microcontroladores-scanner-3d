"""Full simulated scan: fake photos -> detector -> mesh -> picture.

  python simulate_scan.py                     60 angles, 40 points per slice
  python simulate_scan.py --angles 12         a coarse, fast scan
  python simulate_scan.py --noise 25          noisier camera
  python simulate_scan.py --axis-error 10     wrong calibration (axis 10 px off)
  python simulate_scan.py --tilted            camera looks at the laser plane
                                              at a tilt; uses the perspective
                                              map of plane_map.py (needs that
                                              file in the folder too)
  python simulate_scan.py --glitches          add fake problems to some photos
                                              (reflections, hidden parts of the
                                              line, dead photo pairs; needs
                                              glitches.py)
  python simulate_scan.py --glitches --clean  ... and repair them before the
                                              mesh is built (needs cleanup.py)
  python simulate_scan.py --clean --smooth 1  clean-up with one smoothing pass
  python simulate_scan.py --save-photos DIR   also write the fake photos to the
                                              folder DIR (on_00.png, off_00.png,
                                              ...) for scan_folder.py. With
                                              --tilted the camera map is saved
                                              there too (camera_map.json).

It creates  scan.obj  (the scanned mesh) and  scan_preview.png  (a picture).
Needs mesh.py, viewer.py, scanner_config.py, laser_sim.py and detect_line.py
in the same folder.
"""
import argparse
import os
import subprocess
import sys
import time
import numpy as np

import detect_line
from scanner_config import AXIS_COL
from laser_sim import render_frame, object_radius, OBJECT_HEIGHT_MM
from detect_line import detect_profile
from mesh import build_mesh, write_obj, check_mesh

p = argparse.ArgumentParser()
p.add_argument("--angles", type=int, default=60,
               help="photos around the object (default 60)")
p.add_argument("--points", type=int, default=40,
               help="points per slice, top to bottom (default 40)")
p.add_argument("--noise", type=float, default=3.0, help="camera noise")
p.add_argument("--no-lamp", action="store_true", help="remove the lamp glow")
p.add_argument("--axis-error", type=float, default=0.0,
               help="pretend AXIS_COL was measured wrong by this many pixels")
p.add_argument("--tilted", action="store_true",
               help="tilted fake camera + perspective map (plane_map.py)")
p.add_argument("--glitches", action="store_true",
               help="add fake problems to some photos (glitches.py)")
p.add_argument("--glitch-kinds", default="reflection,shadow,dead",
               help="which problems: any of reflection,shadow,dead")
p.add_argument("--clean", action="store_true",
               help="repair wrong points before building the mesh (cleanup.py)")
p.add_argument("--spike", type=float, default=2.0,
               help="clean-up: a point this many mm away from its neighbours "
                    "is called wrong (default 2.0)")
p.add_argument("--smooth", type=int, default=0,
               help="clean-up: number of smoothing passes (default 0)")
p.add_argument("--save-photos", metavar="DIR",
               help="write the fake photos to this folder (for scan_folder.py)")
p.add_argument("--out", default="scan.obj")
p.add_argument("--preview", default="scan_preview.png")
a = p.parse_args()

rng = np.random.default_rng(1)
detect_line.AXIS_COL = AXIS_COL + a.axis_error      # (wrong calibration test)
cam = dict(lamp=not a.no_lamp, noise_sigma=a.noise)

if a.tilted:
    if a.axis_error:
        sys.exit("--axis-error does not apply to --tilted: there is no "
                 "AXIS_COL, the perspective map replaces it.")
    from plane_map import demo_map, detect_profile_plane, PLANE_PX
    print("  building the perspective map from fake cylinders ...")
    tmap = demo_map(np.random.default_rng(11), lamp_strength=0.5)
    if tmap["rms"] > 0.4:
        sys.exit("The perspective map could not be built (see plane_map.py).")
    print(f"  map ready (against the hidden truth: mean "
          f"{tmap['map_err_mean']:.2f} mm, worst {tmap['map_err_worst']:.2f} mm)")
    cam = dict(cam, warp=tmap["warp"], lamp_strength=0.5, **PLANE_PX)

if a.save_photos:
    import cv2
    os.makedirs(a.save_photos, exist_ok=True)
    if a.tilted:
        from plane_map import save_map
        save_map(tmap["H"], os.path.join(a.save_photos, "camera_map.json"))

if a.glitches:
    import glitches
    kinds = tuple(k.strip() for k in a.glitch_kinds.split(",") if k.strip())
    unknown = [k for k in kinds if k not in glitches.ALL_KINDS]
    if unknown:
        sys.exit(f"Unknown --glitch-kinds {unknown}; use any of "
                 f"{','.join(glitches.ALL_KINDS)}")
    glitch_rng = np.random.default_rng(5)         # separate: base scan unchanged

# ---- 1) "scan": two photos per angle, detect the line in each pair --------
start = time.time()
zs = np.linspace(0.0, OBJECT_HEIGHT_MM, a.points)     # heights of every slice
R, truth, damaged = [], [], []
for i in range(a.angles):
    theta = 2 * np.pi * i / a.angles
    on = render_frame(theta, True, rng, **cam)
    off = render_frame(theta, False, rng, **cam)
    if a.glitches:
        on, applied = glitches.damage_pair(on, off, glitch_rng, kinds)
        if applied:
            damaged.append(applied)
    if a.save_photos:
        cv2.imwrite(os.path.join(a.save_photos, f"on_{i:02d}.png"), on)
        cv2.imwrite(os.path.join(a.save_photos, f"off_{i:02d}.png"), off)
    hole = 3.0 if a.clean else None      # clean-up wants holes left empty
    try:
        if a.tilted:
            r, _ = detect_profile_plane(on, off, tmap["H"], a.points, 0.0,
                                        OBJECT_HEIGHT_MM, hole)
        else:
            r, _, _ = detect_profile(on, off, a.points, 0.0, OBJECT_HEIGHT_MM,
                                     hole)
    except RuntimeError:
        if not a.clean:
            sys.exit(f"\nNo laser line found at angle "
                     f"{np.degrees(theta):.0f} deg.\n"
                     f"(With --clean such a photo pair is skipped and repaired.)")
        r = np.full(a.points, np.nan)                     # hole, repaired below
    R.append(np.asarray(r, float))                        # what we measured
    truth.append(list(zip(object_radius(theta, zs), zs))) # what is really there
    print(f"\r  scanning: photo pair {i + 1} of {a.angles}", end="", flush=True)
print(f"\n  scan took {time.time() - start:.1f} s")

if a.glitches:
    names = [k for k in glitches.ALL_KINDS if k in kinds]
    count = {k: sum(k in d for d in damaged) for k in names}
    print(f"  fake problems added to {len(damaged)} of {a.angles} photo pairs: "
          + ", ".join(f"{k} {n}" for k, n in count.items()))

# ---- 1b) optional clean-up of the measured table ----------------------------
if a.clean:
    from cleanup import clean_slices
    R, info = clean_slices(np.array(R), spike_mm=a.spike,
                           smooth_passes=a.smooth)
    print(f"  clean-up: {info['missing']} points missing, {info['wrong']} "
          f"wrong, {info['redone']} of {info['total']} redone"
          + (f", smoothing x{a.smooth}" if a.smooth else ""))
    for w in info["warnings"]:
        print("  WARNING:", w)
slices = [list(zip(r, zs)) for r in R]

# ---- 2) build the mesh from the measured slices ---------------------------
verts, faces = build_mesh(slices)
write_obj(a.out, verts, faces)
closed, volume = check_mesh(verts, faces)

# ---- 3) compare with a mesh built from the TRUE slices --------------------
tverts, tfaces = build_mesh(truth)
_, true_volume = check_mesh(tverts, tfaces)
dist = np.linalg.norm(np.array(verts) - np.array(tverts), axis=1)

print(f"\n  mesh: {len(verts)} vertices, {len(faces)} faces -> {a.out}")
print(f"  closed mesh: {closed}, "
      f"{'outward' if volume > 0 else 'INSIDE-OUT'}")
print(f"  volume  scanned {volume:,.0f} mm3   true {true_volume:,.0f} mm3   "
      f"difference {100 * (volume - true_volume) / true_volume:+.2f} %")
print(f"  distance between scanned and true surface: "
      f"mean {dist.mean():.3f} mm, worst {dist.max():.3f} mm")

# ---- 4) picture ------------------------------------------------------------
viewer = os.path.join(os.path.dirname(os.path.abspath(__file__)), "viewer.py")
if os.path.exists(viewer):
    subprocess.run([sys.executable, viewer, a.out, "--save", a.preview],
                   check=True, stdout=subprocess.DEVNULL)
    print(f"  picture: {a.preview}")
else:
    print("  (viewer.py not found in this folder, so no picture was made)")
