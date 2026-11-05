import contextlib
import json
from dataclasses import KW_ONLY, dataclass, fields, is_dataclass
from enum import Enum
from hashlib import sha256
from pathlib import Path
from typing import TYPE_CHECKING

from willow_package_builder.compiler.source import decode_source
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
    TypeReference,
    VariableDeclaration,
)
from willow_package_builder.compiler.syntax.lexer import Lexer, Token, TokenCategory
from willow_package_builder.compiler.syntax.modifiers import (
    ClassModifierName,
    FunctionModifier,
    ParameterModifier,
    StructModifier,
    VariableModifier,
)
from willow_package_builder.compiler.syntax.parser import DeclarationParser
from willow_package_builder.compiler.syntax.parser.defaults_parser import IndexedArrayDefaults
from willow_package_builder.logging import CompilationError, SourceLocation, info
from willow_package_builder.properties.values import (
    ArrayValue,
    BoolValue,
    DelegateValue,
    EmptyValue,
    EnumValue,
    FloatValue,
    IdentifierValue,
    IntValue,
    NameValue,
    NullValue,
    ObjectValue,
    StringValue,
    StructValue,
)
from willow_package_builder.upackage import FName, Name, ReferencePath

if TYPE_CHECKING:
    from collections.abc import Callable

    from willow_package_builder.package_config import PackageConfig


CLASS_CACHE_SCHEMA_VERSION = 15
DECLARATION_PARSER_VERSION = 13


@dataclass
class CachedClass:
    package_name: str
    source_path: str
    source_hash: str
    declaration: ClassDeclaration

    schema_version: int = CLASS_CACHE_SCHEMA_VERSION
    parser_version: int = DECLARATION_PARSER_VERSION

    _: KW_ONLY

    includes_body_tokens: bool


CACHE_TYPES: dict[str, Callable[..., object]] = {
    cls.__name__: cls
    for cls in (
        CachedClass,
        ClassDeclaration,
        ClassModifier,
        ConstantDeclaration,
        EnumDeclaration,
        FunctionDeclaration,
        OperatorDeclaration,
        ParameterDeclaration,
        StructDeclaration,
        TypeReference,
        VariableDeclaration,
        Token,
        IntValue,
        FloatValue,
        BoolValue,
        StringValue,
        NullValue,
        NameValue,
        IdentifierValue,
        ObjectValue,
        ArrayValue,
        StructValue,
        EmptyValue,
        EnumValue,
        SourceLocation,
        FName,
        Name,
        IndexedArrayDefaults,
        DelegateValue,
        ReferencePath,
    )
}

CACHE_ENUMS: dict[str, type[Enum]] = {
    cls.__name__: cls
    for cls in (
        FunctionCategory,
        OperatorCategory,
        TokenCategory,
        FunctionModifier,
        ParameterModifier,
        ClassModifierName,
        VariableModifier,
        StructModifier,
    )
}


def encode_cache_value(value: object) -> object:
    # Check before str/int because StrEnum and IntEnum inherit them.
    if isinstance(value, Enum):
        return {"$enum": type(value).__name__, "name": value.name}

    if isinstance(value, Name):
        return {"$type": "Name", "fields": {"name": str(value)}}

    if is_dataclass(value) and not isinstance(value, type):
        return {
            "$type": type(value).__name__,
            "fields": {
                item.name: encode_cache_value(getattr(value, item.name)) for item in fields(value)
            },
        }

    if isinstance(value, tuple):
        return {"$tuple": [encode_cache_value(item) for item in value]}

    if isinstance(value, list):
        return [encode_cache_value(item) for item in value]

    if isinstance(value, dict):
        return {
            "$dict": [
                [encode_cache_value(key), encode_cache_value(item)] for key, item in value.items()
            ]
        }

    if value is None or isinstance(value, (str, int, float, bool)):
        return value

    msg = f"Unsupported cache value type: {type(value).__name__}"
    raise TypeError(msg)


def write_cached_class(path: Path, cached: CachedClass) -> None:
    data = encode_cache_value(cached)

    text = json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text + "\n", encoding="utf-8")


