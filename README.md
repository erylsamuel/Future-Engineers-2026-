The presented code is a lightweight implementation of the PUPRemote communication framework, specifically optimized for Pybricks-powered LEGO hubs. It enables a LEGO hub to communicate with an external device such as an ESP32 through the LEGO Powered Up (LPF2) protocol. Compared to the full PUPRemote library, this version removes sensor-emulation functionality and focuses solely on hub-side communication while introducing asynchronous multitasking support.

The primary goals of this implementation are:

Reduced memory consumption on Pybricks hubs

Synchronous remote procedure calls

Asynchronous multitask support

Communication through Powered Up ports

Compatibility with Pybricks cooperative multitasking



---

1. Introduction

Modern LEGO robotics projects often require hardware beyond what a LEGO hub can provide. Devices such as ESP32 microcontrollers can offer:

Wi-Fi connectivity

Bluetooth communication

Additional sensors

Camera systems

AI processing


This library allows a Pybricks hub to treat those external devices as remote extensions.

Instead of directly exchanging raw bytes, the framework creates a Remote Procedure Call (RPC) system where the hub can execute functions located on the external device.

Example:

distance = call("get_distance")

The hub behaves as if the function exists locally, while the actual execution occurs on the ESP32.


---

2. Architecture Overview

The architecture follows a client-server model.

+-------------------+
|   Pybricks Hub    |
|  (Client / Hub)   |
+---------+---------+
          |
          | Powered Up Port
          |
+---------+---------+
|     ESP32 Device  |
|  (Remote Server)  |
+-------------------+

The hub:

Sends commands

Sends arguments

Receives responses


The remote device:

Receives commands

Executes functions

Returns results



---

3. Global Wrapper Functions

The library provides simplified functions that hide object-oriented complexity.


---

connect()

connect("A")

or

connect(1)

Purpose:

Creates a global PUPRemoteHub instance.

Connects to a Powered Up port.


Internally:

pr = PUPRemoteHub(pyport)

This allows block-code users to avoid manual object creation.


---

add_command()

Registers a remote function.

Example:

add_command(
    "temperature",
    "",
    "h"
)

Meaning:

Hub sends nothing.

Receives one signed short integer.



---

add_channel()

Registers a continuous data stream.

Example:

add_channel("gyro", "fff")

The remote device continuously updates the channel while the hub reads it.


---

call()

Executes a command synchronously.

Example:

value = call("temperature")

Execution sequence:

Hub
 |
 |-- send request
 |
 |-- wait
 |
 |-- receive result
 |
Return value


---

call_multitask()

Asynchronous version of call().

Designed for Pybricks multitasking.

Example:

result = await call_multitask("temperature")


---

process_async()

Background task that manages queued requests.

Example:

multitask(
    process_async(),
    some_other_task()
)

Without this function, asynchronous calls will fail.


---

4. The PUPRemote Base Class

The PUPRemote class handles:

Command definitions

Data encoding

Data decoding

Packet size management



---

Constructor

def __init__(self, max_packet_size=16)

Creates:

self.commands
self.modes
self.max_packet_size


---

commands

Stores all registered commands.

Example:

[
    {
        NAME: "temperature",
        SIZE: 2,
        TO_HUB_FORMAT: "h"
    }
]


---

modes

Dictionary for fast lookup.

Example:

{
    "temperature": 0
}


---

5. Commands and Channels

Two communication types exist.


---

Command

A remote function call.

call("add", 5, 10)

The remote side executes:

add(5, 10)

and returns the result.


---

Channel

A continuously updated value.

Example:

battery = call("battery")

The hub simply reads the latest data.


---

6. Data Serialization

Communication occurs as raw bytes.

Python objects must therefore be converted before transmission.

This process is called serialization.


---

encode()

encode(size, format, *argv)

Example:

struct.pack("h", 150)

Produces:

b'\x96\x00'


---

decode()

Performs the reverse operation.

Example:

struct.unpack("h", data)

Returns:

(150,)


---

7. Format Strings

The library uses Python's struct module.

Examples:

Format	Meaning

b	int8
B	uint8
h	int16
H	uint16
i	int32
f	float
ff	two floats
hhh	three int16 values


Example:

add_command(
    "position",
    "",
    "fff"
)

Returns:

(x, y, z)


---

8. repr Mode

Special mode:

