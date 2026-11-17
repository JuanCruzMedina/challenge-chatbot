"""Spec: a pull request is read from a file (add-pr-doc-review)."""
from __future__ import annotations

from pathlib import Path

import pytest

from ecosystem_assistant.pr_review.pull_request import PullRequestError, load_pull_request
from tests.data.helpers import SAMPLE

SAMPLE_PR = Path(SAMPLE) / "prs" / "pr-101-payments-api-v2" / "pr.yaml"


def test_the_sample_pull_request_is_loaded() -> None:
    pr = load_pull_request(SAMPLE_PR)

    assert (pr.id, pr.service) == ("PR-101", "payments-service")
    assert "automatic retries" in pr.title and "deprecated" in pr.description
    assert [(c.path, c.status) for c in pr.changes] == [
        ("service.yaml", "modified"), ("README.md", "modified"), ("docs/api-v2.md", "added")]


def test_a_patch_is_kept_when_given(tmp_path: Path) -> None:
    f = tmp_path / "pr.yaml"
    f.write_text("id: PR-1\nrepo: acme/orders-service\ntitle: T\nchanges:\n  - path: a.py\n    patch: '+x = 1'\n")
    pr = load_pull_request(f)
    assert pr.changes[0].patch == "+x = 1" and pr.description == "" and pr.changes[0].status == "modified"


@pytest.mark.parametrize(("content", "field"), [
    ("repo: a/b\ntitle: T\n", "id"),
    ("id: PR-1\ntitle: T\n", "repo"),
    ("id: PR-1\nrepo: a/b\n", "title"),
    ("id: PR-1\nrepo: a/b\ntitle: T\nchanges:\n  - status: added\n", "path"),
    ("id: PR-1\nrepo: a/b\ntitle: T\nchanges: nope\n", "changes"),
])
def test_an_invalid_file_names_the_problem(tmp_path: Path, content: str, field: str) -> None:
    f = tmp_path / "pr.yaml"
    f.write_text(content)
    with pytest.raises(PullRequestError, match=field):
        load_pull_request(f)


def test_a_missing_or_broken_file_is_a_clear_error(tmp_path: Path) -> None:
    with pytest.raises(PullRequestError, match="cannot be read"):
        load_pull_request(tmp_path / "nope.yaml")
    bad = tmp_path / "bad.yaml"
    bad.write_text("id: [unclosed")
    with pytest.raises(PullRequestError, match="not valid YAML"):
        load_pull_request(bad)
