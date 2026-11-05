from codecs import BOM_UTF16_BE, BOM_UTF16_LE
from typing import TYPE_CHECKING

from willow_package_builder.logging import CompilationError

if TYPE_CHECKING:
    from pathlib import Path


def decode_source(data: bytes, path: Path) -> str:
    """Decode Unicode sources or legacy Windows-1252 exports."""
    encodings = (
        ("utf-16",) if data.startswith((BOM_UTF16_LE, BOM_UTF16_BE)) else ("utf-8-sig", "cp1252")
    )

    for encoding in encodings:
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue

    msg = f"{path}: Source encoding is not supported"
    raise CompilationError(msg)
