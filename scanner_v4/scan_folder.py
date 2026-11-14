"""Scan a FOLDER of photo pairs: photos -> 3D mesh (.obj).

This is the program that will turn the real scanner's photos into a model.
It works the same on the fake photos of the simulator.

  python scan_folder.py FOLDER                       straight-on camera model
                                                     (numbers from scanner_config.py)
  python scan_folder.py FOLDER --map camera_map.json tilted camera (Part F map)
  python scan_folder.py FOLDER --z-range 0 80        give the height range yourself
  python scan_folder.py FOLDER --points 80           more points per slice
  python scan_folder.py FOLDER --no-clean            do not repair bad photos
  python scan_folder.py FOLDER --smooth 1            one smoothing pass
  python scan_folder.py FOLDER --mirror              the scan came out mirrored
  python scan_folder.py FOLDER --per-turn 60         positions in one full turn
                                                     (needed if the LAST photos
                                                     are missing)
  python scan_folder.py FOLDER --check-vase          (fake vase photos only)
                                                     compare with the true shape

THE PHOTOS
  One pair per platform position: on_00.png (laser on) and off_00.png (laser
  off), on_01.png / off_01.png, ... png or jpg. The positions must be EVENLY
  spaced over exactly ONE full turn (60 photos = every 6 degrees). The photo
  number gives the angle: number k of N is at k/N of a turn. Numbers may start
  at 0 (or at 1). A missing number counts as a failed photo and is repaired.
  Take the photos with the same camera settings and the same resolution as
  the ones used for the calibration.

THE HEIGHT RANGE
  Found by itself: for every photo the lowest and the highest point of the laser
  line are measured, and the MEDIAN over all photos is used (one photo with a
  stray reflection cannot stretch it). Never below the platform (z = 0).

Needs: mesh.py, detect_line.py, scanner_config.py, cleanup.py and (for the
picture) viewer.py in the same folder. With --map also plane_map.py,
calibrate.py and laser_sim.py. With --check-vase also laser_sim.py.
"""
import argparse
import os
import re
import subprocess
import sys
import time
import numpy as np
import cv2

import detect_line
from detect_line import (laser_signal, find_line_columns, reject_outliers,
                         detect_profile)
from mesh import build_mesh, write_obj, check_mesh

IMAGE_EXT = (".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff")
HOLE_MM = 3.0            # holes in the laser line longer than this are repaired


# ------------------------------------------------------------ the photos
def find_pairs(folder):
    """Return [(number, on_path, off_path), ...] sorted by number."""
    if not os.path.isdir(folder):
        sys.exit(f"The folder '{folder}' does not exist (check the name, and "
                 f"that the terminal is in the right place, guide 1.5).")
    ons, offs = {}, {}
    for name in os.listdir(folder):
        m = re.fullmatch(r"(on|off)_(\d+)(\.\w+)", name, re.IGNORECASE)
        if m and m.group(3).lower() in IMAGE_EXT:
            table = ons if m.group(1).lower() == "on" else offs
            table[int(m.group(2))] = os.path.join(folder, name)
    lonely = sorted(set(ons) ^ set(offs))
    if lonely:
        sys.exit("These photo numbers have only an on_ or only an off_ photo: "
                 + ", ".join(f"{n:02d}" for n in lonely)
                 + ". Every on_NN needs an off_NN with the same number.")
    if len(ons) < 3:
        sys.exit(f"Need at least 3 on_/off_ photo pairs in '{folder}', found "
                 f"{len(ons)}. Names must look like on_00.png and off_00.png.")
    return [(n, ons[n], offs[n]) for n in sorted(ons)]


def read_pair(on_path, off_path):
    on, off = cv2.imread(on_path), cv2.imread(off_path)
    if on is None or off is None:
        sys.exit(f"Could not read {on_path} and/or {off_path} (damaged file?).")
    if on.shape != off.shape:
        sys.exit(f"{on_path} and {off_path} have different sizes.")
    return on, off


