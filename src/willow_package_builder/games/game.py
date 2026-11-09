from enum import StrEnum
from typing import TYPE_CHECKING, ClassVar

from willow_package_builder.upackage import PackageFlags, PackageFormat

if TYPE_CHECKING:
    from willow_package_builder.opcode import Opcodes


class TargetGame(StrEnum):
    BL1 = "bl1"
    BL2 = "bl2"
    TPS = "tps"


class Game:
    TARGET: ClassVar[TargetGame]

    PACKAGE_VERSION: ClassVar[int]
    LICENSE_VERSION: ClassVar[int]
    ENGINE_VERSION: ClassVar[int]
    COOKER_VERSION: ClassVar[int]

    OPCODES: ClassVar[Opcodes]

    PACKAGE_FLAGS: ClassVar[PackageFlags]

    def package_format(self) -> PackageFormat:
        return PackageFormat(
            self.PACKAGE_VERSION, self.LICENSE_VERSION, self.ENGINE_VERSION, self.COOKER_VERSION
        )
