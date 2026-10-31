from enum import IntEnum, auto
from typing import TYPE_CHECKING


class ScriptOpcode(IntEnum):
    """Script Opcodes.

    Opcodes are only type checking here, to be overridden by game specific opcodes.
    """

    if TYPE_CHECKING:
        # Variable access.
        LOCAL_VARIABLE = auto()
        INSTANCE_VARIABLE = auto()
        DEFAULT_VARIABLE = auto()
        STATE_VARIABLE = auto()
        NATIVE_PARAMETER = auto()
        BOOL_VARIABLE = auto()
        STRUCT_MEMBER = auto()
        OUT_VARIABLE = auto()

        # BL2 optimized local access.
        LOCAL_VARIABLE_INT = auto()
        LOCAL_VARIABLE_FLOAT = auto()
        LOCAL_VARIABLE_BYTE = auto()
        LOCAL_VARIABLE_BOOL = auto()
        LOCAL_VARIABLE_OBJECT = auto()

        # Assignment.
        LET = auto()
        LET_BOOL = auto()
        LET_DELEGATE = auto()

        # Control flow.
        RETURN = auto()
        SWITCH = auto()
        JUMP = auto()
        JUMP_IF_NOT = auto()
        STOP = auto()
        ASSERT = auto()
        CASE = auto()
        NOTHING = auto()
        LABEL_TABLE = auto()
        GOTO_LABEL = auto()
        EAT_RETURN_VALUE = auto()
        SKIP = auto()
        RETURN_NOTHING = auto()
        CONDITIONAL = auto()
        END_OF_SCRIPT = auto()
        FILTER_EDITOR_ONLY = auto()

        # Function calls and arguments.
        END_PARAMETER_VALUE = auto()
        END_FUNCTION_PARAMS = auto()
        VIRTUAL_FUNCTION = auto()
        FINAL_FUNCTION = auto()
        GLOBAL_FUNCTION = auto()
        DEFAULT_PARAMETER_VALUE = auto()
        EMPTY_PARAMETER_VALUE = auto()

        # Context and object creation.
        NEW = auto()
        CLASS_CONTEXT = auto()
        SELF = auto()
        CONTEXT = auto()
        INTERFACE_CONTEXT = auto()

        # Casts.
        META_CLASS_CAST = auto()
        DYNAMIC_CAST = auto()
        PRIMITIVE_CAST = auto()
        INTERFACE_CAST = auto()

        # Constants.
        INT_CONST = auto()
        FLOAT_CONST = auto()
        STRING_CONST = auto()
        OBJECT_CONST = auto()
        NAME_CONST = auto()
        ROTATOR_CONST = auto()
        VECTOR_CONST = auto()
        BYTE_CONST = auto()
        INT_ZERO = auto()
        INT_ONE = auto()
        TRUE = auto()
        FALSE = auto()
        NO_OBJECT = auto()
        INT_CONST_BYTE = auto()
        UNICODE_STRING_CONST = auto()

        # Struct comparisons.
        STRUCT_EQUAL = auto()
        STRUCT_NOT_EQUAL = auto()

        # Fixed-size array access.
        ARRAY_ELEMENT = auto()

        # Dynamic arrays.
        DYNAMIC_ARRAY_ELEMENT = auto()
        DYNAMIC_ARRAY_LENGTH = auto()
        DYNAMIC_ARRAY_INSERT = auto()
        DYNAMIC_ARRAY_REMOVE = auto()
        DYNAMIC_ARRAY_FIND = auto()
        DYNAMIC_ARRAY_FIND_STRUCT = auto()
        DYNAMIC_ARRAY_ADD = auto()
        DYNAMIC_ARRAY_ADD_ITEM = auto()
        DYNAMIC_ARRAY_REMOVE_ITEM = auto()
        DYNAMIC_ARRAY_INSERT_ITEM = auto()
        DYNAMIC_ARRAY_ITERATOR = auto()
        DYNAMIC_ARRAY_SORT = auto()

        # Iteration.
        ITERATOR = auto()
        ITERATOR_POP = auto()
        ITERATOR_NEXT = auto()

        # Delegates.
        DELEGATE_EQUAL = auto()
        DELEGATE_NOT_EQUAL = auto()
        DELEGATE_FUNCTION_EQUAL = auto()
        DELEGATE_FUNCTION_NOT_EQUAL = auto()
        EMPTY_DELEGATE = auto()
        DELEGATE_FUNCTION = auto()
        DELEGATE_PROPERTY = auto()
        INSTANCE_DELEGATE = auto()

        # Debug information.
        DEBUG_INFO = auto()

        # Gearbox attribute expressions.
        ATTRIBUTE_VARIABLE = auto()
        LET_ATTRIBUTE = auto()


