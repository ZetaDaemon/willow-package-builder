# Willow Package Builder

Willow Package Builder builds Unreal packages (`.upk`). Currently supporting Borderlands 2 and Borderlands The Presequel.

## Requirements

- Python **3.14 or newer**.
- [Git](https://git-scm.com/install), available on your `PATH`, for installation from this repository.
- Either **uv** or **pipx**. Choose one installation method below.

Both methods install WPB in an isolated environment and make the `willow-package-builder` command available from any directory. You do not need to clone this repository to use WPB.

## Install with uv

Install uv by following the [official installation instructions](https://docs.astral.sh/uv/getting-started/installation/), then run:

```sh
uv tool install --python 3.14 git+https://github.com/ZetaDaemon/willow-package-builder.git
```

If the tool executable directory is not on your `PATH`, run:

```sh
uv tool update-shell
```

Restart your terminal after changing your `PATH`.

### Update

```sh
uv tool upgrade willow-package-builder
```

### Uninstall

```sh
uv tool uninstall willow-package-builder
```

## Install with pipx

Install pipx using its [official documentation](https://pipx.pypa.io/). Ensure Python 3.14 or newer is installed, then run:

```sh
pipx install --python 3.14 git+https://github.com/ZetaDaemon/willow-package-builder.git
pipx ensurepath
```

If pipx cannot locate Python 3.14, replace `3.14` with the full path to a compatible Python executable.

Restart your terminal after changing your `PATH`.

### Update

```sh
pipx upgrade willow-package-builder
```

### Uninstall

```sh
pipx uninstall willow-package-builder
```

## Verify installation

```sh
willow-package-builder --help
```

Use the hyphenated command `willow-package-builder`; the Python module is named `willow_package_builder`.

## Build a package

Pass the game target and the directory containing your source package's `package.toml`:

```sh
willow-package-builder bl2 "path/to/MyPackage"
```

For The Pre-Sequel:

```sh
willow-package-builder tps "path/to/MyPackage"
```

The source package must be configured with the reference packages it needs. Use reference class dumps for the target game.

By default, output is written next to the source package directory. Specify an output directory with `--output`:

```sh
willow-package-builder bl2 "path/to/MyPackage" --output "path/to/output"
```

A successful build writes a `.upk` file and a corresponding `.manifest.json` file. Their names come from the package configuration.

### Logging and warnings

```sh
# Show Python tracebacks for build errors.
willow-package-builder bl2 "path/to/MyPackage" --debug

# Write build messages only to the log file.
willow-package-builder bl2 "path/to/MyPackage" --silent

# Treat all warnings as errors.
willow-package-builder bl2 "path/to/MyPackage" --warnings error
```

Build logs are written to `willow-package-builder.log` in the source package directory's parent. Run `willow-package-builder --help` for all options, including controls for individual warning categories.
