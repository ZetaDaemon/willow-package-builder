from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from willow_package_builder.games import get_game
from willow_package_builder.logging import info
from willow_package_builder.upackage import FName, Package

from .build_state import PackageBuildState
from .classes.class_builder import ClassBuilder
from .classes.enum_builder import EnumBuilder
from .classes.function_builder import FunctionBuilder
from .classes.property_builder import PropertyBuilder
from .classes.struct_builder import StructBuilder
from .objects.object_builder import ObjectBuilder
from .references import PackageReferences

if TYPE_CHECKING:
    from willow_package_builder.package_config import PackageConfig

    from .build_context import BuildContext
    from .classes.exports import ClassExports, StructExports


@dataclass
class PackageBuilder:
    """Package builder class.

    The different parts of building a package are delegated to different classes.
    The classes share a PackageBuildState to track progress.
    """

    context: BuildContext
    config: PackageConfig

    state: PackageBuildState = field(init=False)
    references: PackageReferences = field(init=False)
    properties: PropertyBuilder = field(init=False)
    functions: FunctionBuilder = field(init=False)
    struct_builder: StructBuilder = field(init=False)
    enums: EnumBuilder = field(init=False)
    class_builder: ClassBuilder = field(init=False)
    object_builder: ObjectBuilder = field(init=False)

    @property
    def package(self) -> Package:
        """Access package from state."""
        return self.state.package

    @property
    def classes(self) -> dict[str, ClassExports]:
        """Access classes from state."""
        return self.state.classes

    @property
    def structs(self) -> dict[str, StructExports]:
        """Access structs from state."""
        return self.state.structs

    def __post_init__(self) -> None:
        """Post init."""
        game = get_game()
        package = Package(FName(self.config.name), game.package_format(), game.PACKAGE_FLAGS)

        self.state = PackageBuildState(self.context, self.config, package)
        self.references = PackageReferences(self.state)
        self.properties = PropertyBuilder(self.state, self.references)
        self.functions = FunctionBuilder(self.state, self.references, self.properties)
        self.struct_builder = StructBuilder(self.state, self.references, self.properties)
        self.enums = EnumBuilder(self.state, self.references)
        self.class_builder = ClassBuilder(self.state, self.references, self.properties)
        self.object_builder = ObjectBuilder(self.state, self.references)

    def manifest(self) -> dict[str, object]:
        """Create the package manifest."""
        return {
            "classes": [
                f"{self.config.name}.{exports.class_object.reference()}"
                for exports in self.classes.values()
            ]
        }

    def build(self) -> Package:
        """Build the package."""
        # Compile classes
        info("Compiling classes")
        self.class_builder.reserve_classes()
        self.class_builder.link_classes()
        self.struct_builder.reserve_structs()
        self.struct_builder.link_structs()
        self.struct_builder.validate_struct_layouts()
        self.enums.build_class_enums()
        self.struct_builder.build_struct_fields()
        self.class_builder.build_class_fields()
        self.functions.build_class_functions()

        # Construct objects
        info("Constructing objects")
        self.object_builder.read_objects()
        self.object_builder.reserve_objects()
        self.object_builder.initialize_payloads()
        self.object_builder.build_all_properties()

        return self.package
