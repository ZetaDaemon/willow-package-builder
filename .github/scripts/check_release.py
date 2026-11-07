"""Check whether the package version needs a GitHub release."""

import json
import os
import subprocess
import tomllib
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

from packaging.version import Version


def main() -> None:
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))["project"]
    version = Version(project["version"])
    tag = f"v{version}"
    url = f"{os.environ['GITHUB_API_URL']}/repos/{os.environ['GH_REPO']}/releases/tags/{quote(tag, safe='')}"
    request = Request(
        url,
        headers={
            "Authorization": f"Bearer {os.environ['GH_TOKEN']}",
            "Accept": "application/vnd.github+json",
        },
    )
    try:
        with urlopen(request) as response:
            release = json.load(response)
    except HTTPError as error:
        if error.code != 404:
            raise
        release = None

    publish = release is None or release["draft"]
    if publish:
        existing_tag = subprocess.run(
            ["git", "rev-parse", "--verify", f"refs/tags/{tag}^{{commit}}"],
            capture_output=True,
            text=True,
        )
        if existing_tag.returncode == 0 and existing_tag.stdout.strip() != os.environ["GITHUB_SHA"]:
            msg = f"{tag} already points to another commit; increment the version"
            raise RuntimeError(msg)

    with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as output:
        print(f"tag={tag}", file=output)
        print(f"publish={str(publish).lower()}", file=output)
        print(
            f"prerelease={str(version.is_prerelease or version.is_devrelease).lower()}", file=output
        )
    print(f"{tag}: {'build and publish' if publish else 'already released; skipping'}")


if __name__ == "__main__":
    main()
