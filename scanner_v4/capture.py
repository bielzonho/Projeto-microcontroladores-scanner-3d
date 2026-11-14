"""Take the photos of a scan: laser on / laser off at every platform position.

It writes the folder that scan_folder.py reads:  on_00.jpg off_00.jpg on_01.jpg ...

  python capture.py --dry-run                   try everything on your PC with a
                                                fake camera, laser and platform
  python capture.py --laser-test                blink the laser (check the wiring)
  python capture.py --turn-test --platform uln2003
                                                one full turn, no photos
  python capture.py --check                     ONE photo pair + a report: is the
                                                laser line bright enough, not
                                                saturated?
  python capture.py --out photos                the real scan, you turn the
                                                platform by hand (default)
  python capture.py --out photos --platform stepper --steps-per-turn 3200
                                                the real scan, a stepper motor
                                                with a STEP/DIR driver turns
                                                the platform
  python capture.py --out photos --platform uln2003
                                                the real scan, a 28BYJ-48 on a
                                                ULN2003 board (4 GPIO pins)
                                                turns the platform

IMPORTANT: the camera, laser and stepper parts could NOT be tested on real
hardware (written from the documentation of picamera2 and gpiozero). Test them
step by step as described in GUIDE.txt, Part I. --dry-run tests everything else.

Pins are BCM numbers (GPIO17 is physical pin 11). Defaults: laser 17, stepper
STEP 20, DIR 21. Needs on the Pi: picamera2, gpiozero (and opencv, numpy for
--check). --dry-run needs laser_sim.py, scanner_config.py, opencv, numpy.
"""
import argparse
import math
import os
import sys
import time


# ----------------------------------------------------------- fake hardware
class FakeLaser:
    def __init__(self, state):
        self.s = state

    def on(self):
        self.s["laser"] = True

    def off(self):
        self.s["laser"] = False

    def close(self):
        self.off()


class FakePlatform:
    def __init__(self, state):
        self.s = state

    def goto(self, k, n):
        self.s["angle"] = 2 * math.pi * k / n

    def finish(self):
        self.s["angle"] = 0.0

    def close(self):
        pass


class FakeCamera:
    def __init__(self, state):
        import numpy as np
        import cv2
        from laser_sim import render_frame
        self.s, self.cv2, self.render = state, cv2, render_frame
        self.rng = np.random.default_rng(1)

    def save(self, path):
        img = self.render(self.s["angle"], self.s["laser"], self.rng)
        self.cv2.imwrite(path, img)

    def info(self):
        return "fake camera (laser_sim.py), 640 x 480"

    def close(self):
        pass


# ----------------------------------------------------------- real hardware
def _need(module, hint):
    try:
        return __import__(module, fromlist=["x"])
    except ImportError:
        sys.exit(f"Could not import '{module}'. {hint}")


class GpioLaser:
    """Laser switched by a GPIO pin (through a transistor, see the guide)."""

    def __init__(self, pin, active_high=True):
        gz = _need("gpiozero", "On the Raspberry Pi: sudo apt install "
                               "python3-gpiozero")
        self.dev = gz.DigitalOutputDevice(pin, active_high=active_high,
                                          initial_value=False)

    def on(self):
        self.dev.on()

    def off(self):
        self.dev.off()

    def close(self):
        try:
            self.dev.off()
        finally:
            self.dev.close()


class ManualPlatform:
    """You turn the platform by hand to every position."""

    def __init__(self):
        pass

    def goto(self, k, n):
        try:
            if k == 0:
                input("  Platform at the START position (mark it!). "
                      "Press Enter to take photo 0 ... ")
            else:
                input(f"  Turn the platform to position {k} of {n} "
                      f"({360.0 * k / n:.1f} degrees from the start), then "
                      f"press Enter ... ")
        except EOFError:
            sys.exit("Manual mode needs a keyboard: run it in a terminal, not "
                     "from a script or a pipe.")

    def finish(self):
        print("  Done. (Turn the platform back to the start if you like.)")

    def close(self):
        pass


