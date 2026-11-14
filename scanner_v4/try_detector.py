"""Hands-on test of the laser-line detector.

  python try_detector.py                      default: vase seen at angle 0
  python try_detector.py --angle 60           same vase, turned 60 degrees
  python try_detector.py --noise 25           noisier camera
  python try_detector.py --no-lamp            no lamp glow in the room
  python try_detector.py --laser-peak 30      very weak laser
  python try_detector.py --axis-error 10      wrong calibration (axis 10 px off)

It prints a small table and saves  try_result.png  (open that picture).
"""
import argparse
import numpy as np
import matplotlib
matplotlib.use("Agg")                      # draw to a file, no window needed
import matplotlib.pyplot as plt

import detect_line
from scanner_config import AXIS_COL, PX_PER_MM, SIN_ALPHA
from laser_sim import render_frame, object_radius, OBJECT_HEIGHT_MM
from detect_line import detect_profile, laser_signal

p = argparse.ArgumentParser()
p.add_argument("--angle", type=float, default=0.0,
               help="platform angle in degrees (default 0)")
p.add_argument("--noise", type=float, default=3.0,
               help="camera noise (default 3)")
p.add_argument("--no-lamp", action="store_true", help="remove the lamp glow")
p.add_argument("--laser-peak", type=float, default=200.0,
               help="laser brightness (default 200)")
p.add_argument("--axis-error", type=float, default=0.0,
               help="pretend AXIS_COL was measured wrong by this many pixels")
p.add_argument("--points", type=int, default=30,
               help="points per slice (default 30)")
p.add_argument("--out", default="try_result.png")
a = p.parse_args()

rng = np.random.default_rng(1)
theta = np.radians(a.angle)
cam = dict(lamp=not a.no_lamp, noise_sigma=a.noise, laser_peak=a.laser_peak)
on = render_frame(theta, True, rng, **cam)
off = render_frame(theta, False, rng, **cam)
signal = laser_signal(on, off)

# pretend the calibration number is wrong (only the detector gets the wrong one)
detect_line.AXIS_COL = AXIS_COL + a.axis_error

one_pixel_mm = 1.0 / (PX_PER_MM * SIN_ALPHA)
found = True
try:
    r, z, cols = detect_profile(on, off, a.points, 0.0, OBJECT_HEIGHT_MM)
except RuntimeError:
    found = False
    cols = np.full(on.shape[0], np.nan)

print(f"angle {a.angle:g} deg | noise {a.noise:g} | lamp "
      f"{'off' if a.no_lamp else 'on'} | laser {a.laser_peak:g} | "
      f"axis error {a.axis_error:g} px")
if found:
    true_r = object_radius(theta, z)
    err = r - true_r
    print("\n  height z    true r    detected r    error")
    for k in range(0, len(z), 5):
        print(f"  {z[k]:6.1f} mm  {true_r[k]:6.2f} mm  {r[k]:8.2f} mm"
              f"  {err[k]:+7.3f} mm")
    mean = np.abs(err).mean()
    print(f"\n  mean error {mean:.3f} mm   (one image pixel = "
          f"{one_pixel_mm:.2f} mm)")
    verdict = ("GOOD: error is smaller than one pixel"
               if mean < one_pixel_mm else
               "BAD: error is bigger than one pixel")
    print("  " + verdict)
else:
    verdict = "NO LASER LINE FOUND in this frame"
    print("\n  " + verdict)

# ---------------------------------------------------------------- picture
fig, ax = plt.subplots(2, 3, figsize=(15, 9))
ax[0, 0].imshow(on[..., ::-1]);  ax[0, 0].set_title("1. laser ON")
ax[0, 1].imshow(off[..., ::-1]); ax[0, 1].set_title("2. laser OFF")
ax[0, 2].imshow(np.clip(signal * 4, 0, 255), cmap="gray", vmin=0, vmax=255)
ax[0, 2].set_title("3. ON minus OFF (x4 brightness)")
ax[1, 0].imshow(on[..., ::-1])
rows = np.where(~np.isnan(cols))[0]
ax[1, 0].scatter(cols[rows], rows, s=2, c="lime")
ax[1, 0].set_title("4. detected line (green dots)")
for k in range(4):
    ax.flat[k].axis("off")

if found:
    zz = np.linspace(0, OBJECT_HEIGHT_MM, 200)
    ax[1, 1].plot(object_radius(theta, zz), zz, "k-", label="true shape")
    ax[1, 1].plot(r, z, "o", color="tab:green", ms=4, label="detected")
    ax[1, 1].set_xlabel("radius r (mm)")
    ax[1, 1].set_ylabel("height z (mm)")
    ax[1, 1].set_title("5. result: black = truth, dots = detected")
    ax[1, 1].legend()
    ax[1, 1].grid(alpha=0.3)
else:
    ax[1, 1].axis("off")
    ax[1, 1].text(0.5, 0.5, "nothing detected", ha="center", va="center",
                  fontsize=16)

ax[1, 2].axis("off")
summary = verdict
if found:
    summary += f"\n\nmean error: {mean:.3f} mm\none pixel = {one_pixel_mm:.2f} mm"
ax[1, 2].text(0.02, 0.95, summary, va="top", fontsize=13)
fig.tight_layout()
fig.savefig(a.out, dpi=80)
print(f"\n  picture saved: {a.out}")