"repr"

Allows transmission of arbitrary Python objects.

Example:

[1,2,3]

is converted to:

"[1, 2, 3]"

and transmitted as text.


---

Advantages

Flexible

Supports many object types


Disadvantages

Slower

Less memory efficient

Uses eval()



---

9. PUPRemoteHub Class

This class provides actual hardware communication.


---

Initialization

self.pup_device = PUPDevice(port)

Creates a Powered Up connection.

If connection fails:

OSError

is raised.


---

10. Command Verification

When a command is added:

add_command()

the library checks:

Mode Name

temperature == remote_mode_name

Packet Size

2 bytes == remote packet size

This prevents communication mismatches.


---

11. Synchronous Communication

Method:

call()

Sequence:

1. Lookup mode
2. Encode arguments
3. Write packet
4. Wait
5. Read packet
6. Decode result
7. Return result

Example:

speed = call("get_speed")


---

12. Asynchronous Communication

A major enhancement of this trimmed version.


---

Problem

Pybricks multitasking can run multiple coroutines simultaneously.

Example:

multitask(
    drive(),
    monitor_sensor()
)

If both tasks access the Powered Up port simultaneously:

IOERR
EAGAIN

can occur.


---

Solution

A centralized queue.

self._queue

All requests enter the queue first.


---

Example:

Task A --> Queue
Task B --> Queue
Task C --> Queue

The queue processes them one at a time.

A
↓
B
↓
C


---

13. Result Holders

Each queued request creates:

[
 False,
 None,
 None
]

Meaning:

[DONE, RESULT, ERROR]

Example:

[
 True,
 42,
 None
]

The task receives:

42


---

14. _execute_call()

Internal asynchronous implementation of call().

Responsibilities:

1. Encode arguments


2. Write data


3. Wait


4. Read response


5. Decode response


6. Return result



Unlike call(), all waits are cooperative:

await wait(...)

This allows other tasks to continue running.


---

15. process_async()

The multitasking engine.

Pseudo-flow:

Loop forever

If queue contains request:

    Execute request

    Store result

    Mark complete

Repeat

This acts as a dedicated communication worker.


---

16. Error Handling

The library includes multiple safety checks.


---

Packet Size Check

assert msg_size <= 16

Prevents oversized packets.


---

Argument Count Check

assert len(argv) == expected

Ensures correct parameter counts.


---

Mode Validation

assert mode_name == advertised_mode

Prevents mismatched command definitions.


---

Async Validation

if not self._multitask_loop_running:

Ensures:

process_async()

is running before multitask calls occur.


---

17. Performance Characteristics

Memory Usage

Approximately 44% smaller than the original PUPRemote implementation.

Achieved by:

Removing sensor-side code

Removing emulation functionality

Focusing only on hub-side communication



---

Packet Size

MAX_PKT = 16

Chosen because:

Pybricks LPF2 communication uses 16-byte payloads efficiently.

Smaller packets reduce memory consumption.



---

Concurrency

Supports multiple simultaneous tasks through:

call_multitask()
process_async()

without risking communication collisions.


---

18. Conclusion

This trimmed PUPRemote implementation is a specialized hub-side communication framework for Pybricks. It transforms low-level Powered Up data exchange into a structured Remote Procedure Call system while maintaining a very small memory footprint.

Its most important contribution is the introduction of a queued asynchronous architecture that allows multiple Pybricks coroutines to safely communicate with an external ESP32 device without generating port-access conflicts. As a result, it is particularly suitable for advanced LEGO robotics projects involving Wi-Fi, AI, vision processing, cloud connectivity, or custom sensors while remaining lightweight enough to run efficiently on resource-constrained LEGO hubs. 



WRO Future Engineers Round 1 Autonomous Navigation System

SPIKE Prime + Pybricks Implementation

This software controls a WRO Future Engineers autonomous vehicle using a LEGO SPIKE Prime hub running Pybricks. The robot is designed to complete three laps of the Round 1 track while maintaining stable lane positioning and executing reliable 90-degree cornering maneuvers.

The navigation system combines:

Gyroscope-based heading control

Ultrasonic wall detection

Direction-locking logic

Drift correction through heading snapping

Multi-stage turn execution

Automatic lap counting


The design emphasizes consistency and repeatability by minimizing accumulated heading error and reducing false turn detections caused by sensor noise.


