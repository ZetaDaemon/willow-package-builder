# pyright: reportTypedDictNotRequiredAccess=false
import struct
from typing import TYPE_CHECKING, Any, ClassVar, Protocol, Required, TypedDict, cast, override

from willow_package_builder.compiler.syntax.keyword import Keyword, KeywordEnum
from willow_package_builder.games import TargetGame
from willow_package_builder.handlers.classes.class_handler import (
    ClassHandler,
    field_validation_error,
)
from willow_package_builder.logging import ObjectDefinitionError
from willow_package_builder.payloads.instance_payload import ObjectInstancePayload
from willow_package_builder.upackage import CORE_OBJECT_PATH, FName, ReferencePath, UObject

if TYPE_CHECKING:
    from willow_package_builder.builder.build_state import PackageBuildState
    from willow_package_builder.handlers import SerializationContext
    from willow_package_builder.objects.definitions import ObjectDefinition

BEHAVIOR_PROVIDER_PATH = ReferencePath("GearboxFramework.BehaviorProviderDefinition")
BEHAVIOR_SEQUENCES_FIELD = FName("BehaviorSequences")
VARIABLE_DATA_FIELD = FName("VariableData")
NATIVE_VALUE_FIELD = FName("Value")
NULL_OBJECT_INDEX = b"\x00" * 4


class EDirectionRelativeToParent(KeywordEnum):
    """GearboxFramework.BehaviorHelpers:EDirectionRelativeToParent."""

    DIRECTION_Default = "DIRECTION_Default"
    DIRECTION_ParentOrientation = "DIRECTION_ParentOrientation"
    DIRECTION_InverseParentOrientation = "DIRECTION_InverseParentOrientation"
    DIRECTION_ParentVelocity = "DIRECTION_ParentVelocity"
    DIRECTION_InverseParentVelocity = "DIRECTION_InverseParentVelocity"
    DIRECTION_Random = "DIRECTION_Random"
    DIRECTION_RandomUpwards = "DIRECTION_RandomUpwards"
    DIRECTION_RandomDownwards = "DIRECTION_RandomDownwards"
    DIRECTION_RandomOnHorizontalPlane = "DIRECTION_RandomOnHorizontalPlane"
    DIRECTION_StraightUp = "DIRECTION_StraightUp"
    DIRECTION_StraightDown = "DIRECTION_StraightDown"
    DIRECTION_StraightTowardTarget = "DIRECTION_StraightTowardTarget"
    DIRECTION_ParentAimDirection = "DIRECTION_ParentAimDirection"
    DIRECTION_InverseParentAimDirection = "DIRECTION_InverseParentAimDirection"
    DIRECTION_InverseTearOffMomentum = "DIRECTION_InverseTearOffMomentum"


class EBehaviorVariableType(KeywordEnum):
    BVAR_None = "BVAR_None"
    BVAR_Bool = "BVAR_Bool"
    BVAR_Int = "BVAR_Int"
    BVAR_Float = "BVAR_Float"
    BVAR_Vector = "BVAR_Vector"
    BVAR_Object = "BVAR_Object"
    BVAR_AllPlayers = "BVAR_AllPlayers"
    BVAR_Attribute = "BVAR_Attribute"
    BVAR_InstanceData = "BVAR_InstanceData"
    BVAR_NamedVariable = "BVAR_NamedVariable"
    BVAR_NamedKismetVariable = "BVAR_NamedKismetVariable"
    BVAR_DirectionVector = "BVAR_DirectionVector"
    BVAR_AttachmentLocation = "BVAR_AttachmentLocation"
    BVAR_UnaryMath = "BVAR_UnaryMath"
    BVAR_BinaryMath = "BVAR_BinaryMath"
    BVAR_Flag = "BVAR_Flag"


class EBehaviorVariableLinkType(KeywordEnum):
    BVARLINK_Unknown = "BVARLINK_Unknown"
    BVARLINK_Context = "BVARLINK_Context"
    BVARLINK_Input = "BVARLINK_Input"
    BVARLINK_Output = "BVARLINK_Output"


