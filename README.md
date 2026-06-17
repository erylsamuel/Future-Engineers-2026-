Abstract

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
