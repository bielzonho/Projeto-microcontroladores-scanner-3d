"""Test capture.py without any hardware.

  python test_capture.py              takes about 1 minute

WHAT THIS PROVES AND WHAT IT DOES NOT
  The Raspberry Pi parts of capture.py (camera, laser pin, stepper) are run
  here against STAND-INS for picamera2 and gpiozero that I wrote from their
  documentation. So this checks MY logic: the order of the calls, the laser
  being on for the 'on' photo and off for the 'off' photo, the stepper
  counting its steps and ending exactly where it started, the files that
  scan_folder.py then reads. It cannot show that the real libraries and the
  real hardware behave the way the stand-ins do.

Needs: capture.py, scan_folder.py, laser_sim.py, scanner_config.py,
detect_line.py, cleanup.py, mesh.py in the same folder.
"""
import math
import os
import sys
import tempfile
import types
import numpy as np
import cv2

import capture
from laser_sim import render_frame, object_radius, OBJECT_HEIGHT_MM
from scan_folder import scan_folder

capture.time.sleep = lambda s: None            # no waiting in the tests

N = 60
STATE = dict(laser=False, steps=0, spt=3200, camera_log=[])
LASER_PIN, STEP_PIN, DIR_PIN = 17, 20, 21
COIL_PINS = (5, 6, 13, 19)
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append(ok)
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"   ({detail})" if detail else ""))


# ----------------------------------------------------- stand-in for gpiozero
class StubDevice:
    levels = {}

    def __init__(self, pin, active_high=True, initial_value=False):
        self.pin, self.active_high, self.closed = pin, active_high, False
        self.laser_on_level = True
        self._set(bool(initial_value))

    def _set(self, logical_on):
        old = StubDevice.levels.get(self.pin)
        high = logical_on == self.active_high            # the real pin level
        StubDevice.levels[self.pin] = high
        if self.pin == LASER_PIN:
            STATE["laser"] = (high == STATE.get("laser_on_level", True))
        if self.pin in COIL_PINS and old != high:                    # a coil changed
            pattern = tuple(int(StubDevice.levels.get(p, False)) for p in COIL_PINS)
            if pattern in capture.HALF_STEP:
                idx = capture.HALF_STEP.index(pattern)
                prev = STATE.get("coil_idx")
                if prev is not None:
                    d = (idx - prev) % 8
                    if d in (1, 7):
                        STATE["steps"] += 1 if d == 1 else -1
                        STATE["pulses"] = STATE.get("pulses", 0) + 1
                    elif d != 0:
                        STATE["coil_errors"] = STATE.get("coil_errors", 0) + 1
                STATE["coil_idx"] = idx
            elif pattern == (0, 0, 0, 0):
                STATE["coil_idx"] = None
        if self.pin == STEP_PIN and old is True and high is False:   # falling edge
            forward = StubDevice.levels.get(DIR_PIN, False)
            STATE["steps"] += 1 if forward else -1
            STATE["pulses"] = STATE.get("pulses", 0) + 1

    def on(self):
        self._set(True)

    def off(self):
        self._set(False)

    def close(self):
        self.closed = True


# --------------------------------------------------- stand-in for picamera2
class StubPicamera2:
    """One frame of delay: a photo shows the state of the PREVIOUS call (my
    guess at a worst case; the real camera may behave differently)."""

    def __init__(self):
        self.rng = np.random.default_rng(1)
        self.prev = (False, 0.0)
        self.started = False
        self.controls = None

    def create_still_configuration(self, main=None, **kw):
        return {"main": main}

    def configure(self, config):
        STATE["camera_log"].append(("configure", config["main"]))

    def set_controls(self, c):
        STATE["camera_log"].append(("set_controls", dict(c), self.started))
        self.controls = c

    def start(self, *a, **k):
        self.started = True
        STATE["camera_log"].append(("start",))

    def _frame(self):
        shown = self.prev
        angle = 2 * math.pi * STATE["steps"] / STATE["spt"]
        self.prev = (STATE["laser"], angle)
        return render_frame(shown[1], shown[0], self.rng, radius_fn=STATE.get("radius_fn"))

    def capture_array(self, name="main"):
        STATE["camera_log"].append(("capture_array",))
        return self._frame()

    def capture_file(self, path, *a, **k):
        STATE["camera_log"].append(("capture_file", STATE["laser"]))
        cv2.imwrite(path, self._frame())

    def capture_metadata(self):
        return {"ExposureTime": self.controls["ExposureTime"],
                "AnalogueGain": self.controls["AnalogueGain"]}

    def stop(self):
        STATE["camera_log"].append(("stop",))

    def close(self):
        STATE["camera_log"].append(("close",))