class Vector(TypedDict, total=False):
    X: float
    Y: float
    Z: float


class Rotator(TypedDict, total=False):
    Pitch: int
    Yaw: int
    Roll: int


class AttributeInitializationData(TypedDict, total=False):
    BaseValueConstant: float
    BaseValueAttribute: str | None
    InitializationDefinition: str | None
    BaseValueScaleConstant: float


class BVVector(TypedDict, total=False):
    Value: Vector


class BVAttributeData(TypedDict, total=False):
    ContextVariable: SubarrayData
    Value: AttributeInitializationData


class BVDirectionVectorData(TypedDict, total=False):
    Direction: EDirectionRelativeToParent
    ParentVariable: SubarrayData
    DefaultDirection: Vector
    DefaultDirectionVariable: SubarrayData
    AdditionalRotation: Rotator
    DefaultConeAroundDirection: float
    ConeVariable: SubarrayData


class BVAttachmentLocationData(TypedDict, total=False):
    SourceVariable: SubarrayData
    AttachmentName: str
    bDefaultToSourceLocation: int
    DefaultLocation: Vector
    DefaultLocationVariable: SubarrayData


class BVInstanceDataData(TypedDict, total=False):
    ContextVariable: SubarrayData
    InstanceDataName: str


class BVBinaryMathData(TypedDict, total=False):
    OperandA: SubarrayData
    OperandB: SubarrayData
    Operation: int


class BVUnaryMathData(TypedDict, total=False):
    Operand: SubarrayData
    Operation: int


class BVFlagData(TypedDict, total=False):
    ContextVariable: SubarrayData
    FlagDef: str | None


class SubarrayData(TypedDict, total=False):
    ArrayIndexAndLength: int


class BehaviorEventUserData(TypedDict, total=False):
    EventName: str
    bEnabled: bool
    bReplicate: bool
    MaxTriggerCount: int
    ReTriggerDelay: float
    FilterObject: str | None


class BehaviorEventData2(TypedDict, total=False):
    UserData: BehaviorEventUserData
    OutputVariables: SubarrayData
    OutputLinks: SubarrayData


class BehaviorSequenceActionData2(TypedDict, total=False):
    Behavior: str
    LinkedVariables: SubarrayData
    OutputLinks: SubarrayData


class BehaviorVariableData(TypedDict, total=False):
    Name: str
    Type: Required[EBehaviorVariableType]
    Value: Any


class BehaviorOutputLinkData2(TypedDict, total=False):
    LinkIdAndLinkedBehavior: int
    ActivateDelay: float


class BehaviorVariableLinkData2(TypedDict, total=False):
    PropertyName: str
    VariableLinkType: EBehaviorVariableLinkType
    ConnectionIndex: int
    LinkedVariables: SubarrayData


class BehaviorSequenceData(TypedDict, total=False):
    BehaviorSequenceName: str
    bEnabledOnSpawn: bool
    bSequenceEnabledMutex: bool
    CustomEnableCondition: str
    EventData2: list[BehaviorEventData2]
    BehaviorData2: list[BehaviorSequenceActionData2]
    VariableData: list[BehaviorVariableData]
    ConsolidatedOutputLinkData: list[BehaviorOutputLinkData2]
    ConsolidatedVariableLinkData: list[BehaviorVariableLinkData2]
    ConsolidatedLinkedVariables: list[int]


class BehaviorProviderDefinitionFields(Protocol):
    BehaviorSequences: list[BehaviorSequenceData]


def validate_value(value: object, annotation: object, path: str) -> None:
    """Validate a raw YAML value against a supplied type annotation."""
    error = field_validation_error(value, annotation, path)
    if error is not None:
        raise ObjectDefinitionError(error)


