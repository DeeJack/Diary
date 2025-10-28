from enum import Enum


class InputType(Enum):
    """Type of input device"""

    TABLET = "tablet"
    MOUSE = "mouse"
    TOUCH = "touch"


class InputAction(Enum):
    """Type of input action"""

    PRESS = "press"
    MOVE = "move"
    RELEASE = "release"
