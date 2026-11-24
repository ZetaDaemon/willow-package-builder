from dataclasses import dataclass, field
from enum import Enum
from typing import Self, override


@dataclass(frozen=True, eq=False)
class Keyword:
    """Text preserving its spelling with case-insensitive equality."""

    text: str
    _comparison_key: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_comparison_key", self.text.casefold())

    def __deepcopy__(self, memo: dict[int, object]) -> Self:
        return self

    @override
    def __hash__(self) -> int:
        return hash(self._comparison_key)

    @override
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Keyword):
            return NotImplemented

        return self._comparison_key == other._comparison_key

    @override
    def __str__(self) -> str:
        return self.text


class KeywordEnum(Keyword, Enum):
    """Enum whose members compare directly with keywords."""


class ScriptKeywords(KeywordEnum):
    """UScrupt keywords."""

    EXTENDS = "extends"
    VAR = "var"
    LOCAL = "local"
    IF = "if"
    ELSE = "else"
    WHILE = "while"
    FOR = "for"
    DO = "do"
    UNTIL = "until"
    RETURN = "return"
    BREAK = "break"
    CONTINUE = "continue"
    TRUE = "true"
    FALSE = "false"
    SELF = "self"
    CLASS = "class"
    STRUCT = "struct"
    ENUM = "enum"
    STATE = "state"
    SUPER = "super"
    GLOBAL = "global"
    IGNORES = "ignores"
    INTERFACE = "interface"
    STRUCT_DEFAULT_PROPERTIES = "structdefaultproperties"
    DEFAULT_PROPERTIES = "defaultproperties"
    REPLICATION = "replication"
    WITHIN = "within"
    NONE = "none"
    BEGIN = "begin"
    END = "end"
    OBJECT = "object"
    DELEGATE = "delegate"
    ARRAY_COUNT = "arraycount"
    FOREACH = "foreach"
    NEW = "new"
    VECT = "vect"
    DEFAULT = "default"
    SWITCH = "switch"
    CASE = "case"
