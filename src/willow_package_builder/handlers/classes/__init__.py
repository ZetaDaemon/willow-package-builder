from typing import TYPE_CHECKING

from willow_package_builder.handlers.classes.behavior_provider_definition_handler import (
    BehaviorProviderDefinitionHandler,
)
from willow_package_builder.handlers.classes.component_handler import ComponentHandler
from willow_package_builder.handlers.classes.static_mesh_component_handler import (
    StaticMeshComponentHandler,
)
from willow_package_builder.handlers.classes.weapon_partlist_handler import (
    WeaponPartListDefinitionHandler,
)
from willow_package_builder.handlers.classes.weapon_partlistcollection_handler import (
    WeaponPartListCollectionDefinitionHandler,
)

from .swfmovie_handler import SwfMovieHandler
from .texture2d_handler import Texture2DHandler

if TYPE_CHECKING:
    from willow_package_builder.handlers.classes.class_handler import ClassHandler

CLASS_HANDLERS: tuple[type[ClassHandler], ...] = (
    Texture2DHandler,
    SwfMovieHandler,
    WeaponPartListDefinitionHandler,
    WeaponPartListCollectionDefinitionHandler,
    BehaviorProviderDefinitionHandler,
    ComponentHandler,
    StaticMeshComponentHandler,
)
