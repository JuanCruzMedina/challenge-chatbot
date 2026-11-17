"""A pull request read from a YAML file, in the format of the sample ``prs/*/pr.yaml`` (design.md D-5)."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


class PullRequestError(ValueError):
    """The pull request file is not valid. The message names the field."""


@dataclass(frozen=True)
class Change:
    path: str
    status: str
    patch: str = ""


@dataclass(frozen=True)
class PullRequest:
    id: str
    repo: str
    title: str
    description: str
    changes: list[Change] = field(default_factory=list)

    @property
    def service(self) -> str:
        """The service the repository holds: the last part of ``owner/service``."""
        return self.repo.rsplit("/", 1)[-1]


def _text(data: dict[str, Any], key: str, where: str, required: bool = True) -> str:
    value = data.get(key)
    if value is None or (isinstance(value, str) and not value.strip()):
        if required:
            raise PullRequestError(f"{where}: the field '{key}' is missing or empty")
        return ""
    if not isinstance(value, str):
        raise PullRequestError(f"{where}: the field '{key}' must be text")
    return value.strip()


def parse_pull_request(data: Any, source: str = "pull request") -> PullRequest:
    if not isinstance(data, dict):
        raise PullRequestError(f"{source}: expected a mapping with id, repo, title, description and changes")
    changes_raw = data.get("changes", [])
    if not isinstance(changes_raw, list):
        raise PullRequestError(f"{source}: the field 'changes' must be a list")
    changes: list[Change] = []
    for number, entry in enumerate(changes_raw, start=1):
        where = f"{source}: change {number}"
        if not isinstance(entry, dict):
            raise PullRequestError(f"{where} must be a mapping with path and status")
        changes.append(Change(_text(entry, "path", where), _text(entry, "status", where, required=False) or "modified",
                              str(entry.get("patch") or "")))
    return PullRequest(
        id=_text(data, "id", source), repo=_text(data, "repo", source), title=_text(data, "title", source),
        description=_text(data, "description", source, required=False), changes=changes,
    )


def load_pull_request(path: Path) -> PullRequest:
    path = Path(path)
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise PullRequestError(f"{path}: cannot be read ({error.strerror or error})") from error
    except yaml.YAMLError as error:
        raise PullRequestError(f"{path}: is not valid YAML ({error})") from error
    return parse_pull_request(data, str(path))
