import struct
from abc import ABC, abstractmethod
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import IntEnum
from typing import TYPE_CHECKING, ClassVar, Self, override

if TYPE_CHECKING:
    from collections.abc import Generator

    from willow_package_builder.upackage import Package, ReferencePath


class ScriptOpcode(IntEnum):
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


FIRST_EXTENDED_NATIVE = 0x60
LAST_EXTENDED_NATIVE = 0x6F

FIRST_DIRECT_NATIVE = 0x70
LAST_DIRECT_NATIVE = 0xFF

UINT16_MAX = (1 << 16) - 1


class BytecodeItem(ABC):
    """ABC for bytecode items.

    Memory size can differ from the length of the raw bytecode.
    """

    _MEMORY_SIZE: ClassVar[int]

    def memory_size(self) -> int:
        """Get the memory size."""
        return self._MEMORY_SIZE

    @abstractmethod
    def serialize(self, package: Package, bytecode: Bytecode) -> bytes:
        """Serialize this item into package bytecode."""


@dataclass(frozen=True, eq=False)
class BytecodeLabel(BytecodeItem):
    """A position in the instruction stream."""

    _MEMORY_SIZE: ClassVar[int] = 0

    @override
    def serialize(self, package: Package, bytecode: Bytecode) -> bytes:
        return b""


@dataclass(frozen=True)
class BytecodeJump(BytecodeItem):
    """An absolute VM offset, resolved during serialization."""

    target: BytecodeLabel

    _MEMORY_SIZE: ClassVar[int] = 2

    @override
    def serialize(self, package: Package, bytecode: Bytecode) -> bytes:
        offset = bytecode.get_label_offset(self.target)

        if not 0 <= offset <= UINT16_MAX:
            msg = f"Jump target outside of it's encoding range: {offset}"
            raise ValueError(msg)

        return struct.pack("<H", offset)


@dataclass(frozen=True)
class BytecodeReference(BytecodeItem):
    """An object reference within bytecode."""

    reference: ReferencePath

    _MEMORY_SIZE: ClassVar[int] = 8

    @override
    def serialize(self, package: Package, bytecode: Bytecode) -> bytes:
        return self.reference.serialize(package)


@dataclass
class IfBlock:
    bytecode: Bytecode
    otherwise: BytecodeLabel | None
    end: BytecodeLabel = field(default_factory=BytecodeLabel)
    active: bool = True

    def advance_branch(self) -> None:
        """Close the preceding body and place its false-condition label."""
        if not self.active:
            msg = "Branch must be inside its if context"
            raise ValueError(msg)

        if self.otherwise is None:
            msg = "Cannot add a branch after else"
            raise ValueError(msg)

        self.bytecode += ScriptOpcode.JUMP
        self.bytecode += BytecodeJump(self.end)
        self.bytecode += self.otherwise

    @contextmanager
    def elif_statement(self, condition: Bytecode) -> Generator[None]:
        self.advance_branch()
        self.otherwise = self.bytecode.begin_if(condition)
        yield

    @contextmanager
    def else_statement(self) -> Generator[None]:
        self.advance_branch()
        self.otherwise = None
        yield


@dataclass
class LoopBlock:
    bytecode: Bytecode
    continue_target: BytecodeLabel
    break_target: BytecodeLabel
    active: bool = True

    def break_statement(self) -> Bytecode:
        if not self.active:
            msg = "Loop block is no longer active"
            raise RuntimeError(msg)

        script = Bytecode()
        script += ScriptOpcode.JUMP
        script += BytecodeJump(self.break_target)
        return script

    def continue_statement(self) -> Bytecode:
        if not self.active:
            msg = "Loop block is no longer active"
            raise RuntimeError(msg)

        script = Bytecode()
        script += ScriptOpcode.JUMP
        script += BytecodeJump(self.continue_target)
        return script


