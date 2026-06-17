#!/usr/bin/env pybricks-micropython
"""
WRO Future Engineers — Round 1 (SPIKE Prime, Pybricks).
  - Drive straight using gyro only
  - First corner determines turn direction — locked for entire run
  - Requires multiple consecutive lost readings before turning
  - motor_drive.hold() after arc so robot cannot coast during steer center
  - No creep forward on the last turn
  - Stops automatically after 3 laps (12 turns)
"""

from pybricks.hubs import PrimeHub
from pybricks.pupdevices import Motor, UltrasonicSensor
from pybricks.parameters import Port, Stop, Direction, Axis
from pybricks.tools import wait, StopWatch

# ─── Ports ───────────────────────────────────────────────────────────────────
PORT_STEER            = Port.F
PORT_DRIVE            = Port.E
PORT_ULTRASONIC_LEFT  = Port.C
PORT_ULTRASONIC_RIGHT = Port.D

# ─── Direction ───────────────────────────────────────────────────────────────
STEER_DIRECTION = Direction.COUNTERCLOCKWISE
DRIVE_DIRECTION = Direction.CLOCKWISE

# ─── Steering ────────────────────────────────────────────────────────────────
STEER_SPEED          = 500
STEER_CENTER         = 0
STEER_CENTER_LEFT    = -1
STEER_CENTER_RIGHT   =  1
STEER_MAX_LEFT       =  85
STEER_MAX_RIGHT      = -85

# ─── Drive ───────────────────────────────────────────────────────────────────
DRIVE_SPEED_STRAIGHT = 600
DRIVE_SPEED_TURN     = 250

# ─── Gyro ────────────────────────────────────────────────────────────────────
GYRO_KP       = 1.2
GYRO_DEADBAND = 1.5

# ─── Ultrasonic ──────────────────────────────────────────────────────────────
US_LOST_MM       = 1800
US_CONFIRM_COUNT = 4

# ─── Turn settings ───────────────────────────────────────────────────────────
TURN_DEGREES    = 75
STEER_LOCK_MS   = 200
BRAKE_MS        = 200
TURN_SETTLE_MS  = 100
CENTER_CREEP_MS = 300

# ─── Lap settings ────────────────────────────────────────────────────────────
TURNS_PER_LAP = 4
TOTAL_LAPS    = 3
TOTAL_TURNS   = TURNS_PER_LAP * TOTAL_LAPS   # = 12

# ─── Timing ──────────────────────────────────────────────────────────────────
STARTUP_DRIVE_MS      = 400
POST_TURN_COOLDOWN_MS = 600

# ─── Loop timing ─────────────────────────────────────────────────────────────
LOOP_DELAY = 10

# ─── Devices ─────────────────────────────────────────────────────────────────
hub         = PrimeHub()
motor_steer = Motor(PORT_STEER, STEER_DIRECTION)
motor_drive = Motor(PORT_DRIVE, DRIVE_DIRECTION)
us_left     = UltrasonicSensor(PORT_ULTRASONIC_LEFT)
us_right    = UltrasonicSensor(PORT_ULTRASONIC_RIGHT)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def clamp(v, lo, hi):
    return max(lo, min(hi, v))

def get_distance(sensor):
    try:
        d = sensor.distance()
        return d if d is not None else 9999
    except:
        return 9999

def active_center(turn_lock):
    if turn_lock == STEER_MAX_LEFT:
        return STEER_CENTER_LEFT
    elif turn_lock == STEER_MAX_RIGHT:
        return STEER_CENTER_RIGHT
    return STEER_CENTER

def steer(angle_deg):
    a = clamp(int(angle_deg), STEER_MAX_RIGHT, STEER_MAX_LEFT)
    motor_steer.run_target(STEER_SPEED, a, then=Stop.HOLD, wait=False)

def steer_wait(angle_deg):
    a = clamp(int(angle_deg), STEER_MAX_RIGHT, STEER_MAX_LEFT)
    motor_steer.run_target(STEER_SPEED, a, then=Stop.HOLD, wait=True)

def drive(speed):
    motor_drive.run(clamp(int(speed), -1000, 1000))

def stop_all():
    motor_drive.hold()
    motor_steer.hold()

def gyro_steer_correction(target_heading, turn_lock=None):
    err = hub.imu.heading() - target_heading
    while err >  180: err -= 360
    while err < -180: err += 360
    center = active_center(turn_lock)
    if abs(err) < GYRO_DEADBAND:
        return center
    return clamp(int(center + GYRO_KP * err), STEER_MAX_RIGHT, STEER_MAX_LEFT)

