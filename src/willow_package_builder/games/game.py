from enum import StrEnum
from typing import TYPE_CHECKING, ClassVar

from willow_package_builder.upackage import FName, PackageFlags, PackageFormat

if TYPE_CHECKING:
    from collections.abc import Mapping

    from willow_package_builder.opcode import Opcodes, PrimitiveCastSelectors


class TargetGame(StrEnum):
    BL1 = "bl1"
    BL2 = "bl2"
    TPS = "tps"


WILLOW_PROBE_BITS: Mapping[FName, int] = {
    FName(name): 1 << bit
    for bit, name in enumerate(
        (
            "Destroyed",
            "GainedChild",
            "LostChild",
            "HitWall",
            "Falling",
            "Landed",
            "Touch",
            "UnTouch",
            "Bump",
            "BeginState",
            "EndState",
            "BaseChange",
            "Attach",
            "Detach",
            "EncroachingOn",
            "EncroachedBy",
            "MayFall",
            "Tick",
            "SeePlayer",
            "EnemyNotVisible",
            "HearNoise",
            "UpdateEyeHeight",
            "SeeMonster",
            "SpecialHandling",
            "BotDesireability",
            "NotifyBump",
            "NotifyLanded",
            "NotifyHitWall",
            "PreBeginPlay",
            "PostBeginPlay",
        )
    )
}


class Game:
    TARGET: ClassVar[TargetGame]

    PACKAGE_VERSION: ClassVar[int]
    LICENSE_VERSION: ClassVar[int]
    ENGINE_VERSION: ClassVar[int]
    COOKER_VERSION: ClassVar[int]

    OPCODES: ClassVar[Opcodes]
    PRIMITIVE_CAST_SELECTORS: ClassVar[PrimitiveCastSelectors]
    PROBE_BITS: ClassVar[Mapping[FName, int]]

    PACKAGE_FLAGS: ClassVar[PackageFlags]

    def package_format(self) -> PackageFormat:
        return PackageFormat(
            self.PACKAGE_VERSION, self.LICENSE_VERSION, self.ENGINE_VERSION, self.COOKER_VERSION
        )
