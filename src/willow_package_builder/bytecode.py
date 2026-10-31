import struct
from abc import ABC, abstractmethod
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, ClassVar, Self, override

from willow_package_builder.upackage import FName

from .opcode import ScriptOpcode

if TYPE_CHECKING:
    from collections.abc import Generator

    from .upackage import Package, ReferencePath


FIRST_EXTENDED_NATIVE = 0x60
LAST_EXTENDED_NATIVE = 0x6F

MIN_NATIVE_INDEX = 1
MAX_NATIVE_INDEX = 0x0FFF

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


@dataclass(frozen=True)
class BytecodeRelativeJump(BytecodeItem):
    origin: BytecodeLabel
    target: BytecodeLabel

    _MEMORY_SIZE: ClassVar[int] = 2

    @override
    def serialize(self, package: Package, bytecode: Bytecode) -> bytes:
        offset = bytecode.get_label_offset(self.target) - bytecode.get_label_offset(self.origin)

        if not 0 <= offset <= UINT16_MAX:
            msg = f"Relative jump distance outside encoding range: {offset}"
            raise ValueError(msg)

        return struct.pack("<H", offset)


@dataclass(frozen=True)
class BytecodeName(BytecodeItem):
    name: FName

    _MEMORY_SIZE: ClassVar[int] = 8

    @override
    def serialize(self, package: Package, bytecode: Bytecode) -> bytes:
        return self.name.serialize(package)


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

    def __iadd__(self, other: Bytecode | bytes | BytecodeItem | ScriptOpcode) -> Self:
        match other:
            case Bytecode():
                self.parts.extend(other.parts)

            case ScriptOpcode():
                self.parts.append(struct.pack("<B", int(other)))

            case bytes() | BytecodeItem():
                self.parts.append(other)

            case _:
                return NotImplemented  # pyright: ignore[reportUnreachable]

        return self

    def __add__(self, other: Bytecode | bytes | BytecodeItem | ScriptOpcode) -> Bytecode:
        result = Bytecode(self.parts.copy())
        result += other
        return result

    def add_constant(self, value: bool | float | str) -> None:
        match value:
            case bool():
                self += ScriptOpcode.TRUE if value else ScriptOpcode.FALSE

            case int():
                match value:
                    case 0:
                        self += ScriptOpcode.INT_ZERO
                    case 1:
                        self += ScriptOpcode.INT_ONE
                    case _:
                        self += ScriptOpcode.INT_CONST
                        self += struct.pack("<i", value)

            case float():
                self += ScriptOpcode.FLOAT_CONST
                self += struct.pack("<f", value)

            case str():
                if "\0" in value:
                    msg = "Bytecode string constants cannot contain embedded null characters"
                    raise ValueError(msg)

                try:
                    encoded = value.encode("ascii") + b"\0"
                    opcode = ScriptOpcode.STRING_CONST
                except UnicodeEncodeError:
                    encoded = value.encode("utf-16-le") + b"\0\0"
                    opcode = ScriptOpcode.UNICODE_STRING_CONST

                self += opcode
                self += encoded

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
        if not MIN_NATIVE_INDEX <= native_index <= MAX_NATIVE_INDEX:
            msg = (
                f"Native index {native_index} is outside the supported "
                f"format range {MIN_NATIVE_INDEX}-{MAX_NATIVE_INDEX}"
            )
            raise ValueError(msg)

        if FIRST_DIRECT_NATIVE <= native_index <= LAST_DIRECT_NATIVE:
            self += struct.pack("<B", native_index)
        else:
            high, low = native_index.to_bytes(2, "big")
            self += struct.pack("<BB", FIRST_EXTENDED_NATIVE + high, low)

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

    @contextmanager
    def for_statement(
        self, initializer: Bytecode, condition: Bytecode, increment: Bytecode
    ) -> Generator[LoopBlock]:
        condition_label = BytecodeLabel()
        increment_label = BytecodeLabel()
        end = BytecodeLabel()
        loop = LoopBlock(self, increment_label, end)

        self += initializer

        self += condition_label
        self += ScriptOpcode.JUMP_IF_NOT
        self += BytecodeJump(end)
        self += condition

        try:
            yield loop
        finally:
            loop.active = False

        self += increment_label
        self += increment

        self += ScriptOpcode.JUMP
        self += BytecodeJump(condition_label)
        self += end

    @contextmanager
    def do_until_statement(self, condition: Bytecode) -> Generator[LoopBlock]:
        start = BytecodeLabel()
        condition_label = BytecodeLabel()
        end = BytecodeLabel()
        loop = LoopBlock(self, condition_label, end)

        self += start

        try:
            yield loop
        finally:
            loop.active = False

        self += condition_label
        self += ScriptOpcode.JUMP_IF_NOT
        self += BytecodeJump(start)
        self += condition
        self += end

    @contextmanager
    def default_parameter(self) -> Generator[None]:
        origin = BytecodeLabel()
        end = BytecodeLabel()

        self += ScriptOpcode.DEFAULT_PARAMETER_VALUE
        self += BytecodeRelativeJump(origin, end)
        self += origin

        yield

        self += ScriptOpcode.END_PARAMETER_VALUE
        self += end
