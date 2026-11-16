# pyright: reportImportCycles = false
from abc import ABC
from copy import deepcopy
from functools import cache
from types import MappingProxyType, UnionType, get_original_bases
from typing import (
    TYPE_CHECKING,
    Any,
    ClassVar,
    NotRequired,
    Required,
    cast,
    get_args,
    get_origin,
    get_type_hints,
    is_protocol,
    is_typeddict,
)

from willow_package_builder.logging import ObjectDefinitionError
from willow_package_builder.upackage import FName

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence
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
    _values: dict[FName, object]

    def __init__(self, definition: ObjectDefinition) -> None:
        self._definition = definition
        self._values = deepcopy(definition.properties)

    def read(self, name: FName) -> object:
        """Return a value from the handler's working data."""
        try:
            return self._values[name]
        except KeyError:
            msg = f"Object {self._definition.reference} has no field {name}"
            raise AttributeError(msg) from None

    @property
    def fields(self) -> Fields:
        """Expose the reference through its declared field interface."""
        return cast("Fields", self)

    @property
    def definition(self) -> ObjectDefinition:
        """Expose the object definition."""
        return self._definition

    def __getattr__(self, key: str) -> object:
        return self.read(FName(key))

    def __setattr__(self, key: str, value: object) -> None:
        if key.startswith("_"):
            object.__setattr__(self, key, value)
            return

        self._values[FName(key)] = value

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

    _property_builder: Callable[[FName, object], None] | None
    _archetype_reader: Callable[[FName], Value] | None
    _archetype_input_reader: Callable[[FName], object] | None

    _built_property_inputs: dict[FName, object]

    def __init__(self, definition: ObjectDefinition, state: PackageBuildState) -> None:
        self.object_reference = ObjectReference(definition)
        self.state = state
        self.extra_values = {}
        self._property_builder = None
        self._archetype_reader = None
        self._archetype_input_reader = None
        self._built_property_inputs = {}

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

    def has_yaml_field(self, name: FName) -> bool:
        """Return whether the YAML definition supplies this field."""
        return name in self.definition.properties

    def discover(self) -> Sequence[ObjectDefinition]:
        """Discover additional object definitions before construction."""
        return ()

    def bind_property_access(
        self,
        build: Callable[[FName, object], None],
        read_archetype: Callable[[FName], Value],
        read_archetype_input: Callable[[FName], object],
    ) -> None:
        """Connect property construction and archetype reads."""
        self._property_builder = build
        self._archetype_reader = read_archetype
        self._archetype_input_reader = read_archetype_input

    def read_archetype_input(self, name: FName) -> object:
        """Read a copy of the Python input used for an inherited property."""
        read = self._archetype_input_reader
        if read is None:
            msg = "Archetype inputs are available after object construction"
            raise RuntimeError(msg)

        return read(name)

    def read_archetype_property(self, name: FName) -> Value:
        """Read the effective property before this object's overrides."""
        read = self._archetype_reader
        if read is None:
            msg = "Archetype properties are available after object construction"
            raise RuntimeError(msg)

        return read(name)

    def build_property(self, name: FName) -> None:
        """Build an export property from the handler's working data."""
        build = self._property_builder
        if build is None:
            msg = "Handler properties can only be built after object construction"
            raise RuntimeError(msg)

        if name in self.EXTRA_FIELDS:
            msg = f"{name} is a handler input and cannot be built as an export property"
            raise ObjectDefinitionError(msg)

        value = self.object_reference.read(name)
        build(name, value)
        self._built_property_inputs[name] = deepcopy(value)

    def build_properties(self, obj: UObject) -> None:
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

    def validate_field(self, name: FName) -> None:
        """Validate a handler input against its field protocol."""
        annotations = _field_annotations(type(self))

        if name not in annotations:
            msg = f"{type(self).__name__} has no field annotation for {name}"
            raise TypeError(msg)

        try:
            value = self.object_reference.read(name)
        except AttributeError:
            msg = f"{self.definition.reference}: Missing field {name}"
            raise ObjectDefinitionError(msg) from None

        error = _field_validation_error(value, annotations[name], str(name))
        if error is not None:
            msg = f"{self.definition.reference}: {error}"
            raise ObjectDefinitionError(msg)

    def read_built_property_input(self, name: FName) -> object:
        """Copy the Python value used to build an explicit property override."""
        if name not in self._built_property_inputs:
            msg = f"{self.definition.reference}: No build input recorded for {name}"
            raise ObjectDefinitionError(msg)

        return deepcopy(self._built_property_inputs[name])


@cache
def _field_annotations(handler_type: type) -> dict[FName, object]:
    for base in get_original_bases(handler_type):
        if get_origin(base) is not ClassHandler:
            continue

        (protocol,) = get_args(base)
        if isinstance(protocol, type) and is_protocol(protocol):
            return {
                FName(name): annotation for name, annotation in get_type_hints(protocol).items()
            }

    return {}


def _field_validation_error(value: object, annotation: object, path: str) -> str | None:
    if annotation is Any:
        return None

    origin = get_origin(annotation)

    if origin in (Required, NotRequired):
        (inner_type,) = get_args(annotation)
        return _field_validation_error(value, inner_type, path)

    if origin is UnionType:
        options = get_args(annotation)

        if len(options) == 2 and type(None) in options:
            if value is None:
                return None
            inner_type = next(option for option in options if option is not type(None))
            return _field_validation_error(value, inner_type, path)

        for option in options:
            if _field_validation_error(value, option, path) is None:
                return None

        return f"{path}: expected {annotation}, got {type(value).__name__}"

    if origin is list:
        if not isinstance(value, list):
            return f"{path}: expected a list, got {type(value).__name__}"

        (element_type,) = get_args(annotation)
        for index, element in enumerate(cast("list[object]", value)):
            error = _field_validation_error(element, element_type, f"{path}[{index}]")
            if error is not None:
                return error

        return None

    if is_typeddict(annotation):
        if not isinstance(value, dict):
            return f"{path}: expected a mapping, got {type(value).__name__}"

        fields = get_type_hints(annotation, include_extras=True)
        items = cast("dict[object, object]", value)

        required_keys = cast("frozenset[str]", annotation.__required_keys__)  # pyright: ignore[reportAttributeAccessIssue]

        for required_key in sorted(required_keys):
            if required_key not in items:
                return f"{path}.{required_key}: required field is missing"
        for required_key in sorted(required_keys):
            if required_key not in items:
                return f"{path}.{required_key}: required field is missing"

        for key, item in items.items():
            if not isinstance(key, str) or key not in fields:
                return f"{path}: unknown field {key!r}"

            error = _field_validation_error(item, fields[key], f"{path}.{key}")
            if error is not None:
                return error

        return None

    if annotation is float and type(value) in (int, float):
        return None

    if annotation in (bool, int, float, str, type(None)):
        if type(value) is annotation:
            return None
        return f"{path}: expected {annotation.__name__}, got {type(value).__name__}"

    msg = f"{path}: unsupported handler field annotation {annotation}"
    raise TypeError(msg)
