from __future__ import annotations

from typing import ClassVar, Protocol, TypedDict, cast, override

from willow_package_builder.games import TargetGame
from willow_package_builder.handlers.classes.class_handler import ClassHandler
from willow_package_builder.handlers.classes.weapon_partlist_handler import (
    CONSOLIDATED_ATTRIBUTE_INIT_DATA_NAME,
    AttributeInitializationData,
    PartGradeWeightData,
    consolidate_parts,
    normalise_initdata,
)
from willow_package_builder.upackage import FName, ReferencePath, UObject


class WeaponCustomPartTypeData(TypedDict, total=False):
    bEnabled: bool
    WeightedParts: list[PartGradeWeightData]


class WeaponPartListCollectionDefinitionFields(Protocol):
    BodyPartData: WeaponCustomPartTypeData
    GripPartData: WeaponCustomPartTypeData
    BarrelPartData: WeaponCustomPartTypeData
    SightPartData: WeaponCustomPartTypeData
    StockPartData: WeaponCustomPartTypeData
    ElementalPartData: WeaponCustomPartTypeData
    Accessory1PartData: WeaponCustomPartTypeData
    Accessory2PartData: WeaponCustomPartTypeData
    MaterialPartData: WeaponCustomPartTypeData
    ConsolidatedAttributeInitData: list[AttributeInitializationData]


WEAPON_PART_LIST_COLLECTION_PATH = ReferencePath("WillowGame.WeaponPartListCollectionDefinition")
BODY_PARTS_NAME = FName("BodyPartData")
GRIP_PARTS_NAME = FName("GripPartData")
BARREL_PARTS_NAME = FName("BarrelPartData")
SIGHT_PARTS_NAME = FName("SightPartData")
STOCK_PARTS_NAME = FName("StockPartData")
ELEMENTAL_PARTS_NAME = FName("ElementalPartData")
ACC1_PARTS_NAME = FName("Accessory1PartData")
ACC2_PARTS_NAME = FName("Accessory2PartData")
MATERIAL_PARTS_NAME = FName("MaterialPartData")


def resolve_part_data(
    data: WeaponCustomPartTypeData,
    consolidated_initdata: list[AttributeInitializationData],
    original_table_size: int,
    *,
    context: str,
) -> None:
    if "WeightedParts" not in data:
        return

    consolidate_parts(
        data["WeightedParts"],
        consolidated_initdata,
        original_table_size,
        context=f"{context}.WeightedParts",
    )


class WeaponPartListCollectionDefinitionHandler(
    ClassHandler[WeaponPartListCollectionDefinitionFields]
):
    """Consolidate the AttributeInitializationData on a WeaponPartListCollectionDefinition."""

    CLASS_PATH: ClassVar[ReferencePath] = WEAPON_PART_LIST_COLLECTION_PATH
    GAME: ClassVar[TargetGame | None] = TargetGame.BL2

    HANDLED_PROPERTIES: ClassVar[frozenset[FName]] = frozenset(
        {
            BODY_PARTS_NAME,
            GRIP_PARTS_NAME,
            BARREL_PARTS_NAME,
            SIGHT_PARTS_NAME,
            STOCK_PARTS_NAME,
            ELEMENTAL_PARTS_NAME,
            ACC1_PARTS_NAME,
            ACC2_PARTS_NAME,
            MATERIAL_PARTS_NAME,
            CONSOLIDATED_ATTRIBUTE_INIT_DATA_NAME,
        }
    )

    def handle_part_data(
        self,
        part_data_name: FName,
        consolidated_initdata: list[AttributeInitializationData],
        original_table_size: int,
    ) -> None:
        if not self.has_yaml_field(part_data_name):
            return
        self.validate_field(part_data_name)
        part_data = cast("WeaponCustomPartTypeData", getattr(self.reference, str(part_data_name)))
        resolve_part_data(
            part_data, consolidated_initdata, original_table_size, context=str(part_data_name)
        )
        self.build_property(part_data_name)

    @override
    def build_properties(self, obj: UObject) -> None:
        slot_names = (
            BODY_PARTS_NAME,
            GRIP_PARTS_NAME,
            BARREL_PARTS_NAME,
            SIGHT_PARTS_NAME,
            STOCK_PARTS_NAME,
            ELEMENTAL_PARTS_NAME,
            ACC1_PARTS_NAME,
            ACC2_PARTS_NAME,
            MATERIAL_PARTS_NAME,
        )
        supplied_slots = [name for name in slot_names if self.has_yaml_field(name)]
        has_table = self.has_yaml_field(CONSOLIDATED_ATTRIBUTE_INIT_DATA_NAME)

        table: list[AttributeInitializationData] = []
        if has_table:
            self.validate_field(CONSOLIDATED_ATTRIBUTE_INIT_DATA_NAME)
            table = self.reference.ConsolidatedAttributeInitData
        else:
            for name in supplied_slots:
                self.validate_field(name)
                part_data = cast("WeaponCustomPartTypeData", self.object_reference.read(name))
                if part_data.get("WeightedParts"):
                    table = cast(
                        "list[AttributeInitializationData]",
                        self.read_archetype_input(CONSOLIDATED_ATTRIBUTE_INIT_DATA_NAME),
                    )
                    break

        for initializer in table:
            normalise_initdata(initializer)

        original_table_size = len(table)
        for name in supplied_slots:
            self.handle_part_data(name, table, original_table_size)

        if has_table or len(table) > original_table_size:
            self.reference.ConsolidatedAttributeInitData = table
            self.build_property(CONSOLIDATED_ATTRIBUTE_INIT_DATA_NAME)
