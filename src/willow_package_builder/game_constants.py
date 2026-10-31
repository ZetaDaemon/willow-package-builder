from typing import final

from .upackage import PackageFlags


@final
class Bl2Consts:
    """Bl2 constants."""

    PACKAGE_VERSION = 832
    LICENSE_VERSION = 46
    ENGINE_VERSION = 1712575
    COOKER_VERSION = 134

    CLASS_UNKNOWN_BYTE = 45

    PACKAGE_FLAGS = (
        PackageFlags.ALLOW_DOWNLOAD
        | PackageFlags.COOKED
        | PackageFlags.CONTAINS_SCRIPT
        | PackageFlags.STRIPPED_SOURCE
    )
