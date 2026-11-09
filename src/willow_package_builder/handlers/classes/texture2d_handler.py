"""Experimental BL2 Texture2D handler with one inline uncompressed mip."""

import struct
from enum import IntFlag
from types import MappingProxyType
from typing import TYPE_CHECKING, ClassVar, Protocol, cast, override
from uuid import UUID

from PIL import Image

from willow_package_builder.compiler.semantics.types import ResolvedType, TypeCategory
from willow_package_builder.games import TargetGame
from willow_package_builder.logging import ObjectDefinitionError
from willow_package_builder.upackage import NONE_NAME, FName, ReferencePath

from .class_handler import ClassHandler

if TYPE_CHECKING:
    from collections.abc import Mapping

    from willow_package_builder.builder.build_state import PackageBuildState
    from willow_package_builder.handlers import SerializationContext
    from willow_package_builder.objects.definitions import ObjectDefinition
    from willow_package_builder.payloads.instance_payload import ObjectInstancePayload
    from willow_package_builder.upackage import UObject

TEXTURE_2D_PATH = ReferencePath("Engine.Texture2D")
SOURCE_NAME = FName("Source")
PIXEL_FORMAT_NAME = FName("PF_A8R8G8B8")
NO_MIPMAPS_NAME = FName("TMGS_NoMipmaps")
UI_TEXTURE_GROUP_NAME = FName("TEXTUREGROUP_UI")

# Verified in original BL2 and TPS texture payloads.
NOT_GORE_TEXTURE_GUID = UUID("80b5376d-4f1b-343d-9d54-3a999e799abd")
END_TEXTURE_GUID = UUID("80b5376d-4f1b-343d-9d54-3a999d799abd")
EMPTY_GUID = UUID(int=0)

ARRAY_COUNT = struct.Struct("<i")
BULK_DATA_HEADER = struct.Struct("<Iiii")
MIP_DIMENSIONS = struct.Struct("<ii")
MIP_COUNT = 1
EMPTY_MIP_COUNT = 0
BYTES_PER_PIXEL = 4
MAX_EXPERIMENTAL_DIMENSION = 4096


class BulkDataFlags(IntFlag):
    """Bulk-data storage flags used by this experiment."""

    NONE = 0


class Texture2DFields(Protocol):
    Source: str
    SizeX: int
    SizeY: int
    OriginalSizeX: int
    OriginalSizeY: int
    Format: FName
    NeverStream: bool
    MipTailBaseIdx: int
    TextureFileCacheName: FName
    MipGenSettings: FName
    LODGroup: FName
    bGoreTexture: bool  # noqa: N815


class Texture2DHandler(ClassHandler[Texture2DFields]):
    """Build a small non-streaming texture from an image file."""

    CLASS_PATH: ClassVar[ReferencePath] = TEXTURE_2D_PATH
    GAME: ClassVar[TargetGame | None] = TargetGame.BL2
    EXTRA_FIELDS: ClassVar[Mapping[FName, ResolvedType | None]] = MappingProxyType(
        {SOURCE_NAME: ResolvedType(TypeCategory.STRING)}
    )

    _width: float
    _height: float
    _pixels: bytes

    def __init__(self, definition: ObjectDefinition, state: PackageBuildState) -> None:  # noqa: D107
        super().__init__(definition, state)
        self._width = 0
        self._height = 0
        self._pixels = b""

    @override
    def initialize(self, obj: UObject) -> None:
        payload = cast("ObjectInstancePayload", obj.payload)
        if payload.class_path != self.CLASS_PATH:
            msg = "Experimental texture handling supports Texture2D itself, not native subclasses"
            raise NotImplementedError(msg)

        if SOURCE_NAME not in self.definition.properties:
            msg = f"{self.definition.source}: Texture2D requires Source"
            raise ObjectDefinitionError(msg)
        source_name = self.reference.Source
        if not source_name:
            msg = f"{self.definition.source}: Source must be an image filename"
            raise ObjectDefinitionError(msg)
        source = self.object_reference.request_asset(source_name)

        try:
            with Image.open(source) as image:
                width, height = image.size
                if any(
                    dimension < 1
                    or dimension > MAX_EXPERIMENTAL_DIMENSION
                    or dimension & (dimension - 1)
                    for dimension in (width, height)
                ):
                    msg = (
                        f"{source}: Experimental textures require power-of-two dimensions "
                        f"between 1 and {MAX_EXPERIMENTAL_DIMENSION}; got {width}x{height}"
                    )
                    raise ObjectDefinitionError(msg)
                self._pixels = image.convert("RGBA").tobytes("raw", "BGRA")
        except OSError as error:
            msg = f"{source}: Cannot read texture image: {error}"
            raise ObjectDefinitionError(msg) from error

        self._width = width
        self._height = height
        self.reference.SizeX = width
        self.reference.SizeY = height
        self.reference.OriginalSizeX = width
        self.reference.OriginalSizeY = height
        self.reference.Format = PIXEL_FORMAT_NAME
        self.reference.NeverStream = True
        self.reference.MipTailBaseIdx = MIP_COUNT - 1
        self.reference.TextureFileCacheName = NONE_NAME
        self.reference.MipGenSettings = NO_MIPMAPS_NAME
        self.reference.LODGroup = UI_TEXTURE_GROUP_NAME
        self.reference.bGoreTexture = False

    @override
    def serialize(
        self, obj: UObject, payload: ObjectInstancePayload, context: SerializationContext
    ) -> bytes:
        if not self._pixels:
            msg = f"Texture was not initialized: {self.definition.reference}"
            raise RuntimeError(msg)
        if len(self._pixels) != self._width * self._height * BYTES_PER_PIXEL:
            msg = f"Texture pixel data has an invalid size: {self.definition.reference}"
            raise RuntimeError(msg)

        properties = super().serialize(obj, payload, context)
        mip_prefix = NOT_GORE_TEXTURE_GUID.bytes_le + ARRAY_COUNT.pack(MIP_COUNT)
        # A missing offset is used only for the initial layout pass.
        payload_offset = 0 if context.payload_offset is None else context.payload_offset
        pixel_offset = payload_offset + len(properties) + len(mip_prefix) + BULK_DATA_HEADER.size
        pixel_size = len(self._pixels)
        return (
            properties
            + mip_prefix
            + BULK_DATA_HEADER.pack(int(BulkDataFlags.NONE), pixel_size, pixel_size, pixel_offset)
            + self._pixels
            + MIP_DIMENSIONS.pack(self._width, self._height)
            + END_TEXTURE_GUID.bytes_le
            + EMPTY_GUID.bytes_le
            + ARRAY_COUNT.pack(EMPTY_MIP_COUNT)
        )
