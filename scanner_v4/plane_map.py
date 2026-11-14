"""Perspective map: turn the pixels of the laser line into millimetres, for a
camera that looks at the laser plane at a tilt (above it, or close to it).

WHY
  The laser light forms a flat, vertical "sheet" through the rotation axis.
  A camera always sees a flat sheet through a 3x3 "perspective map" (a
  homography). If we know that map, every pixel of the laser line converts
  straight to two millimetre values:
      t = distance from the axis along the sheet  (the radius we want)
      z = height above the platform
  This replaces PX_PER_MM, AXIS_COL, BASE_ROW and ALPHA_DEG of scanner_config
  and also handles tilt and "far things look smaller". The camera is FIXED,
  so the map is measured once and saved to camera_map.json.

HOW IT IS MEASURED
  The same cylinders as in calibrate.py. A cylinder of radius R and height H,
  centered on the axis, makes a laser line whose two ends are known points of
  the sheet:   bottom end = (t=R, z=0)    top end = (t=R, z=H).
  Each cylinder gives 2 points. Two cylinders (4 points) are the minimum, three
  are better because then the points can be checked against each other.

USAGE
  python plane_map.py                    demo with FAKE photos from a tilted
                                         fake camera (hidden tilt)
  python plane_map.py --save-photos      same, and write the fake photos to
                                         folders tilt_A, tilt_B, tilt_C
  python plane_map.py --strong-lamp      demo with a lamp so bright that the
                                         camera saturates (shows the warning)
  python plane_map.py --cyl tilt_A 25 50 --cyl tilt_B 35 45 --cyl tilt_C 15 40
                                         use photos from folders (for each
                                         --cyl: folder, radius mm, height mm;
                                         photos named on_00.png / off_00.png ...)
A good map is saved to camera_map.json.
"""
import argparse
import json
import sys
import numpy as np
import cv2

from detect_line import laser_signal, find_line_columns, reject_outliers, resample
from laser_sim import render_frame, object_radius, OBJECT_HEIGHT_MM
from calibrate import make_cylinder, load_pairs, save_pairs

# Layout of the FAKE straight-on laser-plane image, before the fake camera
# bends it. Only the simulator uses this.
PLANE_PX = dict(axis_col=320.0, base_row=440.0, px_per_mm=6.0)
MAP_FILE = "camera_map.json"
CHECK_RADIUS, CHECK_HEIGHT = 30.0, 50.0
SETUPS = [  # name, radius mm, height mm, off-center mm, off-center direction
    ("A", 25.0, 50.0, 1.5, 0.7),
    ("B", 35.0, 45.0, 1.0, 2.1),
    ("C", 15.0, 40.0, 0.5, 4.0),
]


# ------------------------------------------------------------ the map itself
def pixels_to_plane(H, pts):
    """pts: N x 2 array of (column, row)  ->  N x 2 array of (t, z) in mm."""
    pts = np.asarray(pts, np.float64).reshape(-1, 1, 2)
    return cv2.perspectiveTransform(pts, np.asarray(H, np.float64)).reshape(-1, 2)


def save_map(H, path=MAP_FILE):
    with open(path, "w") as f:
        json.dump({"what": "pixel (column, row) -> laser plane (t, z) in mm",
                   "H": np.asarray(H).tolist()}, f, indent=2)


def load_map(path=MAP_FILE):
    with open(path) as f:
        return np.array(json.load(f)["H"], np.float64)


def detect_profile_plane(on, off, H, n_points, z_min, z_max, max_hole_mm=None):
    """Like detect_line.detect_profile, but converts with the perspective map.
    Returns (r, z): n_points radii and heights in mm. max_hole_mm: see
    detect_line.resample (holes become NaN for cleanup.py)."""
    cols = reject_outliers(find_line_columns(laser_signal(on, off)))
    rows = np.where(~np.isnan(cols))[0]
    if len(rows) < 2:
        raise RuntimeError("no laser line found in this frame")
    tz = pixels_to_plane(H, np.column_stack([cols[rows], rows]))
    order = np.argsort(tz[:, 1])
    return resample(tz[order, 0], tz[order, 1], n_points, z_min, z_max,
                    max_hole_mm)