---

1. System Overview

The robot uses three primary sensing and control systems:

Steering System

Controls front wheel direction.

Motor F

Responsibilities:

Center steering

Gyro corrections

Corner execution



---

Drive System

Controls propulsion.

Motor E

Responsibilities:

Straight driving

Corner speed reduction

Braking and stopping



---

Ultrasonic Navigation

Two ultrasonic sensors monitor wall presence.

Left  Sensor → Port C
Right Sensor → Port D

Responsibilities:

Detect open corners

Determine initial turning direction

Trigger turn execution



---

Gyroscope

SPIKE Prime IMU heading sensor.

Responsibilities:

Straight-line stabilization

Heading tracking

Drift correction

Corner completion measurement



---

2. Navigation Philosophy

Instead of continuously following walls, the robot follows a gyro-based heading.

This approach has several advantages:

Traditional Wall Following

Robot
   |
Wall Distance
   |
Steering Correction

Problems:

Sensitive to wall irregularities

Sensor noise affects steering

Oscillation near walls



---

Gyro Heading Following

Robot
   |
Target Heading
   |
Steering Correction

Advantages:

Smoother movement

More repeatable laps

Independent of wall imperfections


The ultrasonic sensors are only used to detect corners.


---

3. Startup Phase

At startup:

motor_steer.reset_angle(0)
hub.imu.reset_heading(0)

The system establishes:

Heading = 0°
Steering = centered

A startup beep confirms initialization.

The robot then performs:

blind_drive()

during which corner detection is disabled.

Purpose:

Move away from the start zone

Prevent immediate false corner detection



---

4. Direction Locking Strategy

One of the most important features is:

turn_lock

The first detected corner determines the entire race direction.

Example:

Left Corner First

Turn 1 → Left

All future turns:
Left
Left
Left
Left

Right Corner First

Turn 1 → Right

All future turns:
Right
Right
Right
Right

This prevents:

Incorrect turn selection

Sensor ambiguity

Accidental direction changes



---

5. Corner Detection

Corner detection relies on wall loss.

Example:

left_lost = distance >= 1800

When the sensor suddenly sees open space:

Wall
Wall
Wall
Open Space

a corner is likely present.


---

Noise Filtering

A single reading is not enough.

The program requires:

US_CONFIRM_COUNT = 4

consecutive confirmations.

Example:

Reading 1 → Open
Reading 2 → Open
Reading 3 → Open
Reading 4 → Open

Only then is the corner accepted.

Benefits:

Rejects sensor spikes

Prevents accidental turns

Improves consistency



---

6. Gyro Steering Controller

Straight driving uses proportional control.

correction = KP × heading_error

Where:

KP = 1.2


---

Example

Target:

0°

Actual:

+5°

Error:

+5°

Correction:

6°

Steering automatically compensates and returns the vehicle toward its target heading.


---

Deadband

GYRO_DEADBAND = 1.5°

Small errors are ignored.

Benefits:

Reduced steering jitter

Smoother driving

Lower motor wear



---

7. Corner Execution

When a corner is confirmed:

do_arc_turn()

is executed.


---

Step 1 — Steering Lock

steer(lock)

The wheels move to maximum steering angle.

Example:

+85°

or

-85°


---

Step 2 — Steering Stabilization

wait(STEER_LOCK_MS)

Purpose:

Allow steering motor to reach position

Ensure consistent turn geometry



---

Step 3 — Arc Turn

The robot drives slowly:

DRIVE_SPEED_TURN = 250

while monitoring gyro rotation.


---

Step 4 — Turn Completion

The turn ends when:

75°

of rotation is detected.

TURN_DEGREES = 75

This value compensates for natural vehicle momentum.


---

Step 5 — Active Braking

motor_drive.hold()

Purpose:

Eliminate coasting

Improve repeatability


Without this step:

Robot continues rolling

causing inconsistent corner exits.


---

8. Heading Snap System

One of the most advanced features is:

snap_heading()


---

The Problem

Suppose each corner finishes:

2° off target

After:

12 turns

drift becomes:

24°

which is enough to miss the lane entirely.


---

The Solution

After each turn:

target_heading = snap_heading(...)

Expected headings become:

0°
-90°
-180°
-270°

or

0°
90°
180°
270°

The robot continuously realigns itself to exact cardinal directions.


---

