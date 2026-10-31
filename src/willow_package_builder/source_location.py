from dataclasses import dataclass


@dataclass(frozen=True)
class SourceLocation:
    line: int
    column: int

    def __str__(self) -> str:
        return f"{self.line}:{self.column}"