# -------------------------------------------------------------- measuring
def measure_line(on, off):
    """Straight (possibly slanted) laser line -> (top end, bottom end), each
    as (column, row)."""
    cols = reject_outliers(find_line_columns(laser_signal(on, off)))
    rows = np.where(~np.isnan(cols))[0]
    if len(rows) < 20:
        raise RuntimeError("laser line not found in one of the photos")
    keep = rows
    for _ in range(4):                       # fit a straight line, drop strays
        b, a = np.polyfit(keep, cols[keep], 1)
        close = keep[np.abs(cols[keep] - (a + b * keep)) < 3.0]
        if len(close) < 20 or len(close) == len(keep):
            break
        keep = close
    top, bottom = float(keep.min()), float(keep.max())
    return (a + b * top, top), (a + b * bottom, bottom)


def measure_cylinder(pairs, radius, height):
    ends = [measure_line(on, off) for on, off in pairs]
    return dict(radius=radius, height=height,
                top=np.mean([e[0] for e in ends], axis=0),
                bottom=np.mean([e[1] for e in ends], axis=0))


def fit_map(cylinders):
    """-> (H, rms_mm, warnings). rms_mm: how well the reference points agree
    with one single map (0 with only two cylinders: nothing to compare)."""
    warnings = []
    if len(cylinders) < 2:
        raise RuntimeError("need at least two cylinders")
    radii = [c["radius"] for c in cylinders]
    if max(radii) - min(radii) < 3:
        raise RuntimeError("the cylinder radii must differ by at least 3 mm")
    src, dst = [], []
    for c in cylinders:
        src += [c["top"], c["bottom"]]
        dst += [(c["radius"], c["height"]), (c["radius"], 0.0)]
    src, dst = np.float64(src), np.float64(dst)
    H, _ = cv2.findHomography(src, dst, 0)
    rms = float(np.sqrt(np.mean(np.sum(
        (pixels_to_plane(H, src) - dst) ** 2, axis=1))))
    if len(cylinders) == 2:
        warnings.append(
            "Only two cylinders: the map is exactly determined, so there is no "
            "way to check it. Use three or more cylinders (more different "
            "radii is better).")
    elif rms > 0.4:
        warnings.append(
            f"The reference points do not fit one single map (they miss by "
            f"{rms:.2f} mm on average, should be under 0.4). One laser line "
            f"is probably cut off at the top or bottom: too weak, saturated by "
            f"a bright lamp or window, or hidden. Or a radius or height was "
            f"typed wrongly. Lower the camera exposure or dim the room light, "
            f"retake the photos, and check the numbers you typed.")
    return H, rms, warnings


# ------------------------------------------------- fake tilted camera (demo)
def secret_warp():
    """The hidden tilt: fake straight-on plane image -> fake camera photo."""
    src = np.float32([[0, 0], [640, 0], [640, 480], [0, 480]])
    dst = np.float32([[10, 10], [630, 20], [600, 470], [40, 460]])
    return cv2.getPerspectiveTransform(src, dst).astype(np.float64)


def true_pixel_map(warp):
    """The exact pixel -> (t, z) map of the fake camera (to grade our result)."""
    ppm, ax, br = (PLANE_PX["px_per_mm"], PLANE_PX["axis_col"],
                   PLANE_PX["base_row"])
    mm_to_plane = np.array([[ppm, 0, ax], [0, -ppm, br], [0, 0, 1.0]])
    inv = np.linalg.inv(warp @ mm_to_plane)
    return inv / inv[2, 2]


def fake_pairs(rng, warp, radius, height, offset, direction, n_angles,
               lamp_strength):
    pairs = []
    for i in range(n_angles):
        theta = 2 * np.pi * i / n_angles
        kw = dict(radius_fn=make_cylinder(radius, offset, direction),
                  height=height, lamp_strength=lamp_strength, warp=warp,
                  **PLANE_PX)
        pairs.append((render_frame(theta, True, rng, **kw),
                      render_frame(theta, False, rng, **kw)))
    return pairs


