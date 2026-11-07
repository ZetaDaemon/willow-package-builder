from typing import TYPE_CHECKING, ClassVar

from willow_package_builder.upackage import PackageFlags, PackageFormat

if TYPE_CHECKING:
    from willow_package_builder.opcode import Opcodes


class Game:
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
