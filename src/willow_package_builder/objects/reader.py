from typing import TYPE_CHECKING, cast

import yaml
from yaml.constructor import ConstructorError

from willow_package_builder.logging.diagnostics import ObjectDefinitionError
from willow_package_builder.upackage import FName, ReferencePath

from .definitions import (
    Definition,
    FolderDefinition,
    ObjectDefinition,
    ObjectDefinitionFlag,
    ObjectField,
)

if TYPE_CHECKING:
    from collections.abc import Hashable
    from pathlib import Path

    from yaml.nodes import MappingNode


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


def parse_object_flags(value: object, context: str) -> frozenset[ObjectDefinitionFlag]:
    """Parse the supported object flags."""
    if not isinstance(value, list):
        msg = f"{context}: Flags must be a list"
        raise ObjectDefinitionError(msg)

    flags: set[ObjectDefinitionFlag] = set()

    for item in value:
        if not isinstance(item, str) or item not in ObjectDefinitionFlag:
            supported = ", ".join(flag.value for flag in ObjectDefinitionFlag)
            msg = f"{context}: Unknown object flag {item!r}; supported flags: {supported}"
            raise ObjectDefinitionError(msg)

        flags.add(ObjectDefinitionFlag(item))

    return frozenset(flags)


def read_object_file(source: Path, root: Definition | None) -> list[ObjectDefinition]:
    definitions: list[ObjectDefinition] = []
    registered: dict[ReferencePath, ObjectDefinition] = {}

    try:
        with source.open(encoding="utf-8") as file:
            for document, data in enumerate(yaml.load_all(file, Loader=ObjectLoader), start=1):
                context = f"{source}, document {document}"

                if not isinstance(data, dict):
                    msg = f"{context}: Expected an object mapping"
                    raise ObjectDefinitionError(msg)

                data = cast("dict[str, object]", data)

                if document == 1:
                    if ObjectField.NAME in data:
                        msg = f"{context}: First object must omit Name; it comes from the filename"
                        raise ObjectDefinitionError(msg)

                    name = source.stem
                else:
                    name = data.pop(ObjectField.NAME, None)

                if not isinstance(name, str) or not name.strip() or "." in name or ":" in name:
                    msg = (
                        f"{context}: Name must be a nonempty local name "
                        "containing neither '.' nor ':'"
                    )
                    raise ObjectDefinitionError(msg)
                name = FName(name)

                class_name = data.pop(ObjectField.CLASS, None)
                if not isinstance(class_name, str) or not class_name.strip():
                    msg = f"{context}: Class must be a nonempty string"
                    raise ObjectDefinitionError(msg)
                class_name = ReferencePath(class_name)

                if not definitions:
                    if ObjectField.OUTER in data:
                        msg = f"{context}: First object cannot specify Outer"
                        raise ObjectDefinitionError(msg)

                    outer = root
                    local_path = ReferencePath(name) if outer is None else outer.reference + name
                else:
                    primary = definitions[0]
                    outer = primary

                    if (outer_name := data.pop(ObjectField.OUTER, None)) is not None:
                        if (
                            not isinstance(outer_name, str)
                            or not outer_name.strip()
                            or ":" in outer_name
                            or any(not segment.strip() for segment in outer_name.split("."))
                        ):
                            msg = f"{context}: Outer must be a valid object path"
                            raise ObjectDefinitionError(msg)

                        outer_path = (
                            primary.reference
                            if ReferencePath(outer_name) == ReferencePath(primary.name)
                            else ReferencePath(outer_name, primary.reference)
                        )

                        resolved = registered.get(outer_path)

                        if resolved is None:
                            msg = (
                                f"{context}: Outer {outer_name!r} must refer "
                                "to an earlier object in the same file"
                            )
                            raise ObjectDefinitionError(msg)

                        outer = resolved

                    # Construct a file-local path, independent of directory ownership.
                    local_path = outer.reference + name

                existing = registered.get(local_path)

                if existing is not None:
                    msg = (
                        f"{context}: Duplicate object {local_path!r}; "
                        f"first declared in document {existing.document}"
                    )
                    raise ObjectDefinitionError(msg)

                flags = parse_object_flags(data.pop(ObjectField.FLAGS, []), context)

                archetype: str | None = None

                if (raw_archetype := data.pop(ObjectField.ARCHETYPE, None)) is not None:
                    if not isinstance(raw_archetype, str) or not raw_archetype.strip():
                        msg = f"{context}: Archetype must be a nonempty reference string"
                        raise ObjectDefinitionError(msg)

                    archetype = raw_archetype.strip()

                raw_properties = data
                properties: dict[FName, object] = {}
                for raw_key, raw_value in raw_properties.items():
                    key = FName(raw_key)
                    if key in properties:
                        msg = f"{context}: Duplicate property {key}"
                        raise ObjectDefinitionError(msg)

                    properties[key] = raw_value

                definition = ObjectDefinition(
                    name, outer, source, class_name, properties, document, flags, archetype
                )

                registered[local_path] = definition
                definitions.append(definition)

                if outer is not None:
                    outer.children.append(definition)

    except yaml.YAMLError as error:
        msg = f"{source}: Invalid object YAML: {error}"
        raise ObjectDefinitionError(msg) from error

    if not definitions:
        msg = f"{source}: Object file contains no documents"
        raise ObjectDefinitionError(msg)

    return definitions


def walk_objects_directory(directory: Path) -> list[Definition]:
    declarations: list[Definition] = []
    registered: dict[ReferencePath, Definition] = {}

    if not directory.is_dir():
        msg = f"Objects directory does not exist or is not a directory: {directory}"
        raise ObjectDefinitionError(msg)

    def register(declaration: Definition) -> None:
        path = declaration.reference
        existing = registered.get(path)

        if existing is not None:
            msg = f"Duplicate object path {path!r}: {existing.source} and {declaration.source}"
            raise ObjectDefinitionError(msg)

        registered[path] = declaration
        declarations.append(declaration)

        if declaration.outer is not None:
            children = declaration.outer.children
            if declaration not in children:
                children.append(declaration)

    def visit(folder: Path, outer: Definition | None) -> None:
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

            name = FName(name)

            path = ReferencePath(name) if outer is None else outer.reference + name
            child_outer = registered.get(path)

            if child_outer is None:
                child_outer = FolderDefinition(name, outer, child_directory)
                register(child_outer)

            visit(child_directory, child_outer)

    visit(directory, None)
    return declarations
