import argparse
from pathlib import Path

from . import build_package


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="willow-package-builder", description="Build packages for Borderlands."
    )
    parser.add_argument("target", type=Path, help="Package source directory")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output directory; defaults to the target's parent directory",
    )
    parser.add_argument("--debug", action="store_true", help="Show Python tracebacks")
    args = parser.parse_args()

    build_package(args.target, args.output, debug=args.debug)


if __name__ == "__main__":
    main()