def decode_cache_value(value: object) -> object:
    match value:
        case list():
            return [decode_cache_value(item) for item in value]

        case dict():
            if "$dict" in value:
                pairs = value["$dict"]

                if not isinstance(pairs, list):
                    msg = "Cached dictionary must contain a list of pairs"
                    raise ValueError(msg)

                result: dict[object, object] = {}

                for pair in pairs:
                    if not isinstance(pair, list) or len(pair) != 2:
                        msg = "Invalid cached dictionary entry"
                        raise ValueError(msg)

                    key = decode_cache_value(pair[0])
                    result[key] = decode_cache_value(pair[1])

                return result
            if "$tuple" in value:
                items = value["$tuple"]

                if not isinstance(items, list):
                    msg = "Cached tuple must contain a list"
                    raise ValueError(msg)

                return tuple(decode_cache_value(item) for item in items)

            if "$enum" in value:
                enum_name = value["$enum"]
                member_name = value.get("name")

                if not isinstance(enum_name, str) or not isinstance(member_name, str):
                    msg = "Invalid cached enum"
                    raise ValueError(msg)

                enum_type = CACHE_ENUMS.get(enum_name)
                if enum_type is None:
                    msg = f"Unknown cached enum: {enum_name!r}"
                    raise ValueError(msg)

                try:
                    return enum_type[member_name]
                except KeyError:
                    msg = f"Unknown member {member_name!r} of {enum_name}"
                    raise ValueError(msg) from None

            if "$type" in value:
                type_name = value["$type"]
                encoded_fields = value.get("fields")

                if not isinstance(type_name, str) or not isinstance(encoded_fields, dict):
                    msg = "Invalid cached declaration"
                    raise ValueError(msg)

                constructor = CACHE_TYPES.get(type_name)
                if constructor is None:
                    msg = f"Unknown cached type: {type_name!r}"
                    raise ValueError(msg)

                if not all(isinstance(key, str) for key in encoded_fields):
                    msg = "Cached field names must be strings"
                    raise ValueError(msg)

                decoded_fields = {
                    key: decode_cache_value(item) for key, item in encoded_fields.items()
                }

                return constructor(**decoded_fields)

            msg = "Unrecognized cache object"
            raise ValueError(msg)

        case str() | int() | float() | bool() | None:
            return value

        case _:
            msg = f"Unsupported cache value type: {type(value).__name__}"
            raise TypeError(msg)


def read_cached_class(path: Path) -> CachedClass:
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    cached = decode_cache_value(data)

    if not isinstance(cached, CachedClass):
        msg = f"Cache does not contain a CachedClass: {path}"
        raise ValueError(msg)  # noqa: TRY004

    return cached


def load_or_parse_class(
    config: PackageConfig, source_path: Path, *, include_body_tokens: bool
) -> CachedClass:
    source_path = source_path.resolve()
    relative_path = source_path.relative_to(config.directory).as_posix()

    source_bytes = source_path.read_bytes()
    source_hash = sha256(source_bytes).hexdigest()

    cache_path = config.directory / ".willow-cache" / Path(relative_path).with_suffix(".json")

    cached = None

    with contextlib.suppress(OSError, ValueError, TypeError, KeyError):
        cached = read_cached_class(cache_path)

    if (
        cached is not None
        and cached.schema_version == CLASS_CACHE_SCHEMA_VERSION
        and cached.parser_version == DECLARATION_PARSER_VERSION
        and cached.package_name == config.name
        and cached.source_path == relative_path
        and cached.source_hash == source_hash
        and isinstance(cached.declaration, ClassDeclaration)  # pyright: ignore[reportUnnecessaryIsInstance]
        and (not include_body_tokens or cached.includes_body_tokens)
    ):
        return cached

    if include_body_tokens:
        info(f"Parsing class {config.name}.{source_path.stem}")
    else:
        info(f"Parsing reference class {config.name}.{source_path.stem}")
    source = decode_source(source_bytes, source_path)

    try:
        declaration = DeclarationParser(Lexer(source).tokenize()).parse_class_declaration(
            include_body_tokens=include_body_tokens
        )
    except CompilationError as error:
        if error.context is None:
            error.context = str(source_path)
        raise

    cached = CachedClass(
        config.name,
        relative_path,
        source_hash,
        declaration,
        includes_body_tokens=include_body_tokens,
    )

    write_cached_class(cache_path, cached)
    return cached
