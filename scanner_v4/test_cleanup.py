"""Test the clean-up (cleanup.py) on fake scans with fake problems.

  python test_cleanup.py            5 scans per case, takes about 2 minutes
  python test_cleanup.py --seeds 2  quicker

For every case it prints how far the scanned radii are from the TRUE radii of
the fake object (mean and worst, in mm), before and after the clean-up, and
saves  cleanup_demo.png  (error maps and one slice).

Needs: laser_sim.py, detect_line.py, scanner_config.py, glitches.py, cleanup.py.
"""
import argparse
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from laser_sim import render_frame, object_radius, OBJECT_HEIGHT_MM
from detect_line import detect_profile
import glitches
from cleanup import clean_slices

N_ANG, N_PTS = 60, 40
ZS = np.linspace(0.0, OBJECT_HEIGHT_MM, N_PTS)
TRUTH = np.array([object_radius(2 * np.pi * i / N_ANG, ZS) for i in range(N_ANG)])


def scan(seed, kinds=(), noise=3.0):
    """Fake scan. Returns (bridged, holes): two tables of measured radii made
    from the SAME photos. In `bridged` a hidden part of the line is crossed by
    a straight line (the old way); in `holes` it is left as NaN (what the
    clean-up wants). A photo pair with no line at all is NaN in both."""
    rng = np.random.default_rng(seed)
    grng = np.random.default_rng(100 + seed)
    B, H = [], []
    for i in range(N_ANG):
        theta = 2 * np.pi * i / N_ANG
        on = render_frame(theta, True, rng, noise_sigma=noise)
        off = render_frame(theta, False, rng, noise_sigma=noise)
        if kinds:
            on, _ = glitches.damage_pair(on, off, grng, kinds)
        try:
            b, _, _ = detect_profile(on, off, N_PTS, 0.0, OBJECT_HEIGHT_MM)
            h, _, _ = detect_profile(on, off, N_PTS, 0.0, OBJECT_HEIGHT_MM, 3.0)
        except RuntimeError:
            b = h = np.full(N_PTS, np.nan)
        B.append(b)
        H.append(h)
    return np.array(B), np.array(H)


def err(R):
    d = np.abs(R - TRUTH)
    return d.mean(), d.max()


def show(name, runs):
    """runs = list of (mean, worst) over the seeds."""
    m = np.mean([r[0] for r in runs])
    w = np.max([r[1] for r in runs])
    return f"{name:<34}{m:>8.3f}{w:>10.2f}"


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=5)
    ap.add_argument("--spike", type=float, default=2.0,
                    help="clean-up threshold in mm (default 2.0)")
    ap.add_argument("--out", default="cleanup_demo.png")
    a = ap.parse_args()
    seeds = range(1, a.seeds + 1)

    rows = {}                                  # name -> list of (mean, worst)

    def add(name, R):
        rows.setdefault(name, []).append(err(R))

    example = None
    for s in seeds:
        print(f"\r  scanning, seed {s} of {a.seeds} ...", end="", flush=True)
        B0, R0 = scan(s)                                      # no problems
        add("1  no problems, raw", B0)
        add("1  no problems, cleaned", clean_slices(R0, a.spike)[0])
        add("1  no problems, cleaned+smooth 1", clean_slices(R0, a.spike, smooth_passes=1)[0])

        B1, R1 = scan(s, ("reflection", "shadow"))
        add("2  reflections+shadows, raw", B1)
        C1, info1 = clean_slices(R1, a.spike)
        add("2  reflections+shadows, cleaned", C1)
        if example is None:
            example = (B1, C1)

        B2, R2 = scan(s, glitches.ALL_KINDS)                  # + dead photos
        C2, info2 = clean_slices(R2, a.spike)
        add("3  + dead photo pairs, cleaned", C2)
        rows.setdefault("_dead", []).append(int(np.isnan(R2).all(axis=1).sum()))

        B3, R3 = scan(s, (), noise=25.0)                      # very noisy camera
        add("4  noisy camera, raw", B3)
        add("4  noisy camera, cleaned", clean_slices(R3, a.spike)[0])
        add("4  noisy camera, cleaned+smooth 1", clean_slices(R3, a.spike, smooth_passes=1)[0])

        # rough surface: noise added straight onto the table (not from photos)
        R5 = TRUTH + np.random.default_rng(200 + s).normal(0, 0.3, TRUTH.shape)
        add("5  rough, 0.3 mm noise, raw", R5)
        for k in (1, 2):
            add(f"5  rough, 0.3 mm noise, smooth {k}",
                clean_slices(R5, a.spike, smooth_passes=k)[0])
    print()

    dead = rows.pop("_dead")
    print(f"\n{'case (radius error vs the truth)':<34}{'mean mm':>8}{'worst mm':>10}")
    for name, runs in rows.items():
        print("  " + show(name, runs))
    print(f"\n  (case 3 had {sum(dead)} dead photo pairs in {a.seeds} scans; "
          f"without --clean the scan stops at the first one)")

    # ---- picture: error maps before / after, and one slice ---------------------
    R1, C1 = example
    e_raw, e_cl = np.abs(R1 - TRUTH), np.abs(C1 - TRUTH)
    i_bad = int(np.argmax(e_raw.max(axis=1)))
    fig, ax = plt.subplots(1, 3, figsize=(14, 4.2))
    for k, (e, title) in enumerate([(e_raw, "error before clean-up (mm)"),
                                    (e_cl, "error after clean-up (mm)")]):
        im = ax[k].imshow(e.T, origin="lower", aspect="auto", vmin=0, vmax=4,
                          extent=[0, N_ANG, 0, OBJECT_HEIGHT_MM], cmap="magma")
        ax[k].set_title(title)
        ax[k].set_xlabel("photo number (angle)")
        ax[k].set_ylabel("height (mm)")
        fig.colorbar(im, ax=ax[k])
    ax[2].plot(TRUTH[i_bad], ZS, "k-", lw=2, label="true")
    ax[2].plot(R1[i_bad], ZS, "r.-", lw=1, label="measured")
    ax[2].plot(C1[i_bad], ZS, "g-", lw=1.5, label="cleaned")
    ax[2].set_title(f"photo {i_bad}: one slice")
    ax[2].set_xlabel("radius (mm)")
    ax[2].set_ylabel("height (mm)")
    ax[2].legend()
    fig.tight_layout()
    fig.savefig(a.out, dpi=110)
    print(f"  picture: {a.out}")
