"""Calibration helper: measure the camera numbers from photos of two cylinders.

It finds the four numbers of scanner_config.py that depend on your build:
    PX_PER_MM, BASE_ROW, AXIS_COL, ALPHA_DEG

HOW IT WORKS (short version)
  Put a straight cylinder (a can, a round container ... any shape with
  straight vertical sides and a round top view) on the platform, roughly in the
  middle. Its laser line is a straight vertical stripe in the photo.
    * height of the stripe in pixels / real height in mm  -> PX_PER_MM
    * bottom end of the stripe                            -> BASE_ROW
    * column of the stripe = AXIS_COL + radius * PX_PER_MM * sin(ALPHA)
  Two cylinders with different radii give two such columns, which is enough
  to solve for both AXIS_COL and ALPHA_DEG. Photos at several angles are
  averaged, so it does not matter if the cylinder is a little off-center.
  If the two cylinders give different PX_PER_MM, one of the stripes was cut
  off (too weak, saturated, hidden) and the helper refuses to give numbers.

USAGE
  python calibrate.py                    demo with FAKE photos (hidden true
                                         numbers, so you can see it works)
  python calibrate.py --save-photos      same, and also write the fake photos
                                         to folders calib_A and calib_B
  python calibrate.py --strong-lamp      demo with a lamp so bright that the
                                         camera saturates (shows the warning)
  python calibrate.py --cyl calib_A 25 50 --cyl calib_B 35 45
                                         use photos from folders. For every
                                         --cyl: folder, radius in mm, height
                                         in mm. Inside a folder, name the
                                         pairs on_00.png / off_00.png,
                                         on_01.png / off_01.png ...
"""
import argparse
import glob
import os
import sys
import numpy as np
import cv2

import detect_line
import scanner_config as cfg
from detect_line import laser_signal, find_line_columns, reject_outliers
from laser_sim import render_frame


# ------------------------------------------------------------ measuring
def measure_pair(on, off):
    """Straight vertical line on a cylinder -> (column, top row, bottom row)."""
    cols = reject_outliers(find_line_columns(laser_signal(on, off)))
    rows = np.where(~np.isnan(cols))[0]
    if len(rows) < 20:
        raise RuntimeError("laser line not found in one of the photos")
    med = np.median(cols[rows])
    keep = rows[np.abs(cols[rows] - med) < 3.0]   # only the straight stretch
    return cols[keep].mean(), keep.min(), keep.max()


def measure_cylinder(pairs, radius, height):
    stats = [measure_pair(on, off) for on, off in pairs]
    cols = np.array([s[0] for s in stats])
    return dict(radius=radius, height=height,
                col=cols.mean(),                       # average over angles
                wobble=(cols.max() - cols.min()) / 2,  # off-center shows here
                top=float(np.median([s[1] for s in stats])),
                bottom=float(np.median([s[2] for s in stats])))


def calibrate(cylinders, assumed_alpha_deg):
    """cylinders: list of dicts from measure_cylinder()."""
    warnings = []
    per_cyl = [(c["bottom"] - c["top"]) / c["height"] for c in cylinders]
    px_per_mm = float(np.mean(per_cyl))
    if len(per_cyl) >= 2 and (max(per_cyl) - min(per_cyl)) / px_per_mm > 0.03:
        values = " and ".join(f"{v:.2f}" for v in per_cyl)
        warnings.append(
            f"The cylinders give different PX_PER_MM ({values}). They should "
            f"agree. One line is probably cut off at the top or bottom: too "
            f"weak, saturated by a bright lamp or window, or hidden. Lower the "
            f"camera exposure or dim the room light, retake the photos, and "
            f"check that the heights you typed are right.")
    base_row = float(np.mean([c["bottom"] for c in cylinders]))
    ordered = sorted(cylinders, key=lambda c: c["radius"])
    if len(ordered) >= 2 and ordered[-1]["radius"] - ordered[0]["radius"] >= 3:
        lo, hi = ordered[0], ordered[-1]
        sin_a = ((hi["col"] - lo["col"])
                 / ((hi["radius"] - lo["radius"]) * px_per_mm))
        if not 0.1 < sin_a < 1.0:
            warnings.append(
                f"The two columns do not make sense (sin of the angle came "
                f"out {sin_a:.2f}). Check the radii and the photos, and that "
                f"the bigger cylinder really is the bigger one.")
            sin_a = float(np.sin(np.radians(assumed_alpha_deg)))
            alpha, assumed = assumed_alpha_deg, True
        else:
            alpha, assumed = float(np.degrees(np.arcsin(sin_a))), False
    else:
        alpha = assumed_alpha_deg
        sin_a = float(np.sin(np.radians(alpha)))
        assumed = True
    axis_col = float(np.mean([c["col"] - c["radius"] * px_per_mm * sin_a
                              for c in cylinders]))
    off_center = [c["wobble"] / (px_per_mm * sin_a) for c in cylinders]
    return dict(PX_PER_MM=px_per_mm, BASE_ROW=base_row, AXIS_COL=axis_col,
                ALPHA_DEG=alpha, alpha_assumed=assumed,
                off_center_mm=off_center, warnings=warnings)