def validate_variable(variable: BehaviorVariableData, path: str) -> object:
    """Validate a YAML variable and return its value with defaults applied."""
    variable_type = EBehaviorVariableType(
        Keyword(variable["Type"])  # pyright: ignore[reportArgumentType]
    )
    value = variable.get("Value")
    value_path = f"{path}.Value"

    empty_link = {"ArrayIndexAndLength": 0}
    zero_vector = {"X": 0.0, "Y": 0.0, "Z": 0.0}
    zero_rotation = {"Pitch": 0, "Yaw": 0, "Roll": 0}

    annotation: object
    default: object

    match variable_type:
        case EBehaviorVariableType.BVAR_Bool:
            annotation, default = bool, False

        case EBehaviorVariableType.BVAR_Int:
            annotation, default = int, 0

        case EBehaviorVariableType.BVAR_Float:
            annotation, default = float, 0.0

        case EBehaviorVariableType.BVAR_Object:
            annotation, default = str | None, None

        case EBehaviorVariableType.BVAR_Vector:
            annotation, default = BVVector, {"Value": zero_vector}

        case EBehaviorVariableType.BVAR_Attribute:
            annotation = BVAttributeData
            default = {
                "ContextVariable": empty_link,
                "Value": {
                    "BaseValueConstant": 0.0,
                    "BaseValueAttribute": None,
                    "InitializationDefinition": None,
                    "BaseValueScaleConstant": 1.0,
                },
            }

        case EBehaviorVariableType.BVAR_InstanceData:
            annotation = BVInstanceDataData
            default = {"ContextVariable": empty_link, "InstanceDataName": "None"}

        case EBehaviorVariableType.BVAR_DirectionVector:
            annotation = BVDirectionVectorData
            default = {
                "Direction": EDirectionRelativeToParent.DIRECTION_Default.text,
                "ParentVariable": empty_link,
                "DefaultDirection": zero_vector,
                "DefaultDirectionVariable": empty_link,
                "AdditionalRotation": zero_rotation,
                "DefaultConeAroundDirection": 0.0,
                "ConeVariable": empty_link,
            }

        case EBehaviorVariableType.BVAR_AttachmentLocation:
            annotation = BVAttachmentLocationData
            default = {
                "SourceVariable": empty_link,
                "AttachmentName": "None",
                "bDefaultToSourceLocation": 0,
                "DefaultLocation": zero_vector,
                "DefaultLocationVariable": empty_link,
            }

        case EBehaviorVariableType.BVAR_UnaryMath:
            annotation = BVUnaryMathData
            default = {"Operand": empty_link, "Operation": 0}

        case EBehaviorVariableType.BVAR_BinaryMath:
            annotation = BVBinaryMathData
            default = {"OperandA": empty_link, "OperandB": empty_link, "Operation": 0}

        case EBehaviorVariableType.BVAR_Flag:
            annotation = BVFlagData
            default = {"ContextVariable": empty_link, "FlagDef": None}

        case (
            EBehaviorVariableType.BVAR_AllPlayers
            | EBehaviorVariableType.BVAR_NamedVariable
            | EBehaviorVariableType.BVAR_NamedKismetVariable
        ):
            annotation, default = type(None), None

        case _:
            msg = f"{path}.Type: unsupported variable type {variable_type.text}"
            raise ObjectDefinitionError(msg)

    if value is None:
        value = default

    validate_value(value, annotation, value_path)

    if isinstance(default, dict):
        defaults = cast("dict[str, object]", default)
        supplied_fields = cast("dict[str, object]", value)
        resolved = defaults | supplied_fields

        for name, field_default in defaults.items():
            if isinstance(field_default, dict):
                nested_defaults = cast("dict[str, object]", field_default)
                supplied = cast("dict[str, object]", supplied_fields.get(name, {}))
                resolved[name] = nested_defaults | supplied

        return resolved

    return value


