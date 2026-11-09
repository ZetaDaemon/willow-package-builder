from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from willow_package_builder.upackage import Package


@dataclass(frozen=True)
class SerializationContext:
    """Package and layout information for payload serialization."""

    package: Package
    payload_offset: int | None = None

    def require_payload_offset(self) -> int:
        """Return the final payload offset when the layout is available."""
        if self.payload_offset is None:
            msg = "Payload layout has not been finalized"
            raise RuntimeError(msg)

        return self.payload_offset