@dataclass
class Bytecode:
    parts: list[bytes | BytecodeItem] = field(default_factory=list)

    _label_offsets: dict[BytecodeLabel, int] = field(default_factory=dict, init=False, repr=False)

    def __iadd__(self, other: Bytecode | bytes | BytecodeItem | ScriptOpcode | int) -> Self:
        if isinstance(other, Bytecode):
            self.parts.extend(other.parts)

        elif isinstance(other, ScriptOpcode):
            self.parts.append(struct.pack("<B", int(other)))

        elif isinstance(other, int):
            if other == 0:
                self += ScriptOpcode.INT_ZERO
            elif other == 1:
                self += ScriptOpcode.INT_ONE
            else:
                self += ScriptOpcode.INT_CONST
                self += struct.pack("<i", other)

        else:
            self.parts.append(other)

        return self

    def __add__(self, other: Bytecode | bytes | BytecodeItem | ScriptOpcode | int) -> Bytecode:
        result = Bytecode(self.parts.copy())
        result += other
        return result

    def memory_size(self) -> int:
        return sum(
            len(part) if isinstance(part, bytes) else part.memory_size() for part in self.parts
        )

    def calculate_label_offsets(self) -> None:
        self._label_offsets.clear()
        offset = 0

        for part in self.parts:
            if isinstance(part, BytecodeLabel):
                if part in self._label_offsets:
                    msg = "Bytecode label was placed more than once"
                    raise ValueError(msg)

                self._label_offsets[part] = offset

            offset += len(part) if isinstance(part, bytes) else part.memory_size()

    def get_label_offset(self, label: BytecodeLabel) -> int:
        """Get the offset for a label."""
        offset = self._label_offsets.get(label)
        if offset is None:
            msg = "Jump target was never placed"
            raise ValueError(msg) from None
        return offset

    def serialize(self, package: Package) -> bytes:
        self.calculate_label_offsets()

        return b"".join(
            part if isinstance(part, bytes) else part.serialize(package, self)
            for part in self.parts
        )

    def add_local_variable(self, reference: ReferencePath) -> None:
        self += ScriptOpcode.LOCAL_VARIABLE
        self += BytecodeReference(reference)

    def add_instance_variable(self, reference: ReferencePath) -> None:
        self += ScriptOpcode.INSTANCE_VARIABLE
        self += BytecodeReference(reference)

    def begin_native_call(self, native_index: int) -> None:
        if not FIRST_DIRECT_NATIVE <= native_index <= LAST_DIRECT_NATIVE:
            msg = "Native index requires an unsupported encoding"
            raise ValueError(msg)

        # Append raw bytes, rather than an integer-constant expression.
        self += struct.pack("<B", native_index)

    def end_native_call(self) -> None:
        self += ScriptOpcode.END_FUNCTION_PARAMS

    @contextmanager
    def native_function(self, native_index: int) -> Generator[None]:
        self.begin_native_call(native_index)

        try:
            yield
        finally:
            self.end_native_call()

    def begin_if(self, condition: Bytecode) -> BytecodeLabel:
        end = BytecodeLabel()
        self += ScriptOpcode.JUMP_IF_NOT
        self += BytecodeJump(end)
        self += condition
        return end

    @contextmanager
    def if_statement(self, condition: Bytecode) -> Generator[IfBlock]:
        branch = IfBlock(self, self.begin_if(condition))

        try:
            yield branch
        finally:
            branch.active = False

        if branch.otherwise is not None:
            self += branch.otherwise

        self += branch.end

    @contextmanager
    def while_statement(self, condition: Bytecode) -> Generator[LoopBlock]:
        start = BytecodeLabel()
        end = BytecodeLabel()
        loop = LoopBlock(self, start, end)

        self += start
        self += ScriptOpcode.JUMP_IF_NOT
        self += BytecodeJump(end)
        self += condition

        try:
            yield loop
        finally:
            loop.active = False

        self += ScriptOpcode.JUMP
        self += BytecodeJump(start)
        self += end
