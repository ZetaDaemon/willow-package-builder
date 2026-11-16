from hashlib import file_digest, sha256
import json
from pathlib import Path

from willow_package_builder.package_config import (
    OBJECTS_DIRECTORY_NAME,
    PACKAGE_CONFIG_FILENAME,
    PackageConfig,
)


def package_source_fingerprint(config: PackageConfig) -> str:
    """Hash the source inputs owned by one package."""
    root = config.directory
    objects = root / OBJECTS_DIRECTORY_NAME
    paths = [
        root / PACKAGE_CONFIG_FILENAME,
        *config.source_files(),
        *(path for path in objects.rglob("*") if path.is_file()),
    ]

    digest = sha256()
    for path in sorted(paths, key=lambda path: path.relative_to(root).as_posix()):
        name = path.relative_to(root).as_posix().encode("utf-8")
        digest.update(len(name).to_bytes(8, "little"))
        digest.update(name)
        with path.open("rb") as file:
            digest.update(file_digest(file, "sha256").digest())

    return digest.hexdigest()


def package_build_fingerprints(
    packages: tuple[PackageConfig, ...], *, target: str, builder_identity: str
) -> dict[Path, str]:
    """Fingerprint each package and the inputs it depends on."""
    fingerprints: dict[Path, str] = {}

    for config in packages:
        inputs = {
            "target": target,
            "builder": builder_identity,
            "source": package_source_fingerprint(config),
            "required": [fingerprints[path] for path in config.required],
            "references": [fingerprints[path] for path in config.references],
        }
        encoded = json.dumps(inputs, sort_keys=True, separators=(",", ":"))
        fingerprints[config.directory] = sha256(encoded.encode("utf-8")).hexdigest()

    return fingerprints


def builder_code_fingerprint() -> str:
    """Hash the builder code used by this invocation."""
    root = Path(__file__).resolve().parent
    sources: list[tuple[str, str]] = []

    for path in sorted(root.rglob("*.py")):
        with path.open("rb") as file:
            sources.append(
                (path.relative_to(root).as_posix(), file_digest(file, "sha256").hexdigest())
            )

    return sha256(json.dumps(sources).encode("utf-8")).hexdigest()
