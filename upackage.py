from __future__ import annotations

import struct
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import IntFlag
from uuid import UUID, uuid4

PACKAGE_SIGNATURE = 0x9E2A83C1


class NameEntryFlags(IntFlag):
    """NameEntryFlags."""

    NONE = 0

    TAG_EXPORT = 0x0000001000000000
    LOAD_FOR_CLIENT = 0x0001000000000000
    LOAD_FOR_SERVER = 0x0002000000000000
    LOAD_FOR_EDITOR = 0x0004000000000000

    DEFAULT = TAG_EXPORT | LOAD_FOR_CLIENT | LOAD_FOR_SERVER | LOAD_FOR_EDITOR


class ObjectFlags(IntFlag):
    """ObjectFlags."""

    NONE = 0

    CLASS_DEFAULT_OBJECT = 0x0000000000000200
    ARCHETYPE_OBJECT = 0x0000000000000400
    ROOT_SET = 0x0000000000004000

    PUBLIC = 0x0000000400000000
    PER_OBJECT_LOCALIZED = 0x0000010000000000
    TRANSIENT = 0x0000400000000000

    LOAD_FOR_CLIENT = 0x0001000000000000
    LOAD_FOR_SERVER = 0x0002000000000000
    LOAD_FOR_EDITOR = 0x0004000000000000
    STANDALONE = 0x0008000000000000

    NOT_FOR_CLIENT = 0x0010000000000000
    NOT_FOR_SERVER = 0x0020000000000000
    NOT_FOR_EDITOR = 0x0040000000000000

    NATIVE = 0x0400000000000000

    LOAD_CONTEXT = LOAD_FOR_CLIENT | LOAD_FOR_SERVER | LOAD_FOR_EDITOR

    DEFAULT_EXPORT = PUBLIC | LOAD_CONTEXT
    CLASS_EXPORT = DEFAULT_EXPORT | STANDALONE
    CDO_EXPORT = DEFAULT_EXPORT | CLASS_DEFAULT_OBJECT


class ExportFlags(IntFlag):
    """ExportFlags."""

    NONE = 0


class PackageFlags(IntFlag):
    """PackageFlags."""

    NONE = 0


class CompressionFlags(IntFlag):
    """CompressionFlags."""

    NONE = 0


@dataclass(eq=False)
class ExternalReference:
    """ExternalReference."""

    name: str
    outer: ExternalReference | None
    class_package: str
    class_name: str

    def serialize(self, package: Package) -> bytes:
        """Convert to bytes."""
        return (
            FName(self.class_package).serialize(package)
            + FName(self.class_name).serialize(package)
            + struct.pack("<i", package.object_index(self.outer))
            + FName(self.name).serialize(package)
        )


class ObjectPayload(ABC):
    """ObjectPayload."""

    @abstractmethod
    def serialize(self, package: Package) -> bytes:
        """Convert to bytes."""


@dataclass(eq=False)
class UObject:
    """UObject."""

    name: str
    outer: UObject | ExternalReference | None
    object_class: UObject | ExternalReference | None
    flags: ObjectFlags
    super_object: UObject | ExternalReference | None = None
    archetype: UObject | ExternalReference | None = None

    payload: ObjectPayload | None = None

    dependencies: list[UObject | ExternalReference] = field(default_factory=list)

    def serialize(self, package: Package, payload_size: int, payload_offset: int) -> bytes:
        """Convert to bytes."""
        return (
            struct.pack(
                "<iii",
                package.object_index(self.object_class),
                package.object_index(self.super_object),
                package.object_index(self.outer),
            )
            + FName(self.name).serialize(package)
            + struct.pack(
                "<iQii",
                package.object_index(self.archetype),
                int(self.flags),
                payload_size,
                payload_offset,
            )
            + struct.pack("<I", int(ExportFlags.NONE))
            + struct.pack("<i", 0)  # Generation net-object counts: empty.
            + UUID(int=0).bytes_le  # No originating package GUID.
            + struct.pack("<I", int(PackageFlags.NONE))
        )

    def serialize_dependencies(self, package: Package) -> bytes:
        return struct.pack("<i", len(self.dependencies)) + b"".join(
            struct.pack("<i", package.object_index(obj)) for obj in self.dependencies
        )


