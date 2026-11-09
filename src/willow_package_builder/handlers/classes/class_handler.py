# pyright: reportImportCycles = false
from abc import ABC
from collections.abc import Mapping
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, ClassVar, cast

from willow_package_builder.logging import ObjectDefinitionError
from willow_package_builder.upackage import FName

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from pathlib import Path

    from willow_package_builder.builder.build_state import PackageBuildState
    from willow_package_builder.compiler.semantics.types import ResolvedType
    from willow_package_builder.games import TargetGame
    from willow_package_builder.handlers import SerializationContext
    from willow_package_builder.objects.definitions import ObjectDefinition
    from willow_package_builder.payloads.instance_payload import ObjectInstancePayload
    from willow_package_builder.properties.values import Value
    from willow_package_builder.upackage import ReferencePath, UObject


class ObjectReference[Fields]:
    _definition: ObjectDefinition

    def __init__(self, definition: ObjectDefinition) -> None:
        self._definition = definition
        self._read_field: Callable[[FName], object] | None = None
        self._write_field: Callable[[FName, object], None] | None = None

    def bind(
        self, read_field: Callable[[FName], object], write_field: Callable[[FName, object], None]
    ) -> None:
        """Connect field access to the constructed object."""
        self._read_field = read_field
        self._write_field = write_field

    @property
    def fields(self) -> Fields:
        """Expose the reference through its declared field interface."""
        return cast("Fields", self)

    @property
    def definition(self) -> ObjectDefinition:
        """Expose the object definition."""
        return self._definition

    def __getattr__(self, key: str) -> object:
        name = FName(key)
        read_field = object.__getattribute__(self, "_read_field")

        if read_field is not None:
            return read_field(name)

        definition = object.__getattribute__(self, "_definition")

        try:
            return definition.properties[name]
        except KeyError:
            msg = f"Object {definition.reference} has no field {key!r}"
            raise AttributeError(msg) from None

    def __setattr__(self, key: str, value: object) -> None:
        if key.startswith("_"):
            object.__setattr__(self, key, value)
            return

        name = FName(key)
        write_field = object.__getattribute__(self, "_write_field")

        if write_field is not None:
            write_field(name, value)
            return

        definition = object.__getattribute__(self, "_definition")
        definition.properties[name] = value

    def request_asset(self, name: str) -> Path:
        """Find an asset in the object's folder or beside its YAML file."""
        source = self.definition.source.resolve()
        directories = (source.with_suffix(""), source.parent)

        for directory in directories:
            asset = (directory / name).resolve()

            if not asset.is_relative_to(directory):
                msg = f"Asset must be inside {directory}: {name}"
                raise ObjectDefinitionError(msg)

            if asset.is_file():
                return asset

        msg = (
            f"Object {self.definition.reference}: Asset {name!r} was not found "
            f"in {directories[0]} or {directories[1]}"
        )
        raise ObjectDefinitionError(msg)


class ClassHandler[Fields = Any](ABC):
    """Customize construction and serialization of an object class."""

    object_reference: ObjectReference[Fields]
    state: PackageBuildState
    extra_values: dict[FName, Value]

    def __init__(self, definition: ObjectDefinition, state: PackageBuildState) -> None:
        self.object_reference = ObjectReference(definition)
        self.state = state
        self.extra_values = {}

    CLASS_PATH: ClassVar[ReferencePath]
    GAME: ClassVar[TargetGame | None] = None

    EXTRA_FIELDS: ClassVar[Mapping[FName, ResolvedType | None]] = MappingProxyType({})
    HANDLED_PROPERTIES: ClassVar[frozenset[FName]] = frozenset()

    @property
    def reference(self) -> Fields:
        """Access fields through the handler's declared interface."""
        return self.object_reference.fields

    @property
    def definition(self) -> ObjectDefinition:
        """Access the object definition through the reference."""
        return self.object_reference.definition

    def discover(self) -> Sequence[ObjectDefinition]:
        """Discover additional object definitions before construction."""
        return ()

    def initialize(self, obj: UObject) -> None:
        """Construct handler-controlled properties and initial native data."""
        return

    def prepare(self, obj: UObject) -> None:
        """Prepare final data after all objects have been initialized."""
        return

    def serialize(
        self, obj: UObject, payload: ObjectInstancePayload, context: SerializationContext
    ) -> bytes:
        """Serialize the ordinary instance payload."""
        return payload.serialize_regular(context.package)
