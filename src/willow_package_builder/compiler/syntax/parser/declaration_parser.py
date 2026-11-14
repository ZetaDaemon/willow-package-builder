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
    StateDeclaration,
    StructDeclaration,
)
from willow_package_builder.compiler.syntax.keyword import ScriptKeywords
from willow_package_builder.compiler.syntax.lexer import Token, TokenCategory
from willow_package_builder.compiler.syntax.modifiers import (
    ClassModifierName,
    FunctionModifier,
    ParameterModifier,
    StateModifier,
    StructModifier,
    VariableModifier,
)
from willow_package_builder.compiler.syntax.parser.defaults_parser import DefaultsParser
from willow_package_builder.compiler.syntax.punctuation import Operator, Punctuation
from willow_package_builder.logging import CompilationError, SourceLocation, WarningCode, warn
from willow_package_builder.upackage import FName

from .declaration_syntax_parser import DeclarationSyntaxParser


class DeclarationParser(DeclarationSyntaxParser):
    def parse_class_header(self) -> ClassDeclaration:
        start = self.expect_identifier()

        if start not in (ScriptKeywords.CLASS, ScriptKeywords.INTERFACE):
            msg = f"Expected class or interface, got {start} at {start.line}:{start.column}"
            raise CompilationError(msg)

        is_interface = start == ScriptKeywords.INTERFACE
        name = self.expect_identifier().fname

        parent = None
        within = None
        modifiers: list[ClassModifier] = []

        while not self.match(Punctuation.SEMICOLON):
            token = self.peek()

            if token.category is TokenCategory.EOF:
                msg = f"Unterminated class header for {name!r}"
                raise CompilationError(msg)

            token = self.expect_identifier()

            if token == ScriptKeywords.EXTENDS:
                if parent is not None:
                    msg = "Class header declares extends more than once"
                    raise CompilationError(msg)

                parent = self.parse_qualified_name()
                continue

            if token == ScriptKeywords.WITHIN:
                if within is not None:
                    msg = "Class header declares within more than once"
                    raise CompilationError(msg)

                within = self.parse_qualified_name()
                continue

            try:
                modifier_name = ClassModifierName(token)
            except ValueError:
                msg = f"Unrecognised class modifier {token}"
                raise CompilationError(msg) from None

            arguments = None

            if self.peek() == Punctuation.LEFT_PAREN:
                arguments = self.parse_parenthesized_tokens()

            modifiers.append(ClassModifier(modifier_name, arguments))

        return ClassDeclaration(
            name,
            parent,
            is_interface,
            within,
            tuple(modifiers),
            location=SourceLocation(start.line, start.column),
        )

    def parse_constant_declaration(self) -> ConstantDeclaration:
        self.expect(VariableModifier.CONST)
        name = self.expect_identifier().fname
        self.expect(Operator.EQUAL)

        value_tokens: list[Token] = []
        closing_symbols: list[Punctuation] = []
        pairs = {
            Punctuation.LEFT_PAREN: Punctuation.RIGHT_PAREN,
            Punctuation.LEFT_BRACKET: Punctuation.RIGHT_BRACKET,
            Punctuation.LEFT_BRACE: Punctuation.RIGHT_BRACE,
        }

        while True:
            token = self.peek()

            if token.category is TokenCategory.EOF:
                msg = f"Unterminated constant declaration for {name!r}"
                raise CompilationError(msg)

            if token == Punctuation.SEMICOLON and not closing_symbols:
                self.advance()
                break

            if token.category is TokenCategory.SYMBOL:
                for opening, closing in pairs.items():
                    if token == opening:
                        closing_symbols.append(closing)
                        break
                else:
                    if token in pairs.values():
                        if not closing_symbols or token != closing_symbols[-1]:
                            msg = (
                                f"Unexpected {token} in constant {name!r} "
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
        self.expect(ScriptKeywords.ENUM)
        name = self.expect_identifier().fname
        opening = self.expect(Punctuation.LEFT_BRACE)

        members: list[FName] = []

        while not self.match(Punctuation.RIGHT_BRACE):
            token = self.peek()

            if token.category is TokenCategory.EOF:
                msg = f"Unterminated enum {name!r}, opened at {opening.line}:{opening.column}"
                raise CompilationError(msg)

            member = self.expect_identifier()
            member_name = member.fname

            if member_name in members and not allow_duplicate_members:
                msg = f"Duplicate enum member {member} at {member.line}:{member.column}"
                raise CompilationError(msg)

            members.append(member_name)

            if self.match(Punctuation.RIGHT_BRACE):
                break

            self.expect(Punctuation.COMMA)

        self.expect(Punctuation.SEMICOLON)

        if not members:
            msg = f"Enum {name!r} must contain at least one member"
            raise CompilationError(msg)

        prefix = str(members[0]).split("_", 1)[0]
        sentinel = FName(f"{prefix}_MAX")

        if members[-1] == sentinel:
            if warn_explicit_sentinel:
                warn(WarningCode.EXPLICIT_ENUM_SENTINEL, f"Explicit _MAX member in enum {name}")

            members.pop()

        if not members:
            msg = f"Enum {name!r} has no non-sentinel members"
            raise CompilationError(msg)

        return EnumDeclaration(name, tuple(members))

    def parse_struct_declaration(self, *, reference_only: bool = False) -> StructDeclaration:
        start = self.expect(ScriptKeywords.STRUCT)

        modifiers: list[StructModifier] = []

        while self.peek() in StructModifier:
            modifiers.append(StructModifier(self.advance()))

        name = self.expect_identifier().fname

        parent = None
        if self.match(ScriptKeywords.EXTENDS):
            parent = self.parse_qualified_name()

        declaration = StructDeclaration(
            name, parent, tuple(modifiers), location=SourceLocation(start.line, start.column)
        )

        opening = self.expect(Punctuation.LEFT_BRACE)

        while not self.match(Punctuation.RIGHT_BRACE):
            token = self.peek()

            if token.category is TokenCategory.EOF:
                msg = f"Unterminated struct {name!r}, opened at {opening.line}:{opening.column}"
                raise CompilationError(msg)

            if self.match(Punctuation.SEMICOLON):
                continue

            if token == ScriptKeywords.VAR:
                declaration.variables.extend(self.parse_variable_declaration())
                continue

            if token == ScriptKeywords.STRUCT_DEFAULT_PROPERTIES:
                if declaration.default_tokens is not None:
                    msg = f"Struct {name!r} has multiple default blocks"
                    raise CompilationError(msg)

                self.advance()
                declaration.default_tokens = self.parse_braced_tokens()
                self.parse_declared_defaults(declaration, reference_only=reference_only)
                continue

            msg = f"Unsupported struct member {token} at {token.line}:{token.column}"
            raise CompilationError(msg)

        self.expect(Punctuation.SEMICOLON)
        return declaration

    def is_operator_start(self) -> bool:
        offset = 0

        while (modifier := self.peek(offset)) in FunctionModifier:
            offset += 1

            if modifier == FunctionModifier.NATIVE and self.peek(offset) == Punctuation.LEFT_PAREN:
                offset += 1

                if self.peek(offset).category is not TokenCategory.INTEGER:
                    return False

                offset += 1

                if self.peek(offset) != Punctuation.RIGHT_PAREN:
                    return False

                offset += 1

        return self.peek(offset) in OperatorCategory

    def parse_parameter_default(self) -> tuple[Token, ...]:
        tokens: list[Token] = []
        closing_symbols: list[Punctuation] = []
        pairs = {
            Punctuation.LEFT_BRACE: Punctuation.RIGHT_BRACE,
            Punctuation.LEFT_BRACKET: Punctuation.RIGHT_BRACKET,
            Punctuation.LEFT_PAREN: Punctuation.RIGHT_PAREN,
        }

        while True:
            token = self.peek()

            if token.category is TokenCategory.EOF:
                msg = f"Unterminated parameter default at {token.line}:{token.column}"
                raise CompilationError(msg)

            if token.category is TokenCategory.SYMBOL:
                if not closing_symbols and token in (Punctuation.COMMA, Punctuation.RIGHT_PAREN):
                    break

                for opening, closing in pairs.items():
                    if token == opening:
                        closing_symbols.append(closing)
                        break
                else:
                    if token in pairs.values():
                        if not closing_symbols or token != closing_symbols[-1]:
                            msg = (
                                f"Unexpected {token} in parameter default "
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
        self.expect(Punctuation.LEFT_PAREN)
        parameters: list[ParameterDeclaration] = []

        if self.match(Punctuation.RIGHT_PAREN):
            return parameters

        while True:
            modifiers: list[ParameterModifier] = []

            while self.peek() in ParameterModifier:
                modifiers.append(ParameterModifier(self.advance()))

            type_ref = self.parse_type()
            name_token = self.expect_identifier()
            array_dimension, array_dimension_name = self.parse_array_dimension()

            default_tokens = None
            if self.match(Operator.EQUAL):
                default_tokens = self.parse_parameter_default()

            parameters.append(
                ParameterDeclaration(
                    name_token.fname,
                    type_ref,
                    tuple(modifiers),
                    default_tokens,
                    array_dimension,
                    array_dimension_name,
                    location=SourceLocation(name_token.line, name_token.column),
                )
            )

            if self.match(Punctuation.RIGHT_PAREN):
                return parameters

            self.expect(Punctuation.COMMA)

    def parse_operator_declaration(self, *, include_body_tokens: bool) -> OperatorDeclaration:
        modifiers: list[FunctionModifier] = []
        native_index = None
        start = self.peek()

        while self.peek() in FunctionModifier:
            token = self.advance()
            try:
                modifier = FunctionModifier(token)
            except ValueError:
                msg = f"Unknown operator modifier {token} at {token.line}:{token.column}"
                raise CompilationError(msg) from None

            modifiers.append(modifier)

            if modifier == FunctionModifier.NATIVE and self.match(Punctuation.LEFT_PAREN):
                native_index = self.parse_integer()
                self.expect(Punctuation.RIGHT_PAREN)

        category_token = self.expect_identifier()

        try:
            category = OperatorCategory(category_token)
        except ValueError:
            msg = f"Expected operator declaration at {category_token.line}:{category_token.column}"
            raise CompilationError(msg) from None

        precedence = None
        if category is OperatorCategory.BINARY:
            self.expect(Punctuation.LEFT_PAREN)
            precedence = self.parse_integer()
            self.expect(Punctuation.RIGHT_PAREN)

        return_type = self.parse_type()

        name_token = self.peek()
        if name_token.category not in (TokenCategory.SYMBOL, TokenCategory.IDENTIFIER):
            msg = f"Expected operator name at {name_token.line}:{name_token.column}"
            raise CompilationError(msg)

        name_token = self.advance()
        parameters = self.parse_parameters()

        expected_count = 2 if category is OperatorCategory.BINARY else 1
        if len(parameters) != expected_count:
            msg = f"{category} {name_token} requires {expected_count} parameters"
            raise CompilationError(msg)

        # Symbol operators such as + aren't identifier tokens
        operator_name = name_token.operator_name
        if operator_name is None:
            msg = f"Expected an operator name, got {name_token}"
            raise CompilationError(msg)
        declaration = OperatorDeclaration(
            operator_name,
            category,
            return_type,
            parameters,
            native_index,
            precedence,
            tuple(modifiers),
            location=SourceLocation(start.line, start.column),
        )

        if self.match(Punctuation.SEMICOLON):
            return declaration

        opening = self.expect(Punctuation.LEFT_BRACE)
        declaration.has_body = True

        if include_body_tokens:
            declaration.body_tokens = []

        depth = 1

        while depth:
            token = self.advance()

            if token.category is TokenCategory.EOF:
                msg = (
                    f"Unterminated operator body for {name_token}, opened at "
                    f"{opening.line}:{opening.column}"
                )
                raise CompilationError(msg)

            if token.category is TokenCategory.SYMBOL:
                if token == Punctuation.LEFT_BRACE:
                    depth += 1
                elif token == Punctuation.RIGHT_BRACE:
                    depth -= 1

            if depth and declaration.body_tokens is not None:
                declaration.body_tokens.append(token)

        return declaration

    def parse_function_header(self) -> FunctionDeclaration:
        modifiers: list[FunctionModifier] = []
        native_index = None

        start = self.peek()

        while self.peek() in FunctionModifier:
            token = self.advance()
            try:
                modifier = FunctionModifier(token)
            except ValueError:
                msg = f"Unknown function modifier {token} at {token.line}:{token.column}"
                raise CompilationError(msg) from None

            modifiers.append(modifier)

            if modifier == FunctionModifier.NATIVE and self.match(Punctuation.LEFT_PAREN):
                native_index = self.parse_integer()
                self.expect(Punctuation.RIGHT_PAREN)

        category_token = self.expect_identifier()
        try:
            category = FunctionCategory(category_token)
        except ValueError:
            msg = (
                f"Expected function declaration, got {category_token} "
                f"at {category_token.line}:{category_token.column}"
            )
            raise CompilationError(msg) from None

        first_type = self.parse_type()

        if self.peek() == Punctuation.LEFT_PAREN:
            # No return type: the first identifier was the function name.
            if first_type.arguments or "." in str(first_type.name):
                msg = "Function name must be an unqualified identifier"
                raise CompilationError(msg)

            name = first_type.name.name
            return_type = None
        else:
            return_type = first_type
            name = self.expect_identifier().fname

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
        if self.match(Punctuation.SEMICOLON):
            return declaration

        opening = self.expect(Punctuation.LEFT_BRACE)
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
                if token == Punctuation.LEFT_BRACE:
                    depth += 1
                elif token == Punctuation.RIGHT_BRACE:
                    depth -= 1

            # Exclude the closing brace belonging to the function itself.
            if depth and declaration.body_tokens is not None:
                declaration.body_tokens.append(token)

        return declaration

    def parse_class_declaration(self, *, include_body_tokens: bool) -> ClassDeclaration:
        declaration = self.parse_class_header()

        while self.peek().category is not TokenCategory.EOF:
            token = self.peek()

            # Allow empty declarations between members.
            if self.match(Punctuation.SEMICOLON):
                continue

            if token == VariableModifier.CONST:
                declaration.constants.append(self.parse_constant_declaration())
                continue

            if token == ScriptKeywords.ENUM:
                declaration.enums.append(
                    self.parse_enum_declaration(
                        warn_explicit_sentinel=include_body_tokens,
                        allow_duplicate_members=not include_body_tokens,
                    )
                )
                continue

            if token == ScriptKeywords.STRUCT:
                declaration.structs.append(
                    self.parse_struct_declaration(reference_only=not include_body_tokens)
                )
                continue

            if token == ScriptKeywords.VAR:
                declaration.variables.extend(self.parse_variable_declaration())
                continue

            if token == ScriptKeywords.DEFAULT_PROPERTIES:
                if declaration.default_tokens is not None:
                    msg = f"Class {declaration.name!r} has multiple default blocks"
                    raise CompilationError(msg)

                self.advance()
                declaration.default_tokens = self.parse_braced_tokens()
                self.parse_declared_defaults(declaration, reference_only=not include_body_tokens)
                continue

            if token == ScriptKeywords.REPLICATION:
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
                declaration.states.append(
                    self.parse_state_declaration(include_body_tokens=include_body_tokens)
                )
                continue

            # Check operators before functions: both can begin with native.
            if self.is_operator_start():
                declaration.operators.append(
                    self.parse_operator_declaration(include_body_tokens=include_body_tokens)
                )
                continue

            if token in FunctionModifier or token in FunctionCategory:
                declaration.functions.append(
                    self.parse_function_declaration(include_body_tokens=include_body_tokens)
                )
                continue

            msg = f"Unsupported class member {token} at {token.line}:{token.column}"
            raise CompilationError(msg)

        return declaration

    def is_state_start(self) -> bool:
        offset = 0

        while self.peek(offset) in StateModifier:
            offset += 1

        return self.peek(offset) == ScriptKeywords.STATE

    def parse_state_declaration(self, *, include_body_tokens: bool) -> StateDeclaration:
        start = self.peek()
        modifiers: list[StateModifier] = []

        while self.peek() in StateModifier:
            modifiers.append(StateModifier(self.advance()))

        self.expect(ScriptKeywords.STATE)

        editable = self.match(Punctuation.LEFT_PAREN)
        if editable:
            self.expect(Punctuation.RIGHT_PAREN)

        name = self.expect_identifier().fname
        parent = None
        if self.match(ScriptKeywords.EXTENDS):
            parent = self.expect_identifier().fname

        body_tokens = self.parse_braced_tokens()
        closing = self.tokens[self.position - 1]
        eof = Token(TokenCategory.EOF, "", closing.line, closing.column)
        parser = DeclarationParser([*body_tokens, eof])

        state = StateDeclaration(
            name=name,
            parent=parent,
            modifiers=tuple(modifiers),
            editable=editable,
            location=SourceLocation(start.line, start.column),
        )

        while parser.peek().category is not TokenCategory.EOF:
            if parser.match(ScriptKeywords.IGNORES):
                state.ignores.append(parser.expect_identifier().fname)
                while parser.match(Punctuation.COMMA):
                    state.ignores.append(parser.expect_identifier().fname)

                parser.expect(Punctuation.SEMICOLON)
                continue

            token = parser.peek()
            if token in FunctionModifier or token in FunctionCategory:
                state.functions.append(
                    parser.parse_function_declaration(include_body_tokens=include_body_tokens)
                )
                continue

            if include_body_tokens:
                state.code_tokens = body_tokens[parser.position :]
            break

        return state

    def parse_declared_defaults(
        self, declaration: ClassDeclaration | StructDeclaration, *, reference_only: bool
    ) -> None:
        tokens = declaration.default_tokens

        if tokens is None:
            msg = "Default tokens have not been captured"
            raise ValueError(msg)

        parser = DefaultsParser.from_default_tokens(tokens)

        try:
            parsed = parser.parse_defaults(include_object_properties=not reference_only)

            if isinstance(declaration, StructDeclaration) and parser.default_objects:
                msg = "Object declarations inside struct defaults are not implemented"
                raise NotImplementedError(msg)
        except CompilationError as error:
            if not reference_only:
                raise

            declaration.parsed_defaults = {}
            if isinstance(declaration, ClassDeclaration):
                declaration.default_objects = []
            declaration.default_parse_error = str(error)
        else:
            declaration.parsed_defaults = parsed
            if isinstance(declaration, ClassDeclaration):
                if reference_only:
                    declaration.reference_default_objects = parser.default_objects
                else:
                    declaration.default_objects = parser.default_objects
