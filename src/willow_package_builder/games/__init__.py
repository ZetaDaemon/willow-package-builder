from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING

from willow_package_builder.games.game import TargetGame as TargetGame

from .bl2 import Bl2
from .tps import TPS

if TYPE_CHECKING:
    from collections.abc import Generator

    from .game import Game

__all__ = ["TargetGame", "get_game", "select_game"]

GAMES: tuple[type[Game], ...] = (Bl2, TPS)

GAME_DICT = {g.TARGET: g for g in GAMES}

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