Result

Long-term heading drift is effectively eliminated.

This is particularly important during Lap 3 when accumulated gyro error becomes significant.


---

9. Post-Turn Recovery

After each turn:

blind_drive()

runs briefly.

Purpose:

Ignore ultrasonic sensors

Exit the corner cleanly

Avoid retriggering the same opening


This creates a cooldown zone after every corner.


---

10. Lap Counting

The track consists of:

TURNS_PER_LAP = 4

The robot performs:

TOTAL_LAPS = 3

Therefore:

TOTAL_TURNS = 12


---

Lap Completion

Every four turns:

turn_count % 4 == 0

a confirmation beep is played.

This provides audible lap feedback.


---

11. Run Completion

After:

12 turns

the robot:

1. Drives forward slightly


2. Stops


3. Plays three completion beeps



stop_all()

This ensures the robot fully exits the final corner before terminating.


---

12. Key Engineering Features

Feature	Purpose

Gyro Steering	Straight-line stability
Direction Locking	Prevents wrong-way turns
Consecutive Corner Confirmation	Noise rejection
Arc-Based Turning	Smooth cornering
Active Braking	Eliminates coasting
Heading Snap	Prevents cumulative drift
Cooldown Zone	Prevents duplicate corner detection
Automatic Lap Counting	Fully autonomous completion
Final Stop Logic	Consistent run termination



---

Conclusion

This Round 1 navigation algorithm prioritizes reliability over complexity. Rather than relying on continuous wall-following, the robot uses the gyroscope as its primary navigation reference and employs ultrasonic sensors only for corner recognition. The combination of direction locking, multi-sample corner confirmation, active braking, and heading snapping creates a highly repeatable autonomous system capable of completing three laps with minimal accumulated error. These design choices make the program particularly well suited for WRO Future Engineers Round 1, where consistency and robustness are more valuable than aggressive speed.


WRO Future Engineers Round 2 Autonomous System

Hybrid Navigation + External Vision Obstacle Avoidance (SPIKE Prime + Pybricks + PUPRemote)


---

Abstract

This system is a fully integrated autonomous control program for WRO Future Engineers Round 2. It combines:

Gyro-based track navigation (wall detection + arc turning)

Direction-locking logic for consistent race orientation

Multi-stage obstacle detection via external color sensor (PUPRemote)

Real-time obstacle avoidance with recovery steering

Sensor conflict isolation between navigation and obstacle systems


The core design principle is task separation with controlled interaction, ensuring obstacle handling never corrupts track navigation logic.


---

1. System Architecture

1.1 Core Control Hub

LEGO Education SPIKE Prime Hub

Responsibilities:

IMU-based heading tracking

Steering control (motor F)

Drive motor control (motor E)

Ultrasonic-based corner detection

Lap and turn state machine



---

1.2 Navigation Sensors

Left Ultrasonic → Port C

Right Ultrasonic → Port D


Used exclusively for:

Wall loss detection

Corner triggering

Direction lock initialization



---

1.3 External Vision System (PUPRemote Layer)

Communication through:

Port B → PUPRemoteHub

Channel: "hl"

Data: color ID stream (1 = green, 2 = red)


This separates perception from navigation logic.


---

2. System Design Philosophy

The system is built on three independent layers:

Layer 1 — Track Navigation (Primary Control)

Gyro steering

Arc turning

Lap counting

Wall-loss detection


Layer 2 — Obstacle Handling (Interrupt System)

Color detection via external module

Steering override

Recovery correction


Layer 3 — Safety Isolation Layer

Disables corner detection during obstacle events

Prevents false triggers from obstacle geometry



---

3. PUPRemote Communication Model

The robot uses a lightweight RPC-like channel:

p = PUPRemoteHub(Port.B)
p.add_channel('hl', to_hub_fmt='b')

Data Contract

Value	Meaning

0	No obstacle
1	Green obstacle
2	Red obstacle


Design Benefit

Removes processing load from hub

Allows real-time obstacle classification

Keeps navigation deterministic



---

4. Track Navigation System

4.1 Gyro-Based Steering

The robot maintains:

target_heading → gyro correction loop

Controller:

error = current_heading - target_heading
correction = KP × error

KP = 1.2

Deadband = 1.5°


Result:

Stable straight-line movement without wall dependency.


---

4.2 Corner Detection Logic

