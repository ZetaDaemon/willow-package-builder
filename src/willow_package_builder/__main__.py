import argparse
from pathlib import Path
from typing import cast

from willow_package_builder.games import TargetGame, select_game
from willow_package_builder.logging import WarningAction, WarningCode

from . import build_package


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
    args = parser.parse_args()

    conflicting = set(args.ignore_warning) & set(args.error_warning)

    if conflicting:
        codes = ", ".join(sorted(code.value for code in conflicting))
        parser.error(f"Warnings cannot be both ignored and errors: {codes}")

    default_action = cast("WarningAction", args.warnings)
    warning_actions: dict[WarningCode, WarningAction] = dict.fromkeys(WarningCode, default_action)
    warning_actions.update(dict.fromkeys(args.ignore_warning, WarningAction.IGNORE))
    warning_actions.update(dict.fromkeys(args.error_warning, WarningAction.ERROR))

    with select_game(args.game):
        build_package(
            args.target,
            args.output,
            debug=args.debug,
            silent_console=args.silent_console,
            warning_actions=warning_actions,
        )


if __name__ == "__main__":
    main()
