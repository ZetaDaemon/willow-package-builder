#!/usr/bin/env bash
set -euo pipefail

uv run python -m willow_package_builder "example uc/ExamplePackage" --output tests