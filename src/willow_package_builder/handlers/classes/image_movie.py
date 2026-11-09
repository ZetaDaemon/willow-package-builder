"""Generate a one-frame Scaleform movie displaying an external texture.

The container and external-image fields follow the supplied BL2 icon dump.
This is a small image-movie writer, not a general SWF compiler.
"""

import struct
import zlib
from enum import IntEnum, IntFlag

# SWF bit-field widths and fixed-point representations.
BITS_PER_BYTE = 8
FLAG_BITS = 1
BIT_COUNT_BITS = 5
STYLE_INDEX_WIDTH_BITS = 4
STYLE_CHANGE_FLAG_BITS = 5
EDGE_WIDTH_BITS = 4
EDGE_WIDTH_BIAS = 2
MAX_EDGE_BITS = (1 << EDGE_WIDTH_BITS) - 1 + EDGE_WIDTH_BIAS
FIXED_FRACTION_BITS = 16
FRAME_RATE_FRACTION_BITS = 8
FIXED_ONE = 1 << FIXED_FRACTION_BITS
TWIPS_PER_PIXEL = 20

# Tag length occupies the low six bits; all ones introduce a following UI32 length.
TAG_LENGTH_BITS = 6
EXTENDED_TAG_LENGTH = (1 << TAG_LENGTH_BITS) - 1
EXTENDED_NET_STRING_LENGTH = 0xFF
STRING_TERMINATOR = b"\0"

# Little-endian byte-aligned structures; variable-width fields use BitWriter.
BYTE = struct.Struct("<B")
CHARACTER_ID = struct.Struct("<H")
SHORT_TAG_HEADER = struct.Struct("<H")
LONG_TAG_HEADER = struct.Struct("<HI")
MOVIE_HEADER = struct.Struct("<3sBI")  # Signature, SWF version, uncompressed file length.
FRAME_HEADER = struct.Struct("<HH")  # FIXED8 frame rate, frame count.
EXPORTER_HEADER = struct.Struct("<HIH")  # Exporter version, flags, image file format.
EXTERNAL_IMAGE_HEADER = struct.Struct("<HHHHH")  # Image ID, ID category, format, width, height.
EXPORTED_ASSET_HEADER = struct.Struct("<HH")  # Asset count, character ID.
PLACEMENT_HEADER = struct.Struct("<BHH")  # Flags, display depth, character ID.
FILE_ATTRIBUTES = struct.Struct("<I")

# Container and exporter settings matching the supported BL2 GFX format.
COMPRESSED_GFX_SIGNATURE = b"CFX"
SWF_VERSION = 11
GFX_EXPORT_VERSION = 0x036E
FILE_TGA = 13
EXPORTER_FLAGS = 0
EXPORTER_IMAGE_PREFIX = ""
FILE_ATTRIBUTE_FLAGS = 0  # No ActionScript 3 or metadata declaration.
EXTERNAL_IMAGE_ID_CATEGORY = 0  # Image ID is an ordinary SWF character ID.
# Retain the extra zero byte observed after the external image's two NetStrings.
EXTERNAL_IMAGE_TRAILER = b"\0"

# Layout and resource IDs for this one-image, one-frame movie.
BITMAP_ID = 1
SHAPE_ID = 2
FILL_STYLE_COUNT = 1
FILL_STYLE_INDEX = 1
FILL_INDEX_BITS = FILL_STYLE_INDEX.bit_length()
LINE_STYLE_COUNT = 0
LINE_INDEX_BITS = 0
EXPORTED_ASSET_COUNT = 1
DISPLAY_DEPTH = 1
FRAME_COUNT = 1
FRAME_RATE = 24
MIN_DIMENSION = 1
MAX_DIMENSION = 2048
# Retain the existing stage and centred-artwork convention; this cleanup does not change layout.
STAGE_WIDTH = 550
STAGE_HEIGHT = 400
# MATRIX with no scale, rotation, or translation; unused final bit is padding.
IDENTITY_MATRIX = b"\x00"


class Tag(IntEnum):
    """SWF and Scaleform tag codes emitted by this writer."""

    END = 0
    SHOW_FRAME = 1
    DEFINE_SHAPE = 2
    PLACE_OBJECT_2 = 26
    EXPORT_ASSETS = 56
    FILE_ATTRIBUTES = 69
    EXPORTER_INFO = 1000
    DEFINE_EXTERNAL_IMAGE_2 = 1009


class PlaceObjectFlags(IntFlag):
    """Optional fields present in a PlaceObject2 record."""

    HAS_CHARACTER = 0x02
    HAS_MATRIX = 0x04


class ShapeRecordType(IntEnum):
    """First bit of a shape record."""

    STYLE_CHANGE = 0
    EDGE = 1


