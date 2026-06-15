# =============================================================================
#  Raspberry Pi Pico – MicroPython Firmware
#  Components : Servo MG995 | Stepper 28BYJ-48 + ULN2003 | 2× LED
#               2× Push-button | SSD1306 OLED 128×64
#
#  WIRING GUIDE
#  ┌──────────────────────────────────────────────────────────────┐
#  │  Component        │  Pico GPIO                              │
#  ├───────────────────┼─────────────────────────────────────────┤
#  │  Servo signal     │  GP16  (PWM)                           │
#  │  Stepper IN1–IN4  │  GP2, GP3, GP4, GP5                   │
#  │  LED 1            │  GP6                                   │
#  │  LED 2            │  GP7                                   │
#  │  Button 1 (CW)    │  GP8  → GND  (internal pull-up)       │
#  │  Button 2 (CCW)   │  GP9  → GND  (internal pull-up)       │
#  │  OLED SDA         │  GP14 (I2C1)                          │
#  │  OLED SCL         │  GP15 (I2C1)                          │
#  │  All GND          │  Any GND pin                          │
#  │  Servo / Stepper  │  VBUS (5 V) or external 5 V supply    │
#  └──────────────────────────────────────────────────────────────┘
#
#  DEPENDENCIES
#  Upload ssd1306.py to the Pico before running.
#  Source: https://github.com/micropython/micropython-lib/tree/master/micropython/drivers/display/ssd1306
#
#  OPERATION
#  ① Button 1 held  → servo sweeps clockwise   (0 → 180°)
#  ② Button 2 held  → servo sweeps anti-clockwise (180 → 0°)
#  ③ Both held      → servo locks; stepper runs 2 rev with accel ramps
#  ④ Stepper active → LEDs blink alternately, OLED shows progress bar
#  ⑤ Stepper done   → OLED shows DONE screen; system halts
# =============================================================================

from machine import Pin, PWM, I2C
import utime
import ssd1306

# ─────────────────────────────────────────────────────────────────────────────
# PIN ASSIGNMENTS
# ─────────────────────────────────────────────────────────────────────────────
SERVO_PIN    = 16
STEP_PINS    = (2, 3, 4, 5)   # ULN2003 IN1 → IN4
LED1_PIN     = 6
LED2_PIN     = 7
BTN1_PIN     = 8               # Servo CW  / trigger when held with BTN2
BTN2_PIN     = 9               # Servo CCW / trigger when held with BTN1
OLED_SDA     = 14
OLED_SCL     = 15


# ─────────────────────────────────────────────────────────────────────────────
# SERVO  (TowerPro MG995)
#   50 Hz PWM, pulse 500 µs (0°) → 2500 µs (180°)
# ─────────────────────────────────────────────────────────────────────────────
_servo_pwm = PWM(Pin(SERVO_PIN))
_servo_pwm.freq(50)

_SERVO_MIN_US = 500
_SERVO_MAX_US = 2500
_PERIOD_US    = 20_000          # 1 / 50 Hz

SERVO_SPEED_DEG = 1.5           # degrees advanced per 20 ms main-loop tick

_servo_angle: float = 90.0      # current position, updated by move functions


def _angle_to_duty(angle: float) -> int:
    """Map 0–180 ° → 16-bit duty cycle for 50 Hz PWM."""
    angle = max(0.0, min(180.0, angle))
    pulse = _SERVO_MIN_US + (angle / 180.0) * (_SERVO_MAX_US - _SERVO_MIN_US)
    return int(pulse / _PERIOD_US * 65535)


def servo_set(angle: float) -> float:
    """Write angle to servo and return clamped angle."""
    global _servo_angle
    _servo_angle = max(0.0, min(180.0, angle))
    _servo_pwm.duty_u16(_angle_to_duty(_servo_angle))
    return _servo_angle


def servo_angle_pct() -> float:
    """Return current servo position as 0–100 %."""
    return _servo_angle / 180.0 * 100.0


# Initialise at centre
servo_set(90.0)


# ─────────────────────────────────────────────────────────────────────────────
# STEPPER  (28BYJ-48  +  ULN2003APG)
#   Half-step mode → 4096 half-steps per output-shaft revolution
#   Stride angle   : 5.625° / 64 gear ratio = 0.08789° per half-step
# ─────────────────────────────────────────────────────────────────────────────
_step_pins = [Pin(p, Pin.OUT) for p in STEP_PINS]

