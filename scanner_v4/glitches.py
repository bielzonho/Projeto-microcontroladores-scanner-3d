"""Fake problems, for testing the clean-up step (cleanup.py).

Real photos go wrong in a few typical ways. damage_pair() adds them to a fake
laser-on photo:

  reflection  a bright spot that is NOT the laser line (the laser bouncing off
              a shiny part of the object or the platform). In the rows where
              the spot is brighter than the line, the detector follows the spot.
  shadow      part of the line is hidden (the object blocks the laser or the
              camera's view). The detector finds nothing in those rows and
              draws a straight line across the hole.
  dead        the whole photo pair is useless (the laser did not switch on,
              someone walked past, the lamp flickered). No line at all.

The chances are fixed: about 12 % of photo pairs get a reflection, 12 % get a
shadow, 3 % are dead.
"""
import numpy as np
from detect_line import laser_signal, find_line_columns

ALL_KINDS = ("reflection", "shadow", "dead")
CHANCE = dict(reflection=0.12, shadow=0.12, dead=0.03)


def damage_pair(on, off, rng, kinds=ALL_KINDS):
    """Return (damaged_on_photo, list_of_kinds_applied). The laser-off photo is
    never changed. The random numbers are always drawn, so changing `kinds`
    does not change which photos are picked."""
    roll = rng.random(3)             # reflection, shadow, dead
    u = rng.random(6)                # sizes and places
    cols = find_line_columns(laser_signal(on, off))
    rows = np.where(~np.isnan(cols))[0]
    if len(rows) < 20:
        return on, []                # nothing to damage

    if "dead" in kinds and roll[2] < CHANCE["dead"]:
        return off.copy(), ["dead"]

    h, w = on.shape[:2]
    out = on.astype(np.float32)
    applied = []

    if "reflection" in kinds and roll[0] < CHANCE["reflection"]:
        cy = rows[0] + u[0] * (rows[-1] - rows[0])
        side = 1.0 if u[1] < 0.5 else -1.0
        cx = np.nanmedian(cols) + side * (25 + 45 * u[2])
        sy, sx = 8 + 8 * u[3], 4.0
        yy, xx = np.mgrid[0:h, 0:w]
        g = np.exp(-0.5 * (((yy - cy) / sy) ** 2 + ((xx - cx) / sx) ** 2))
        out[..., 2] += 380 * g
        out[..., 1] += 130 * g
        out[..., 0] += 130 * g
        applied.append("reflection")

    if "shadow" in kinds and roll[1] < CHANCE["shadow"]:
        span = int(15 + 95 * u[4])                        # 15 to 110 pixel rows
        room = max(1, rows[-1] - rows[0] - span)
        y0 = int(rows[0] + u[5] * room)
        out[y0:y0 + span] = off[y0:y0 + span]             # laser light gone
        applied.append("shadow")

    return np.clip(out, 0, 255).astype(np.uint8), applied