class StyleChangeFlags(IntFlag):
    """Fields following a shape's non-edge record bit."""

    NONE = 0
    MOVE_TO = 0x01
    FILL_STYLE_0 = 0x02
    FILL_STYLE_1 = 0x04
    LINE_STYLE = 0x08
    NEW_STYLES = 0x10


class BitmapFillType(IntEnum):
    """Bitmap fill encoding used for the rectangular image shape."""

    CLIPPED = 0x41


class BitWriter:
    """Write the most-significant-bit-first fields used by SWF."""

    _bits: list[int]

    def __init__(self) -> None:  # noqa: D107
        self._bits = []

    def unsigned(self, value: int, count: int) -> None:
        """Append an unsigned integer using exactly count bits."""
        if value < 0 or value >= 1 << count:
            msg = f"Value {value} does not fit in {count} unsigned bits"
            raise ValueError(msg)
        self._bits.extend((value >> bit) & 1 for bit in reversed(range(count)))

    def signed(self, value: int, count: int) -> None:
        """Append a signed integer using two's-complement encoding."""
        if not -(1 << (count - 1)) <= value < 1 << (count - 1):
            msg = f"Value {value} does not fit in {count} signed bits"
            raise ValueError(msg)
        self.unsigned(value & ((1 << count) - 1), count)

    def flag(self, *, enabled: bool) -> None:
        """Append one boolean bit."""
        self.unsigned(int(enabled), FLAG_BITS)

    def finish(self) -> bytes:
        """Return packed bytes with zero padding to the next byte boundary."""
        bits = self._bits + [0] * (-len(self._bits) % BITS_PER_BYTE)
        return bytes(
            sum(bits[start + bit] << (BITS_PER_BYTE - 1 - bit) for bit in range(BITS_PER_BYTE))
            for start in range(0, len(bits), BITS_PER_BYTE)
        )


def signed_bits(*values: int) -> int:
    """Return a common signed bit width, including the sign bit."""
    return max(1, *(value.bit_length() + 1 for value in values))


def rectangle(left: int, right: int, top: int, bottom: int) -> bytes:
    """Encode a SWF RECT using coordinates measured in twips."""
    bits = BitWriter()
    count = signed_bits(left, right, top, bottom)
    bits.unsigned(count, BIT_COUNT_BITS)
    for value in (left, right, top, bottom):
        bits.signed(value, count)
    return bits.finish()


def matrix(scale: int, x: int, y: int) -> bytes:
    """Encode equal FIXED16 axis scales and a twip translation, without rotation."""
    bits = BitWriter()
    bits.flag(enabled=True)  # HasScale.
    count = signed_bits(scale)
    bits.unsigned(count, BIT_COUNT_BITS)
    bits.signed(scale, count)
    bits.signed(scale, count)
    bits.flag(enabled=False)  # HasRotate.
    count = signed_bits(x, y)
    bits.unsigned(count, BIT_COUNT_BITS)
    bits.signed(x, count)
    bits.signed(y, count)
    return bits.finish()


def tag(code: Tag, payload: bytes = b"") -> bytes:
    """Prefix a tag with its code and short or extended payload length."""
    size = len(payload)
    header = code << TAG_LENGTH_BITS
    if size < EXTENDED_TAG_LENGTH:
        return SHORT_TAG_HEADER.pack(header | size) + payload
    return LONG_TAG_HEADER.pack(header | EXTENDED_TAG_LENGTH, size) + payload


def net_string(text: str) -> bytes:
    """Encode a short UTF-8 NetString, with a byte count and no terminator."""
    encoded = text.encode("utf-8")
    if len(encoded) >= EXTENDED_NET_STRING_LENGTH:
        msg = (
            "Experimental image movies require names shorter than "
            f"{EXTENDED_NET_STRING_LENGTH} UTF-8 bytes"
        )
        raise ValueError(msg)
    return BYTE.pack(len(encoded)) + encoded


def _write_straight_edge(bits: BitWriter, dx: int, dy: int) -> None:
    """Append one horizontal or vertical edge of the image rectangle."""
    delta = dx or dy
    count = max(EDGE_WIDTH_BIAS, signed_bits(delta))
    if count > MAX_EDGE_BITS:
        msg = "Image edge exceeds the SWF straight-edge limit"
        raise ValueError(msg)
    bits.unsigned(ShapeRecordType.EDGE, FLAG_BITS)
    bits.flag(enabled=True)  # StraightFlag: this is not a curved edge.
    bits.unsigned(count - EDGE_WIDTH_BIAS, EDGE_WIDTH_BITS)
    bits.flag(enabled=False)  # GeneralLineFlag: only one coordinate changes.
    bits.flag(enabled=dx == 0)  # VertLineFlag.
    bits.signed(delta, count)


