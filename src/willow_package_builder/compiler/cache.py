import contextlib
import json
from dataclasses import dataclass, fields, is_dataclass
from enum import Enum
from hashlib import sha256
from pathlib import Path
from typing import TYPE_CHECKING

from willow_package_builder.logging import CompilationError

from .declarations import (
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
    TypeReference,
    VariableDeclaration,
)
from .lexer import Lexer, Token, TokenType
from .parser import Parser

if TYPE_CHECKING:
    from collections.abc import Callable

    from willow_package_builder.package_config import PackageConfig


CLASS_CACHE_SCHEMA_VERSION = 1
DECLARATION_PARSER_VERSION = 3


@dataclass
class CachedClass:
    package_name: str
    source_path: str
    source_hash: str
    declaration: ClassDeclaration

    includes_body_tokens: bool

    schema_version: int = CLASS_CACHE_SCHEMA_VERSION
    parser_version: int = DECLARATION_PARSER_VERSION


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
    )
}

CACHE_ENUMS: dict[str, type[Enum]] = {
    cls.__name__: cls for cls in (FunctionType, OperatorType, TokenType)
}


def encode_cache_value(value: object) -> object:
    # Check before str/int because StrEnum and IntEnum inherit them.
    if isinstance(value, Enum):
        return {"$enum": type(value).__name__, "name": value.name}

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
    if isinstance(value, list):
        return [decode_cache_value(item) for item in value]

    if isinstance(value, dict):
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

            decoded_fields = {key: decode_cache_value(item) for key, item in encoded_fields.items()}

            return constructor(**decoded_fields)

        msg = "Unrecognized cache object"
        raise ValueError(msg)

    if value is None or isinstance(value, (str, int, float, bool)):
        return value

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

    source = source_bytes.decode("utf-8-sig")

    try:
        declaration = Parser(Lexer(source).tokenize()).parse_class_declaration(
            include_body_tokens=include_body_tokens
        )
    except CompilationError as exc:
        msg = f"{source_path}: {exc}"
        raise CompilationError(msg) from exc

    cached = CachedClass(
        package_name=config.name,
        source_path=relative_path,
        source_hash=source_hash,
        declaration=declaration,
        includes_body_tokens=include_body_tokens,
    )

    write_cached_class(cache_path, cached)
    return cached
