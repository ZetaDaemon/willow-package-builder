from contextlib import contextmanager
from contextvars import ContextVar
from enum import StrEnum
from typing import TYPE_CHECKING

from willow_package_builder.games.tps import TPS

from .bl2 import Bl2

if TYPE_CHECKING:
    from collections.abc import Generator

    from .game import Game


class TargetGame(StrEnum):
    BL1 = "bl1"
    BL2 = "bl2"
    TPS = "tps"


GAME_DICT: dict[TargetGame, type[Game]] = {TargetGame.BL2: Bl2, TargetGame.TPS: TPS}

_active_game: ContextVar[Game | None] = ContextVar("active_game", default=None)


def get_game() -> Game:
    game = _active_game.get()

    if game is None:
        msg = "No target game is active"
        raise RuntimeError(msg)

    return game


@contextmanager
def select_game(target: TargetGame) -> Generator[Game]:
    if _active_game.get() is not None:
        msg = "A target game is already active"
        raise RuntimeError(msg)

    game_class = GAME_DICT.get(target)

    if game_class is None:
        msg = f"Target game {target.value!r} is not supported yet"
        raise NotImplementedError(msg)

    game = game_class()
    token = _active_game.set(game)

    try:
        yield game
    finally:
        _active_game.reset(token)