sys.modules["gpiozero"] = types.SimpleNamespace(DigitalOutputDevice=StubDevice)
sys.modules["picamera2"] = types.SimpleNamespace(Picamera2=StubPicamera2)


def reset(laser_on_level=True):
    StubDevice.levels.clear()
    STATE.update(laser=False, steps=0, pulses=0, camera_log=[], spt=3200,
                 laser_on_level=laser_on_level, radius_fn=None, coil_idx=None,
                 coil_errors=0)


def radius_error(R, fn=object_radius, shift=0):
    """Radii against the true shape. shift=1 compares with the object turned
    by one photo step (a mirrored scan made with --mirror starts one step
    later; turning the object about its axis is not an error)."""
    n = len(R)
    zs = np.linspace(0.0, OBJECT_HEIGHT_MM, R.shape[1])
    truth = np.array([fn(2 * np.pi * (i + shift) / n, zs) for i in range(n)])
    return float(np.abs(R - truth).mean()), float(np.abs(R - truth).max())


def scan_dir(folder, **kw):
    # the fake photos have the vase 0..60 mm; give the range to isolate capture.py
    return scan_folder(folder, z_range=(0.0, 60.0), **kw)["R"]


if __name__ == "__main__":
    print("\n1. DRY RUN (fake camera, laser and platform), then scan_folder")
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "dry")
        capture.main(["--dry-run", "--out", out, "--photos", str(N)])
        files = sorted(os.listdir(out))
        check("120 photo files written", len(files) == 2 * N, f"{len(files)} files")
        check("names on_00.jpg / off_00.jpg ...",
              "on_00.jpg" in files and f"off_{N-1:02d}.jpg" in files)
        m, w = radius_error(scan_dir(out))
        check("scan_folder reads them, vase radius error small", m < 0.05,
              f"mean {m:.3f} mm, worst {w:.2f} mm (jpg files)")
        try:
            capture.main(["--dry-run", "--out", out, "--photos", str(N)])
            check("refuses to write into a folder that has photos", False)
        except SystemExit:
            check("refuses to write into a folder that has photos", True)
        try:
            capture.main(["--dry-run", "--out", os.path.join(tmp, "x"), "--photos", "2"])
            check("refuses --photos 2", False)
        except SystemExit:
            check("refuses --photos 2", True)

    print("\n2. STEPPER + PI CAMERA CODE (stand-ins), 3200 steps per turn, 60 photos")
    with tempfile.TemporaryDirectory() as tmp:
        reset()
        out = os.path.join(tmp, "step")
        capture.main(["--platform", "stepper", "--steps-per-turn", "3200",
                      "--out", out, "--photos", str(N), "--format", "png"])
        log = STATE["camera_log"]
        names = [e[0] for e in log]
        sc = [e for e in log if e[0] == "set_controls"][0]
        check("controls set AFTER configure and BEFORE start",
              names.index("configure") < names.index("set_controls") < names.index("start"))
        c = sc[1]
        check("auto exposure and auto white balance OFF, values given",
              c["AeEnable"] is False and c["AwbEnable"] is False
              and isinstance(c["ExposureTime"], int) and c["ExposureTime"] == 8333
              and isinstance(c["AnalogueGain"], float)
              and isinstance(c["ColourGains"], tuple), str(c))
        check("picture size passed as {\"size\": (W, H)}", log[0] == ("configure", {"size": (1640, 1232)}))
        n_arr = names.count("capture_array")
        check("2 frames discarded before every photo",
              n_arr == 2 * 2 * N and names.count("capture_file") == 2 * N,
              f"{n_arr} discards, {names.count('capture_file')} photos")
        lasers = [e[1] for e in log if e[0] == "capture_file"]
        check("laser ON for every on_ photo and OFF for every off_ photo",
              lasers == [True, False] * N)
        check("laser is off at the end", STATE["laser"] is False)
        check("camera stopped and closed", names[-2:] == ["stop", "close"])
        check("stepper: exactly 3200 pulses, net position back at the start",
              STATE["pulses"] == 3200 and STATE["steps"] == 3200,
              f"{STATE['pulses']} pulses, {STATE['steps']} net steps (a full turn)")
        R = scan_dir(out)
        m, w = radius_error(R)
        check("scan_folder on those photos: radius error small", m < 0.05,
              f"mean {m:.3f} mm, worst {w:.2f} mm")

    print("\n3. STEP ROUNDING (3200 steps / 60 photos = 53.33 steps)")
    reset()
    plat = capture.StepperPlatform(3200, STEP_PIN, DIR_PIN, step_delay=0, settle=0)
    worst = 0.0
    for k in range(N):
        plat.goto(k, N)
        worst = max(worst, abs(plat.pos - k * 3200 / N))
    plat.finish()
    check("every photo position within half a step of the exact angle",
          worst <= 0.5 + 1e-9, f"worst {worst:.2f} steps = {worst * 360 / 3200:.3f} degrees")
    check("back at exactly 0 after the last move", plat.pos == 0 and STATE["steps"] == 3200)

    print("\n4. --reverse AND --laser-active-low (an object that is NOT mirror-symmetric)")
    def lopsided(theta, z):                      # cos(3 theta - 1) is not symmetric
        return (20 + 8 * np.sin(2 * np.pi * z / 60.0)) * (1 + 0.15 * np.cos(3 * theta - 1.0))
    with tempfile.TemporaryDirectory() as tmp:
        reset(laser_on_level=False)                       # laser on when pin LOW
        STATE["radius_fn"] = lopsided
        out = os.path.join(tmp, "fwd")
        capture.main(["--platform", "stepper", "--steps-per-turn", "3200",
                      "--laser-active-low", "--out", out, "--photos", str(N)])
        check("--laser-active-low: laser on for on_ photos, off for off_",
              [e[1] for e in STATE["camera_log"] if e[0] == "capture_file"] == [True, False] * N)
        m, _ = radius_error(scan_dir(out), lopsided)
        check("normal direction: the scan matches the object", m < 0.05, f"mean {m:.3f} mm")
        reset()
        STATE["radius_fn"] = lopsided
        out = os.path.join(tmp, "rev")
        capture.main(["--platform", "stepper", "--steps-per-turn", "3200", "--reverse",
                      "--out", out, "--photos", str(N)])
        R = scan_dir(out)
        m0, _ = radius_error(R, lopsided)
        m1, _ = radius_error(R[::-1], lopsided, shift=1)    # what --mirror does
        check("--reverse gives a MIRRORED scan; --mirror in scan_folder.py fixes "
              "it (up to a turn of one photo step, which is only a rotation)",
              m1 < 0.05 < m0, f"error {m0:.2f} mm as is, {m1:.3f} mm with --mirror")

    print("\n5. --laser-test AND --turn-test")
    reset()
    calls = []
    orig_on = StubDevice.on
    StubDevice.on = lambda self: (calls.append(1) if self.pin == LASER_PIN else None, orig_on(self))[1]
    capture.main(["--laser-test"])
    StubDevice.on = orig_on
    check("--laser-test blinks 3 times and ends off", len(calls) == 3 and not STATE["laser"])
    reset()
    capture.main(["--platform", "stepper", "--steps-per-turn", "3200", "--turn-test"])
    check("--turn-test makes exactly one full turn", STATE["steps"] == 3200 and STATE["pulses"] == 3200)

    print("\n6. --check REPORT on fake photo pairs")
    expected = {"normal laser": "fine", "very weak laser": "NO LINE",
                "very bright lamp": "OFF"}
    for label, kw in [("normal laser", {}),
                      ("very weak laser", dict(laser_peak=25.0)),
                      ("very bright lamp", dict(lamp_strength=2.5))]:
        rng = np.random.default_rng(5)
        with tempfile.TemporaryDirectory() as tmp:
            on = render_frame(0.0, True, rng, **kw)
            off = render_frame(0.0, False, rng, **kw)
            cv2.imwrite(os.path.join(tmp, "on.png"), on)
            cv2.imwrite(os.path.join(tmp, "off.png"), off)
            print(f"\n  --- {label}")
            problems = capture.analyse_pair(os.path.join(tmp, "on.png"),
                                            os.path.join(tmp, "off.png"))
        want = expected[label]
        ok = (not problems) if want == "fine" else any(want in p for p in problems)
        check(f"report for '{label}'", ok, "no problem reported" if not problems
              else "; ".join(p.split(".")[0] for p in problems))

    print("\n7. TURNING THE PLATFORM BY HAND: what does an angle error cost?")
    print("   (60 fake photos, each at the nominal angle plus a random error)")
    print(f"   {'angle error (std)':<20}{'mean mm':>9}{'worst mm':>10}")
    for sigma in (0.0, 0.5, 1.0, 2.0):
        rng = np.random.default_rng(9)
        with tempfile.TemporaryDirectory() as tmp:
            jit = np.radians(rng.normal(0, sigma, N))
            for i in range(N):
                th = 2 * np.pi * i / N + jit[i]
                cv2.imwrite(os.path.join(tmp, f"on_{i:02d}.png"), render_frame(th, True, rng))
                cv2.imwrite(os.path.join(tmp, f"off_{i:02d}.png"), render_frame(th, False, rng))
            m, w = radius_error(scan_dir(tmp))
        print(f"   {sigma:>5.1f} degrees       {m:>9.3f}{w:>10.2f}")

    print("\n8. MANUAL PLATFORM (you turn it by hand): prompts and no-keyboard message")
    import builtins
    real_input = builtins.input
    reset()
    prompts = []
    builtins.input = lambda p="": prompts.append(p) or ""
    with tempfile.TemporaryDirectory() as tmp:
        capture.main(["--out", os.path.join(tmp, "man"), "--photos", "12"])
    check("one prompt per position (12)", len(prompts) == 12, f"{len(prompts)} prompts")
    check("first prompt asks for the START position, the next name the angle",
          "START" in prompts[0] and "30.0 degrees" in prompts[1])

    def no_keyboard(p=""):
        raise EOFError
    builtins.input = no_keyboard
    reset()
    try:
        with tempfile.TemporaryDirectory() as tmp:
            capture.main(["--out", os.path.join(tmp, "man"), "--photos", "12"])
        check("clear message when there is no keyboard", False)
    except SystemExit as e:
        check("clear message when there is no keyboard", "keyboard" in str(e))
    finally:
        builtins.input = real_input
    check("laser is off after the failed run", STATE["laser"] is False)

    print("\n9. ULN2003 + 28BYJ-48 (the project's motor), 4096 half-steps per turn")
    with tempfile.TemporaryDirectory() as tmp:
        reset()
        STATE["spt"] = 4096
        out = os.path.join(tmp, "uln")
        capture.main(["--platform", "uln2003", "--out", out, "--photos", str(N),
                      "--format", "png"])
        check("every coil change is exactly one step of the half-step sequence",
              STATE["coil_errors"] == 0 and STATE["pulses"] > 0,
              f"{STATE['coil_errors']} wrong changes")
        check("4096 half-steps, net position a full turn, back on phase 0",
              STATE["pulses"] == 4096 and STATE["steps"] == 4096,
              f"{STATE['pulses']} steps, net {STATE['steps']}")
        check("all four coils off at the end",
              not any(StubDevice.levels[p] for p in COIL_PINS))
        check("laser ON for every on_ photo and OFF for every off_ photo",
              [e[1] for e in STATE["camera_log"] if e[0] == "capture_file"] == [True, False] * N)
        m, w = radius_error(scan_dir(out))
        check("scan_folder on those photos: radius error small", m < 0.05,
              f"mean {m:.3f} mm, worst {w:.2f} mm")

        reset()
        STATE["spt"] = 4096
        STATE["radius_fn"] = lopsided
        out = os.path.join(tmp, "uln_rev")
        capture.main(["--platform", "uln2003", "--reverse", "--out", out,
                      "--photos", str(N)])
        R = scan_dir(out)
        m0, _ = radius_error(R, lopsided)
        m1, _ = radius_error(R[::-1], lopsided, shift=1)
        check("--reverse turns the other way (net -4096) and gives a mirrored scan",
              STATE["steps"] == -4096 and STATE["coil_errors"] == 0 and m1 < 0.05 < m0,
              f"net {STATE['steps']}, error {m0:.2f} mm as is, {m1:.3f} mm with --mirror")

    reset()
    STATE["spt"] = 4096
    capture.main(["--platform", "uln2003", "--turn-test"])
    check("--turn-test: exactly one full turn", STATE["steps"] == 4096 and STATE["pulses"] == 4096)

    reset()
    plat = capture.Uln2003Platform(4096, COIL_PINS, 0, 0, settle=0)
    worst = 0.0
    for k in range(N):
        plat.goto(k, N)
        worst = max(worst, abs(plat.pos - k * 4096 / N))
    plat.finish()
    check("4096 / 60 = 68.27 steps per photo: every position within half a step",
          worst <= 0.5 + 1e-9, f"worst {worst:.2f} steps = {worst * 360 / 4096:.3f} degrees")

    plat = capture.Uln2003Platform(4096, COIL_PINS, 0.0025, 0.007, settle=0)
    d = [plat._delay_for(i, 400) for i in range(400)]
    d68 = [plat._delay_for(i, 68) for i in range(68)]
    check("ramp: slow at both ends, full speed in the middle, symmetric",
          d[0] == 0.007 and d[200] == 0.0025 and abs(d[0] - d[-1]) < 1e-12
          and all(0.0025 - 1e-12 <= x <= 0.007 + 1e-12 for x in d + d68),
          f"one photo step (68 half-steps) = about {sum(d68):.2f} s of motor time")

    print(f"\n  {sum(RESULTS)} of {len(RESULTS)} checks passed")
    sys.exit(0 if all(RESULTS) else 1)