class _StepperBase:
    """What every stepper platform shares. Positions are rounded from the
    exact value (photo k of n is at step round(k * steps_per_turn / n)), so the
    small rounding errors never add up: after a full turn the platform is
    exactly back at the start."""

    def target(self, k, n):
        return round(k * self.spt / n)

    def goto(self, k, n):
        self._move(self.target(k, n) - self.pos)
        time.sleep(self.settle)                    # let the vibration die out

    def finish(self):
        self._move(self.spt - self.pos)            # complete the turn
        self.pos = 0


class StepperPlatform(_StepperBase):
    """Platform turned by a stepper motor through a STEP/DIR driver (A4988,
    DRV8825, TB6600 ...)."""

    def __init__(self, steps_per_turn, step_pin, dir_pin, enable_pin=None,
                 step_delay=0.002, reverse=False, settle=0.7):
        gz = _need("gpiozero", "On the Raspberry Pi: sudo apt install "
                               "python3-gpiozero")
        if not steps_per_turn or steps_per_turn < 8:
            sys.exit("--steps-per-turn is needed for the stepper (motor steps "
                     "x microstepping x gear ratio, for example 200 x 16 = "
                     "3200).")
        self.spt = int(steps_per_turn)
        self.step = gz.DigitalOutputDevice(step_pin, initial_value=False)
        self.dir = gz.DigitalOutputDevice(dir_pin, initial_value=False)
        self.enable = None
        if enable_pin is not None:                 # drivers enable with LOW
            self.enable = gz.DigitalOutputDevice(enable_pin, active_high=False,
                                                 initial_value=True)
        self.delay, self.reverse, self.settle = step_delay, reverse, settle
        self.pos = 0                               # steps from the start

    def _move(self, n):
        if n == 0:
            return
        forward = (n > 0) != self.reverse
        self.dir.on() if forward else self.dir.off()
        time.sleep(0.001)                          # DIR must settle first
        for _ in range(abs(n)):
            self.step.on()
            time.sleep(self.delay / 2)
            self.step.off()
            time.sleep(self.delay / 2)
        self.pos += n

    def close(self):
        for d in (self.step, self.dir, self.enable):
            if d is not None:
                d.close()


# Half-step sequence of the 28BYJ-48 (IN1, IN2, IN3, IN4): the same eight
# phases as in the scanner_v3/main.py of the project. Every phase differs from
# the next in exactly one coil.
HALF_STEP = ((1, 0, 0, 0), (1, 1, 0, 0), (0, 1, 0, 0), (0, 1, 1, 0),
             (0, 0, 1, 0), (0, 0, 1, 1), (0, 0, 0, 1), (1, 0, 0, 1))


