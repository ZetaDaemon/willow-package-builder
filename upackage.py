from __future__ import annotations

import struct
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import IntFlag
from typing import Any, overload, override
from uuid import UUID, uuid4
from warnings import deprecated

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

    ALLOW_DOWNLOAD = 0x00000001
    COOKED = 0x00000008
    CONTAINS_SCRIPT = 0x00200000
    STRIPPED_SOURCE = 0x40000000


class CompressionFlags(IntFlag):
    """CompressionFlags."""

    NONE = 0


@dataclass(init=False, eq=False, frozen=True)
class Name:
    """String with case insensitive comparisons."""

    name: str

    def __init__(self, name: str) -> None:
        object.__setattr__(self, "name", name)

    @override
    def __hash__(self) -> int:
        return hash(self.name.casefold())

    @override
    def __eq__(self, other: object) -> bool:
        if isinstance(other, Name):
            return self.name.casefold() == other.name.casefold()
        return NotImplemented

    @override
    def __str__(self) -> str:
        return self.name

    @override
    def __repr__(self) -> str:
        return str(self)

    def is_none(self) -> bool:
        """Check if the value is none."""
        return self.name.casefold() == "none"


INT32_MAX = (1 << 31) - 1


@dataclass(init=False, eq=False, frozen=True)
class FName:
    """FName."""

    name: Name
    number: int = 0

    @overload
    def __init__(self, name: str) -> None: ...
    @overload
    def __init__(self, name: Name, number: int = 0) -> None: ...
    def __init__(self, name: Name | str, number: int = 0) -> None:
        if isinstance(name, str):
            name, number = FName._split_str_to_name_number(name)

        object.__setattr__(self, "name", name)
        object.__setattr__(self, "number", number)

    @staticmethod
    def _split_str_to_name_number(value: str) -> tuple[Name, int]:
        name = value
        number = 0
        base, separator, suffix = value.rpartition("_")
        if (
            separator
            and base
            and suffix.isascii()
            and suffix.isdecimal()
            and (suffix == "0" or not suffix.startswith("0"))
        ):
            number = int(suffix) + 1
            if number > INT32_MAX:
                raise ValueError
            name = base
        return Name(name), number

    @override
    def __str__(self) -> str:
        if self.number == 0:
            return str(self.name)

        return f"{self.name}_{self.number - 1}"

    @override
    def __repr__(self) -> str:
        return str(self)

    @override
    def __hash__(self) -> int:
        return hash(str(self).casefold())

    @override
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, FName):
            return NotImplemented
        return self.name == other.name and self.number == other.number

    def serialize(self, package: Package) -> bytes:
        """Convert to bytes."""
        return struct.pack("<ii", package.name_index(self.name), self.number)

    def is_none(self) -> bool:
        """Check if the name is none."""
        return self.number == 0 and self.name.is_none()


@dataclass(init=False, eq=False, frozen=True)
class ReferencePath:
    """Path to a UObject or ExternalReference."""

    name: FName
    outer: ReferencePath | None

    @overload
    def __init__(self) -> None: ...
    @overload
    def __init__(self, name: str | Name | FName) -> None: ...
    @overload
    def __init__(self, name: str | Name | FName, outer: ReferencePath | None) -> None: ...
    def __init__(
        self, name: str | Name | FName = "None", outer: ReferencePath | None = None
    ) -> None:

        if isinstance(name, str):
            segments = name.split(".")

            if any(not segment for segment in segments):
                msg = f"Path contains an empty segment: {name!r}"
                raise ValueError(msg)

            *parents, last = segments
            for segment in parents:
                outer = ReferencePath(FName(segment), outer)

            name = FName(last)
        if isinstance(name, Name):
            name = FName(name)

        object.__setattr__(self, "name", name)
        object.__setattr__(self, "outer", outer)

        if outer is not None and outer.is_none():
            msg = "Outer cannot be a null ReferencePath; omit it for a root path"
            raise ValueError(msg)

    @override
    def __hash__(self) -> int:
        return hash(str(self).casefold())

    @override
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ReferencePath):
            return NotImplemented

        return str(self).casefold() == str(other).casefold()

    @override
    def __str__(self) -> str:
        s = str(self.name)
        if self.outer is not None and not self.outer.is_none():
            s = f"{self.outer}.{s}"

        return s

    @override
    def __repr__(self) -> str:
        return str(self)

    def __add__(self, other: Name | FName) -> ReferencePath:
        if self.is_none():
            return ReferencePath(other)
        return ReferencePath(other, self)

    def is_none(self) -> bool:
        """Check if the path is none."""
        return self.outer is None and self.name.is_none()

    def serialize(self, package: Package) -> bytes:
        """Serialize the referenced object's package index."""
        index = 0 if self.is_none() else package.object_index(package.lookup_object_by_path(self))
        return struct.pack("<i", index)


@dataclass(eq=False)
class ExternalReference:
    """ExternalReference."""

    name: FName
    class_package: FName
    class_name: FName
    outer: ReferencePath = field(default_factory=ReferencePath)

    def serialize(self, package: Package) -> bytes:
        """Convert to bytes."""
        return (
            self.class_package.serialize(package)
            + self.class_name.serialize(package)
            + self.outer.serialize(package)
            + self.name.serialize(package)
        )

    def reference(self) -> ReferencePath:
        return self.outer + self.name


class ObjectPayload(ABC):
    """ObjectPayload."""

    @abstractmethod
    def serialize(self, package: Package) -> bytes:
        """Convert to bytes."""


