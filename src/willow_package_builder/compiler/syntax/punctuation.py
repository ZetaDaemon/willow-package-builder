from enum import StrEnum


class Punctuation(StrEnum):
    LEFT_PAREN = "("
    RIGHT_PAREN = ")"
    LEFT_BRACE = "{"
    RIGHT_BRACE = "}"
    LEFT_BRACKET = "["
    RIGHT_BRACKET = "]"
    SEMICOLON = ";"
    COLON = ":"
    COMMA = ","
    DOT = "."


class Operator(StrEnum):
    # Assignment.
    EQUAL = "="
    IADD = "+="
    ISUBTRACT = "-="
    IMULTIPLY = "*="
    IDIVIDE = "/="
    IMODULO = "%="

    # Arithmetic.
    ADD = "+"
    SUBTRACT = "-"
    MULTIPLY = "*"
    DIVIDE = "/"
    MODULO = "%"
    POWER = "**"
    INCREMENT = "++"
    DECREMENT = "--"

    # Comparison.
    EQUAL_EQUAL = "=="
    NOT_EQUAL = "!="
    APPROX_EQUAL = "~="
    LESS = "<"
    GREATER = ">"
    LESS_EQUAL = "<="
    GREATER_EQUAL = ">="

    # Logical.
    NOT = "!"
    AND = "&&"
    OR = "||"
    XOR = "^^"

    # Bitwise.
    BITWISE_NOT = "~"
    BITWISE_AND = "&"
    BITWISE_OR = "|"
    BITWISE_XOR = "^"
    BITWISE_AND_ASSIGN = "&="
    BITWISE_OR_ASSIGN = "|="
    BITWISE_XOR_ASSIGN = "^="

    # Shifts.
    SHIFT_LEFT = "<<"
    SHIFT_RIGHT = ">>"
    UNSIGNED_SHIFT_RIGHT = ">>>"
    SHIFT_LEFT_ASSIGN = "<<="
    SHIFT_RIGHT_ASSIGN = ">>="
    UNSIGNED_SHIFT_RIGHT_ASSIGN = ">>>="

    # String concatenation.
    CONCAT = "$"
    SPACE_CONCAT = "@"
    CONCAT_ASSIGN = "$="
    SPACE_CONCAT_ASSIGN = "@="

    # Conditional expression.
    QUESTION = "?"
    COLON = ":"