def map_error_mm(H_est, H_true):
    """Worst / mean distance between our map and the true map, over the area
    t = 0..40 mm, z = 0..55 mm (using the true map to make the pixels)."""
    tt, zz = np.meshgrid(np.linspace(0, 40, 17), np.linspace(0, 55, 12))
    mm = np.column_stack([tt.ravel(), zz.ravel()])
    px = pixels_to_plane(np.linalg.inv(H_true), mm)
    err = np.linalg.norm(pixels_to_plane(H_est, px) - mm, axis=1)
    return float(err.mean()), float(err.max())


def demo_map(rng, n_angles=12, lamp_strength=0.5, save_photos=False):
    """Fake cylinders -> measured map. Returns a dict with the map and, since
    this is a demo, the hidden truth and quality numbers."""
    warp = secret_warp()
    cyls, all_pairs = [], []
    for name, radius, height, offset, direction in SETUPS:
        pairs = fake_pairs(rng, warp, radius, height, offset, direction,
                           n_angles, lamp_strength)
        if save_photos:
            save_pairs(f"tilt_{name}", pairs)
            print(f"  wrote {len(pairs) * 2} fake photos to tilt_{name}/")
        all_pairs.append(pairs)
        cyls.append(measure_cylinder(pairs, radius, height))
    H, rms, warnings = fit_map(cyls)
    mean_err, worst_err = map_error_mm(H, true_pixel_map(warp))
    return dict(H=H, warp=warp, rms=rms, warnings=warnings, pairs=all_pairs,
                map_err_mean=mean_err, map_err_worst=worst_err)


def check_with_new_cylinder(rng, warp, radius_of_line, lamp_strength, n=8):
    """Photos of a 4th cylinder that was not used for the map, measured by
    `radius_of_line(on, off) -> mean radius`. Returns the mean error in mm."""
    radii = []
    for i in range(n):
        theta = 2 * np.pi * i / n
        kw = dict(radius_fn=make_cylinder(CHECK_RADIUS), height=CHECK_HEIGHT,
                  lamp_strength=lamp_strength, warp=warp, **PLANE_PX)
        on = render_frame(theta, True, rng, **kw)
        off = render_frame(theta, False, rng, **kw)
        radii.append(radius_of_line(on, off))
    return float(np.mean(radii)) - CHECK_RADIUS


def vase_errors(rng, demo, lamp_strength, n=12):
    """Scan the fake vase with the tilted camera and compare with its true
    shape, once with the perspective map and once with the straight-on model
    of Part E (calibrate.py). Returns (map_errors, simple_errors,
    simple_warning); the last two are None if calibrate.py gave up."""
    import calibrate as ce
    import detect_line
    warning, cal = None, None
    try:
        cyls = [ce.measure_cylinder(demo["pairs"][k], SETUPS[k][1],
                                    SETUPS[k][2]) for k in range(2)]
        cal = ce.calibrate(cyls, 45.0)
        warning = cal["warnings"][0] if cal["warnings"] else None
    except RuntimeError as e:
        warning = str(e)
    saved = (detect_line.PX_PER_MM, detect_line.AXIS_COL,
             detect_line.BASE_ROW, detect_line.SIN_ALPHA)
    e_map, e_simple = [], []
    for i in range(n):
        theta = 2 * np.pi * i / n
        kw = dict(lamp_strength=lamp_strength, warp=demo["warp"], **PLANE_PX)
        on = render_frame(theta, True, rng, **kw)
        off = render_frame(theta, False, rng, **kw)
        r, z = detect_profile_plane(on, off, demo["H"], 30, 0.0,
                                    OBJECT_HEIGHT_MM)
        e_map.append(np.abs(r - object_radius(theta, z)))
        if cal is not None:
            ce.use_calibration(cal)
            try:
                r2, z2, _ = detect_line.detect_profile(on, off, 30, 0.0,
                                                       OBJECT_HEIGHT_MM)
                e_simple.append(np.abs(r2 - object_radius(theta, z2)))
            finally:
                (detect_line.PX_PER_MM, detect_line.AXIS_COL,
                 detect_line.BASE_ROW, detect_line.SIN_ALPHA) = saved
    return (np.concatenate(e_map),
            np.concatenate(e_simple) if e_simple else None, warning)


