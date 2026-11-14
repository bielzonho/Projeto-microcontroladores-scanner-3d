"""Clean up a scan BEFORE building the mesh: remove wrong points, fill holes,
optionally smooth.

The scan is a table of radii:  R[i][j] = radius (mm) at photo angle i and
height number j.  Row i is one photo pair, column j is one height.

The idea: the object is smooth from one photo angle to the next. A point that
sits far away from the same height in the neighbouring photos is almost
certainly a detection mistake (a reflection, a shadow, a lamp flicker).
Such points are thrown away and re-filled from the good neighbours.

  R_clean, info = clean_slices(R)

R may contain NaN (a photo pair where no line was found at all). Those are
filled too.

Limits (also in GUIDE.txt, Part H):
  * a real feature that changes by more than spike_mm between two photo angles
    (a thin rib, a sharp corner) looks like a mistake and gets smoothed away.
    More photos per turn (--angles) or a larger spike_mm helps.
  * if more than `window` photos in a row are bad at the same height, there is
    not enough good data around the hole; the result is only a guess and
    info["warnings"] says so.
"""
import warnings
import numpy as np


def _neighbour_median(R, window):
    """Median of the 2*window neighbours at the same height (angle wraps
    around: the last photo is next to the first)."""
    shifted = [np.roll(R, -k, axis=0)
               for k in range(-window, window + 1) if k != 0]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)   # all-NaN is fine here
        return np.nanmedian(np.stack(shifted), axis=0)


def _longest_run(flags):
    """Longest run of True in a circular 1-D boolean array."""
    n = len(flags)
    if flags.all():
        return n
    start = int(np.argmin(flags))                  # begin at a False
    best = run = 0
    for k in range(n):
        if flags[(start + k) % n]:
            run += 1
            best = max(best, run)
        else:
            run = 0
    return best


def clean_slices(R, spike_mm=2.0, window=3, grow=2, smooth_passes=0):
    """Return (R_clean, info).

    spike_mm      a point farther than this from the median of its neighbours
                  (same height, `window` photos on each side) is called wrong
    window        how many neighbouring photos on each side are looked at
    grow          also redo this many height steps above and below every wrong
                  point (the edges of a bad patch are usually a little off too)
    smooth_passes 0 = no smoothing. Each pass blends every point with its four
                  neighbours (weights 1-2-1) along angle and along height.
    """
    R = np.array(R, dtype=float)
    if R.ndim != 2:
        raise ValueError("R must be a table: photos x heights")
    n_ang, n_h = R.shape
    if n_ang < 2 * window + 1:
        raise ValueError(f"need at least {2 * window + 1} photos to clean up")

    # ---- 1) find the wrong points ---------------------------------------
    missing = np.isnan(R)
    ref = _neighbour_median(R, window)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        spike = np.abs(R - ref) > spike_mm               # NaN compares False
    bad = missing | spike
    seed = bad.copy()
    for s in range(1, grow + 1):                         # spread along height
        bad[:, s:] |= seed[:, :-s]
        bad[:, :-s] |= seed[:, s:]

    # ---- 2) refill them from the good photos at the same height ----------
    out = R.copy()
    out[bad] = np.nan
    idx = np.arange(n_ang)
    for j in range(n_h):
        ok = ~np.isnan(out[:, j])
        if ok.sum() >= 2 and (~ok).any():
            out[~ok, j] = np.interp(idx[~ok], idx[ok], out[ok, j], period=n_ang)
    for i in range(n_ang):                               # rare leftovers
        nan = np.isnan(out[i])
        if nan.any():
            if nan.all():
                raise ValueError("a whole photo has no usable data and its "
                                 "neighbours have none either")
            h = np.arange(n_h)
            out[i, nan] = np.interp(h[nan], h[~nan], out[i, ~nan])

    # ---- 3) optional smoothing ----------------------------------------------
    for _ in range(smooth_passes):
        out = 0.25 * np.roll(out, 1, 0) + 0.5 * out + 0.25 * np.roll(out, -1, 0)
        p = np.pad(out, ((0, 0), (1, 1)), mode="edge")
        out = 0.25 * p[:, :-2] + 0.5 * p[:, 1:-1] + 0.25 * p[:, 2:]

    # ---- report ---------------------------------------------------------------
    longest = max(_longest_run(bad[:, j]) for j in range(n_h))
    warns = []
    if longest > window:
        warns.append(f"{longest} photos in a row are bad at the same height "
                     f"(more than {window}); the repair there is only a guess")
    share = (spike & ~missing).sum() / max(1, (~missing).sum())
    if share > 0.02:
        warns.append(f"{100 * share:.1f} % of the points looked wrong. Either "
                     f"many photos are bad (reflections? a flickering lamp?) "
                     f"or the object has detail finer than the spacing between "
                     f"photos, and real shape is being removed. Try more photos "
                     f"per turn or a larger spike_mm, and look at the result.")
    info = dict(
        total=int(R.size),
        missing=int(missing.sum()),                  # no line found at all
        wrong=int((spike & ~missing).sum()),         # far from the neighbours
        redone=int(bad.sum()),                       # including the spread
        bad_photos=[int(i) for i in np.where(bad.all(axis=1))[0]],
        longest_run=int(longest),
        smooth_passes=smooth_passes,
        warnings=warns,
    )
    return out, info
