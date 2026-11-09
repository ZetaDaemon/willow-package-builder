"""Experimental BL2 SwfMovie handler for one packaged Texture2D."""

import struct
import zlib
from enum import Enum
from types import MappingProxyType
from typing import TYPE_CHECKING, ClassVar, Protocol, cast, override

from willow_package_builder.compiler.semantics.types import ResolvedType, TypeCategory
from willow_package_builder.games import TargetGame
from willow_package_builder.logging import ObjectDefinitionError
from willow_package_builder.objects.definitions import FolderDefinition
from willow_package_builder.payloads.instance_payload import ObjectInstancePayload
from willow_package_builder.properties.reference_text import parse_reference_text
from willow_package_builder.properties.values import IntValue
from willow_package_builder.upackage import FName, ReferencePath, UObject

from .class_handler import ClassHandler
from .image_movie import build_image_movie

if TYPE_CHECKING:
    from collections.abc import Mapping

    from willow_package_builder.builder.build_state import PackageBuildState
    from willow_package_builder.objects.definitions import ObjectDefinition

PACKAGE_URL_PREFIX = "/ package/"
TEXTURE_FILE_SUFFIX = ".tga"

SWF_MOVIE_PATH = ReferencePath("GFxUI.SwfMovie")
TEXTURE_2D_PATH = ReferencePath("Engine.Texture2D")
TEXTURE_2D_SHORT_PATH = ReferencePath("Texture2D")

TEXTURE_FIELD = FName("Texture")
SIZE_X_FIELD = FName("SizeX")
SIZE_Y_FIELD = FName("SizeY")
WIDTH_FIELD = FName("Width")
HEIGHT_FIELD = FName("Height")
SOURCE_FIELD = FName("Source")

MOVIE_HEADER = struct.Struct("<3sBI")


class MovieSignature(Enum):
    """Movie containers recognized by the source importer."""

    SWF = b"FWS"
    COMPRESSED_SWF = b"CWS"
    GFX = b"GFX"
    COMPRESSED_GFX = b"CFX"
    LZMA_SWF = b"ZWS"


class SwfMovieFields(Protocol):
    Source: str
    Texture: ReferencePath | None
    Width: int
    Height: int
    RawData: list[int]
    References: list[ReferencePath]


