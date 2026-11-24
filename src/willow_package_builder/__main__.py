import argparse
from pathlib import Path
from typing import Protocol, cast

from willow_package_builder.build_settings import BuildSettings
from willow_package_builder.games import TargetGame, select_game
from willow_package_builder.logging import WarningAction, WarningCode

from . import build_package


class BuildArguments(Protocol):
    """Typed interface for the parsed command-line arguments."""

    game: TargetGame
    target: Path
    output: Path | None

    debug: bool
    silent_console: bool
    log_objects: bool
    force: bool
    re_cache: bool

    warnings: WarningAction
    ignore_warning: list[WarningCode]
    error_warning: list[WarningCode]

    reference_path: list[Path]


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="willow-package-builder", description="Build packages for Borderlands."
    )
    parser.add_argument("game", type=TargetGame, choices=list(TargetGame), help="The game target.")
    parser.add_argument("target", type=Path, help="Package source directory")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output directory; defaults to the target's parent directory",
    )
    parser.add_argument("--debug", action="store_true", help="Show Python tracebacks")
    parser.add_argument(
        "--silent",
        "--silent-console",
        dest="silent_console",
        action="store_true",
        help="Write build messages only to the log file",
    )
    parser.add_argument(
        "--warnings",
        type=WarningAction,
        choices=list(WarningAction),
        default=WarningAction.WARN,
        help="Default warning action: warn, ignore, or error",
    )
    parser.add_argument(
        "--ignore-warning",
        type=WarningCode,
        choices=list(WarningCode),
        action="append",
        default=[],
        help="Ignore a warning category; may be repeated",
    )
    parser.add_argument(
        "--error-warning",
        type=WarningCode,
        choices=list(WarningCode),
        action="append",
        default=[],
        help="Treat a warning category as an error; may be repeated",
    )
    parser.add_argument(
        "--reference-path",
        type=Path,
        action="append",
        default=[],
        help="Directory containing reference package folders; may be repeated",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Rebuild packages even when their outputs are up to date",
    )
    parser.add_argument(
        "--re-cache",
        action="store_true",
        help="Reparse class sources and regenerate declaration caches",
    )
    parser.add_argument(
        "--log-objects", action="store_true", help="Log each top-level object as it is built"
    )
    args = cast("BuildArguments", parser.parse_args())  # pyright: ignore[reportInvalidCast]

    conflicting = set(args.ignore_warning) & set(args.error_warning)

    if conflicting:
        codes = ", ".join(sorted(code.value for code in conflicting))
        parser.error(f"Warnings cannot be both ignored and errors: {codes}")

    default_action = args.warnings
    warning_actions: dict[WarningCode, WarningAction] = dict.fromkeys(WarningCode, default_action)
    warning_actions.update(dict.fromkeys(args.ignore_warning, WarningAction.IGNORE))
    warning_actions.update(dict.fromkeys(args.error_warning, WarningAction.ERROR))

    with select_game(args.game):
        build_package(
            args.target,
            args.output,
            warning_actions=warning_actions,
            reference_paths=tuple(args.reference_path),
            settings=BuildSettings(
                debug=args.debug,
                silent_console=args.silent_console,
                log_objects=args.log_objects,
                force=args.force,
                re_cache=args.re_cache,
            ),
        )


if __name__ == "__main__":
    main()
