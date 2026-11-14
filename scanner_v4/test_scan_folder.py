"""Test scan_folder.py on fake objects of DIFFERENT heights.

  python test_scan_folder.py

The scanner program is not told the height of the objects. For each fake object
this writes a folder of photo pairs (in a temporary place), lets scan_folder
find the height range by itself, and compares the measured radii with the true
shape. Takes about 1 minute.

Needs: scanner_config.py, laser_sim.py, detect_line.py, cleanup.py,
scan_folder.py, plane_map.py, calibrate.py in the same folder.
"""
import os
import tempfile
import numpy as np
import cv2

from laser_sim import render_frame
from scan_folder import scan_folder
from plane_map import demo_map, PLANE_PX, save_map

N = 60


def bowl(theta, z):                      # short and wide, 2 bumps
    return (22 + 6 * np.sin(np.pi * z / 35.0)) * (1 + 0.10 * np.cos(2 * theta))


def column(theta, z):                    # tall and thin, 3 bumps
    return (15 + 5 * np.cos(2 * np.pi * z / 70.0)) * (
        1 + 0.12 * np.cos(3 * theta + 1.0))


def cup(theta, z):                       # medium, for the tilted camera
    return (18 + 7 * np.sin(2 * np.pi * z / 45.0)) * (1 + 0.08 * np.cos(4 * theta))


def write_photos(folder, fn, height, rng, **cam):
    os.makedirs(folder)
    for i in range(N):
        theta = 2 * np.pi * i / N
        kw = dict(radius_fn=fn, height=height, **cam)
        cv2.imwrite(os.path.join(folder, f"on_{i:02d}.png"),
                    render_frame(theta, True, rng, **kw))
        cv2.imwrite(os.path.join(folder, f"off_{i:02d}.png"),
                    render_frame(theta, False, rng, **kw))


def compare(name, folder, fn, height, H=None):
    res = scan_folder(folder, H=H)
    n = len(res["R"])
    truth = np.array([fn(2 * np.pi * i / n, res["zs"]) for i in range(n)])
    d = np.abs(res["R"] - truth)
    print(f"  {name:<28}{height:>7.1f}   {res['z_lo']:>5.1f} to {res['z_hi']:>5.1f}"
          f"{d.mean():>10.3f}{d.max():>9.2f}")
    return res["z_hi"] - res["z_lo"] - height


if __name__ == "__main__":
    rng = np.random.default_rng(3)
    errs = []
    print(f"\n  {'object':<28}{'true mm':>7}   {'height found':<13}"
          f"{'mean err':>10}{'worst':>9}")
    with tempfile.TemporaryDirectory() as tmp:
        for name, fn, height in [("short bowl", bowl, 35.0),
                                 ("tall column", column, 70.0)]:
            folder = os.path.join(tmp, name.replace(" ", "_"))
            write_photos(folder, fn, height, rng)
            errs.append(compare(name, folder, fn, height))

        tmap = demo_map(np.random.default_rng(11), lamp_strength=0.5)
        folder = os.path.join(tmp, "cup")
        write_photos(folder, cup, 45.0, rng, warp=tmap["warp"],
                     lamp_strength=0.5, **PLANE_PX)
        errs.append(compare("cup, tilted camera + map", folder, cup, 45.0,
                            H=tmap["H"]))
    print(f"\n  height found minus true height: "
          + ", ".join(f"{e:+.2f}" for e in errs) + " mm")