class SwfMovieHandler(ClassHandler[SwfMovieFields]):
    """Generate a static image movie referencing an independently defined texture.

    This first experiment requires the texture to be an export in this UPK;
    dimensions of externally loaded textures are not available to the builder.
    """

    CLASS_PATH: ClassVar[ReferencePath] = SWF_MOVIE_PATH
    GAME: ClassVar[TargetGame | None] = TargetGame.BL2
    EXTRA_FIELDS: ClassVar[Mapping[FName, ResolvedType | None]] = MappingProxyType(
        {
            SOURCE_FIELD: ResolvedType(TypeCategory.STRING),
            TEXTURE_FIELD: ResolvedType(TypeCategory.OBJECT, TEXTURE_2D_PATH),
            WIDTH_FIELD: ResolvedType(TypeCategory.INT),
            HEIGHT_FIELD: ResolvedType(TypeCategory.INT),
        }
    )
    _texture_path: ReferencePath

    def __init__(self, definition: ObjectDefinition, state: PackageBuildState) -> None:
        super().__init__(definition, state)
        self._texture_path = ReferencePath()

    @override
    def initialize(self, obj: UObject) -> None:
        outer = self.definition.outer

        if not isinstance(outer, FolderDefinition) or outer.outer is not None:
            msg = (
                f"{self.definition.reference}: SwfMovie must be directly inside "
                "a root package folder because GetPathForLoadMovie() omits "
                "intermediate outers"
            )
            raise ObjectDefinitionError(msg)

        if not isinstance(obj.payload, ObjectInstancePayload):
            msg = "SwfMovie requires an object instance payload"
            raise TypeError(msg)
        if obj.payload.class_path != SWF_MOVIE_PATH:
            msg = "Movie handling supports SwfMovie itself, not subclasses"
            raise NotImplementedError(msg)
        properties = self.definition.properties
        has_source = SOURCE_FIELD in properties
        has_texture = TEXTURE_FIELD in properties

        if has_source == has_texture:
            msg = f"{self.definition.reference}: Specify exactly one of Source or Texture"
            raise ObjectDefinitionError(msg)

        if has_source:
            if WIDTH_FIELD in properties or HEIGHT_FIELD in properties:
                msg = (
                    f"{self.definition.reference}: Width and Height only apply to "
                    "Texture generation; Source movies retain their existing layout"
                )
                raise ObjectDefinitionError(msg)
            self._initialize_source()
        else:
            self._initialize_texture()

    def _initialize_source(self) -> None:
        """Embed a premade movie without rewriting its data or references."""
        source_name = self.definition.properties[SOURCE_FIELD]

        if not isinstance(source_name, str) or not source_name:
            msg = f"{self.definition.reference}: Source must be a movie filename"
            raise ObjectDefinitionError(msg)

        source = self.object_reference.request_asset(source_name)

        try:
            data = source.read_bytes()
        except OSError as error:
            msg = f"{source}: Cannot read movie: {error}"
            raise ObjectDefinitionError(msg) from error

        if len(data) < MOVIE_HEADER.size:
            msg = f"{source}: Movie header is truncated"
            raise ObjectDefinitionError(msg)

        magic, _version, expected_size = MOVIE_HEADER.unpack_from(data)

        try:
            signature = MovieSignature(magic)
        except ValueError:
            msg = f"{source}: Unsupported movie signature {magic!r}; expected SWF or GFX"
            raise ObjectDefinitionError(msg) from None

        if signature is MovieSignature.LZMA_SWF:
            msg = f"{source}: LZMA-compressed SWF import is not implemented"
            raise NotImplementedError(msg)

        body = data[MOVIE_HEADER.size :]

        if signature in (MovieSignature.COMPRESSED_SWF, MovieSignature.COMPRESSED_GFX):
            try:
                body = zlib.decompress(body)
            except zlib.error as error:
                msg = f"{source}: Invalid compressed movie data: {error}"
                raise ObjectDefinitionError(msg) from error

        actual_size = MOVIE_HEADER.size + len(body)

        if expected_size != actual_size:
            msg = (
                f"{source}: Movie header declares {expected_size} uncompressed bytes, "
                f"but the file contains {actual_size}"
            )
            raise ObjectDefinitionError(msg)

        self.reference.RawData = list(data)

    def _initialize_texture(self) -> None:
        """Resolve the texture input for image-movie generation."""
        raw = self.reference.Texture
        if isinstance(raw, ReferencePath):
            path = raw

        elif isinstance(raw, str):  # pyright: ignore[reportUnnecessaryIsInstance]
            annotation, path = parse_reference_text(
                str(self.definition.reference), raw, self.definition.reference
            )
            if annotation is not None and annotation not in (
                TEXTURE_2D_PATH,
                TEXTURE_2D_SHORT_PATH,
            ):
                msg = f"{self.definition.reference}: Expected a Texture2D annotation"
                raise ObjectDefinitionError(msg)

        else:
            msg = f"{self.definition.reference}: Texture must be an object reference"
            raise ObjectDefinitionError(msg)

        if path.is_none():
            msg = f"{self.definition.reference}: Texture cannot be None"
            raise ObjectDefinitionError(msg)
        self._texture_path = path
        self.reference.References = [path]

    @override
    def prepare(self, obj: UObject) -> None:
        if self._texture_path.is_none():
            return

        try:
            texture = self.state.package.lookup_object_by_path(self._texture_path)
        except KeyError:
            msg = f"{self.definition.reference}: Unknown texture {self._texture_path}"
            raise ObjectDefinitionError(msg) from None
        if not isinstance(texture, UObject) or not isinstance(
            texture.payload, ObjectInstancePayload
        ):
            msg = (
                f"{self.definition.reference}: Experimental movie generation requires "
                "a Texture2D built in this package"
            )
            raise ObjectDefinitionError(msg)
        if texture.payload.class_path != TEXTURE_2D_PATH:
            msg = f"{self.definition.reference}: {self._texture_path} is not a Texture2D"
            raise ObjectDefinitionError(msg)

        width = texture.payload.properties.get(SIZE_X_FIELD)
        height = texture.payload.properties.get(SIZE_Y_FIELD)
        if not isinstance(width, IntValue) or not isinstance(height, IntValue):
            msg = f"{self.definition.reference}: Texture dimensions are not initialized"
            raise ObjectDefinitionError(msg)

        display_width = cast("int | None", self.definition.properties.get(WIDTH_FIELD))
        display_height = cast("int | None", self.definition.properties.get(HEIGHT_FIELD))

        for field, value in ((WIDTH_FIELD, display_width), (HEIGHT_FIELD, display_height)):
            if field in self.definition.properties and (type(value) is not int or value <= 0):
                msg = f"{self.definition.reference}: {field} must be a positive integer"
                raise ObjectDefinitionError(msg)

        if display_width is None and display_height is None:
            display_width = width.value
            display_height = height.value

        if display_width is None:
            if display_height is None:
                display_width = width.value
                display_height = height.value
            else:
                display_width = max(1, round(width.value * display_height / height.value))
        elif display_height is None:
            display_height = max(1, round(height.value * display_width / width.value))

        try:
            texture_filename = (
                PACKAGE_URL_PREFIX
                + self.state.package.object_path(texture).replace(".", "/")
                + TEXTURE_FILE_SUFFIX
            )
            movie = build_image_movie(
                str(texture.name), display_width, display_height, texture_filename
            )
        except ValueError as error:
            msg = f"{self.definition.reference}: {error}"
            raise ObjectDefinitionError(msg) from error
        self.reference.RawData = list(movie)
