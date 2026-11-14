"""Find the laser line in a camera frame and turn it into (radius, height).

Pipeline for one platform angle:
  1. laser_signal()      laser-on frame minus laser-off frame, red channel
  2. find_line_columns() in every image row, where is the line (sub-pixel)?
  3. reject_outliers()   drop isolated wrong detections
  4. columns_to_profile()  pixels -> millimetres
  5. resample()          fixed number of points, so every slice matches
"""
import numpy as np
import cv2
from scanner_config import PX_PER_MM, AXIS_COL, BASE_ROW, SIN_ALPHA


def laser_signal(frame_on, frame_off=None):
    """How much extra red the laser added (float image).
    With frame_off the ambient light cancels out; without it we keep the raw red
    channel (the 'article' way, which needs a hand-tuned threshold)."""
    red_on = frame_on[..., 2].astype(np.float32)
    if frame_off is not None:
        sig = np.clip(red_on - frame_off[..., 2].astype(np.float32), 0, None)
    else:
        sig = red_on
    return cv2.GaussianBlur(sig, (0, 0), 1.0)            # tame the noise


def find_line_columns(signal, min_signal=40.0, half_window=5):
    """For each row return the line's column (float), or NaN if not found.
    Uses the brightest pixel, then an intensity-weighted average around it, so
    the answer is finer than one pixel."""
    h, w = signal.shape
    cols = np.full(h, np.nan)
    for y in range(h):
        row = signal[y]
        x0 = int(np.argmax(row))
        peak = row[x0]
        if peak < min_signal:
            continue                                     # no laser in this row
        lo, hi = max(0, x0 - half_window), min(w, x0 + half_window + 1)
        weights = np.clip(row[lo:hi] - 0.5 * peak, 0, None)  # top half only
        if weights.sum() > 0:
            cols[y] = (np.arange(lo, hi) * weights).sum() / weights.sum()
    return cols


def reject_outliers(cols, window=7, max_dev=4.0):
    """Drop a detection that sits more than max_dev pixels away from the median
    of its neighbours."""
    out = cols.copy()
    for y in range(len(cols)):
        if np.isnan(cols[y]):
            continue
        near = cols[max(0, y - window):y + window + 1]
        near = near[~np.isnan(near)]
        if len(near) >= 3 and abs(cols[y] - np.median(near)) > max_dev:
            out[y] = np.nan
    return out


def columns_to_profile(cols):
    """Pixels -> millimetres. Returns (r, z) sorted from low to high."""
    rows = np.where(~np.isnan(cols))[0]
    z = (BASE_ROW - rows) / PX_PER_MM
    r = (cols[rows] - AXIS_COL) / (PX_PER_MM * SIN_ALPHA)
    order = np.argsort(z)
    return r[order], z[order]


def resample(r, z, n_points, z_min, z_max, max_hole_mm=None):
    """Pick n_points evenly spaced heights. Returns (r_values, z_values).

    Where the line was not found for a stretch of rows, the normal answer is a
    straight line across the hole (max_hole_mm=None, the default). With
    max_hole_mm=3.0, every height that is farther than max_hole_mm/2 from the
    nearest measured height gets NaN instead (a hole longer than 3 mm, or the
    ends of the line if they stop short of z_min / z_max). cleanup.py then
    repairs those points from the neighbouring photos."""
    zs = np.linspace(z_min, z_max, n_points)
    out = np.interp(zs, z, r)
    if max_hole_mm is not None:
        nearest = np.abs(zs[:, None] - np.asarray(z)[None, :]).min(axis=1)
        out[nearest > max_hole_mm / 2.0] = np.nan
    return out, zs


def detect_profile(frame_on, frame_off, n_points, z_min, z_max,
                   max_hole_mm=None):
    """Whole pipeline for one angle. Returns (r, z, cols)."""
    cols = reject_outliers(find_line_columns(laser_signal(frame_on, frame_off)))
    r, z = columns_to_profile(cols)
    if len(r) < 2:
        raise RuntimeError("no laser line found in this frame")
    r, z = resample(r, z, n_points, z_min, z_max, max_hole_mm)
    return r, z, cols
