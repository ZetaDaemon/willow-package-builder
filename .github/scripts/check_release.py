"""Check whether the package version needs a GitHub release."""

import json
import os
import re
import subprocess
import tomllib
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

from packaging.version import InvalidVersion, Version


def release_notes(version: Version, changelog: Path) -> str:
    """Extract one version's Markdown section from the changelog."""
    text = changelog.read_text(encoding="utf-8")
    headings = list(re.finditer(r"^##[ \t]+(.+)$", text, re.MULTILINE))
    matches: list[str] = []

    for index, heading in enumerate(headings):
        label = re.match(r"\[([^\]]+)\]", heading.group(1))
        if label is None:
            continue
        try:
            section_version = Version(label.group(1))
        except InvalidVersion:
            continue
        if section_version != version:
            continue

        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        matches.append(text[heading.end() : end].strip())

    if len(matches) != 1:
        msg = (
            f"{changelog}: Expected exactly one section for version {version}, found {len(matches)}"
        )
        raise RuntimeError(msg)
    if not matches[0]:
        msg = f"{changelog}: Release notes for {version} are empty"
        raise RuntimeError(msg)
    return matches[0] + "\n"


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
        notes = release_notes(version, Path("CHANGELOG.md"))
        Path("release-notes.md").write_text(notes, encoding="utf-8")

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