@dataclass(eq=False)
class UObject:
    """UObject."""

    name: FName
    flags: ObjectFlags
    outer: ReferencePath = field(default_factory=ReferencePath)
    object_class: ReferencePath = field(default_factory=ReferencePath)
    super_object: ReferencePath = field(default_factory=ReferencePath)
    archetype: ReferencePath = field(default_factory=ReferencePath)

    payload: ObjectPayload | None = None

    dependencies: list[ReferencePath] = field(default_factory=list)

    def serialize(self, package: Package, payload_size: int, payload_offset: int) -> bytes:
        """Convert to bytes."""
        return (
            self.object_class.serialize(package)
            + self.super_object.serialize(package)
            + self.outer.serialize(package)
            + self.name.serialize(package)
            + self.archetype.serialize(package)
            + struct.pack("<Qii", int(self.flags), payload_size, payload_offset)
            + struct.pack("<I", int(ExportFlags.NONE))
            + struct.pack("<i", 0)  # Generation net-object counts: empty.
            + UUID(int=0).bytes_le  # No originating package GUID.
            + struct.pack("<I", int(PackageFlags.NONE))
        )

    def serialize_dependencies(self, package: Package) -> bytes:
        return struct.pack("<i", len(self.dependencies)) + b"".join(
            obj.serialize(package) for obj in self.dependencies
        )

    def reference(self) -> ReferencePath:
        return self.outer + self.name


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

    name: FName
    format: PackageFormat
    flags: int

    guid: UUID = field(default_factory=uuid4)

    _exports: list[UObject] = field(default_factory=list)
    _imports: list[ExternalReference] = field(default_factory=list)

    _object_map: dict[ReferencePath, UObject | ExternalReference] = field(
        default_factory=dict, init=False, repr=False
    )
    _names: list[Name] | tuple[Name, ...] = field(default_factory=list)

    def add_name(self, name: Name | FName) -> None:
        """Add a name to the list, without duplication."""
        if isinstance(self._names, tuple):
            msg = "Cannot add a name after name-table serialization."
            raise RuntimeError(msg)  # noqa: TRY004

        if isinstance(name, FName):
            name = name.name

        if name not in self._names:
            self._names.append(name)

    def add_import(self, obj: ExternalReference) -> ReferencePath:
        """Add an import."""
        key = obj.reference()
        existing = self._object_map.get(key)

        if existing is obj:
            return key
        if existing is not None:
            emsg = f"Object already registered: {key}"
            raise ValueError(emsg)

        self.add_name(obj.name)
        self.add_name(obj.class_package)
        self.add_name(obj.class_name)

        self._imports.append(obj)
        self._object_map[key] = obj
        return key

    def add_export(self, obj: UObject) -> ReferencePath:
        """Add an export."""
        key = obj.reference()
        existing = self._object_map.get(key)

        if existing is obj:
            return key
        if existing is not None:
            emsg = f"Object already registered: {key}"
            raise ValueError(emsg)

        self.add_name(obj.name)

        self._exports.append(obj)
        self._object_map[key] = obj
        return key

    def name_index(self, name: Name) -> int:
        """Get the index of a name."""
        key = name

        for index, existing in enumerate(self._names):
            if existing == key:
                return index

        if isinstance(self._names, tuple):
            msg = f"Name table is finalized; name is not registered: {name}"
            raise ValueError(msg)  # noqa: TRY004

        self.add_name(name)
        return self.name_index(name)

    def lookup_object_by_path(self, path: ReferencePath) -> UObject | ExternalReference:
        """Lookup an object by the path."""
        return self._object_map[path]

    @overload
    @deprecated("Use ReferencePath.serialize() instead")
    def object_index(self, obj: ReferencePath) -> int: ...
    @overload
    def object_index(self, obj: UObject | ExternalReference | None) -> int: ...
    def object_index(self, obj: UObject | ExternalReference | ReferencePath | None) -> int:
        """Lookup the index of an object for serialization."""
        if obj is None:
            return 0
        if isinstance(obj, ReferencePath):
            obj = self.lookup_object_by_path(obj)
        if isinstance(obj, UObject):
            return self._exports.index(obj) + 1
        return (self._imports.index(obj) + 1) * -1

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
                msg = f"Object has no payload: {obj.reference()}"
                raise ValueError(msg)

            try:
                payload = obj.payload.serialize(self)
            except ValueError as exc:
                msg = f"Failed to serialize {obj.reference()}: {exc}"
                raise ValueError(msg) from exc

            payloads.append(payload)

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
        import_data = self.serialize_imports()
        dependency_data = self.serialize_dependencies()

        # This also registers all names in exports
        export_table_size = len(self.serialize_exports(payloads, data_offset=0))

        name_data = self.serialize_names()
        placeholder_layout = PackageLayout(
            names_offset=0,
            imports_offset=0,
            exports_offset=0,
            dependencies_offset=0,
            payload_offset=0,
        )

        header_size = len(self.serialize_header(placeholder_layout))

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


def serialize_fstring(value: str | ReferencePath | Name) -> bytes:
    value = str(value)
    try:
        encoded = value.encode("ascii") + b"\0"
        length = len(encoded)
    except UnicodeEncodeError:
        encoded = value.encode("utf-16-le") + b"\0\0"
        length = -(len(encoded) // 2)

    return struct.pack("<i", length) + encoded