# ------------------------------------------------------ fake photos (demo)
def make_cylinder(radius, offset_mm=0.0, direction=0.0):
    """Radius (mm) of a cylinder as the laser sees it at platform angle theta.
    offset_mm > 0 means the cylinder was not placed exactly in the middle."""
    def fn(theta, z):
        phi = theta - direction
        r = offset_mm * np.cos(phi) + np.sqrt(
            radius ** 2 - (offset_mm * np.sin(phi)) ** 2)
        return np.full_like(z, r, dtype=float)
    return fn


def fake_photos(rng, camera, radius, height, offset_mm, n_angles, direction,
                lamp_strength):
    pairs = []
    for i in range(n_angles):
        theta = 2 * np.pi * i / n_angles
        kw = dict(radius_fn=make_cylinder(radius, offset_mm, direction),
                  height=height, lamp_strength=lamp_strength, **camera)
        pairs.append((render_frame(theta, True, rng, **kw),
                      render_frame(theta, False, rng, **kw)))
    return pairs


# -------------------------------------------------------- photos on disk
def save_pairs(folder, pairs):
    os.makedirs(folder, exist_ok=True)
    for i, (on, off) in enumerate(pairs):
        cv2.imwrite(os.path.join(folder, f"on_{i:02d}.png"), on)
        cv2.imwrite(os.path.join(folder, f"off_{i:02d}.png"), off)


def load_pairs(folder):
    pairs = []
    for on_path in sorted(glob.glob(os.path.join(folder, "on_*.*"))):
        folder_part, name = os.path.split(on_path)
        off_path = os.path.join(folder_part, "off_" + name[len("on_"):])
        on, off = cv2.imread(on_path), cv2.imread(off_path)
        if on is None or off is None:
            sys.exit(f"Could not read {on_path} and its partner {off_path}.")
        pairs.append((on, off))
    if len(pairs) < 3:
        sys.exit(f"Need at least 3 on_/off_ pairs in '{folder}', found "
                 f"{len(pairs)}.")
    return pairs


# ------------------------------------------------------------- reporting
def paste_block(cal):
    note = "   # assumed, not measured" if cal["alpha_assumed"] else ""
    return (f"PX_PER_MM = {cal['PX_PER_MM']:.3f}\n"
            f"AXIS_COL = {cal['AXIS_COL']:.2f}\n"
            f"BASE_ROW = {cal['BASE_ROW']:.0f}\n"
            f"ALPHA_DEG = {cal['ALPHA_DEG']:.2f}{note}")


def print_warnings(cal):
    for w in cal["warnings"]:
        print("\n  WARNING: " + w)
    print("\n  No numbers to paste: fix the problem above and run again.")