# ------------------------------------------------------------------- main
def main():
    p = argparse.ArgumentParser()
    p.add_argument("--cyl", nargs=3, action="append",
                   metavar=("FOLDER", "RADIUS_MM", "HEIGHT_MM"),
                   help="photos of one cylinder (repeat for each cylinder)")
    p.add_argument("--save-photos", action="store_true",
                   help="demo only: also write the fake photos to disk")
    p.add_argument("--strong-lamp", action="store_true",
                   help="demo only: a lamp bright enough to saturate the camera")
    p.add_argument("--angles", type=int, default=12,
                   help="demo only: photo pairs per cylinder (default 12)")
    p.add_argument("--out", default=MAP_FILE, help="map file to write")
    a = p.parse_args()

    # ------------------------------------------------ real photos from disk
    if a.cyl:
        cyls = []
        for folder, radius, height in a.cyl:
            pairs = load_pairs(folder)
            print(f"  {folder}: {len(pairs)} photo pairs, radius {radius} mm, "
                  f"height {height} mm")
            cyls.append(measure_cylinder(pairs, float(radius), float(height)))
        try:
            H, rms, warnings = fit_map(cyls)
        except RuntimeError as e:
            sys.exit(f"\n  {e}")
        print(f"\n  reference points agree within {rms:.2f} mm (rms)")
        for w in warnings:
            print("\n  WARNING: " + w)
        if rms > 0.4 and len(cyls) > 2:
            print("\n  Map NOT saved: fix the problem above and run again.")
            return
        save_map(H, a.out)
        print(f"\n  map saved to {a.out}")
        return

    # --------------------------------------------------------------- demo
    lamp = 1.0 if a.strong_lamp else 0.5
    rng = np.random.default_rng(11)
    demo = demo_map(rng, a.angles, lamp, a.save_photos)
    print(f"\nPerspective map from {len(SETUPS)} fake cylinders, tilted fake "
          f"camera ({a.angles} photo pairs each, "
          f"{'very bright' if a.strong_lamp else 'normal'} lamp)\n")
    print(f"  reference points agree within {demo['rms']:.2f} mm (rms)")
    print(f"  against the hidden truth (demo only), over the whole area "
          f"t 0-40 mm, z 0-55 mm:")
    print(f"      map error: mean {demo['map_err_mean']:.2f} mm, "
          f"worst {demo['map_err_worst']:.2f} mm")
    for w in demo["warnings"]:
        print("\n  WARNING: " + w)
    if demo["rms"] > 0.4:
        print("\n  Map NOT saved: fix the problem above and run again.")
        return
    save_map(demo["H"], a.out)
    print(f"\n  map saved to {a.out}")

    # Check 1: the good habit with real hardware, a known object not used
    # for the map.
    def with_map(on, off):
        r, _ = detect_profile_plane(on, off, demo["H"], 20, 1.0,
                                    CHECK_HEIGHT - 1.0)
        return float(r.mean())
    e_cyl = check_with_new_cylinder(rng, demo["warp"], with_map, lamp)
    print(f"\nCheck 1: a 4th cylinder (radius {CHECK_RADIUS:g} mm) that was not "
          f"used for the map")
    print(f"  measured radius error: {e_cyl:+.2f} mm")

    # Check 2: a shape that changes with height, all points, two methods.
    e_map, e_simple, warning = vase_errors(rng, demo, lamp)
    print("\nCheck 2: the fake vase, 12 photo pairs, every measured point "
          "compared with the true shape")
    print(f"  perspective map (this part)      : mean error "
          f"{e_map.mean():.2f} mm, worst {e_map.max():.2f} mm")
    if e_simple is not None:
        print(f"  straight-on model (calibrate.py) : mean error "
              f"{e_simple.mean():.2f} mm, worst {e_simple.max():.2f} mm")
    else:
        print("  straight-on model (calibrate.py) : could not be calibrated")
    if warning:
        print(f"      calibrate.py's own check says: {warning[:84]}...")


if __name__ == "__main__":
    main()
