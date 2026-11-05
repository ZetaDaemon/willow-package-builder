from collections.abc import Hashable
from pathlib import Path

import yaml
from yaml.constructor import ConstructorError
from yaml.nodes import MappingNode

from willow_package_builder.logging import CompilationError
from willow_package_builder.logging.diagnostics import ObjectDefinitionError

from .declarations import FolderDeclaration, ObjectDeclaration, ObjectFlag


class ObjectLoader(yaml.SafeLoader):
    """Safe YAML loader that rejects duplicate mapping keys."""

    def construct_mapping(self, node: MappingNode, deep: bool = False) -> dict[Hashable, object]:
        mapping: dict[Hashable, object] = {}

        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)

            if not isinstance(key, str):
                msg = "Object definition mapping keys must be strings"
                raise ConstructorError(None, None, msg, key_node.start_mark)

            if key in mapping:
                msg = f"Duplicate YAML key {key!r}"
                raise ConstructorError(None, None, msg, key_node.start_mark)

            mapping[key] = self.construct_object(value_node, deep=deep)

        return mapping


def object_path(declaration: ObjectDeclaration | FolderDeclaration) -> str:
    parts: list[str] = []
    part = declaration
    while part is not None:
        parts.append(part.name)
        part = part.outer
    return ".".join(reversed(parts))


def parse_object_flags(value: object, context: str) -> frozenset[ObjectFlag]:
    """Parse the supported object flags."""
    if not isinstance(value, list):
        msg = f"{context}: Flags must be a list"
        raise ObjectDefinitionError(msg)

    flags: set[ObjectFlag] = set()

    for item in value:
        if not isinstance(item, str) or item not in ObjectFlag:
            supported = ", ".join(flag.value for flag in ObjectFlag)
            msg = f"{context}: Unknown object flag {item!r}; supported flags: {supported}"
            raise ObjectDefinitionError(msg)

        flags.add(ObjectFlag(item))

    return frozenset(flags)


def read_object_file(
    source: Path, root: ObjectDeclaration | FolderDeclaration | None
) -> list[ObjectDeclaration]:
    declarations: list[ObjectDeclaration] = []
    registered: dict[str, ObjectDeclaration] = {}

    try:
        with source.open(encoding="utf-8") as file:
            for document, data in enumerate(yaml.load_all(file, Loader=ObjectLoader), start=1):
                context = f"{source}, document {document}"

                if not isinstance(data, dict):
                    msg = f"{context}: Expected an object mapping"
                    raise ObjectDefinitionError(msg)

                if document == 1:
                    if "Name" in data:
                        msg = f"{context}: First object must omit Name; it comes from the filename"
                        raise ObjectDefinitionError(msg)

                    name = source.stem
                else:
                    name = data.pop("Name", None)

                if not isinstance(name, str) or not name.strip() or "." in name or ":" in name:
                    msg = (
                        f"{context}: Name must be a nonempty local name "
                        "containing neither '.' nor ':'"
                    )
                    raise ObjectDefinitionError(msg)

                class_name = data.pop("Class", None)
                if not isinstance(class_name, str) or not class_name.strip():
                    msg = f"{context}: Class must be a nonempty string"
                    raise ObjectDefinitionError(msg)

                if not declarations:
                    if "Outer" in data:
                        msg = f"{context}: First object cannot specify Outer"
                        raise ObjectDefinitionError(msg)

                    outer = root
                    local_path = name
                else:
                    primary = declarations[0]
                    outer = primary

                    if "Outer" in data:
                        outer_name = data.pop("Outer")

                        if (
                            not isinstance(outer_name, str)
                            or not outer_name.strip()
                            or ":" in outer_name
                            or any(not segment.strip() for segment in outer_name.split("."))
                        ):
                            msg = f"{context}: Outer must be a valid object path"
                            raise ObjectDefinitionError(msg)

                        # Outer paths are relative to the primary object.
                        # Its own name may explicitly select the primary.
                        if outer_name.casefold() == primary.name.casefold():
                            outer_path = primary.name
                        else:
                            outer_path = f"{primary.name}.{outer_name}"

                        resolved = registered.get(outer_path.casefold())

                        if resolved is None:
                            msg = (
                                f"{context}: Outer {outer_name!r} must refer "
                                "to an earlier object in the same file"
                            )
                            raise ObjectDefinitionError(msg)

                        outer = resolved

                    # Construct a file-local path, independent of directory ownership.
                    parts = [name]
                    ancestor = outer

                    while ancestor is not primary:
                        parts.append(ancestor.name)
                        parent = ancestor.outer

                        if not isinstance(parent, ObjectDeclaration):
                            msg = f"{context}: Invalid in-file ownership chain"
                            raise RuntimeError(msg)  # noqa: TRY004

                        ancestor = parent

                    parts.append(primary.name)
                    local_path = ".".join(reversed(parts))

                key = local_path.casefold()
                existing = registered.get(key)

                if existing is not None:
                    msg = (
                        f"{context}: Duplicate object {local_path!r}; "
                        f"first declared in document {existing.document}"
                    )
                    raise ObjectDefinitionError(msg)

                flags = parse_object_flags(data.pop("Flags", []), context)

                properties = data

                declaration = ObjectDeclaration(
                    name, class_name, outer, properties, source, document, flags=flags
                )

                registered[key] = declaration
                declarations.append(declaration)

                if outer is not None:
                    outer.children.append(declaration)

    except yaml.YAMLError as error:
        msg = f"{source}: Invalid object YAML: {error}"
        raise ObjectDefinitionError(msg) from error

    if not declarations:
        msg = f"{source}: Object file contains no documents"
        raise ObjectDefinitionError(msg)

    return declarations


def walk_objects_directory(directory: Path) -> list[FolderDeclaration | ObjectDeclaration]:
    declarations: list[FolderDeclaration | ObjectDeclaration] = []
    registered: dict[str, FolderDeclaration | ObjectDeclaration] = {}

    if not directory.is_dir():
        msg = f"Objects directory does not exist or is not a directory: {directory}"
        raise ObjectDefinitionError(msg)

    def register(declaration: FolderDeclaration | ObjectDeclaration) -> None:
        path = object_path(declaration)
        key = path.casefold()
        existing = registered.get(key)

        if existing is not None:
            msg = f"Duplicate object path {path!r}: {existing.source} and {declaration.source}"
            raise ObjectDefinitionError(msg)

        registered[key] = declaration
        declarations.append(declaration)

        if declaration.outer is not None:
            children = declaration.outer.children
            if declaration not in children:
                children.append(declaration)

    def visit(folder: Path, outer: FolderDeclaration | ObjectDeclaration | None) -> None:
        entries = sorted(folder.iterdir(), key=lambda entry: (entry.name.casefold(), entry.name))

        # Register this directory's objects before examining subdirectories.
        for source in entries:
            if not source.is_file() or source.suffix.casefold() not in (".yaml", ".yml"):
                continue

            for declaration in read_object_file(source, outer):
                register(declaration)

        for child_directory in entries:
            if not child_directory.is_dir():
                continue

            name = child_directory.name

            if not name.strip() or "." in name or ":" in name:
                msg = (
                    f"{child_directory}: Folder name must be a nonempty "
                    "local name containing neither '.' nor ':'"
                )
                raise ObjectDefinitionError(msg)

            path = name if outer is None else f"{object_path(outer)}.{name}"
            child_outer = registered.get(path.casefold())

            if child_outer is None:
                child_outer = FolderDeclaration(name, outer, child_directory)
                register(child_outer)

            visit(child_directory, child_outer)

    visit(directory, None)
    return declarations
