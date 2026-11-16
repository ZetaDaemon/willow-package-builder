from typing import ClassVar, Protocol, TypedDict, override

from willow_package_builder.games import TargetGame
from willow_package_builder.handlers.classes.class_handler import ClassHandler
from willow_package_builder.logging.diagnostics import ObjectDefinitionError
from willow_package_builder.upackage import FName, ReferencePath, UObject


class AttributeInitializationData(TypedDict, total=False):
    BaseValueConstant: float
    BaseValueAttribute: str | None
    InitializationDefinition: str | None
    BaseValueScaleConstant: float


class ManufacturerCustomGradeWeightData(TypedDict, total=False):
    Manufacturer: str | None
    DefaultWeight: AttributeInitializationData
    DefaultWeightIndex: int


class PartGradeWeightData(TypedDict, total=False):
    Part: str | None
    Manufacturers: list[ManufacturerCustomGradeWeightData]
    MinGameStage: AttributeInitializationData
    MinGameStageIndex: int
    MaxGameStage: AttributeInitializationData
    MaxGameStageIndex: int
    DefaultWeight: AttributeInitializationData
    DefaultWeightIndex: int


class WeaponPartListDefinitionFields(Protocol):
    WeightedParts: list[PartGradeWeightData]
    ConsolidatedAttributeInitData: list[AttributeInitializationData]


MAX_BYTE = 255


def normalise_initdata(initdata: AttributeInitializationData) -> None:
    if "BaseValueConstant" not in initdata:
        initdata["BaseValueConstant"] = 0
    if "BaseValueAttribute" not in initdata:
        initdata["BaseValueAttribute"] = None
    if "InitializationDefinition" not in initdata:
        initdata["InitializationDefinition"] = None
    if "BaseValueScaleConstant" not in initdata:
        initdata["BaseValueScaleConstant"] = 1


def lookup_index(
    initdata: AttributeInitializationData, consolidated_initdata: list[AttributeInitializationData]
) -> int:
    normalise_initdata(initdata)
    try:
        index = consolidated_initdata.index(initdata)
    except ValueError:
        index = len(consolidated_initdata)
        if index > MAX_BYTE:
            msg = "ConsolidatedAttributeInitData exceeds the byte index range"
            raise ObjectDefinitionError(msg)  # noqa: B904
        consolidated_initdata.append(initdata)
    return index


def resolve_index(
    part: PartGradeWeightData | ManufacturerCustomGradeWeightData,
    consolidated_initdata: list[AttributeInitializationData],
    init_name: str,
    index_name: str,
    default: AttributeInitializationData,
    original_table_size: int,
    *,
    context: str,
) -> None:
    if init_name in part:
        if index_name in part:
            msg = f"Specify either {init_name} or {index_name}"
            raise ObjectDefinitionError(msg)
        part[index_name] = lookup_index(part.pop(init_name), consolidated_initdata)  # pyright: ignore[reportArgumentType]
    elif index_name in part:
        index = part[index_name]
        if (
            type(index) is not int  # pyright: ignore[reportUnknownArgumentType]
            or not 0 <= index <= MAX_BYTE
            or index >= len(consolidated_initdata)
            or index >= original_table_size
        ):
            msg = (
                f"{context}.{index_name}: index {index!r} does not reference an entry "
                f"in the original ConsolidatedAttributeInitData table "
                f"({original_table_size} entries, maximum index {MAX_BYTE})"
            )

            raise ObjectDefinitionError(msg)
    else:
        part[index_name] = lookup_index(default, consolidated_initdata)


def consolidate_parts(
    parts: list[PartGradeWeightData],
    consolidated_initdata: list[AttributeInitializationData],
    original_table_size: int,
    *,
    context: str,
) -> None:
    for part_index, part in enumerate(parts):
        part_context = f"{context}[{part_index}]"
        resolve_index(
            part,
            consolidated_initdata,
            "DefaultWeight",
            "DefaultWeightIndex",
            {"BaseValueConstant": 0},
            original_table_size,
            context=part_context,
        )
        resolve_index(
            part,
            consolidated_initdata,
            "MinGameStage",
            "MinGameStageIndex",
            {"BaseValueConstant": 1},
            original_table_size,
            context=part_context,
        )
        resolve_index(
            part,
            consolidated_initdata,
            "MaxGameStage",
            "MaxGameStageIndex",
            {"BaseValueConstant": 100},
            original_table_size,
            context=part_context,
        )
        for manufacturer_index, manufacturer in enumerate(part.get("Manufacturers", [])):
            manufacturer_context = f"{part_context}.Manufacturers[{manufacturer_index}]"
            resolve_index(
                manufacturer,
                consolidated_initdata,
                "DefaultWeight",
                "DefaultWeightIndex",
                {"BaseValueConstant": 100},
                original_table_size,
                context=manufacturer_context,
            )


WEAPON_PART_LIST_PATH = ReferencePath("WillowGame.WeaponPartListDefinition")
WEIGHTED_PARTS_NAME = FName("WeightedParts")
CONSOLIDATED_ATTRIBUTE_INIT_DATA_NAME = FName("ConsolidatedAttributeInitData")


class WeaponPartListDefinitionHandler(ClassHandler[WeaponPartListDefinitionFields]):
    """Consolidate the AttributeInitializationData on a WeaponPartListDefinition."""

    CLASS_PATH: ClassVar[ReferencePath] = WEAPON_PART_LIST_PATH
    GAME: ClassVar[TargetGame | None] = TargetGame.BL2

    HANDLED_PROPERTIES: ClassVar[frozenset[FName]] = frozenset(
        {WEIGHTED_PARTS_NAME, CONSOLIDATED_ATTRIBUTE_INIT_DATA_NAME}
    )

    @override
    def build_properties(self, obj: UObject) -> None:
        if not self.has_yaml_field(WEIGHTED_PARTS_NAME):
            if self.has_yaml_field(CONSOLIDATED_ATTRIBUTE_INIT_DATA_NAME):
                self.validate_field(CONSOLIDATED_ATTRIBUTE_INIT_DATA_NAME)
                self.build_property(CONSOLIDATED_ATTRIBUTE_INIT_DATA_NAME)
            return

        self.validate_field(WEIGHTED_PARTS_NAME)
        parts = self.reference.WeightedParts

        if self.has_yaml_field(CONSOLIDATED_ATTRIBUTE_INIT_DATA_NAME):
            self.validate_field(CONSOLIDATED_ATTRIBUTE_INIT_DATA_NAME)
            table = self.reference.ConsolidatedAttributeInitData
            for initializer in table:
                normalise_initdata(initializer)
        else:
            table = []

        original_table_size = len(table)
        consolidate_parts(parts, table, original_table_size, context=str(WEIGHTED_PARTS_NAME))

        self.reference.ConsolidatedAttributeInitData = table

        self.build_property(WEIGHTED_PARTS_NAME)
        self.build_property(CONSOLIDATED_ATTRIBUTE_INIT_DATA_NAME)