def snap_heading(raw_heading, turn_count, turn_lock):
    """
    Snaps target_heading to the nearest exact 90° multiple after each arc.
    Without this, a 2-3° error per turn compounds to 24-36° off by turn 12
    — enough to drift into the inner wall on lap 3.

    CCW (left turns):  expected headings are 0, -90, -180, -270, ...
    CW  (right turns): expected headings are 0,  90,  180,  270, ...

    If the raw IMU reading is within ±25° of expected, snap to exact.
    Otherwise round to nearest 90° — handles larger gyro drift gracefully.
    """
    if turn_lock == STEER_MAX_LEFT:
        expected = -90 * turn_count
    else:
        expected = 90 * turn_count
    if abs(raw_heading - expected) <= 25:
        return expected
    return round(raw_heading / 90) * 90

def blind_drive(duration_ms, target_heading, turn_lock=None):
    """Drive gyro-straight for duration_ms with detection completely off."""
    timer = StopWatch()
    while timer.time() < duration_ms:
        correction = gyro_steer_correction(target_heading, turn_lock)
        steer(correction)
        drive(DRIVE_SPEED_STRAIGHT)
        wait(LOOP_DELAY)

def check_wall_lost(turn_lock, lost_count_left, lost_count_right):
    left_lost  = get_distance(us_left)  >= US_LOST_MM
    right_lost = get_distance(us_right) >= US_LOST_MM

    lost_count_left  = (lost_count_left  + 1) if left_lost  else max(0, lost_count_left  - 1)
    lost_count_right = (lost_count_right + 1) if right_lost else max(0, lost_count_right - 1)

    left_confirmed  = lost_count_left  >= US_CONFIRM_COUNT
    right_confirmed = lost_count_right >= US_CONFIRM_COUNT

    if turn_lock is not None:
        if turn_lock == STEER_MAX_LEFT and left_confirmed:
            return STEER_MAX_LEFT, lost_count_left, lost_count_right
        elif turn_lock == STEER_MAX_RIGHT and right_confirmed:
            return STEER_MAX_RIGHT, lost_count_left, lost_count_right
        else:
            return None, lost_count_left, lost_count_right
    else:
        if left_confirmed and not right_confirmed:
            return STEER_MAX_LEFT, lost_count_left, lost_count_right
        elif right_confirmed and not left_confirmed:
            return STEER_MAX_RIGHT, lost_count_left, lost_count_right
        else:
            return None, lost_count_left, lost_count_right

def do_arc_turn(lock, turn_lock, is_last_turn):
    steer(lock)
    wait(STEER_LOCK_MS)

    start_rotation = hub.imu.rotation(Axis.Z)
    drive(DRIVE_SPEED_TURN)

    while abs(hub.imu.rotation(Axis.Z) - start_rotation) < TURN_DEGREES:
        wait(LOOP_DELAY)

    motor_drive.hold()
    wait(BRAKE_MS)

    steer_wait(active_center(turn_lock))
    wait(100)

    if not is_last_turn:
        drive(DRIVE_SPEED_STRAIGHT)
        wait(CENTER_CREEP_MS)
        wait(TURN_SETTLE_MS)

    return hub.imu.heading()


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    motor_steer.reset_angle(0)
    steer_wait(STEER_CENTER)
    hub.imu.reset_heading(0)
    wait(500)

    target_heading   = 0
    turn_count       = 0
    turn_lock        = None
    lost_count_left  = 0
    lost_count_right = 0

    hub.speaker.beep(frequency=800, duration=200)
    wait(300)

    blind_drive(STARTUP_DRIVE_MS, target_heading)

    while turn_count < TOTAL_TURNS:

        lock, lost_count_left, lost_count_right = check_wall_lost(
            turn_lock, lost_count_left, lost_count_right
        )

        if lock is not None:
            if turn_lock is None:
                turn_lock = lock
                hub.speaker.beep(frequency=600, duration=100)
                wait(80)
                hub.speaker.beep(frequency=900, duration=100)
                wait(80)

            lost_count_left  = 0
            lost_count_right = 0

            is_last_turn   = (turn_count + 1 == TOTAL_TURNS)
            raw_heading    = do_arc_turn(lock, turn_lock, is_last_turn)
            turn_count    += 1

            # Snap to exact 90° multiple — prevents per-turn drift accumulating
            target_heading = snap_heading(raw_heading, turn_count, turn_lock)

            if turn_count % TURNS_PER_LAP == 0:
                hub.speaker.beep(frequency=1000, duration=300)
                wait(100)

            if not is_last_turn:
                blind_drive(POST_TURN_COOLDOWN_MS, target_heading, turn_lock)
                lost_count_left  = 0
                lost_count_right = 0

        else:
            correction = gyro_steer_correction(target_heading, turn_lock)
            steer(correction)
            drive(DRIVE_SPEED_STRAIGHT)

        wait(LOOP_DELAY)

    # ── 3 laps done ───────────────────────────────────────────────────────────
    stop_all()
    hub.speaker.beep(frequency=1200, duration=200)
    wait(150)
    hub.speaker.beep(frequency=1200, duration=200)
    wait(150)
    hub.speaker.beep(frequency=1200, duration=200)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        stop_all()
        print("ERROR:", e)