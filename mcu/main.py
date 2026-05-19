from machine import Pin, PWM, I2C
import time
import ssd1306

# =========================
# SERVO
# =========================
class ServoController:
    def __init__(self, pin, min_angle=20, max_angle=160):
        self.pwm = PWM(Pin(pin))
        self.pwm.freq(50)

        self.min_angle = min_angle
        self.max_angle = max_angle

        self.min_us = 500
        self.max_us = 2500

        self.angle = 90
        self.set_angle(self.angle)

    def _us_to_duty(self, us):
        return int(us * 65535 // 20000)

    def set_angle(self, angle):
        angle = max(self.min_angle, min(self.max_angle, angle))
        self.angle = angle

        pulse = self.min_us + (self.max_us - self.min_us) * (angle / 180)
        self.pwm.duty_u16(self._us_to_duty(int(pulse)))

    def adjust(self, delta):
        self.set_angle(self.angle + delta)

    def get_height_cm(self):
        return 10 + (self.angle - self.min_angle) / (self.max_angle - self.min_angle) * 11


# =========================
# STEPPER
# =========================
class StepperController:
    HALF_STEP_SEQ = (
        (1,0,0,0),(1,1,0,0),(0,1,0,0),(0,1,1,0),
        (0,0,1,0),(0,0,1,1),(0,0,0,1),(1,0,0,1)
    )

    def __init__(self, pins):
        self.pins = [Pin(p, Pin.OUT) for p in pins]
        self.index = 0

        self.steps_per_rev = 4096

        # aceleração
        self.ramp_steps = 300
        self.min_delay = 0.004
        self.max_delay = 0.015

    def step(self):
        sequence = StepperController.HALF_STEP_SEQ[self.index]

        for pin, val in zip(self.pins, sequence):
            pin.value(val)

        self.index = (self.index + 1) % len(self.HALF_STEP_SEQ)

    def release(self):
        for p in self.pins:
            p.value(0)

    def get_delay(self, step, total_steps):
        if step < self.ramp_steps:
            p = step / self.ramp_steps
            return self.max_delay - (self.max_delay - self.min_delay) * p

        elif step > total_steps - self.ramp_steps:
            remaining = total_steps - step
            p = remaining / self.ramp_steps
            return self.max_delay - (self.max_delay - self.min_delay) * p

        else:
            return self.min_delay


# =========================
# DISPLAY
# =========================
class DisplayManager:
    def __init__(self):
        i2c = I2C(0, scl=Pin(1), sda=Pin(0), freq=400000)
        self.oled = ssd1306.SSD1306_I2C(128, 64, i2c)

    def show_idle(self, height):
        self.oled.fill(0)
        self.oled.text("Altura:", 0, 0)
        self.oled.text("{:.1f} cm".format(height), 0, 10)
        self.oled.text("Estado:", 0, 30)
        self.oled.text("Ajuste", 0, 40)
        self.oled.show()

    def show_scan(self, height, percent, remaining):
        self.oled.fill(0)
        self.oled.text("Altura:", 0, 0)
        self.oled.text("{:.1f} cm".format(height), 0, 10)
        self.oled.text("Scan: {}%".format(percent), 0, 25)
        self.oled.text("Tempo: {}s".format(int(remaining)), 0, 40)
        self.oled.show()

    def show_done(self):
        self.oled.fill(0)
        self.oled.text("Scan completo", 0, 25)
        self.oled.show()


# =========================
# LEDS
# =========================
class LEDController:
    def __init__(self, p1, p2):
        self.led1 = Pin(p1, Pin.OUT)
        self.led2 = Pin(p2, Pin.OUT)
        self.state = 0

    def blink(self):
        self.state ^= 1
        self.led1.value(self.state)
        self.led2.value(not self.state)

    def off(self):
        self.led1.value(0)
        self.led2.value(0)


# =========================
# BOTÕES
# =========================
class ButtonController:
    def __init__(self, up_pin, down_pin):
        self.up = Pin(up_pin, Pin.IN, Pin.PULL_UP)
        self.down = Pin(down_pin, Pin.IN, Pin.PULL_UP)

    def up_pressed(self):
        return self.up.value() == 0

    def down_pressed(self):
        return self.down.value() == 0

    def both_pressed(self):
        return self.up_pressed() and self.down_pressed()


# =========================
# CONTROLLER PRINCIPAL
# =========================
class ScannerController:
    def __init__(self):
        self.servo = ServoController(16)
        self.stepper = StepperController((6,7,8,9))
        self.display = DisplayManager()
        self.leds = LEDController(2,3)
        self.buttons = ButtonController(14,15)

        self.total_steps = self.stepper.steps_per_rev * 2

    def run(self):
        last_adjust = time.ticks_ms()
        both_start = None

        while True:
            now = time.ticks_ms()

            if not self.buttons.both_pressed():
                # ajuste de altura
                if time.ticks_diff(now, last_adjust) > 60:
                    last_adjust = now

                    if self.buttons.up_pressed():
                        self.servo.adjust(+2)

                    elif self.buttons.down_pressed():
                        self.servo.adjust(-2)

                both_start = None

            else:
                if both_start is None:
                    both_start = now

                elif time.ticks_diff(now, both_start) > 600:
                    self.scan()
                    while self.buttons.both_pressed():
                        time.sleep(0.05)
                    both_start = None

            self.display.show_idle(self.servo.get_height_cm())
            time.sleep(0.01)

    def scan(self):
        start = time.ticks_ms()
        last_blink = start

        for step in range(self.total_steps):

            self.stepper.step()

            delay = self.stepper.get_delay(step, self.total_steps)

            percent = int((step / self.total_steps) * 100)

            elapsed = time.ticks_diff(time.ticks_ms(), start) / 1000
            if step > 10:
                total_est = elapsed / (step / self.total_steps)
                remaining = total_est - elapsed
            else:
                remaining = 0

            if time.ticks_diff(time.ticks_ms(), last_blink) > 150:
                last_blink = time.ticks_ms()
                self.leds.blink()

            self.display.show_scan(
                self.servo.get_height_cm(),
                percent,
                remaining
            )

            time.sleep(delay)

        self.stepper.release()
        self.leds.off()
        self.display.show_done()
        time.sleep(2)


# =========================
# MAIN
# =========================
scanner = ScannerController()
scanner.run()
