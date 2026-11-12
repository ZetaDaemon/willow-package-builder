from dataclasses import dataclass
from enum import Enum
from typing import override


@dataclass(frozen=True, eq=False)
class Keyword:
    """Text preserving its spelling with case-insensitive equality."""

    text: str

    @override
    def __hash__(self) -> int:
        return hash(self.text.casefold())

    @override
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Keyword):
            return NotImplemented

        return self.text.casefold() == other.text.casefold()

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
