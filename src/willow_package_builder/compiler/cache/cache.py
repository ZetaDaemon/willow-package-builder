import contextlib
import pickle
from dataclasses import KW_ONLY, dataclass
from hashlib import sha256
from pathlib import Path
from typing import TYPE_CHECKING

from willow_package_builder.build_settings import get_build_settings
from willow_package_builder.compiler.source import decode_source
from willow_package_builder.compiler.syntax.declarations import ClassDeclaration
from willow_package_builder.compiler.syntax.lexer import Lexer
from willow_package_builder.compiler.syntax.parser import DeclarationParser
from willow_package_builder.logging import CompilationError, info

if TYPE_CHECKING:
    from willow_package_builder.package_config import PackageConfig
    from willow_package_builder.upackage import FName


CLASS_CACHE_SCHEMA_VERSION = 22
DECLARATION_PARSER_VERSION = 18


@dataclass
class CachedClass:
    package_name: FName
    source_path: Path
    source_hash: str
    declaration: ClassDeclaration

    schema_version: int = CLASS_CACHE_SCHEMA_VERSION
    parser_version: int = DECLARATION_PARSER_VERSION

    _: KW_ONLY

    includes_body_tokens: bool


def write_cached_class(path: Path, cached: CachedClass) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = pickle.dumps(cached, protocol=pickle.HIGHEST_PROTOCOL)
    path.write_bytes(data)


def read_cached_class(path: Path) -> CachedClass:
    with path.open("rb") as file:
        cached = pickle.load(file)  # noqa: S301

    if not isinstance(cached, CachedClass):
        msg = f"Cache does not contain a CachedClass: {path}"
        raise ValueError(msg)  # noqa: TRY004

    return cached


def load_or_parse_class(
    config: PackageConfig, source_path: Path, *, include_body_tokens: bool
) -> CachedClass:
    source_path = source_path.resolve()
    relative_path = source_path.relative_to(config.directory)

    source_bytes = source_path.read_bytes()
    source_hash = sha256(source_bytes).hexdigest()

    cache_path = config.directory / ".willow-cache" / Path(relative_path).with_suffix(".pickle")

    cached = None

    if not get_build_settings().re_cache:
        with contextlib.suppress(
            OSError,
            ValueError,
            TypeError,
            KeyError,
            AttributeError,
            EOFError,
            ImportError,
            pickle.UnpicklingError,
        ):
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