# 8-phase half-step sequence  (IN1, IN2, IN3, IN4)
_HALF_STEP = (
    (1, 0, 0, 0),
    (1, 1, 0, 0),
    (0, 1, 0, 0),
    (0, 1, 1, 0),
    (0, 0, 1, 0),
    (0, 0, 1, 1),
    (0, 0, 0, 1),
    (1, 0, 0, 1),
)

_step_idx: int = 0

STEPS_PER_REV  = 4096           # half-step, geared output shaft
REVOLUTIONS    = 2
TOTAL_STEPS    = STEPS_PER_REV * REVOLUTIONS   # 8192

ACCEL_STEPS    = 600            # ramp-up / ramp-down length (≈ 7.3 % each)
DELAY_MIN_US   = 1_100          # fastest inter-step delay  (high speed)
DELAY_MAX_US   = 7_000          # slowest inter-step delay  (start / stop)


def _stepper_apply() -> None:
    seq = _HALF_STEP[_step_idx]
    for i, pin in enumerate(_step_pins):
        pin.value(seq[i])


def _stepper_advance(direction: int = 1) -> None:
    global _step_idx
    _step_idx = (_step_idx + direction) % 8
    _stepper_apply()


def _stepper_off() -> None:
    """De-energise all coils (saves current, avoids heat)."""
    for pin in _step_pins:
        pin.value(0)


def _trapezoidal_delay(step: int) -> int:
    """
    Trapezoidal velocity profile.
    Linear acceleration → constant → linear deceleration.
    Returns inter-step delay in microseconds.
    """
    if step < ACCEL_STEPS:
        t = step / ACCEL_STEPS
    elif step > TOTAL_STEPS - ACCEL_STEPS:
        t = (TOTAL_STEPS - step) / ACCEL_STEPS
    else:
        t = 1.0
    # Clamp t
    t = max(0.0, min(1.0, t))
    return int(DELAY_MAX_US - (DELAY_MAX_US - DELAY_MIN_US) * t)


# ─────────────────────────────────────────────────────────────────────────────
# LEDs
# ─────────────────────────────────────────────────────────────────────────────
_led1 = Pin(LED1_PIN, Pin.OUT)
_led2 = Pin(LED2_PIN, Pin.OUT)

LED_BLINK_STEPS = 120           # toggle every N steps ≈ 0.13 s at full speed


def _leds_off() -> None:
    _led1.value(0)
    _led2.value(0)


# ─────────────────────────────────────────────────────────────────────────────
# BUTTONS  (active-LOW, internal pull-ups enabled)
# ─────────────────────────────────────────────────────────────────────────────
_btn1 = Pin(BTN1_PIN, Pin.IN, Pin.PULL_UP)
_btn2 = Pin(BTN2_PIN, Pin.IN, Pin.PULL_UP)


def read_buttons() -> tuple:
    """Return (b1_pressed, b2_pressed) as booleans."""
    return (not _btn1.value(), not _btn2.value())


# ─────────────────────────────────────────────────────────────────────────────
# OLED  (SSD1306, 128×64, I2C1)
# ─────────────────────────────────────────────────────────────────────────────
_i2c = I2C(1, sda=Pin(OLED_SDA), scl=Pin(OLED_SCL), freq=400_000)
_oled = ssd1306.SSD1306_I2C(128, 64, _i2c)

# Progress bar geometry
_BAR_X = 4
_BAR_Y = 46
_BAR_W = 120
_BAR_H = 12


def _draw_progress_bar(pct: float) -> None:
    """Draw a bordered progress bar filled to pct (0–100)."""
    _oled.rect(_BAR_X, _BAR_Y, _BAR_W, _BAR_H, 1)
    fill = int(max(0.0, min(100.0, pct)) / 100.0 * (_BAR_W - 2))
    if fill > 0:
        _oled.fill_rect(_BAR_X + 1, _BAR_Y + 1, fill, _BAR_H - 2, 1)