# ------------------------------------------------------------ measuring
def pair_extent(on, off, H=None):
    """Lowest and highest laser point (mm) in one photo pair, or None."""
    cols = reject_outliers(find_line_columns(laser_signal(on, off)))
    rows = np.where(~np.isnan(cols))[0]
    if len(rows) < 20:
        return None
    if H is None:
        z = (detect_line.BASE_ROW - rows) / detect_line.PX_PER_MM
    else:
        from plane_map import pixels_to_plane
        z = pixels_to_plane(H, np.column_stack([cols[rows], rows]))[:, 1]
    return float(z.min()), float(z.max())


def scan_folder(folder, H=None, n_points=40, z_range=None, clean=True,
                spike_mm=2.0, smooth=0, progress=False, per_turn=None):
    """Photos in a folder -> table of radii. Returns a dict:
         R         table: one row per photo slot, n_points radii (mm) each
         zs        the n_points heights (mm)
         z_lo, z_hi  the height range used
         failed    names of photo pairs where no laser line was found
         missing   photo numbers that do not exist (counted as failed)
         info      report of the clean-up (None if clean=False)
         n_pairs   number of photo pairs found
         warnings  list of text warnings
    """
    warnings = []
    pairs = find_pairs(folder)
    first = pairs[0][0]
    shift = 1 if first == 1 else 0               # on_01 ... on_60 -> slots 0..59
    slots = [n - shift for n, _, _ in pairs]
    n_slots = per_turn if per_turn else max(slots) + 1
    if max(slots) >= n_slots:
        sys.exit(f"Photo number {max(slots) + shift} does not fit: --per-turn "
                 f"{n_slots} means numbers {shift:02d} to "
                 f"{n_slots - 1 + shift:02d}.")
    missing = [s for s in range(n_slots) if s not in set(slots)]
    if missing and not per_turn:
        warnings.append(
            f"Photo numbers are missing and I assume {n_slots} positions per "
            f"turn (highest number + 1). If the LAST photos are the missing "
            f"ones, the angles come out wrong: give the true number with "
            f"--per-turn N.")
    if missing and not clean:
        sys.exit("Photo numbers missing: " + ", ".join(f"{s:02d}" for s in missing)
                 + ". Without clean-up every position is needed; retake them "
                   "or remove --no-clean.")

    # ---- pass 1: where does the laser line start and end? ------------------
    extents, shape = {}, None
    for k, (n, on_p, off_p) in enumerate(pairs):
        on, off = read_pair(on_p, off_p)
        if shape is None:
            shape = on.shape
        elif on.shape != shape:
            sys.exit(f"{on_p} has a different size from the first photo.")
        extents[n] = pair_extent(on, off, H)
        if progress:
            print(f"\r  looking at the photos: {k + 1} of {len(pairs)}",
                  end="", flush=True)
    good = [e for e in extents.values() if e is not None]
    failed = [f"on_{n:02d}" for n, e in extents.items() if e is None]
    if len(good) < 3:
        sys.exit("No laser line found in most of the photos. Check the laser "
                 "and the camera exposure (guide, Part C-2, the weak-laser "
                 "experiment).")
    if z_range is not None:
        z_lo, z_hi = z_range
    else:
        lows = np.array([e[0] for e in good])
        highs = np.array([e[1] for e in good])
        z_lo = max(0.0, float(np.median(lows)))
        z_hi = float(np.median(highs))
        spread = max(np.percentile(highs, 90) - np.percentile(highs, 10),
                     np.percentile(lows, 90) - np.percentile(lows, 10))
        if spread > 3.0:
            warnings.append(
                f"The laser line ends at quite different heights in different "
                f"photos (spread {spread:.1f} mm). Part of the object may be "
                f"hidden, or its top is not level. Every angle gets the same "
                f"height range, so the mesh may show steps. Give the range "
                f"yourself with --z-range if you know it.")
    if z_hi - z_lo < 5.0:
        sys.exit(f"The height range found is only {z_hi - z_lo:.1f} mm "
                 f"({z_lo:.1f} to {z_hi:.1f}). Something is wrong with the "
                 f"photos or the calibration. If you know the range, give it "
                 f"with --z-range LOW HIGH.")
    if progress:
        print()

    # ---- pass 2: radii at fixed heights, one row per photo slot -----------
    zs = np.linspace(z_lo, z_hi, n_points)
    R = np.full((n_slots, n_points), np.nan)
    hole = HOLE_MM if clean else None
    for k, (n, on_p, off_p) in enumerate(pairs):
        if extents[n] is not None:
            on, off = read_pair(on_p, off_p)
            if H is None:
                r = detect_profile(on, off, n_points, z_lo, z_hi, hole)[0]
            else:
                from plane_map import detect_profile_plane
                r = detect_profile_plane(on, off, H, n_points, z_lo, z_hi,
                                         hole)[0]
            R[n - shift] = r
        if progress:
            print(f"\r  measuring: photo pair {k + 1} of {len(pairs)}",
                  end="", flush=True)
    if progress:
        print()
    if failed and not clean:
        sys.exit("No laser line found in: " + ", ".join(failed)
                 + ". Retake them, or remove --no-clean to repair them.")
    if len(failed) + len(missing) > 0.3 * n_slots:
        warnings.append(f"{len(failed) + len(missing)} of {n_slots} photo pairs "
                        f"have no usable laser line. The repair of so many is "
                        f"unreliable: check the laser, the exposure and the "
                        f"room light (guide, Part C-2).")

    # ---- clean-up --------------------------------------------------------------
    info = None
    if clean:
        from cleanup import clean_slices
        try:
            R, info = clean_slices(R, spike_mm=spike_mm, smooth_passes=smooth)
        except ValueError as e:
            sys.exit(f"Clean-up not possible: {e}. (Use --no-clean only if the "
                     f"photos are good.)")
        warnings += info["warnings"]
    elif smooth:
        warnings.append("--smooth only works together with the clean-up; "
                        "ignored because of --no-clean.")
    return dict(R=R, zs=zs, z_lo=z_lo, z_hi=z_hi, failed=failed,
                missing=missing, info=info, n_pairs=len(pairs),
                warnings=warnings)


