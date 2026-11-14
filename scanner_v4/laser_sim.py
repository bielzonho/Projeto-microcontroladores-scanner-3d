"""Fake camera frames of a laser line on a turntable object.

Geometry (simple, side-on camera):
  * the laser plane contains the rotation axis (it cuts the object in half);
  * the camera looks at that cut from ALPHA_DEG to the side;
  * a surface point at radius r therefore appears r*sin(ALPHA) away from the
    axis column, so   column = AXIS_COL + r * PX_PER_MM * sin(ALPHA)
  * row gives the height:   z = (BASE_ROW - row) / PX_PER_MM

Not simulated: perspective from an elevated camera, lens distortion, parts of
the object hiding the line from the camera. Those come with the real camera.
"""
import numpy as np
import cv2
from scanner_config import (IMG_W, IMG_H, PX_PER_MM, AXIS_COL, BASE_ROW,
                            SIN_ALPHA)

OBJECT_HEIGHT_MM = 60.0


def object_radius(theta, z):
    """True radius (mm) of the fake object at body angle theta and height z.
    Same vase shape as fake_scan() in mesh.py."""
    r = 20 + 8 * np.sin(2 * np.pi * z / OBJECT_HEIGHT_MM)
    return r * (1 + 0.15 * np.cos(3 * theta))


def render_frame(theta, laser_on, rng, lamp=True, noise_sigma=3.0,
                 laser_peak=200.0, line_sigma=1.6, radius_fn=None,
                 height=None, axis_col=None, base_row=None,
                 px_per_mm=None, alpha_deg=None, lamp_strength=1.0,
                 warp=None):
    """Return a BGR uint8 image like the camera would give.

    theta       body angle (radians) that the laser plane is cutting right now
    laser_on    False gives the 'laser off' reference frame
    lamp        add a warm lamp glow (stray light that is NOT the laser)
    noise_sigma sensor noise
    laser_peak  how much red the laser adds at the middle of the line
    line_sigma  thickness of the line in pixels

    Optional (used by calibrate.py, leave them out for the normal vase):
    radius_fn   function (theta, z) -> radius in mm, instead of the vase
    height      object height in mm
    axis_col, base_row, px_per_mm, alpha_deg
                camera numbers to use instead of the ones in scanner_config.py
    lamp_strength  1.0 = the normal lamp, 0.5 = half as bright, ...
    warp        3x3 perspective matrix (used by plane_map.py). The laser line
                is first drawn as seen straight-on (alpha is ignored, the
                image is the laser plane itself at px_per_mm) and then bent
                by this matrix, like a camera looking at the plane at a tilt.
                The lamp glow and the noise are added after the bending.
    """
    h, w = IMG_H, IMG_W
    radius_fn = radius_fn or object_radius
    height_mm = OBJECT_HEIGHT_MM if height is None else height
    ax_col = AXIS_COL if axis_col is None else axis_col
    b_row = BASE_ROW if base_row is None else base_row
    ppm = PX_PER_MM if px_per_mm is None else px_per_mm
    sin_a = SIN_ALPHA if alpha_deg is None else np.sin(np.radians(alpha_deg))
    if warp is not None:
        sin_a = 1.0                       # we draw the laser plane itself
    img = np.zeros((h, w, 3), np.float32)
    img += [18, 22, 25]                                  # dark background (B,G,R)

    if lamp:
        yy, xx = np.mgrid[0:h, 0:w]
        glow = lamp_strength * np.exp(
            -(((xx - 470) ** 2 + (yy - 200) ** 2) / (2 * 90.0 ** 2)))
        img[..., 0] += 60 * glow
        img[..., 1] += 140 * glow
        img[..., 2] += 215 * glow                        # warm = mostly red

    if laser_on:
        rows = np.arange(h)
        z = (b_row - rows) / ppm
        on_object = (z >= 0) & (z <= height_mm)          # no object = no line
        rr = rows[on_object]
        r = radius_fn(theta, z[on_object])
        xc = ax_col + r * ppm * sin_a
        g = np.exp(-((np.arange(w)[None, :] - xc[:, None]) ** 2)
                   / (2 * line_sigma ** 2))
        target = img if warp is None else np.zeros_like(img)
        target[rr, :, 2] += laser_peak * g               # strong red
        target[rr, :, 1] += 0.35 * laser_peak * g        # a bit of green/blue
        target[rr, :, 0] += 0.35 * laser_peak * g
        if warp is not None:
            img += cv2.warpPerspective(target, np.asarray(warp, np.float64),
                                       (w, h), flags=cv2.INTER_LINEAR)

    img += rng.normal(0, noise_sigma, img.shape)
    return np.clip(img, 0, 255).astype(np.uint8)