def _centred_x(text: str) -> int:
    """Return x offset to horizontally centre 8-px-wide text."""
    return max(0, (128 - len(text) * 8) // 2)


def oled_servo_screen(pct: float) -> None:
    """Display servo position percentage with progress bar."""
    _oled.fill(0)
    title = "SERVO POSITION"
    _oled.text(title, _centred_x(title), 2)
    _oled.hline(0, 13, 128, 1)
    label = f"{pct:.1f}%"
    _oled.text(label, _centred_x(label), 26)
    _draw_progress_bar(pct)
    _oled.show()


def oled_stepper_screen(pct: float) -> None:
    """Display stepper progress bar and percentage."""
    _oled.fill(0)
    title = "STEPPER RUNNING"
    _oled.text(title, _centred_x(title), 2)
    _oled.hline(0, 13, 128, 1)
    label = f"{pct:.1f}%"
    _oled.text(label, _centred_x(label), 26)
    _draw_progress_bar(pct)
    _oled.show()


def oled_done_screen() -> None:
    """Final DONE screen with full bar."""
    _oled.fill(0)
    # Completed bar at top
    title = "COMPLETE"
    _oled.text(title, _centred_x(title), 2)
    _oled.hline(0, 13, 128, 1)
    pct_label = "100.0%"
    _oled.text(pct_label, _centred_x(pct_label), 22)
    _draw_progress_bar(100.0)
    # DONE banner
    _oled.hline(0, 43, 128, 1)
    done = ">>> DONE <<<"
    _oled.text(done, _centred_x(done), 52)
    _oled.show()


# ─────────────────────────────────────────────────────────────────────────────
# STEPPER SEQUENCE  (blocking)
# ─────────────────────────────────────────────────────────────────────────────
def run_stepper_sequence() -> None:
    """
    Drive the stepper for TOTAL_STEPS with a trapezoidal velocity profile.
    Alternates LEDs and updates the OLED progress bar during the run.
    Blocking – must only be called from the state machine transition.
    """
    led_state     = False
    last_oled_pct = -1

    for s in range(TOTAL_STEPS):
        delay_us = _trapezoidal_delay(s)
        _stepper_advance(1)
        utime.sleep_us(delay_us)

        # ── LED blink (alternate to indicate activity) ──────────────────────
        if s % LED_BLINK_STEPS == 0:
            led_state = not led_state
            _led1.value(led_state)
            _led2.value(not led_state)

        # ── OLED update (once per integer % change to limit I2C traffic) ────
        pct_now = int(s / TOTAL_STEPS * 100)
        if pct_now != last_oled_pct:
            last_oled_pct = pct_now
            oled_stepper_screen(float(pct_now))

    # Wrap up
    _stepper_off()
    _leds_off()
    oled_done_screen()


# ─────────────────────────────────────────────────────────────────────────────
# MAIN STATE MACHINE
# ─────────────────────────────────────────────────────────────────────────────
_STATE_SERVO   = 0   # Waiting for button input, servo controllable
_STATE_STEPPER = 1   # Stepper running (transitions out automatically)
_STATE_DONE    = 2   # Sequence complete – idle

LOOP_PERIOD_MS = 20  # Main-loop cadence (controls servo sweep speed)

state = _STATE_SERVO

# Render initial screen
oled_servo_screen(servo_angle_pct())

print("=== Pico Firmware Ready ===")
print("BTN1 → servo CW | BTN2 → servo CCW | BOTH → lock + run stepper")

# ─────────────────────────────────────────────────────────────────────────────
while True:
    tick_start = utime.ticks_ms()

    # ── SERVO CONTROL STATE ──────────────────────────────────────────────────
    if state == _STATE_SERVO:
        b1, b2 = read_buttons()

        if b1 and b2:
            # ── Both pressed: lock servo, then run stepper ───────────────────
            print("Both buttons held → locking servo and starting stepper.")
            servo_set(_servo_angle)           # Freeze PWM at current angle
            state = _STATE_STEPPER
            run_stepper_sequence()            # Blocking; handles OLED & LEDs
            state = _STATE_DONE
            print("Stepper complete. System halted – reset Pico to restart.")

        elif b1:
            # ── Button 1: sweep clockwise (angle increasing) ─────────────────
            servo_set(_servo_angle + SERVO_SPEED_DEG)
            oled_servo_screen(servo_angle_pct())

        elif b2:
            # ── Button 2: sweep anti-clockwise (angle decreasing) ────────────
            servo_set(_servo_angle - SERVO_SPEED_DEG)
            oled_servo_screen(servo_angle_pct())

    # ── DONE STATE ───────────────────────────────────────────────────────────
    elif state == _STATE_DONE:
        # Display is already showing the DONE screen; nothing more to do.
        # The firmware idles here until the Pico is reset or power-cycled.
        utime.sleep_ms(500)
        continue

    # ── Pace the main loop to LOOP_PERIOD_MS ────────────────────────────────
    elapsed = utime.ticks_diff(utime.ticks_ms(), tick_start)
    sleep   = max(0, LOOP_PERIOD_MS - elapsed)
    utime.sleep_ms(sleep)
