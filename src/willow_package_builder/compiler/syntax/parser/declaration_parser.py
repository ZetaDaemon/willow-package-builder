from willow_package_builder.compiler.syntax.declarations import (
    ClassDeclaration,
    ClassModifier,
    ConstantDeclaration,
    EnumDeclaration,
    FunctionCategory,
    FunctionDeclaration,
    OperatorCategory,
    OperatorDeclaration,
    ParameterDeclaration,
    StructDeclaration,
)
from willow_package_builder.compiler.syntax.lexer import Token, TokenCategory
from willow_package_builder.compiler.syntax.modifiers import (
    ClassModifierName,
    FunctionModifier,
    ParameterModifier,
    StateModifier,
    StructModifier,
)
from willow_package_builder.compiler.syntax.parser.defaults_parser import DefaultsParser
from willow_package_builder.logging import CompilationError, SourceLocation, WarningCode, warn

from .declaration_syntax_parser import DeclarationSyntaxParser


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

            if token.category is TokenCategory.EOF:
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

            try:
                modifier_name = ClassModifierName(keyword)
            except ValueError:
                msg = f"Unrecognised class modifier {keyword}"
                raise CompilationError(msg) from None

            arguments = None
            if self.peek().text == "(":
                arguments = self.parse_parenthesized_tokens()

            modifiers.append(ClassModifier(modifier_name, arguments))

        return ClassDeclaration(
            name,
            parent,
            is_interface,
            within,
            tuple(modifiers),
            location=SourceLocation(token.line, token.column),
        )

    def parse_constant_declaration(self) -> ConstantDeclaration:
        self.expect("const")
        name = self.expect_identifier().text
        self.expect("=")

        value_tokens: list[Token] = []
        closing_symbols: list[str] = []
        pairs = {"(": ")", "[": "]", "{": "}"}

        while True:
            token = self.peek()

            if token.category is TokenCategory.EOF:
                msg = f"Unterminated constant declaration for {name!r}"
                raise CompilationError(msg)

            if token.text == ";" and not closing_symbols:
                self.advance()
                break

            if token.category is TokenCategory.SYMBOL:
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

        return ConstantDeclaration(name, tuple(value_tokens))

    def parse_enum_declaration(
        self, *, warn_explicit_sentinel: bool = True, allow_duplicate_members: bool = False
    ) -> EnumDeclaration:
        self.expect("enum")
        name = self.expect_identifier().text
        opening = self.expect("{")

        members: list[str] = []
        seen: set[str] = set()

        while not self.match("}"):
            token = self.peek()

            if token.category is TokenCategory.EOF:
                msg = f"Unterminated enum {name!r}, opened at {opening.line}:{opening.column}"
                raise CompilationError(msg)

            member = self.expect_identifier()
            key = member.text.casefold()

            if key in seen and not allow_duplicate_members:
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

        return EnumDeclaration(name, tuple(members))

    def parse_struct_declaration(self, *, reference_only: bool = False) -> StructDeclaration:
        start = self.expect("struct")

        modifiers: list[StructModifier] = []

        while self.peek().text.casefold() in StructModifier:
            modifiers.append(StructModifier(self.advance().text.casefold()))

        name = self.expect_identifier().text

        parent = None
        if self.match("extends"):
            parent = self.parse_qualified_name()

        declaration = StructDeclaration(
            name, parent, tuple(modifiers), location=SourceLocation(start.line, start.column)
        )

        opening = self.expect("{")

        while not self.match("}"):
            token = self.peek()
            keyword = token.text.casefold()

            if token.category is TokenCategory.EOF:
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
                self.parse_declared_defaults(declaration, reference_only=reference_only)
                continue

            msg = f"Unsupported struct member {token.text!r} at {token.line}:{token.column}"
            raise CompilationError(msg)

        self.expect(";")
        return declaration

    def is_operator_start(self) -> bool:
        offset = 0

        while self.peek(offset).text.casefold() in FunctionModifier:
            modifier = self.peek(offset).text.casefold()
            offset += 1

            if modifier == FunctionModifier.NATIVE and self.peek(offset).text == "(":
                offset += 1

                if self.peek(offset).category is not TokenCategory.INTEGER:
                    return False

                offset += 1

                if self.peek(offset).text != ")":
                    return False

                offset += 1

        return self.peek(offset).text.casefold() in OperatorCategory

    def parse_parameter_default(self) -> tuple[Token, ...]:
        tokens: list[Token] = []
        closing_symbols: list[str] = []
        pairs = {"(": ")", "[": "]", "{": "}"}

        while True:
            token = self.peek()

            if token.category is TokenCategory.EOF:
                msg = f"Unterminated parameter default at {token.line}:{token.column}"
                raise CompilationError(msg)

            if token.category is TokenCategory.SYMBOL:
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
            modifiers: list[ParameterModifier] = []

            while self.peek().text.casefold() in ParameterModifier:
                modifier = self.advance().text.casefold()
                try:
                    modifier = ParameterModifier(modifier)
                except ValueError:
                    msg = f"Unrecognised parameter modifier {modifier}"
                    raise CompilationError(msg) from None

                modifiers.append(modifier)

            type_ref = self.parse_type()
            name_token = self.expect_identifier()
            name = name_token.text
            array_dimension, array_dimension_name = self.parse_array_dimension()

            default_tokens = None
            if self.match("="):
                default_tokens = self.parse_parameter_default()

            parameters.append(
                ParameterDeclaration(
                    name,
                    type_ref,
                    tuple(modifiers),
                    default_tokens,
                    array_dimension,
                    array_dimension_name,
                    location=SourceLocation(name_token.line, name_token.column),
                )
            )

            if self.match(")"):
                return parameters

            self.expect(",")

    def parse_operator_declaration(self, *, include_body_tokens: bool) -> OperatorDeclaration:
        modifiers: list[FunctionModifier] = []
        native_index = None
        start = self.peek()

        while self.peek().text.casefold() in FunctionModifier:
            token = self.advance()
            try:
                modifier = FunctionModifier(token.text.casefold())
            except ValueError:
                msg = f"Unknown operator modifier {token.text!r} at {token.line}:{token.column}"
                raise CompilationError(msg) from None

            modifiers.append(modifier)

            if modifier == FunctionModifier.NATIVE and self.match("("):
                native_index = self.parse_integer()
                self.expect(")")

        category_token = self.expect_identifier()

        try:
            category = OperatorCategory(category_token.text.casefold())
        except ValueError:
            msg = f"Expected operator declaration at {category_token.line}:{category_token.column}"
            raise CompilationError(msg) from None

        precedence = None
        if category is OperatorCategory.BINARY:
            self.expect("(")
            precedence = self.parse_integer()
            self.expect(")")

        return_type = self.parse_type()

        name_token = self.peek()
        if name_token.category not in (TokenCategory.SYMBOL, TokenCategory.IDENTIFIER):
            msg = f"Expected operator name at {name_token.line}:{name_token.column}"
            raise CompilationError(msg)

        name = self.advance().text
        parameters = self.parse_parameters()

        expected_count = 2 if category is OperatorCategory.BINARY else 1
        if len(parameters) != expected_count:
            msg = f"{category} {name!r} requires {expected_count} parameters"
            raise CompilationError(msg)

        declaration = OperatorDeclaration(
            name,
            category,
            return_type,
            parameters,
            native_index,
            precedence,
            tuple(modifiers),
            location=SourceLocation(start.line, start.column),
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

            if token.category is TokenCategory.EOF:
                msg = (
                    f"Unterminated operator body for {name!r}, opened at "
                    f"{opening.line}:{opening.column}"
                )
                raise CompilationError(msg)

            if token.category is TokenCategory.SYMBOL:
                if token.text == "{":
                    depth += 1
                elif token.text == "}":
                    depth -= 1

            if depth and declaration.body_tokens is not None:
                declaration.body_tokens.append(token)

        return declaration

    def parse_function_header(self) -> FunctionDeclaration:
        modifiers: list[FunctionModifier] = []
        native_index = None

        start = self.peek()

        while self.peek().text.casefold() in FunctionModifier:
            token = self.advance()
            try:
                modifier = FunctionModifier(token.text.casefold())
            except ValueError:
                msg = f"Unknown function modifier {token.text!r} at {token.line}:{token.column}"
                raise CompilationError(msg) from None

            modifiers.append(modifier)

            if modifier == FunctionModifier.NATIVE and self.match("("):
                native_index = self.parse_integer()
                self.expect(")")

        category_token = self.expect_identifier()
        try:
            category = FunctionCategory(category_token.text.casefold())
        except ValueError:
            msg = (
                f"Expected function declaration, got {category_token.text!r} "
                f"at {category_token.line}:{category_token.column}"
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
            name,
            return_type,
            parameters,
            category,
            tuple(modifiers),
            native_index,
            location=SourceLocation(start.line, start.column),
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

            if token.category is TokenCategory.EOF:
                msg = (
                    f"Unterminated function body for {declaration.name!r}, "
                    f"opened at {opening.line}:{opening.column}"
                )
                raise CompilationError(msg)

            if token.category is TokenCategory.SYMBOL:
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

        while self.peek().category is not TokenCategory.EOF:
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
                    self.parse_enum_declaration(
                        warn_explicit_sentinel=include_body_tokens,
                        allow_duplicate_members=not include_body_tokens,
                    )
                )
                continue

            if keyword == "struct":
                declaration.structs.append(
                    self.parse_struct_declaration(reference_only=not include_body_tokens)
                )
                continue

            if keyword == "var":
                declaration.variables.extend(self.parse_variable_declaration())
                continue

            if keyword == "defaultproperties":
                if declaration.default_tokens is not None:
                    msg = f"Class {declaration.name!r} has multiple default blocks"
                    raise CompilationError(msg)

                self.advance()
                declaration.default_tokens = self.parse_braced_tokens()
                self.parse_declared_defaults(declaration, reference_only=not include_body_tokens)
                continue

            if keyword == "replication":
                if include_body_tokens:
                    msg = (
                        f"Replication blocks are not implemented in "
                        f"{declaration.name} at {token.line}:{token.column}"
                    )
                    raise NotImplementedError(msg)

                self.advance()
                self.parse_braced_tokens()
                continue

            if self.is_state_start():
                if include_body_tokens:
                    msg = (
                        f"State compilation is not implemented in "
                        f"{declaration.name} at {token.line}:{token.column}"
                    )
                    raise NotImplementedError(msg)

                self.skip_state_declaration()
                continue

            # Check operators before functions: both can begin with native.
            if self.is_operator_start():
                declaration.operators.append(
                    self.parse_operator_declaration(include_body_tokens=include_body_tokens)
                )
                continue

            if keyword in FunctionModifier or keyword in FunctionCategory:
                declaration.functions.append(
                    self.parse_function_declaration(include_body_tokens=include_body_tokens)
                )
                continue

            msg = f"Unsupported class member {token.text!r} at {token.line}:{token.column}"
            raise CompilationError(msg)

        return declaration

    def is_state_start(self) -> bool:
        offset = 0

        while self.peek(offset).text.casefold() in StateModifier:
            offset += 1

        return self.peek(offset).text.casefold() == "state"

    def skip_state_declaration(self) -> None:
        while self.peek().text.casefold() in StateModifier:
            self.advance()

        self.expect("state")

        if self.peek().text == "(":
            self.parse_parenthesized_tokens()

        self.expect_identifier()

        if self.match("extends"):
            self.expect_identifier()

        self.parse_braced_tokens()

    def parse_declared_defaults(
        self, declaration: ClassDeclaration | StructDeclaration, *, reference_only: bool
    ) -> None:
        tokens = declaration.default_tokens

        if tokens is None:
            msg = "Default tokens have not been captured"
            raise ValueError(msg)

        parser = DefaultsParser.from_default_tokens(tokens)

        try:
            parsed = parser.parse_defaults(skip_object_definitions=reference_only)
        except CompilationError as error:
            if not reference_only:
                raise

            declaration.parsed_defaults = {}
            declaration.default_parse_error = str(error)
        else:
            declaration.parsed_defaults = parsed
            declaration.default_parse_error = None