Uses ultrasonic “wall loss”:

distance >= 1800 mm

Filtered using:

US_CONFIRM_COUNT = 4

This prevents:

false positives from reflections

temporary sensor noise



---

4.3 Direction Lock System

First detected corner defines track orientation:

Left lock → all turns left

Right lock → all turns right


This prevents mid-run direction instability.


---

4.4 Arc Turn Execution

Turning uses IMU Z-axis rotation:

TURN_DEGREES = 75

Process:

1. Lock steering


2. Begin rotation tracking


3. Drive arc until threshold reached


4. Brake using motor hold



This ensures repeatable geometry-based turning rather than time-based turning.


---

5. Drift Control System

5.1 Heading Snap Correction

After every turn:

snap_heading()

Forces heading alignment to:

0°

±90°

±180°

±270°


Why this matters:

Without it, small gyro errors accumulate:

2° × 12 turns = 24° drift

Which is enough to miss lanes in Round 2.


---

5.2 Pre-Turn Creep

PRE_TURN_CREEP_MS = 300

Purpose:

Ensures robot is fully inside corner entry zone

Reduces early-turn triggering errors



---

5.3 Post-Turn Creep

POST_TURN_CREEP_MS = 800

Purpose:

Forces robot toward next wall

Improves next corner detection reliability



---

6. Obstacle Avoidance System

This is the most complex subsystem.


---

6.1 Triggering

Obstacle detection occurs via:

get_color()

Confirmed using:

STABLE_NEEDED = 2

This prevents false triggers.


---

6.2 Five-Phase Avoidance Model

Phase 1 — Approach Stabilization

Robot stabilizes alignment before reacting.


---

Phase 2 — Primary Steer

Green → left avoidance

Red → right avoidance


Steering is fully locked first.


---

Phase 3 — Minimum Hold + Validation

Key innovation:

STEER_MS (minimum forced hold)

Then:

waits until color disappears


Why dual system exists:

Prevents:

early return (obstacle still present)

late return (overshoot past obstacle)



---

Phase 4 — Counter-Steer Recovery

COUNTER_ANGLE

Brings robot back toward lane center.


---

Phase 5 — Re-centering + Forward Push

AVOID_RE_CENTER = 0
POST_AVOID_FORWARD_MS

Purpose:

stabilize heading

prevent rebound drift toward obstacle



---

7. Critical Safety Isolation

Obstacle Lock System

obstacle_active = True

While active:

wall detection is disabled

corner detection is frozen


Why this matters:

Without isolation:

Obstacle edge → ultrasonic sees gap → false corner → wrong turn

This would completely break Round 2 consistency.


---

8. System State Machine

Simplified flow:

NORMAL DRIVING
    ↓
CORNER DETECTED
    ↓
ARC TURN
    ↓
POST-TURN RECOVERY
    ↓
OBSTACLE CHECK
    ↓
IF OBSTACLE → INTERRUPT STATE
    ↓
OBSTACLE AVOIDANCE
    ↓
RETURN TO TRACK STATE


---

9. Performance Characteristics

Strengths

Deterministic corner execution

Strong noise filtering (multi-stage confirmation)

External vision reduces sensor load

Stable recovery logic after avoidance

Fully autonomous loop for 3 laps



---

Tradeoffs

Higher computational complexity

Dependency on external communication link

Slight latency introduced by PUPRemote polling

Requires tuning of multiple timing constants



---

10. Engineering Highlights

Feature	Purpose

PUPRemote integration	External perception system
Dual-phase obstacle validation	Prevent premature steering reversal
Heading snap system	Eliminates drift accumulation
Pre/post turn creep	Improves corner geometry consistency
Obstacle isolation lock	Prevents sensor conflict
Arc-based IMU turning	High repeatability
Multi-frame color confirmation	Noise filtering
Recovery steering loop	Lane re-alignment



---

Conclusion

This Round 2 system represents a multi-layer autonomous robotics architecture where navigation and perception are decoupled but tightly synchronized. The design prioritizes robustness through state isolation, redundancy in sensing validation, and strict control of sensor interference.

Compared to Round 1, this version introduces a major architectural shift:

from single-system navigation

to a multi-subsystem reactive architecture with external perception integration


This makes the robot significantly more adaptable to dynamic obstacles while maintaining consistent track performance over multiple laps.

