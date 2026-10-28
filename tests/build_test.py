from pathlib import Path

from willow_package_builder import build_package

project_directory = Path(__file__).resolve().parents[1]
target_directory = (project_directory / "example uc" / "ExamplePackage").resolve()

build_package(target_directory, Path(__file__).parent)