class Bl2Opcode(IntEnum):
    """Bl2 opcode statements."""

    # Variable access.
    LOCAL_VARIABLE = 0x00
    INSTANCE_VARIABLE = 0x01
    DEFAULT_VARIABLE = 0x02
    STATE_VARIABLE = 0x03
    NATIVE_PARAMETER = 0x29
    BOOL_VARIABLE = 0x2D
    STRUCT_MEMBER = 0x35
    OUT_VARIABLE = 0x48

    # BL2 optimized local access.
    # These use local-table operands, not ordinary property references.
    LOCAL_VARIABLE_INT = 0x4C
    LOCAL_VARIABLE_FLOAT = 0x4D
    LOCAL_VARIABLE_BYTE = 0x4E
    LOCAL_VARIABLE_BOOL = 0x4F
    LOCAL_VARIABLE_OBJECT = 0x50

    # Assignment.
    LET = 0x0F
    LET_BOOL = 0x14
    LET_DELEGATE = 0x44

    # Control flow.
    RETURN = 0x04
    SWITCH = 0x05
    JUMP = 0x06
    JUMP_IF_NOT = 0x07
    STOP = 0x08
    ASSERT = 0x09
    CASE = 0x0A
    NOTHING = 0x0B
    LABEL_TABLE = 0x0C
    GOTO_LABEL = 0x0D
    EAT_RETURN_VALUE = 0x0E
    SKIP = 0x18
    RETURN_NOTHING = 0x3A
    CONDITIONAL = 0x45
    END_OF_SCRIPT = 0x53
    FILTER_EDITOR_ONLY = 0x5A

    # Function calls and arguments.
    END_PARAMETER_VALUE = 0x15
    END_FUNCTION_PARAMS = 0x16
    VIRTUAL_FUNCTION = 0x1B
    FINAL_FUNCTION = 0x1C
    GLOBAL_FUNCTION = 0x37
    DEFAULT_PARAMETER_VALUE = 0x49
    EMPTY_PARAMETER_VALUE = 0x4A

    # Context and object creation.
    NEW = 0x11
    CLASS_CONTEXT = 0x12
    SELF = 0x17
    CONTEXT = 0x19
    INTERFACE_CONTEXT = 0x51

    # Casts.
    META_CLASS_CAST = 0x13
    DYNAMIC_CAST = 0x2E
    PRIMITIVE_CAST = 0x38
    INTERFACE_CAST = 0x52

    # Constants.
    INT_CONST = 0x1D
    FLOAT_CONST = 0x1E
    STRING_CONST = 0x1F
    OBJECT_CONST = 0x20
    NAME_CONST = 0x21
    ROTATOR_CONST = 0x22
    VECTOR_CONST = 0x23
    BYTE_CONST = 0x24
    INT_ZERO = 0x25
    INT_ONE = 0x26
    TRUE = 0x27
    FALSE = 0x28
    NO_OBJECT = 0x2A
    INT_CONST_BYTE = 0x2C
    UNICODE_STRING_CONST = 0x34

    # Struct comparisons.
    STRUCT_EQUAL = 0x32
    STRUCT_NOT_EQUAL = 0x33

    # Fixed-size array access.
    ARRAY_ELEMENT = 0x1A

    # Dynamic arrays.
    DYNAMIC_ARRAY_ELEMENT = 0x10
    DYNAMIC_ARRAY_LENGTH = 0x36
    DYNAMIC_ARRAY_INSERT = 0x39
    DYNAMIC_ARRAY_REMOVE = 0x40
    DYNAMIC_ARRAY_FIND = 0x46
    DYNAMIC_ARRAY_FIND_STRUCT = 0x47
    DYNAMIC_ARRAY_ADD = 0x54
    DYNAMIC_ARRAY_ADD_ITEM = 0x55
    DYNAMIC_ARRAY_REMOVE_ITEM = 0x56
    DYNAMIC_ARRAY_INSERT_ITEM = 0x57
    DYNAMIC_ARRAY_ITERATOR = 0x58
    DYNAMIC_ARRAY_SORT = 0x59

    # Iteration.
    ITERATOR = 0x2F
    ITERATOR_POP = 0x30
    ITERATOR_NEXT = 0x31

    # Delegates.
    DELEGATE_EQUAL = 0x3B
    DELEGATE_NOT_EQUAL = 0x3C
    DELEGATE_FUNCTION_EQUAL = 0x3D
    DELEGATE_FUNCTION_NOT_EQUAL = 0x3E
    EMPTY_DELEGATE = 0x3F
    DELEGATE_FUNCTION = 0x42
    DELEGATE_PROPERTY = 0x43
    INSTANCE_DELEGATE = 0x4B

    # Debug information.
    DEBUG_INFO = 0x41

    # Gearbox attribute expressions.
    ATTRIBUTE_VARIABLE = 0x5E
    LET_ATTRIBUTE = 0x5F


# Currently only bl2 is supported, so just set it here.
ScriptOpcode = Bl2Opcode  # pyright: ignore[reportAssignmentType]  # noqa: F811