class BehaviorProviderDefinitionHandler(ClassHandler[BehaviorProviderDefinitionFields]):
    """Build BL2 behavior providers with null object variable values."""

    CLASS_PATH: ClassVar[ReferencePath] = BEHAVIOR_PROVIDER_PATH
    GAME: ClassVar[TargetGame | None] = TargetGame.BL2
    HANDLED_PROPERTIES: ClassVar[frozenset[FName]] = frozenset({BEHAVIOR_SEQUENCES_FIELD})

    _variables: list[BehaviorVariableData]
    _variable_paths: list[str]

    def __init__(self, definition: ObjectDefinition, state: PackageBuildState) -> None:
        super().__init__(definition, state)
        self._variables = []
        self._variable_paths = []

    @override
    def build_properties(self, obj: UObject) -> None:
        if not self.has_yaml_field(BEHAVIOR_SEQUENCES_FIELD):
            msg = "BehaviorSequences must be supplied explicitly for a behavior provider"
            raise ObjectDefinitionError(msg)

        self.validate_field(BEHAVIOR_SEQUENCES_FIELD)

        for sequence_index, sequence in enumerate(self.reference.BehaviorSequences):
            rows = sequence.get("VariableData", [])
            sequence_path = f"BehaviorSequences[{sequence_index}].VariableData"

            if not isinstance(rows, list):
                msg = f"{sequence_path}: expected a list"
                raise ObjectDefinitionError(msg)

            for variable_index, row in enumerate(rows):
                path = f"{sequence_path}[{variable_index}]"
                native_row = row.copy()
                native_row["Value"] = validate_variable(row, path)
                self._variables.append(native_row)
                self._variable_paths.append(path)
                row.pop("Value", None)

        self.build_property(BEHAVIOR_SEQUENCES_FIELD)

        payload = obj.payload
        if not isinstance(payload, ObjectInstancePayload):
            msg = "Behavior provider requires an object instance payload"
            raise TypeError(msg)

    @override
    def serialize(
        self, obj: UObject, payload: ObjectInstancePayload, context: SerializationContext
    ) -> bytes:
        properties = super().serialize(obj, payload, context)
        variables = b"".join(
            self._serialize_variable(variable, index, context, self._variable_paths[index])
            for index, variable in enumerate(self._variables)
        )
        return properties + variables

    def _serialize_variable(
        self, variable: BehaviorVariableData, index: int, context: SerializationContext, path: str
    ) -> bytes:
        variable_type = EBehaviorVariableType(
            Keyword(variable["Type"])  # pyright: ignore[reportArgumentType]
        )
        value = variable["Value"]

        match variable_type:
            case (
                EBehaviorVariableType.BVAR_AllPlayers
                | EBehaviorVariableType.BVAR_NamedVariable
                | EBehaviorVariableType.BVAR_NamedKismetVariable
            ):
                return b""

            case EBehaviorVariableType.BVAR_Bool:
                return struct.pack("<I", int(cast("bool", value)))

            case EBehaviorVariableType.BVAR_Int:
                return struct.pack("<i", cast("int", value))

            case EBehaviorVariableType.BVAR_Float:
                return struct.pack("<f", cast("float", value))

            case EBehaviorVariableType.BVAR_Vector:
                vector = cast("BVVector", value)["Value"]
                return struct.pack("<fff", vector["X"], vector["Y"], vector["Z"])

            case EBehaviorVariableType.BVAR_Object:
                if value is None:
                    return NULL_OBJECT_INDEX
                value = cast("str", value)

                value = self.resolve_object_reference(f"{path}.Value", value, CORE_OBJECT_PATH)

                return value.serialize(context.package)

            case EBehaviorVariableType.BVAR_Attribute:
                attribute = cast("BVAttributeData", value)

                con_var = attribute["ContextVariable"]["ArrayIndexAndLength"]
                const = attribute["Value"]["BaseValueConstant"]
                attr = attribute["Value"]["BaseValueAttribute"]
                initdef = attribute["Value"]["InitializationDefinition"]
                scale = attribute["Value"]["BaseValueScaleConstant"]

                attr = self.resolve_object_reference(
                    f"{path}.Value.Value.BaseValueAttribute",
                    attr,
                    ReferencePath("Engine.AttributeDefinition"),
                )
                initdef = self.resolve_object_reference(
                    f"{path}.Value.Value.InitializationDefinition",
                    initdef,
                    ReferencePath("Engine.AttributeInitializationDefinition"),
                )

                return struct.pack(
                    "<if4s4sf",
                    con_var,
                    const,
                    attr.serialize(context.package),
                    initdef.serialize(context.package),
                    scale,
                )

            case EBehaviorVariableType.BVAR_InstanceData:
                instance = cast("BVInstanceDataData", value)

                con_var = instance["ContextVariable"]["ArrayIndexAndLength"]
                name = FName(instance["InstanceDataName"])
                return struct.pack("<i8s", con_var, name.serialize(context.package))

            case EBehaviorVariableType.BVAR_DirectionVector:
                direction_vect = cast("BVDirectionVectorData", value)

                rel_dir = direction_vect["Direction"]
                rel_dir = EDirectionRelativeToParent(Keyword(rel_dir))  # pyright: ignore[reportArgumentType]
                rel_dir = FName(rel_dir.text)
                parent = direction_vect["ParentVariable"]["ArrayIndexAndLength"]
                default_dir = direction_vect["DefaultDirection"]
                dx, dy, dz = default_dir["X"], default_dir["Y"], default_dir["Z"]
                default_dir_var = direction_vect["DefaultDirectionVariable"]["ArrayIndexAndLength"]
                rotation = direction_vect["AdditionalRotation"]
                p, y, r = rotation["Pitch"], rotation["Yaw"], rotation["Roll"]
                cone = direction_vect["DefaultConeAroundDirection"]
                cone_var = direction_vect["ConeVariable"]["ArrayIndexAndLength"]

                return struct.pack(
                    "<8sifffiiiifi",
                    rel_dir.serialize(context.package),
                    parent,
                    dx,
                    dy,
                    dz,
                    default_dir_var,
                    p,
                    y,
                    r,
                    cone,
                    cone_var,
                )

            case EBehaviorVariableType.BVAR_AttachmentLocation:
                attachment = cast("BVAttachmentLocationData", value)

                source = attachment["SourceVariable"]["ArrayIndexAndLength"]
                name = FName(attachment["AttachmentName"])
                default_to_source = attachment["bDefaultToSourceLocation"]
                default_loc = attachment["DefaultLocation"]
                dx, dy, dz = default_loc["X"], default_loc["Y"], default_loc["Z"]
                default_loc_var = attachment["DefaultLocationVariable"]["ArrayIndexAndLength"]

                return struct.pack(
                    "<i8sIfffi",
                    source,
                    name.serialize(context.package),
                    default_to_source,
                    dx,
                    dy,
                    dz,
                    default_loc_var,
                )

            case EBehaviorVariableType.BVAR_UnaryMath:
                umath = cast("BVUnaryMathData", value)

                operand = umath["Operand"]["ArrayIndexAndLength"]
                operation = umath["Operation"]

                return struct.pack("<ii", operand, operation)

            case EBehaviorVariableType.BVAR_BinaryMath:
                bmath = cast("BVBinaryMathData", value)

                operand_a = bmath["OperandA"]["ArrayIndexAndLength"]
                operand_b = bmath["OperandB"]["ArrayIndexAndLength"]
                operation = bmath["Operation"]

                return struct.pack("<iii", operand_a, operand_b, operation)

            case EBehaviorVariableType.BVAR_Flag:
                flag = cast("BVFlagData", value)

                con_var = flag["ContextVariable"]["ArrayIndexAndLength"]
                flag_def = flag["FlagDef"]
                flag_def = self.resolve_object_reference(
                    f"{path}.Value.FlagDef",
                    flag_def,
                    ReferencePath("GearboxFramework.FlagDefinition"),
                )

                return struct.pack("<i4s", con_var, flag_def.serialize(context.package))

            case _:
                msg = (
                    f"Variable {index}: serialization for {variable_type.text} "
                    "with this value is unsupported"
                )
                raise ObjectDefinitionError(msg)