def use_calibration(cal):
    """Same effect as pasting the numbers into scanner_config.py."""
    detect_line.PX_PER_MM = cal["PX_PER_MM"]
    detect_line.AXIS_COL = cal["AXIS_COL"]
    detect_line.BASE_ROW = cal["BASE_ROW"]
    detect_line.SIN_ALPHA = float(np.sin(np.radians(cal["ALPHA_DEG"])))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--cyl", nargs=3, action="append",
                   metavar=("FOLDER", "RADIUS_MM", "HEIGHT_MM"),
                   help="photos of one cylinder (repeat for the second one)")
    p.add_argument("--save-photos", action="store_true",
                   help="demo only: also write the fake photos to disk")
    p.add_argument("--strong-lamp", action="store_true",
                   help="demo only: a lamp bright enough to saturate the camera")
    p.add_argument("--angles", type=int, default=12,
                   help="demo only: photo pairs per cylinder (default 12)")
    a = p.parse_args()

    # ------------------------------------------------ real photos from disk
    if a.cyl:
        cyls = []
        for folder, radius, height in a.cyl:
            pairs = load_pairs(folder)
            print(f"  {folder}: {len(pairs)} photo pairs, radius {radius} mm, "
                  f"height {height} mm")
            cyls.append(measure_cylinder(pairs, float(radius), float(height)))
        cal = calibrate(cyls, cfg.ALPHA_DEG)
        print("\nMeasured calibration")
        if cal["warnings"]:
            print_warnings(cal)
            return
        print("\n" + paste_block(cal))
        if cal["alpha_assumed"]:
            print(f"\n  Only one cylinder (or radii too close): ALPHA_DEG was "
                  f"ASSUMED to be {cfg.ALPHA_DEG:g}. Use two cylinders with "
                  f"clearly different radii to measure it.")
        for c, off in zip(cyls, cal["off_center_mm"]):
            print(f"  cylinder radius {c['radius']:g} mm was about "
                  f"{off:.1f} mm off-center")
        print("\nCopy the lines above into scanner_config.py (replace the "
              "old ones).")
        return

    # --------------------------------------------------------------- demo
    # The camera numbers below are SECRET: calibrate() never sees them, only
    # the photos. They are printed at the end so you can check the result.
    secret = dict(axis_col=331.4, base_row=437, px_per_mm=5.7, alpha_deg=41.0)
    lamp_strength = 1.0 if a.strong_lamp else 0.5
    rng = np.random.default_rng(7)
    setups = [("A", 25.0, 50.0, 1.5, 0.7), ("B", 35.0, 45.0, 1.0, 2.1)]

    cyls = []
    for name, radius, height, offset, direction in setups:
        pairs = fake_photos(rng, secret, radius, height, offset, a.angles,
                            direction, lamp_strength)
        if a.save_photos:
            save_pairs(f"calib_{name}", pairs)
            print(f"  wrote {len(pairs) * 2} fake photos to calib_{name}/")
        cyls.append(measure_cylinder(pairs, radius, height))

    cal = calibrate(cyls, cfg.ALPHA_DEG)
    print(f"\nCalibration from 2 fake cylinders ({a.angles} photo pairs each, "
          f"{'very bright' if a.strong_lamp else 'normal'} lamp)\n")
    print("  number       secret true value   measured    error")
    rows = [("PX_PER_MM", secret["px_per_mm"], cal["PX_PER_MM"], "{:.3f}"),
            ("BASE_ROW", secret["base_row"], cal["BASE_ROW"], "{:.1f}"),
            ("AXIS_COL", secret["axis_col"], cal["AXIS_COL"], "{:.2f}"),
            ("ALPHA_DEG", secret["alpha_deg"], cal["ALPHA_DEG"], "{:.2f}")]
    for name, true, got, fmt in rows:
        print(f"  {name:<11}  {fmt.format(true):>17}  {fmt.format(got):>10}"
              f"  {got - true:+8.3f}")
    if cal["warnings"]:
        print_warnings(cal)
        return
    for (name, radius, _, offset, _), est in zip(setups, cal["off_center_mm"]):
        print(f"\n  cylinder {name}: really placed {offset:.1f} mm off-center, "
              f"estimated {est:.1f} mm")

    print("\nPaste into scanner_config.py:\n")
    print(paste_block(cal))

    # ---- check with a third cylinder, like you should do with real hardware
    check_r, check_h = 30.0, 50.0
    print(f"\nCheck: scan a third cylinder (radius {check_r:g} mm) and "
          f"measure it")
    for label, use_cal in (("default numbers", None), ("calibrated", cal)):
        saved = (detect_line.PX_PER_MM, detect_line.AXIS_COL,
                 detect_line.BASE_ROW, detect_line.SIN_ALPHA)
        if use_cal:
            use_calibration(use_cal)
        radii = []
        for i in range(8):
            theta = 2 * np.pi * i / 8
            kw = dict(radius_fn=make_cylinder(check_r), height=check_h,
                      lamp_strength=lamp_strength, **secret)
            on = render_frame(theta, True, rng, **kw)
            off = render_frame(theta, False, rng, **kw)
            r, _, _ = detect_line.detect_profile(on, off, 20, 1.0,
                                                 check_h - 1.0)
            radii.append(r.mean())
        (detect_line.PX_PER_MM, detect_line.AXIS_COL,
         detect_line.BASE_ROW, detect_line.SIN_ALPHA) = saved
        print(f"  with {label:<15}: measured radius "
              f"{np.mean(radii):6.2f} mm  (error {np.mean(radii) - check_r:+.2f} mm)")


if __name__ == "__main__":
    main()