def image_shape(width: int, height: int) -> bytes:
    """Encode a centred rectangle with one clipped external-bitmap fill."""
    width *= TWIPS_PER_PIXEL
    height *= TWIPS_PER_PIXEL
    left, top = -(width // 2), -(height // 2)
    bounds = rectangle(left, left + width, top, top + height)
    fills = BYTE.pack(FILL_STYLE_COUNT) + BYTE.pack(BitmapFillType.CLIPPED)
    fills += CHARACTER_ID.pack(BITMAP_ID)
    fills += matrix(TWIPS_PER_PIXEL * FIXED_ONE, left, top)

    bits = BitWriter()
    bits.unsigned(FILL_INDEX_BITS, STYLE_INDEX_WIDTH_BITS)
    bits.unsigned(LINE_INDEX_BITS, STYLE_INDEX_WIDTH_BITS)
    bits.unsigned(ShapeRecordType.STYLE_CHANGE, FLAG_BITS)
    flags = StyleChangeFlags.FILL_STYLE_1 | StyleChangeFlags.MOVE_TO
    bits.unsigned(flags, STYLE_CHANGE_FLAG_BITS)
    count = signed_bits(left, top)
    bits.unsigned(count, BIT_COUNT_BITS)
    bits.signed(left, count)
    bits.signed(top, count)
    bits.unsigned(FILL_STYLE_INDEX, FILL_INDEX_BITS)

    for dx, dy in ((width, 0), (0, height), (-width, 0), (0, -height)):
        _write_straight_edge(bits, dx, dy)

    # EndShapeRecord is a non-edge record with every style-change flag cleared.
    bits.unsigned(ShapeRecordType.STYLE_CHANGE, FLAG_BITS)
    bits.unsigned(StyleChangeFlags.NONE, STYLE_CHANGE_FLAG_BITS)
    return (
        CHARACTER_ID.pack(SHAPE_ID) + bounds + fills + BYTE.pack(LINE_STYLE_COUNT) + bits.finish()
    )


def build_image_movie(texture_name: str, width: int, height: int, texture_filename: str) -> bytes:
    """Build a compressed, single-frame GFX movie referencing one external image."""
    if not MIN_DIMENSION <= width <= MAX_DIMENSION or not MIN_DIMENSION <= height <= MAX_DIMENSION:
        msg = (
            f"Experimental image movies support dimensions from {MIN_DIMENSION} to {MAX_DIMENSION}"
        )
        raise ValueError(msg)
    if not texture_name or "\0" in texture_name:
        msg = "Movie texture name must be non-empty and contain no NUL"
        raise ValueError(msg)

    exporter = EXPORTER_HEADER.pack(GFX_EXPORT_VERSION, EXPORTER_FLAGS, FILE_TGA)
    exporter += net_string(EXPORTER_IMAGE_PREFIX) + net_string(texture_name)

    external = EXTERNAL_IMAGE_HEADER.pack(
        BITMAP_ID, EXTERNAL_IMAGE_ID_CATEGORY, FILE_TGA, width, height
    )
    external += net_string(texture_name) + net_string(texture_filename) + EXTERNAL_IMAGE_TRAILER

    exports = EXPORTED_ASSET_HEADER.pack(EXPORTED_ASSET_COUNT, BITMAP_ID)
    exports += texture_name.encode("utf-8") + STRING_TERMINATOR

    placement_flags = PlaceObjectFlags.HAS_CHARACTER | PlaceObjectFlags.HAS_MATRIX
    placement = PLACEMENT_HEADER.pack(placement_flags, DISPLAY_DEPTH, SHAPE_ID) + IDENTITY_MATRIX

    body = rectangle(0, STAGE_WIDTH * TWIPS_PER_PIXEL, 0, STAGE_HEIGHT * TWIPS_PER_PIXEL)
    body += FRAME_HEADER.pack(FRAME_RATE << FRAME_RATE_FRACTION_BITS, FRAME_COUNT)
    body += b"".join(
        (
            tag(Tag.EXPORTER_INFO, exporter),
            tag(Tag.FILE_ATTRIBUTES, FILE_ATTRIBUTES.pack(FILE_ATTRIBUTE_FLAGS)),
            tag(Tag.DEFINE_EXTERNAL_IMAGE_2, external),
            tag(Tag.EXPORT_ASSETS, exports),
            tag(Tag.DEFINE_SHAPE, image_shape(width, height)),
            tag(Tag.PLACE_OBJECT_2, placement),
            tag(Tag.SHOW_FRAME),
            tag(Tag.END),
        )
    )
    header = MOVIE_HEADER.pack(COMPRESSED_GFX_SIGNATURE, SWF_VERSION, len(body) + MOVIE_HEADER.size)
    return header + zlib.compress(body)
