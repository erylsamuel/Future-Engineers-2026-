#!/usr/bin/env pybricks-micropython
"""
WRO Future Engineers — Round 1 (SPIKE Prime, Pybricks).
  Combined: wall-following (Code 1) + obstacle avoidance (Code 2).

  Wall-following (Code 1 — UNCHANGED):
  - Drive straight using gyro only
  - First corner determines turn direction — locked for entire run
  - Requires multiple consecutive lost readings before turning
  - motor_drive.hold() after arc so robot cannot coast during steer center
  - No creep forward on the last turn
  - Stops automatically after 3 laps (12 turns)

  Obstacle avoidance (Code 2 — UNCHANGED):
  - PUPRemoteHub on Port.B reads color sensor via pupremote
  - color 1 → steer left (green light); color 2 → steer right (red light)
  - 5-phase avoidance: follow straight, steer, hold until clear,
    counter-steer, re-center
  - Avoidance only fires during straight-driving (never mid-turn)
  - Ultrasonic wall detection is LOCKED (ignored) for the entire duration of
    obstacle avoidance so the obstacle sides cannot trigger a false corner turn

  FIX 1 — pre-turn creep forward:
  - When a corner is detected (wall lost), the robot now drives straight for
    PRE_TURN_CREEP_MS before starting the arc turn.

  FIX 2 — post-turn creep forward (interruptible):
  - After every arc turn the robot drives straight for POST_TURN_CREEP_MS
    so it gets close enough to the next wall for the ultrasonic to detect.

  FIX 3 — separate obstacle avoidance counter-steer center:
  - avoid_obstacle() Phase 5 always re-centers to hard 0 (AVOID_RE_CENTER).

  FIX 4 — Phase 2/3 steer logic (over-turn fix):
  - STEER_MS now runs FIRST as a minimum guaranteed hold so the robot clears
    the obstacle on the first encounter (prevents snapping back too early).
  - After STEER_MS, the color-clear loop still runs to confirm the obstacle
    is truly gone before counter-steering — this prevents over-turning on
    subsequent obstacles where the robot arrives at a different angle and
    may still see the color after the timed period ends.
  - Together these two steps handle both cases: too-early return (obstacle 1)
    and too-late return / over-swing (obstacle 2+).
"""

from pybricks.hubs import PrimeHub
from pybricks.pupdevices import Motor, UltrasonicSensor
from pybricks.parameters import Port, Stop, Direction, Axis, Color
from pybricks.tools import wait, StopWatch
from pupremote_hub import PUPRemoteHub

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
DRIVE_SPEED_STRAIGHT = 100
DRIVE_SPEED_TURN     = 100

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
STARTUP_DRIVE_MS = 400

# ─── Loop timing ─────────────────────────────────────────────────────────────
LOOP_DELAY = 10

# ─── Obstacle avoidance ───────────────────────────────────────────────────────
FOLLOW_TIME_MS  = 50
STEER_ANGLE     = 30

# Minimum time (ms) to hold the avoidance steer before the color-clear check.
# Prevents snapping back too early on obstacle 1 (robot hasn't passed it yet).
# Lower if robot swings out too wide on obstacle 1.
# Upper bound is naturally capped by the color-clear loop that follows.
STEER_MS        = 450

COUNTER_ANGLE   = 25   # counter-steer angle — obstacle avoidance ONLY
COUNTER_MS      = 450  # how long to hold counter-steer

# Re-center target after obstacle avoidance — always hard 0.
# Must NOT use active_center(): the ±1 offsets are wall-following compensation
# only.  gyro_steer_correction() re-applies active_center on the next tick.
AVOID_RE_CENTER = 0

# How long (ms) to keep driving forward after counter-steer, before re-centering.
# Moves the robot clear of the obstacle before the steer snaps back to 0.
# Start at 300 ms. Raise if robot still clips the pillar on re-center.
# Lower if it overshoots toward the outer wall.
POST_AVOID_FORWARD_MS = 300

STABLE_NEEDED   = 2

# ─── Pre-turn creep (FIX 1) ──────────────────────────────────────────────────
PRE_TURN_CREEP_MS = 300

# ─── Post-turn creep (FIX 2) ─────────────────────────────────────────────────
POST_TURN_CREEP_MS = 800

# ─── Devices ─────────────────────────────────────────────────────────────────
hub         = PrimeHub()
motor_steer = Motor(PORT_STEER, STEER_DIRECTION)
motor_drive = Motor(PORT_DRIVE, DRIVE_DIRECTION)
us_left     = UltrasonicSensor(PORT_ULTRASONIC_LEFT)
us_right    = UltrasonicSensor(PORT_ULTRASONIC_RIGHT)

p = PUPRemoteHub(Port.B)
p.add_channel('hl', to_hub_fmt='b')


# ─── Helpers (Code 1 — UNCHANGED) ────────────────────────────────────────────

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

def post_turn_drive(duration_ms, target_heading, turn_lock,
                    stable_color_ref, stable_count_ref):
    stable_color = stable_color_ref
    stable_count = stable_count_ref
    timer = StopWatch()
    while timer.time() < duration_ms:
        correction = gyro_steer_correction(target_heading, turn_lock)
        steer(correction)
        drive(DRIVE_SPEED_STRAIGHT)

        color_id = get_color()
        if color_id == stable_color:
            stable_count += 1
        else:
            stable_color = color_id
            stable_count = 1

        if stable_color in (1, 2) and stable_count >= STABLE_NEEDED:
            return stable_color, stable_color, stable_count

        wait(LOOP_DELAY)

    return 0, stable_color, stable_count


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