# ------------------------------------------------------------------- main
def main():
    p = argparse.ArgumentParser(description="photos in a folder -> .obj mesh")
    p.add_argument("folder", help="folder with on_00.png, off_00.png, ...")
    p.add_argument("--map", metavar="FILE",
                   help="perspective map from plane_map.py (tilted camera). "
                        "Without it the straight-on model of scanner_config.py "
                        "is used.")
    p.add_argument("--points", type=int, default=40,
                   help="points per slice, bottom to top (default 40)")
    p.add_argument("--z-range", type=float, nargs=2, metavar=("LOW", "HIGH"),
                   help="height range in mm (default: found automatically)")
    p.add_argument("--per-turn", type=int, metavar="N",
                   help="photo positions in one full turn (default: highest "
                        "photo number + 1). Needed if the last photos are "
                        "missing.")
    p.add_argument("--no-clean", action="store_true",
                   help="do not repair bad photos")
    p.add_argument("--spike", type=float, default=2.0,
                   help="clean-up limit in mm (default 2.0, see guide Part G)")
    p.add_argument("--smooth", type=int, default=0,
                   help="smoothing passes (default 0)")
    p.add_argument("--mirror", action="store_true",
                   help="mirror the result (if the platform turns the other way)")
    p.add_argument("--check-vase", action="store_true",
                   help="only for the fake vase photos: compare with the true "
                        "shape")
    p.add_argument("--out", default="scan.obj")
    p.add_argument("--preview", default="scan_preview.png")
    a = p.parse_args()

    H = None
    if a.map:
        if not os.path.exists(a.map):
            sys.exit(f"Map file '{a.map}' not found. Make it with plane_map.py "
                     f"(guide, Part F).")
        from plane_map import load_map
        H = load_map(a.map)

    start = time.time()
    pairs = find_pairs(a.folder)
    print(f"  folder '{a.folder}': {len(pairs)} photo pairs")
    if H is None:
        alpha = np.degrees(np.arcsin(detect_line.SIN_ALPHA))
        print(f"  camera model: straight-on, numbers of scanner_config.py "
              f"(PX_PER_MM {detect_line.PX_PER_MM:g}, AXIS_COL "
              f"{detect_line.AXIS_COL:g}, BASE_ROW {detect_line.BASE_ROW:g}, "
              f"ALPHA_DEG {alpha:g})")
        if (detect_line.PX_PER_MM, detect_line.AXIS_COL, detect_line.BASE_ROW,
                round(alpha, 3)) == (6.0, 320, 440, 45.0):
            print("  (these are the fake-camera numbers that came with the "
                  "guide: right for the\n   simulator's photos, wrong for real "
                  "ones. Calibrate first: Part E or F.)")
    else:
        print(f"  camera model: perspective map from {a.map}")

    try:
        res = scan_folder(a.folder, H, a.points,
                          tuple(a.z_range) if a.z_range else None,
                          not a.no_clean, a.spike, a.smooth, progress=True,
                          per_turn=a.per_turn)
    except SystemExit:
        print()                          # end the progress line first
        raise
    R, zs = res["R"], res["zs"]
    print(f"  positions in one turn: {len(R)} ({360.0 / len(R):.2f} degrees "
          f"per photo). Must be the number your scanner took in ONE full turn.")
    print(f"  height range: {res['z_lo']:.1f} to {res['z_hi']:.1f} mm "
          f"({res['z_hi'] - res['z_lo']:.1f} mm tall)"
          + ("  (given by you)" if a.z_range else "  (found in the photos)"))
    if res["failed"]:
        print("  no laser line found in: " + ", ".join(res["failed"]))
    if res["missing"]:
        print("  photo numbers missing: "
              + ", ".join(f"{s:02d}" for s in res["missing"]))
    if res["info"]:
        i = res["info"]
        print(f"  clean-up: {i['missing']} points missing, {i['wrong']} wrong, "
              f"{i['redone']} of {i['total']} redone"
              + (f", smoothing x{a.smooth}" if a.smooth else ""))
    for w in res["warnings"]:
        print("  WARNING:", w)
    if len(R) < 24:
        print(f"  note: only {len(R)} photo positions: the surface will look "
              f"faceted (guide, Part D).")

    if a.mirror:
        R = R[::-1]
    slices = [list(zip(r, zs)) for r in R]
    verts, faces = build_mesh(slices)
    write_obj(a.out, verts, faces)
    closed, volume = check_mesh(verts, faces)
    v = np.array(verts)
    size = v.max(axis=0) - v.min(axis=0)
    print(f"\n  mesh: {len(verts)} vertices, {len(faces)} faces -> {a.out}")
    print(f"  closed mesh: {closed}, {'outward' if volume > 0 else 'INSIDE-OUT'}")
    print(f"  volume {volume:,.0f} mm3")
    print(f"  size: {size[0]:.1f} x {size[1]:.1f} mm across, "
          f"{size[2]:.1f} mm tall   (took {time.time() - start:.1f} s)")

    if a.check_vase:
        from laser_sim import object_radius
        n = len(R)
        truth = np.array([object_radius(2 * np.pi * i / n, zs)
                          for i in range(n)])
        if a.mirror:
            truth = truth[::-1]
        d = np.abs(R - truth)
        print(f"  distance to the TRUE fake vase: mean {d.mean():.3f} mm, "
              f"worst {d.max():.3f} mm")

    viewer = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "viewer.py")
    if os.path.exists(viewer):
        subprocess.run([sys.executable, viewer, a.out, "--save", a.preview],
                       check=True, stdout=subprocess.DEVNULL)
        print(f"  picture: {a.preview}")
    else:
        print("  (viewer.py not found in this folder, so no picture was made)")


if __name__ == "__main__":
    main()
