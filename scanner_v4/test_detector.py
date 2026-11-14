"""Check the detector against the fake scanner.

  python test_detector.py

It "scans" the fake vase at 40 angles, detects the laser line in every frame,
compares the result with the true radius, and saves detector_demo.png.
"""
import numpy as np
import cv2
from scanner_config import IMG_H, IMG_W, SIN_ALPHA, PX_PER_MM
from laser_sim import render_frame, object_radius, OBJECT_HEIGHT_MM
from detect_line import (detect_profile, laser_signal, find_line_columns)

NUM_ANGLES = 40
NUM_POINTS = 30          # points per slice (heights)
rng = np.random.default_rng(1)


def stats(errors):
    e = np.abs(np.concatenate(errors))
    return e.mean(), np.percentile(e, 95), e.max()


# ---- 1) full pipeline: laser on + laser off ------------------------------
errors = []
for i in range(NUM_ANGLES):
    theta = 2 * np.pi * i / NUM_ANGLES
    on = render_frame(theta, True, rng)
    off = render_frame(theta, False, rng)
    r, z, cols = detect_profile(on, off, NUM_POINTS, 0.0, OBJECT_HEIGHT_MM)
    errors.append(r - object_radius(theta, z))
mean, p95, worst = stats(errors)
print(f"laser-on minus laser-off : mean error {mean:.3f} mm, "
      f"95% under {p95:.3f} mm, worst {worst:.3f} mm")

# ---- 2) the 'article' way: one frame, fixed red threshold -----------------
for thresh in (180, 235, 250):
    errors, failed = [], 0
    for i in range(NUM_ANGLES):
        theta = 2 * np.pi * i / NUM_ANGLES
        on = render_frame(theta, True, rng)
        cols = find_line_columns(laser_signal(on, None), min_signal=thresh)
        rows = np.where(~np.isnan(cols))[0]
        if len(rows) < 2:
            failed += 1
            continue
        z = (440 - rows) / PX_PER_MM
        r = (cols[rows] - 320) / (PX_PER_MM * SIN_ALPHA)
        ok = (z >= 0) & (z <= OBJECT_HEIGHT_MM)
        errors.append(r[ok] - object_radius(theta, z[ok]))
        # rows with a detection but no object = false detections
        errors.append(np.full(int((~ok).sum()), 30.0))
    mean, p95, worst = stats(errors)
    print(f"single frame, threshold {thresh}: mean error {mean:.3f} mm, "
          f"worst {worst:.1f} mm (30 = false detection on empty row)")

# ---- 3) picture for the guide ---------------------------------------------
theta = 0.0
on = render_frame(theta, True, rng)
off = render_frame(theta, False, rng)
r, z, cols = detect_profile(on, off, NUM_POINTS, 0.0, OBJECT_HEIGHT_MM)

sig = laser_signal(on, off)
sig_img = cv2.cvtColor(np.clip(sig * 4, 0, 255).astype(np.uint8),
                       cv2.COLOR_GRAY2BGR)
overlay = on.copy()
for y, x in enumerate(cols):
    if not np.isnan(x):
        cv2.circle(overlay, (int(round(x)), y), 1, (0, 255, 0), -1)


def label(img, text):
    img = img.copy()
    cv2.rectangle(img, (0, 0), (IMG_W, 26), (0, 0, 0), -1)
    cv2.putText(img, text, (8, 19), cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                (255, 255, 255), 1, cv2.LINE_AA)
    return img


grid = np.vstack([
    np.hstack([label(on, "1. laser ON"), label(off, "2. laser OFF")]),
    np.hstack([label(sig_img, "3. ON minus OFF (x4 brightness)"),
               label(overlay, "4. detected line (green dots)")]),
])
cv2.imwrite("detector_demo.png", grid)
print("saved detector_demo.png")
