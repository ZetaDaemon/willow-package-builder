from enum import IntEnum


class ScriptOpcode(IntEnum):
    RETURN = 0x04
    NOTHING = 0x0B
    END_OF_SCRIPT = 0x53