# ─── Helpers (Code 2) ────────────────────────────────────────────────────────

def get_color():
    try:
        result = p.call('hl')
        if isinstance(result, (tuple, list)) and len(result) > 0:
            return result[0]
        elif isinstance(result, int):
            return result
    except:
        pass
    return 0

def avoid_obstacle(color):
    if color == 1:
        steer_angle = -STEER_ANGLE
        counter     = COUNTER_ANGLE
        hub.light.on(Color.GREEN)
    else:
        steer_angle = STEER_ANGLE
        counter     = -COUNTER_ANGLE
        hub.light.on(Color.RED)

    # Phase 1: Drive straight for FOLLOW_TIME_MS
    motor_steer.run_target(600, 0, wait=True)
    motor_steer.hold()
    elapsed = 0
    while elapsed < FOLLOW_TIME_MS:
        wait(20)
        elapsed += 20

    # Phase 2: Steer in WRO direction
    motor_steer.run_target(600, steer_angle, wait=True)
    motor_steer.hold()

    # Phase 3: Hold steer for STEER_MS minimum, THEN wait until color is gone.
    #
    # Two-part design (FIX 4):
    #   Part A — timed hold (STEER_MS):
    #     Guarantees the robot travels far enough past the obstacle before
    #     checking.  Without this, the sensor loses the color momentarily
    #     mid-pass and the robot snaps back too early (obstacle 1 problem).
    #
    #   Part B — color-clear loop (6 consecutive no-detects):
    #     After the timed hold, we still confirm the obstacle is truly gone.
    #     On obstacle 2+ the robot may arrive at a slightly different lateral
    #     position — STEER_MS alone would expire while the obstacle is still
    #     visible, causing the counter-steer to fire too early and over-swing.
    #     The color-clear loop prevents that.
    elapsed = 0
    while elapsed < STEER_MS:
        wait(20)
        elapsed += 20
    no_detect = 0
    while no_detect < 6:
        if get_color() != color:
            no_detect += 1
        else:
            no_detect = 0
        wait(20)

    # Phase 4: Counter-steer (obstacle avoidance only — never touches
    # active_center() offsets used by normal wall-following)
    motor_steer.run_target(500, counter, wait=True)
    motor_steer.hold()
    elapsed = 0
    while elapsed < COUNTER_MS:
        get_color()
        wait(20)
        elapsed += 20

    # Phase 5: Drive forward briefly while still counter-steered, THEN re-center.
    # This pushes the robot away from the obstacle before straightening —
    # prevents the re-center swing from nudging back toward the pillar.
    # Tune POST_AVOID_FORWARD_MS: raise if robot still drifts back toward
    # the obstacle after re-centering, lower if it overshoots toward the wall.
    elapsed = 0
    while elapsed < POST_AVOID_FORWARD_MS:
        wait(20)
        elapsed += 20

    motor_steer.run_target(300, AVOID_RE_CENTER, wait=True)
    wait(200)
    motor_steer.hold()
    hub.light.off()


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

    stable_color    = 0
    stable_count    = 0
    obstacle_active = False

    hub.speaker.beep(frequency=800, duration=200)
    wait(300)

    blind_drive(STARTUP_DRIVE_MS, target_heading)

    while turn_count < TOTAL_TURNS:

        if obstacle_active:
            lock = None
        else:
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

            blind_drive(PRE_TURN_CREEP_MS, target_heading, turn_lock)

            is_last_turn   = (turn_count + 1 == TOTAL_TURNS)
            raw_heading    = do_arc_turn(lock, turn_lock, is_last_turn)
            turn_count    += 1

            target_heading = snap_heading(raw_heading, turn_count, turn_lock)

            if turn_count % TURNS_PER_LAP == 0:
                hub.speaker.beep(frequency=1000, duration=300)
                wait(100)

            if not is_last_turn:
                confirmed_post, stable_color, stable_count = post_turn_drive(
                    POST_TURN_CREEP_MS, target_heading, turn_lock,
                    0, 0
                )
                lost_count_left  = 0
                lost_count_right = 0

                if confirmed_post in (1, 2):
                    obstacle_active = True
                    avoid_obstacle(confirmed_post)
                    obstacle_active = False
                    lost_count_left  = 0
                    lost_count_right = 0
                    stable_color     = 0
                    stable_count     = 0
                    correction = gyro_steer_correction(target_heading, turn_lock)
                    steer(correction)
                    drive(DRIVE_SPEED_STRAIGHT)
            else:
                stable_color = 0
                stable_count = 0

        else:
            color_id = get_color()
            if color_id == stable_color:
                stable_count += 1
            else:
                stable_color = color_id
                stable_count = 1

            confirmed = stable_color if stable_count >= STABLE_NEEDED else 0

            if confirmed in (1, 2):
                obstacle_active  = True
                lost_count_left  = 0
                lost_count_right = 0
                avoid_obstacle(confirmed)
                obstacle_active  = False
                lost_count_left  = 0
                lost_count_right = 0
                stable_color     = 0
                stable_count     = 0
                correction = gyro_steer_correction(target_heading, turn_lock)
                steer(correction)
                drive(DRIVE_SPEED_STRAIGHT)
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