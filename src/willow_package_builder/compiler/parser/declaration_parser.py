from willow_package_builder.compiler.declarations import (
    ClassDeclaration,
    ClassModifier,
    ConstantDeclaration,
    EnumDeclaration,
    FunctionDeclaration,
    FunctionType,
    OperatorDeclaration,
    OperatorType,
    ParameterDeclaration,
    StructDeclaration,
)
from willow_package_builder.compiler.lexer import Token, TokenType
from willow_package_builder.logging import CompilationError, WarningCode, warn

from .declaration_syntax_parser import DeclarationSyntaxParser

PARAMETER_MODIFIERS = frozenset({"out", "optional", "coerce", "skip", "const"})
FUNCTION_MODIFIERS = frozenset(
    {
        "native",
        "static",
        "final",
        "simulated",
        "exec",
        "latent",
        "singular",
        "iterator",
        "public",
        "protected",
        "private",
        "reliable",
        "unreliable",
        "client",
        "server",
    }
)
STRUCT_MODIFIERS = frozenset(
    {
        "native",
        "export",
        "noexport",
        "transient",
        "atomic",
        "immutable",
        "immutablewhencooked",
        "strictconfig",
    }
)


class DeclarationParser(DeclarationSyntaxParser):
    def parse_class_header(self) -> ClassDeclaration:
        token = self.expect_identifier()
        keyword = token.text.casefold()

        if keyword not in ("class", "interface"):
            msg = f"Expected class or interface, got {token.text!r} at {token.line}:{token.column}"
            raise CompilationError(msg)

        is_interface = keyword == "interface"
        name = self.expect_identifier().text

        parent = None
        within = None
        modifiers: list[ClassModifier] = []

        while not self.match(";"):
            token = self.peek()

            if token.type is TokenType.EOF:
                msg = f"Unterminated class header for {name!r}"
                raise CompilationError(msg)

            keyword = self.expect_identifier().text.casefold()

            if keyword == "extends":
                if parent is not None:
                    msg = "Class header declares extends more than once"
                    raise CompilationError(msg)

                parent = self.parse_qualified_name()
                continue

            if keyword == "within":
                if within is not None:
                    msg = "Class header declares within more than once"
                    raise CompilationError(msg)

                within = self.parse_qualified_name()
                continue

            arguments = None
            if self.peek().text == "(":
                arguments = self.parse_parenthesized_tokens()

            modifiers.append(ClassModifier(name=keyword, arguments=arguments))

        return ClassDeclaration(name, parent, is_interface, within, tuple(modifiers))

    def parse_constant_declaration(self) -> ConstantDeclaration:
        self.expect("const")
        name = self.expect_identifier().text
        self.expect("=")

        value_tokens: list[Token] = []
        closing_symbols: list[str] = []
        pairs = {"(": ")", "[": "]", "{": "}"}

        while True:
            token = self.peek()

            if token.type is TokenType.EOF:
                msg = f"Unterminated constant declaration for {name!r}"
                raise CompilationError(msg)

            if token.text == ";" and not closing_symbols:
                self.advance()
                break

            if token.type is TokenType.SYMBOL:
                if token.text in pairs:
                    closing_symbols.append(pairs[token.text])
                elif token.text in (")", "]", "}"):
                    if not closing_symbols or token.text != closing_symbols[-1]:
                        msg = (
                            f"Unexpected {token.text!r} in constant {name!r} "
                            f"at {token.line}:{token.column}"
                        )
                        raise CompilationError(msg)

                    closing_symbols.pop()

            value_tokens.append(self.advance())

        if not value_tokens:
            msg = f"Constant {name!r} requires a value"
            raise CompilationError(msg)

        return ConstantDeclaration(name=name, value_tokens=tuple(value_tokens))

    def parse_enum_declaration(self, *, warn_explicit_sentinel: bool = True) -> EnumDeclaration:
        self.expect("enum")
        name = self.expect_identifier().text
        opening = self.expect("{")

        members: list[str] = []
        seen: set[str] = set()

        while not self.match("}"):
            token = self.peek()

            if token.type is TokenType.EOF:
                msg = f"Unterminated enum {name!r}, opened at {opening.line}:{opening.column}"
                raise CompilationError(msg)

            member = self.expect_identifier()
            key = member.text.casefold()

            if key in seen:
                msg = f"Duplicate enum member {member.text!r} at {member.line}:{member.column}"
                raise CompilationError(msg)

            seen.add(key)
            members.append(member.text)

            if self.match("}"):
                break

            self.expect(",")

        self.expect(";")

        if not members:
            msg = f"Enum {name!r} must contain at least one member"
            raise CompilationError(msg)

        prefix = members[0].split("_", 1)[0]
        max_member = f"{prefix}_MAX"

        if members[-1].casefold() == max_member.casefold():
            if warn_explicit_sentinel:
                warn(WarningCode.EXPLICIT_ENUM_SENTINEL, f"Explicit _MAX member in enum {name}")
            members.pop()

        if not members:
            msg = f"Enum {name!r} has no non-sentinel members"
            raise CompilationError(msg)

        return EnumDeclaration(name=name, members=tuple(members))

    def parse_struct_declaration(self) -> StructDeclaration:
        self.expect("struct")

        modifiers: list[str] = []

        while self.peek().text.casefold() in STRUCT_MODIFIERS:
            modifiers.append(self.advance().text.casefold())

        name = self.expect_identifier().text

        parent = None
        if self.match("extends"):
            parent = self.parse_qualified_name()

        declaration = StructDeclaration(name=name, parent=parent, modifiers=tuple(modifiers))

        opening = self.expect("{")

        while not self.match("}"):
            token = self.peek()
            keyword = token.text.casefold()

            if token.type is TokenType.EOF:
                msg = f"Unterminated struct {name!r}, opened at {opening.line}:{opening.column}"
                raise CompilationError(msg)

            if self.match(";"):
                continue

            if keyword == "var":
                declaration.variables.extend(self.parse_variable_declaration())
                continue

            if keyword == "structdefaultproperties":
                if declaration.default_tokens is not None:
                    msg = f"Struct {name!r} has multiple default blocks"
                    raise CompilationError(msg)

                self.advance()
                declaration.default_tokens = self.parse_braced_tokens()
                continue

            msg = f"Unsupported struct member {token.text!r} at {token.line}:{token.column}"
            raise CompilationError(msg)

        self.expect(";")
        return declaration

    def is_operator_start(self) -> bool:
        offset = 0

        while self.peek(offset).text.casefold() in FUNCTION_MODIFIERS:
            modifier = self.peek(offset).text.casefold()
            offset += 1

            if modifier == "native" and self.peek(offset).text == "(":
                offset += 1

                if self.peek(offset).type is not TokenType.INTEGER:
                    return False

                offset += 1

                if self.peek(offset).text != ")":
                    return False

                offset += 1

        return self.peek(offset).text.casefold() in OperatorType

    def parse_parameter_default(self) -> tuple[Token, ...]:
        tokens: list[Token] = []
        closing_symbols: list[str] = []
        pairs = {"(": ")", "[": "]", "{": "}"}

        while True:
            token = self.peek()

            if token.type is TokenType.EOF:
                msg = f"Unterminated parameter default at {token.line}:{token.column}"
                raise CompilationError(msg)

            if token.type is TokenType.SYMBOL:
                if not closing_symbols and token.text in (",", ")"):
                    break

                if token.text in pairs:
                    closing_symbols.append(pairs[token.text])
                elif token.text in (")", "]", "}"):
                    if not closing_symbols or token.text != closing_symbols[-1]:
                        msg = (
                            f"Unexpected {token.text!r} in parameter default "
                            f"at {token.line}:{token.column}"
                        )
                        raise CompilationError(msg)

                    closing_symbols.pop()

            tokens.append(self.advance())

        if not tokens:
            token = self.peek()
            msg = f"Expected parameter default at {token.line}:{token.column}"
            raise CompilationError(msg)

        return tuple(tokens)

    def parse_parameters(self) -> list[ParameterDeclaration]:
        self.expect("(")
        parameters: list[ParameterDeclaration] = []

        if self.match(")"):
            return parameters

        while True:
            modifiers: list[str] = []

            while self.peek().text.casefold() in PARAMETER_MODIFIERS:
                modifiers.append(self.advance().text.casefold())

            type_ref = self.parse_type()
            name = self.expect_identifier().text
            default_tokens = None
            if self.match("="):
                default_tokens = self.parse_parameter_default()

            parameters.append(
                ParameterDeclaration(name, type_ref, tuple(modifiers), default_tokens)
            )

            if self.match(")"):
                return parameters

            self.expect(",")

    def parse_operator_declaration(self, *, include_body_tokens: bool) -> OperatorDeclaration:
        modifiers: list[str] = []
        native_index = None

        while self.peek().text.casefold() in FUNCTION_MODIFIERS:
            modifier = self.advance().text.casefold()
            modifiers.append(modifier)

            if modifier == "native" and self.match("("):
                native_index = self.parse_integer()
                self.expect(")")

        kind_token = self.expect_identifier()

        try:
            kind = OperatorType(kind_token.text.casefold())
        except ValueError:
            msg = f"Expected operator declaration at {kind_token.line}:{kind_token.column}"
            raise CompilationError(msg) from None

        precedence = None
        if kind is OperatorType.BINARY:
            self.expect("(")
            precedence = self.parse_integer()
            self.expect(")")

        return_type = self.parse_type()

        name_token = self.peek()
        if name_token.type not in (TokenType.SYMBOL, TokenType.IDENTIFIER):
            msg = f"Expected operator name at {name_token.line}:{name_token.column}"
            raise CompilationError(msg)

        name = self.advance().text
        parameters = self.parse_parameters()

        expected_count = 2 if kind is OperatorType.BINARY else 1
        if len(parameters) != expected_count:
            msg = f"{kind} {name!r} requires {expected_count} parameters"
            raise CompilationError(msg)

        declaration = OperatorDeclaration(
            name=name,
            op_type=kind,
            return_type=return_type,
            parameters=parameters,
            native_index=native_index,
            precedence=precedence,
            modifiers=tuple(modifiers),
        )

        if self.match(";"):
            return declaration

        opening = self.expect("{")
        declaration.has_body = True

        if include_body_tokens:
            declaration.body_tokens = []

        depth = 1

        while depth:
            token = self.advance()

            if token.type is TokenType.EOF:
                msg = (
                    f"Unterminated operator body for {name!r}, opened at "
                    f"{opening.line}:{opening.column}"
                )
                raise CompilationError(msg)

            if token.type is TokenType.SYMBOL:
                if token.text == "{":
                    depth += 1
                elif token.text == "}":
                    depth -= 1

            if depth and declaration.body_tokens is not None:
                declaration.body_tokens.append(token)

        return declaration

    def parse_function_header(self) -> FunctionDeclaration:
        modifiers: list[str] = []
        native_index = None

        while self.peek().text.casefold() in FUNCTION_MODIFIERS:
            modifier = self.advance().text.casefold()
            modifiers.append(modifier)

            if modifier == "native" and self.match("("):
                native_index = self.parse_integer()
                self.expect(")")

        kind_token = self.expect_identifier()
        try:
            kind = FunctionType(kind_token.text.casefold())
        except ValueError:
            msg = (
                f"Expected function declaration, got {kind_token.text!r} "
                f"at {kind_token.line}:{kind_token.column}"
            )
            raise CompilationError(msg) from None

        first_type = self.parse_type()

        if self.peek().text == "(":
            # No return type: the first identifier was the function name.
            if first_type.arguments or "." in first_type.name:
                msg = "Function name must be an unqualified identifier"
                raise CompilationError(msg)

            name = first_type.name
            return_type = None
        else:
            return_type = first_type
            name = self.expect_identifier().text

        parameters = self.parse_parameters()

        return FunctionDeclaration(
            name=name,
            return_type=return_type,
            parameters=parameters,
            func_type=kind,
            modifiers=tuple(modifiers),
            native_index=native_index,
        )

    def parse_function_declaration(self, *, include_body_tokens: bool) -> FunctionDeclaration:
        declaration = self.parse_function_header()

        # Declaration without a body.
        if self.match(";"):
            return declaration

        opening = self.expect("{")
        declaration.has_body = True

        if include_body_tokens:
            declaration.body_tokens = []

        depth = 1

        while depth:
            token = self.advance()

            if token.type is TokenType.EOF:
                msg = (
                    f"Unterminated function body for {declaration.name!r}, "
                    f"opened at {opening.line}:{opening.column}"
                )
                raise CompilationError(msg)

            if token.type is TokenType.SYMBOL:
                if token.text == "{":
                    depth += 1
                elif token.text == "}":
                    depth -= 1

            # Exclude the closing brace belonging to the function itself.
            if depth and declaration.body_tokens is not None:
                declaration.body_tokens.append(token)

        return declaration

    def parse_class_declaration(self, *, include_body_tokens: bool) -> ClassDeclaration:
        declaration = self.parse_class_header()

        while self.peek().type is not TokenType.EOF:
            token = self.peek()
            keyword = token.text.casefold()

            # Allow empty declarations between members.
            if self.match(";"):
                continue

            if keyword == "const":
                declaration.constants.append(self.parse_constant_declaration())
                continue

            if keyword == "enum":
                declaration.enums.append(
                    self.parse_enum_declaration(warn_explicit_sentinel=include_body_tokens)
                )
                continue

            if keyword == "struct":
                declaration.structs.append(self.parse_struct_declaration())
                continue

            if keyword == "var":
                declaration.variables.extend(self.parse_variable_declaration())
                continue

            # Check operators before functions: both can begin with native.
            if self.is_operator_start():
                declaration.operators.append(
                    self.parse_operator_declaration(include_body_tokens=include_body_tokens)
                )
                continue

            if keyword in FUNCTION_MODIFIERS or keyword in FunctionType:
                declaration.functions.append(
                    self.parse_function_declaration(include_body_tokens=include_body_tokens)
                )
                continue

            msg = f"Unsupported class member {token.text!r} at {token.line}:{token.column}"
            raise CompilationError(msg)

        return declaration