class Uln2003Platform(_StepperBase):
    """28BYJ-48 stepper on a ULN2003 board, driven DIRECTLY by four GPIO pins
    (IN1 to IN4) with the half-step sequence above. steps_per_turn is the
    number of HALF-steps for one turn of the platform (4096 in the project's
    main.py; the real gear ratio may differ a little, check with --turn-test).
    Each move starts and ends slowly (a short ramp) so the motor does not lose
    steps. The coils stay on while the scan runs (holds the position) and are
    switched off at the end."""

    def __init__(self, steps_per_turn=4096, pins=(5, 6, 13, 19),
                 step_delay=0.0025, start_delay=0.007, reverse=False,
                 settle=0.7):
        gz = _need("gpiozero", "On the Raspberry Pi: sudo apt install "
                               "python3-gpiozero")
        if not steps_per_turn or steps_per_turn < 8:
            sys.exit("--steps-per-turn must be at least 8 (4096 half-steps "
                     "for one turn of a 28BYJ-48).")
        self.spt = int(steps_per_turn)
        self.coils = [gz.DigitalOutputDevice(p, initial_value=False)
                      for p in pins]
        self.delay, self.start_delay = step_delay, start_delay
        self.reverse, self.settle = reverse, settle
        self.idx, self.pos = 0, 0
        self._apply()                              # energise phase 0

    def _apply(self):
        for coil, v in zip(self.coils, HALF_STEP[self.idx]):
            coil.on() if v else coil.off()

    def _release(self):
        for coil in self.coils:
            coil.off()

    def _delay_for(self, i, total):
        """Seconds to wait after step i of a move of `total` steps: slow at
        both ends of the move, fast in the middle."""
        ramp = min(40, total // 2)
        edge = min(i, total - 1 - i)
        if ramp == 0 or edge >= ramp:
            return self.delay
        return self.start_delay - (self.start_delay - self.delay) * edge / ramp

    def _move(self, n):
        if n == 0:
            return
        direction = 1 if (n > 0) != self.reverse else -1
        total = abs(n)
        for i in range(total):
            self.idx = (self.idx + direction) % 8
            self._apply()
            time.sleep(self._delay_for(i, total))
        self.pos += n

    def finish(self):
        super().finish()
        self._release()                            # no heat when idle

    def close(self):
        try:
            self._release()
        finally:
            for coil in self.coils:
                coil.close()


class PiCamera:
    """Raspberry Pi camera through picamera2, exposure and white balance FIXED
    (they must not change between the laser-on and the laser-off photo)."""

    def __init__(self, size, exposure_us, gain, colour_gains, discard):
        p2 = _need("picamera2", "On the Raspberry Pi: sudo apt install "
                                "python3-picamera2 (and check the camera "
                                "cable, guide Part I).")
        self.cam = p2.Picamera2()
        config = self.cam.create_still_configuration({"size": tuple(size)})
        self.cam.configure(config)
        self.want = dict(AeEnable=False, AwbEnable=False,
                         ExposureTime=int(exposure_us),
                         AnalogueGain=float(gain),
                         ColourGains=tuple(colour_gains))
        self.cam.set_controls(self.want)           # after configure, before start
        self.cam.start()
        time.sleep(1.0)
        self.discard, self.size = discard, tuple(size)

    def save(self, path):
        for _ in range(self.discard):              # frames taken before the
            self.cam.capture_array("main")         # laser changed are thrown away
        self.cam.capture_file(path)

    def info(self):
        md = {}
        try:
            md = self.cam.capture_metadata()
        except Exception:                          # not essential
            pass
        got_e, got_g = md.get("ExposureTime"), md.get("AnalogueGain")
        text = (f"Pi camera {self.size[0]} x {self.size[1]}, exposure "
                f"asked {self.want['ExposureTime']} us, camera reports {got_e} us; "
                f"gain asked {self.want['AnalogueGain']:g}, camera reports "
                f"{got_g if got_g is None else round(got_g, 2)}")
        if got_e is not None and abs(got_e - self.want["ExposureTime"]) > 0.05 * \
                self.want["ExposureTime"] + 60:
            text += ("\n  WARNING: the camera is not using the exposure that was "
                     "asked for (it may round or limit it).")
        return text

    def close(self):
        try:
            self.cam.stop()
        finally:
            self.cam.close()


# ----------------------------------------------------------------- the work
def capture_pair(laser, camera, on_path, off_path, laser_settle):
    laser.on()
    time.sleep(laser_settle)
    camera.save(on_path)
    laser.off()
    time.sleep(laser_settle)
    camera.save(off_path)


def analyse_pair(on_path, off_path):
    """Report on one photo pair: is the laser line good enough for the
    detector? Returns the list of problems found (empty = looks fine). The
    limits are my judgement, not measured on real photos."""
    import numpy as np
    import cv2
    from detect_line import laser_signal, find_line_columns, reject_outliers
    on, off = cv2.imread(on_path), cv2.imread(off_path)
    h, w = on.shape[:2]
    sig = laser_signal(on, off)
    cols = reject_outliers(find_line_columns(sig))
    rows = np.where(~np.isnan(cols))[0]
    print(f"\n  photo size {w} x {h}")
    print(f"  rows with a laser line found: {100 * len(rows) / h:.0f} % of the "
          f"picture height")
    problems = []
    if len(rows) < 0.05 * h:
        problems.append("NO LINE FOUND. Is the laser on and pointing at the "
                        "object? Is the exposure far too short or too long? Is "
                        "the room too bright? Try --laser-test, then change "
                        "--exposure-us.")
    else:
        span = rows.max() - rows.min() + 1
        holes = 1 - len(rows) / span
        ci = np.clip(np.round(cols[rows]).astype(int), 0, w - 1)
        peak = float(np.median(sig[rows, ci]))
        print(f"  holes inside the line: {100 * holes:.0f} %")
        print(f"  line brightness (laser on minus off, median): {peak:.0f}   "
              f"(the detector needs 40 at least; aim for 100 or more)")
        if peak < 60:
            problems.append("The line is WEAK. Dim the room, or raise "
                            "--exposure-us (or --gain a little).")
        if holes > 0.10:
            problems.append(f"The line has holes ({100 * holes:.0f} % of its "
                            f"length). Parts of the object may hide it, or "
                            f"light may wash it out (see the next number).")
    off_full = float(np.mean(off[..., 2] >= 250))
    print(f"  laser-OFF photo, pixels already at full red (255): "
          f"{100 * off_full:.1f} %")
    if off_full > 0.01:
        problems.append("In the laser-OFF photo some pixels are already at full "
                        "red, so the laser cannot show up there (the difference "
                        "is zero, guide Part C). A lamp or window is too bright "
                        "or the exposure is too long: lower --exposure-us, dim "
                        "the room or cover the light.")
    print()
    if problems:
        for p in problems:
            print("  PROBLEM:", p)
    else:
        print("  Looks fine. Open both photos and look at them yourself too.")
    return problems


def build_parser():
    p = argparse.ArgumentParser(description="take the photo pairs of a scan")
    p.add_argument("--out", default="photos", help="folder for the photos "
                   "(default photos; check photos for --check)")
    p.add_argument("--photos", type=int, default=60,
                   help="positions in one full turn (default 60 = every 6 "
                        "degrees)")
    p.add_argument("--format", choices=["jpg", "png"], default="jpg",
                   help="file type (default jpg; png is slower to save)")
    p.add_argument("--overwrite", action="store_true",
                   help="allow writing into a folder that already has photos")
    g = p.add_argument_group("what to do instead of a scan")
    g.add_argument("--dry-run", action="store_true",
                   help="fake camera, laser and platform (no hardware needed)")
    g.add_argument("--laser-test", action="store_true",
                   help="blink the laser 3 times")
    g.add_argument("--turn-test", action="store_true",
                   help="one full turn of the stepper, no photos")
    g.add_argument("--check", action="store_true",
                   help="take one photo pair and report on it")
    h = p.add_argument_group("platform")
    h.add_argument("--platform", choices=["manual", "stepper", "uln2003"],
                   default="manual",
                   help="manual: you turn it; stepper: STEP/DIR driver; "
                        "uln2003: 28BYJ-48 on a ULN2003 board")
    h.add_argument("--steps-per-turn", type=int,
                   help="stepper: steps for one full turn of the PLATFORM "
                        "(uln2003: half-steps, default 4096)")
    h.add_argument("--coil-pins", type=int, nargs=4, default=[5, 6, 13, 19],
                   metavar=("IN1", "IN2", "IN3", "IN4"),
                   help="uln2003: GPIO (BCM) pins on IN1..IN4 "
                        "(default 5 6 13 19)")
    h.add_argument("--step-pin", type=int, default=20)
    h.add_argument("--dir-pin", type=int, default=21)
    h.add_argument("--enable-pin", type=int, default=None)
    h.add_argument("--step-delay", type=float, default=None,
                   help="seconds per step (default 0.002 for stepper, 0.0025 "
                        "for uln2003; slower is safer)")
    h.add_argument("--reverse", action="store_true",
                   help="turn the other way")
    h.add_argument("--settle", type=float, default=0.7,
                   help="seconds to wait after the platform moved")
    c = p.add_argument_group("laser")
    c.add_argument("--laser-pin", type=int, default=17)
    c.add_argument("--laser-active-low", action="store_true",
                   help="the laser switches on when the pin goes LOW")
    c.add_argument("--laser-settle", type=float, default=0.3,
                   help="seconds to wait after switching the laser")
    m = p.add_argument_group("camera")
    m.add_argument("--size", type=int, nargs=2, default=[1640, 1232],
                   metavar=("W", "H"), help="picture size (default 1640 1232)")
    m.add_argument("--exposure-us", type=int, default=8333,
                   help="exposure in microseconds (default 8333 = 1/120 s, "
                        "which averages out the flicker of lamps on 60 Hz mains)")
    m.add_argument("--gain", type=float, default=1.0)
    m.add_argument("--colour-gains", type=float, nargs=2, default=[1.0, 1.0],
                   metavar=("RED", "BLUE"))
    m.add_argument("--discard", type=int, default=2,
                   help="frames thrown away before every photo (default 2)")
    return p


def existing_photos(folder):
    if not os.path.isdir(folder):
        return []
    return [f for f in os.listdir(folder)
            if f.lower().startswith(("on_", "off_"))]


def main(argv=None):
    a = build_parser().parse_args(argv)
    if a.photos < 3:
        sys.exit("--photos must be at least 3 (60 is a good value).")

    # ---- put the hardware together ----------------------------------------
    state = {"laser": False, "angle": 0.0}
    if a.dry_run:
        laser, platform = FakeLaser(state), FakePlatform(state)
        camera = FakeCamera(state)
        a.settle = a.laser_settle = 0.0
    else:
        laser = GpioLaser(a.laser_pin, not a.laser_active_low)
        platform = None
        camera = None
    try:
        if a.laser_test:
            print("  Laser test: 3 blinks (1 s on, 1 s off). Do not look into "
                  "the beam.")
            for _ in range(3):
                laser.on()
                time.sleep(1.0)
                laser.off()
                time.sleep(1.0)
            print("  Done. Did it blink three times?")
            return
        if not a.dry_run:
            if a.platform == "stepper":
                platform = StepperPlatform(
                    a.steps_per_turn, a.step_pin, a.dir_pin, a.enable_pin,
                    0.002 if a.step_delay is None else a.step_delay,
                    a.reverse, a.settle)
            elif a.platform == "uln2003":
                platform = Uln2003Platform(
                    a.steps_per_turn or 4096, a.coil_pins,
                    0.0025 if a.step_delay is None else a.step_delay,
                    reverse=a.reverse, settle=a.settle)
            else:
                platform = ManualPlatform()
        if a.turn_test:
            if a.dry_run or a.platform not in ("stepper", "uln2003"):
                sys.exit("--turn-test needs --platform stepper or uln2003.")
            print("  Mark the platform and a fixed point next to it. "
                  "One full turn starts in 3 seconds ...")
            time.sleep(3)
            platform.goto(0, 1)
            platform.finish()
            print("  Done. Is the mark exactly back where it started? If it "
                  "turned too little or too much, change --steps-per-turn.")
            return
        if not a.dry_run:
            camera = PiCamera(a.size, a.exposure_us, a.gain, a.colour_gains,
                              a.discard)

        # ---- one pair and a report ------------------------------------------
        out = a.out if a.out != "photos" or not a.check else "check_photos"
        ext = a.format
        if a.check:
            os.makedirs(out, exist_ok=True)
            print("  " + camera.info())
            on_p = os.path.join(out, f"on_00.{ext}")
            off_p = os.path.join(out, f"off_00.{ext}")
            capture_pair(laser, camera, on_p, off_p, a.laser_settle)
            print(f"  wrote {on_p} and {off_p}")
            analyse_pair(on_p, off_p)
            return

        # ---- the scan ---------------------------------------------------------
        if existing_photos(out) and not a.overwrite:
            sys.exit(f"The folder '{out}' already has photos. Use another "
                     f"--out name, or --overwrite.")
        os.makedirs(out, exist_ok=True)
        print("  " + camera.info())
        print(f"  {a.photos} positions, one every {360.0 / a.photos:.2f} "
              f"degrees -> folder '{out}'")
        start = time.time()
        done = 0
        try:
            for k in range(a.photos):
                platform.goto(k, a.photos)
                capture_pair(laser, camera,
                             os.path.join(out, f"on_{k:02d}.{ext}"),
                             os.path.join(out, f"off_{k:02d}.{ext}"),
                             a.laser_settle)
                done += 1
                print(f"\r  photo pair {done} of {a.photos}", end="",
                      flush=True)
            print()
            platform.finish()
        except KeyboardInterrupt:
            print(f"\n  Stopped by you after {done} pairs. A scan needs a full "
                  f"turn: take the photos again.")
            return
        secs = time.time() - start
        print(f"  {done} photo pairs in {int(secs // 60)} min {secs % 60:.0f} s")
        print(f"  Next:  python scan_folder.py {out}"
              + ("   (with --map camera_map.json if you use Part F)"))
    finally:
        for dev in (camera, platform, laser):
            if dev is not None:
                try:
                    dev.close()
                except Exception:
                    pass


if __name__ == "__main__":
    main()
