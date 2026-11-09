from typing import TYPE_CHECKING

from .swfmovie_handler import SwfMovieHandler
from .texture2d_handler import Texture2DHandler

if TYPE_CHECKING:
    from willow_package_builder.handlers.classes.class_handler import ClassHandler

CLASS_HANDLERS: tuple[type[ClassHandler], ...] = (Texture2DHandler, SwfMovieHandler)
