from typing import final

from willow_package_builder.opcode import Opcode
from willow_package_builder.upackage import PackageFlags

from .game import Game


@final
class Bl2Opcode:
    """BL2 opcode statements."""

    # Variable access.
    LOCAL_VARIABLE = Opcode(0x00)
    INSTANCE_VARIABLE = Opcode(0x01)
    DEFAULT_VARIABLE = Opcode(0x02)
    SWITCH_SIZE = Opcode(0x03)
    NATIVE_PARAMETER = Opcode(0x29)
    BOOL_VARIABLE = Opcode(0x2D)
    STRUCT_MEMBER = Opcode(0x35)
    OUT_VARIABLE = Opcode(0x48)

    # BL2 optimized local access.
    # These use local-table operands, not ordinary property references.
    LOCAL_VARIABLE_INT = Opcode(0x4C)
    LOCAL_VARIABLE_FLOAT = Opcode(0x4D)
    LOCAL_VARIABLE_BYTE = Opcode(0x4E)
    LOCAL_VARIABLE_BOOL = Opcode(0x4F)
    LOCAL_VARIABLE_OBJECT = Opcode(0x50)

    # Assignment.
    LET = Opcode(0x0F)
    LET_BOOL = Opcode(0x14)
    LET_DELEGATE = Opcode(0x44)

    # Control flow.
    RETURN = Opcode(0x04)
    SWITCH = Opcode(0x05)
    JUMP = Opcode(0x06)
    JUMP_IF_NOT = Opcode(0x07)
    STOP = Opcode(0x08)
    ASSERT = Opcode(0x09)
    CASE = Opcode(0x0A)
    NOTHING = Opcode(0x0B)
    LABEL_TABLE = Opcode(0x0C)
    GOTO_LABEL = Opcode(0x0D)
    EAT_RETURN_VALUE = Opcode(0x0E)
    SKIP = Opcode(0x18)
    RETURN_NOTHING = Opcode(0x3A)
    CONDITIONAL = Opcode(0x45)
    END_OF_SCRIPT = Opcode(0x53)
    FILTER_EDITOR_ONLY = Opcode(0x5A)

    # Function calls and arguments.
    END_PARAMETER_VALUE = Opcode(0x15)
    END_FUNCTION_PARAMS = Opcode(0x16)
    VIRTUAL_FUNCTION = Opcode(0x1B)
    FINAL_FUNCTION = Opcode(0x1C)
    GLOBAL_FUNCTION = Opcode(0x37)
    DEFAULT_PARAMETER_VALUE = Opcode(0x49)
    EMPTY_PARAMETER_VALUE = Opcode(0x4A)

    # Context and object creation.
    NEW = Opcode(0x11)
    CLASS_CONTEXT = Opcode(0x12)
    SELF = Opcode(0x17)
    CONTEXT = Opcode(0x19)
    INTERFACE_CONTEXT = Opcode(0x51)

    # Casts.
    META_CLASS_CAST = Opcode(0x13)
    DYNAMIC_CAST = Opcode(0x2E)
    PRIMITIVE_CAST = Opcode(0x38)
    INTERFACE_CAST = Opcode(0x52)

    # Constants.
    INT_CONST = Opcode(0x1D)
    FLOAT_CONST = Opcode(0x1E)
    STRING_CONST = Opcode(0x1F)
    OBJECT_CONST = Opcode(0x20)
    NAME_CONST = Opcode(0x21)
    ROTATOR_CONST = Opcode(0x22)
    VECTOR_CONST = Opcode(0x23)
    BYTE_CONST = Opcode(0x24)
    INT_ZERO = Opcode(0x25)
    INT_ONE = Opcode(0x26)
    TRUE = Opcode(0x27)
    FALSE = Opcode(0x28)
    NO_OBJECT = Opcode(0x2A)
    INT_CONST_BYTE = Opcode(0x2C)
    UNICODE_STRING_CONST = Opcode(0x34)

    # Struct comparisons.
    STRUCT_EQUAL = Opcode(0x32)
    STRUCT_NOT_EQUAL = Opcode(0x33)

    # Fixed-size array access.
    ARRAY_ELEMENT = Opcode(0x1A)

    # Dynamic arrays.
    DYNAMIC_ARRAY_ELEMENT = Opcode(0x10)
    DYNAMIC_ARRAY_LENGTH = Opcode(0x36)
    DYNAMIC_ARRAY_INSERT = Opcode(0x39)
    DYNAMIC_ARRAY_REMOVE = Opcode(0x40)
    DYNAMIC_ARRAY_FIND = Opcode(0x46)
    DYNAMIC_ARRAY_FIND_STRUCT = Opcode(0x47)
    DYNAMIC_ARRAY_ADD = Opcode(0x54)
    DYNAMIC_ARRAY_ADD_ITEM = Opcode(0x55)
    DYNAMIC_ARRAY_REMOVE_ITEM = Opcode(0x56)
    DYNAMIC_ARRAY_INSERT_ITEM = Opcode(0x57)
    DYNAMIC_ARRAY_ITERATOR = Opcode(0x58)
    DYNAMIC_ARRAY_SORT = Opcode(0x59)

    # Iteration.
    ITERATOR = Opcode(0x2F)
    ITERATOR_POP = Opcode(0x30)
    ITERATOR_NEXT = Opcode(0x31)

    # Delegates.
    DELEGATE_EQUAL = Opcode(0x3B)
    DELEGATE_NOT_EQUAL = Opcode(0x3C)
    DELEGATE_FUNCTION_EQUAL = Opcode(0x3D)
    DELEGATE_FUNCTION_NOT_EQUAL = Opcode(0x3E)
    EMPTY_DELEGATE = Opcode(0x3F)
    DELEGATE_FUNCTION = Opcode(0x42)
    DELEGATE_PROPERTY = Opcode(0x43)
    INSTANCE_DELEGATE = Opcode(0x4B)

    # Debug information.
    DEBUG_INFO = Opcode(0x41)

    # Gearbox attribute expressions.
    ATTRIBUTE_VARIABLE = Opcode(0x5E)
    LET_ATTRIBUTE = Opcode(0x5F)


@final
class Bl2(Game):
    PACKAGE_VERSION = 832
    LICENSE_VERSION = 46
    ENGINE_VERSION = 1712575
    COOKER_VERSION = 134

    OPCODES = Bl2Opcode()

    PACKAGE_FLAGS = (
        PackageFlags.ALLOW_DOWNLOAD
        | PackageFlags.COOKED
        | PackageFlags.CONTAINS_SCRIPT
        | PackageFlags.STRIPPED_SOURCE
    )