@dataclass
class FName:
    """FName."""

    name: str
    number: int = 0

    def serialize(self, package: Package) -> bytes:
        """Convert to bytes."""
        return struct.pack("<ii", package.name_index(self.name), self.number)


@dataclass
class PackageFormat:
    """PackageFormat."""

    version: int
    license_version: int
    engine_version: int
    cooker_version: int


@dataclass
class PackageLayout:
    """PackageLayout."""

    names_offset: int
    imports_offset: int
    exports_offset: int
    dependencies_offset: int
    payload_offset: int


@dataclass
class Package:
    """Package."""

    name: str
    format: PackageFormat
    flags: int

    guid: UUID = field(default_factory=uuid4)

    _exports: list[UObject] = field(default_factory=list)
    _imports: list[ExternalReference] = field(default_factory=list)

    _object_map: dict[str, UObject | ExternalReference] = field(
        default_factory=dict, init=False, repr=False
    )
    _names: list[str] | tuple[str, ...] = field(default_factory=list)

    def object_index_by_path(self, path: str) -> int:
        """Lookup the index of an object path for serialization."""
        return self.object_index(self._object_map[path.casefold()])

    def object_index(self, obj: UObject | ExternalReference | None) -> int:
        """Lookup the index of an object for serialization."""
        if obj is None:
            return 0
        if isinstance(obj, UObject):
            return self._exports.index(obj) + 1
        return (self._imports.index(obj) + 1) * -1

    def object_path(self, obj: UObject | ExternalReference) -> str:
        """Build the path for an object."""
        parts = [obj.name]
        root = obj

        while root.outer is not None:
            root = root.outer
            parts.append(root.name)

        if isinstance(root, UObject):
            parts.append(self.name)

        return ".".join(reversed(parts)).casefold()

    def add_import(self, obj: ExternalReference) -> None:
        """Add an import."""
        key = self.object_path(obj)
        existing = self._object_map.get(key)

        if existing is obj:
            return
        if existing is not None:
            emsg = f"Object already registered: {key}"
            raise ValueError(emsg)

        self.add_name(obj.name)
        self.add_name(obj.class_package)
        self.add_name(obj.class_name)

        self._imports.append(obj)
        self._object_map[self.object_path(obj)] = obj

    def add_export(self, obj: UObject) -> None:
        """Add an export."""
        key = self.object_path(obj)
        existing = self._object_map.get(key)

        if existing is obj:
            return
        if existing is not None:
            emsg = f"Object already registered: {key}"
            raise ValueError(emsg)

        self.add_name(obj.name)

        self._exports.append(obj)
        self._object_map[key] = obj

    def name_index(self, name: str) -> int:
        """Get the index of a name."""
        key = name.casefold()

        for index, existing in enumerate(self._names):
            if existing.casefold() == key:
                return index

        if isinstance(self._names, tuple):
            msg = f"Name table is finalized; name is not registered: {name}"
            raise ValueError(msg)  # noqa: TRY004

        self.add_name(name)
        return self.name_index(name)

    def add_name(self, name: str) -> None:
        """Add a name to the list, without duplication."""
        if isinstance(self._names, tuple):
            msg = "Cannot add a name post name map serialization."
            raise RuntimeError(msg)  # noqa: TRY004
        key = name.casefold()

        if any(existing.casefold() == key for existing in self._names):
            return

        self._names.append(name)

    def serialize_names(self) -> bytes:
        """Convert all names to bytes."""
        if isinstance(self._names, list):
            self._names = tuple(self._names)
        return b"".join(
            serialize_fstring(name) + struct.pack("<Q", int(NameEntryFlags.DEFAULT))
            for name in self._names
        )

    def serialize_imports(self) -> bytes:
        """Convert all imports to bytes."""
        entries = [obj.serialize(self) for obj in self._imports]

        return b"".join(entries)

    def serialize_payloads(self) -> list[bytes]:
        """Serialize payloads in export-table order."""
        payloads: list[bytes] = []

        for obj in self._exports:
            if obj.payload is None:
                msg = f"Object has no payload: {self.object_path(obj)}"
                raise ValueError(msg)

            payloads.append(obj.payload.serialize(self))

        return payloads

    def serialize_exports(self, payloads: list[bytes], data_offset: int) -> bytes:
        """Convert all exports to bytes."""
        if len(payloads) != len(self._exports):
            msg = "Each export must have one serialized payload"
            raise ValueError(msg)

        entries: list[bytes] = []

        for obj, payload in zip(self._exports, payloads, strict=True):
            entry = obj.serialize(self, len(payload), data_offset)
            entries.append(entry)
            data_offset += len(payload)

        return b"".join(entries)

    def serialize_dependencies(self) -> bytes:
        return b"".join(obj.serialize_dependencies(self) for obj in self._exports)

    def serialize_header(self, layout: PackageLayout) -> bytes:
        export_count = len(self._exports)
        import_count = len(self._imports)
        name_count = len(self._names)

        return (
            struct.pack("<IHH", PACKAGE_SIGNATURE, self.format.version, self.format.license_version)
            + struct.pack("<i", layout.payload_offset)  # Total header size.
            + serialize_fstring("None")  # Folder name, not package identity.
            + struct.pack("<I", int(self.flags))
            + struct.pack(
                "<iiiiii",
                name_count,
                layout.names_offset,
                export_count,
                layout.exports_offset,
                import_count,
                layout.imports_offset,
            )
            + struct.pack("<i", layout.dependencies_offset)
            + struct.pack(
                "<iiii",
                layout.payload_offset,  # Empty import/export GUID section.
                0,  # Import GUID count.
                0,  # Export GUID count.
                0,  # No thumbnail table.
            )
            + self.guid.bytes_le
            + struct.pack("<i", 1)  # One generation record.
            + struct.pack(
                "<iii",
                export_count,
                name_count,
                0,  # Generation net-object count.
            )
            + struct.pack("<ii", self.format.engine_version, self.format.cooker_version)
            + struct.pack("<I", int(CompressionFlags.NONE))
            + struct.pack("<i", 0)  # No compressed chunks.
            + struct.pack("<I", 0)  # Package source marker.
            + struct.pack("<i", 0)  # No additional packages to cook.
            + struct.pack("<i", 0)  # No texture allocations.
        )

    def serialize(self) -> bytes:
        """Convert the whole package to bytes."""
        # All names and objects must already be registered.
        payloads = self.serialize_payloads()

        name_data = self.serialize_names()
        import_data = self.serialize_imports()
        dependency_data = self.serialize_dependencies()

        placeholder_layout = PackageLayout(
            names_offset=0,
            imports_offset=0,
            exports_offset=0,
            dependencies_offset=0,
            payload_offset=0,
        )

        header_size = len(self.serialize_header(placeholder_layout))
        export_table_size = len(self.serialize_exports(payloads, data_offset=0))

        names_offset = header_size
        imports_offset = names_offset + len(name_data)
        exports_offset = imports_offset + len(import_data)
        dependencies_offset = exports_offset + export_table_size
        payload_offset = dependencies_offset + len(dependency_data)

        layout = PackageLayout(
            names_offset=names_offset,
            imports_offset=imports_offset,
            exports_offset=exports_offset,
            dependencies_offset=dependencies_offset,
            payload_offset=payload_offset,
        )

        header_data = self.serialize_header(layout)
        export_data = self.serialize_exports(payloads, data_offset=layout.payload_offset)

        return (
            header_data
            + name_data
            + import_data
            + export_data
            + dependency_data
            + b"".join(payloads)
        )


def serialize_fstring(value: str) -> bytes:
    try:
        encoded = value.encode("ascii") + b"\0"
        length = len(encoded)
    except UnicodeEncodeError:
        encoded = value.encode("utf-16-le") + b"\0\0"
        length = -(len(encoded) // 2)

    return struct.pack("<i", length) + encoded
