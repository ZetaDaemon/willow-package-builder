# Willow Package Builder

Willow Package Builder (WPB) builds Unreal packages (`.upk`). Currently supporting Borderlands 2 and Borderlands The Presequel.

## Requirements

- Python **3.14 or newer**.
- [Git](https://git-scm.com/install), available on your `PATH`, for installation from this repository.
- Either **uv** or **pipx**. Choose one installation method below.

Both methods install WPB in an isolated environment and make the `willow-package-builder` command available from any directory. You do not need to clone this repository to use WPB.

The installation commands below use the `latest` tag, which tracks the latest stable release. Prereleases do not move this tag.

## Install with uv

Install uv by following the [official installation instructions](https://docs.astral.sh/uv/getting-started/installation/), then run:

```sh
uv tool install --python 3.14 "git+https://github.com/ZetaDaemon/willow-package-builder.git@latest"
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
pipx install --python 3.14 "git+https://github.com/ZetaDaemon/willow-package-builder.git@latest"
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

## Install a specific version

Replace `latest` with the release tag you want. For example, for a release tagged `v0.2.0`:

```sh
uv tool install --force --python 3.14 "git+https://github.com/ZetaDaemon/willow-package-builder.git@v0.2.0"
```

Or with pipx:

```sh
pipx install --force --python 3.14 "git+https://github.com/ZetaDaemon/willow-package-builder.git@v0.2.0"
```

`--force` replaces an existing installation if present. A specific version tag stays on that release; upgrading does not switch it to another release tag. Reinstall with `@latest` to return to the stable update channel.

### Prereleases

Install a prerelease using its exact tag, for example `v0.3.0rc1`:

```sh
uv tool install --force --python 3.14 "git+https://github.com/ZetaDaemon/willow-package-builder.git@v0.3.0rc1"
```

For pipx, replace the tag in its installation command in the same way. These version tags are examples; select a tag that exists on the [releases page](https://github.com/ZetaDaemon/willow-package-builder/releases).

## Verify installation

```sh
willow-package-builder --help
```

Use the hyphenated command `willow-package-builder`; the Python module is named `willow_package_builder`.

## Usage
See [USAGE.md](USAGE.md) for package setup and object definitions.