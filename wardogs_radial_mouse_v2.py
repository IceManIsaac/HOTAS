# WARDOGS / general radial mini-stick -> mouse
# Joystick Gremlin (current user-script API)
#
# Key changes vs the first version:
# - No freelook/hold button: always active while the Gremlin profile is active.
# - No ModeVariable: works regardless of Gremlin mode.
# - Reads BOTH axes together on a fixed periodic loop.
# - Sends direct relative mouse deltas instead of using the shared MouseController.
# - Uses fractional-pixel accumulation for smooth low-speed movement.
# - Much higher default maximum speed.

import math
import time

from gremlin import sendinput
from gremlin.types import InputType
from gremlin.user_script import (
    PhysicalInputVariable,
    FloatVariable,
    IntegerVariable,
    BoolVariable,
    periodic,
)

x_axis = PhysicalInputVariable(
    "Mini-stick X",
    "Select the MHG mini-stick horizontal axis (usually RX)",
    False,
    [InputType.JoystickAxis],
)

y_axis = PhysicalInputVariable(
    "Mini-stick Y",
    "Select the MHG mini-stick vertical axis (usually RY)",
    False,
    [InputType.JoystickAxis],
)

deadzone = FloatVariable(
    "Radial deadzone",
    "Circular center deadzone; 0.10 = 10 percent",
    False,
    0.10,
    0.0,
    0.50,
)

max_speed = IntegerVariable(
    "Maximum mouse speed",
    "Maximum synthetic mouse speed in relative counts/pixels per second",
    False,
    1800,
    100,
    6000,
)

response_exponent = FloatVariable(
    "Response exponent",
    "1.0 = linear; higher values give finer control near center",
    False,
    1.35,
    0.50,
    4.00,
)

x_sensitivity = FloatVariable(
    "X sensitivity",
    "Horizontal sensitivity multiplier",
    False,
    1.0,
    0.10,
    3.0,
)

y_sensitivity = FloatVariable(
    "Y sensitivity",
    "Vertical sensitivity multiplier",
    False,
    1.0,
    0.10,
    3.0,
)

invert_x = BoolVariable(
    "Invert X",
    "Invert horizontal movement",
    False,
    False,
)

invert_y = BoolVariable(
    "Invert Y",
    "Invert vertical movement",
    False,
    False,
)

_last_time = None
_remainder_x = 0.0
_remainder_y = 0.0


@periodic(0.01)  # 100 Hz
def radial_mouse(joy):
    global _last_time, _remainder_x, _remainder_y

    now = time.monotonic()
    if _last_time is None:
        _last_time = now
        return

    # Use real elapsed time so output speed remains stable if the periodic
    # scheduler jitters slightly.
    dt = now - _last_time
    _last_time = now

    # Avoid a large jump after a pause/hitch.
    dt = max(0.0, min(dt, 0.05))

    try:
        x = float(joy[x_axis.device_guid].axis(x_axis.input_id).value)
        y = float(joy[y_axis.device_guid].axis(y_axis.input_id).value)
    except Exception:
        # If either device/axis is temporarily unavailable, simply emit nothing.
        _remainder_x = 0.0
        _remainder_y = 0.0
        return

    # Clamp malformed/out-of-range device values.
    x = max(-1.0, min(1.0, x))
    y = max(-1.0, min(1.0, y))

    if invert_x.value:
        x = -x
    if invert_y.value:
        y = -y

    magnitude = math.hypot(x, y)
    dz = deadzone.value

    # True circular/radial deadzone.
    if magnitude <= dz:
        _remainder_x = 0.0
        _remainder_y = 0.0
        return

    # Direction is derived from the full 2D vector.
    direction_x = x / magnitude
    direction_y = y / magnitude

    # Normalize radial travel so the edge of the stick is 100% regardless
    # of direction. This prevents cardinal-vs-diagonal speed changes.
    magnitude = min(magnitude, 1.0)
    radial = (magnitude - dz) / (1.0 - dz)
    radial = max(0.0, min(1.0, radial))

    # Radial response curve.
    speed = max_speed.value * (radial ** response_exponent.value)

    velocity_x = direction_x * speed * x_sensitivity.value
    velocity_y = direction_y * speed * y_sensitivity.value

    # Convert velocity to this tick's relative motion while preserving
    # fractions so low-speed motion does not vanish due to integer rounding.
    _remainder_x += velocity_x * dt
    _remainder_y += velocity_y * dt

    dx = math.trunc(_remainder_x)
    dy = math.trunc(_remainder_y)

    _remainder_x -= dx
    _remainder_y -= dy

    if dx != 0 or dy != 0:
        sendinput.mouse_relative_motion(dx, dy)
