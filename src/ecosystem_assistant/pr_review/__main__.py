"""Entry point: ``uv run python -m ecosystem_assistant.pr_review <pr.yaml> [--dry-run]`` (design.md D-4, D-7).

Meant to be called by CI when a pull request is merged. Exit code 0 after a review, 2 when the pull request file,
the workspace or the model cannot be used.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from ecosystem_assistant.pr_review.pull_request import PullRequestError, load_pull_request
from ecosystem_assistant.pr_review.review import AgentOpener, review_pull_request


def default_opener(workspace: Path, audit_file: Path | None, scratch: Path | None,
                   server_env: Mapping[str, str]) -> Any:
    """The real agent. A dry run gets its own index in the scratch folder so the project's index is not touched."""
    from ecosystem_assistant.agent.agent import Agent
    from ecosystem_assistant.agent.knowledge import KnowledgeService
    from ecosystem_assistant.knowledge.retrieval.index import RetrievalIndex
    from ecosystem_assistant.llm.settings import llm_from_env

    index = RetrievalIndex(scratch / "index") if scratch is not None else RetrievalIndex()
    return Agent.open(workspace=workspace, audit_file=audit_file,
                      knowledge=KnowledgeService(workspace, index, llm_from_env()), extra_env=server_env)


def main(
    argv: list[str] | None = None,
    agent_opener: AgentOpener = default_opener,
    write: Callable[[str], Any] = print,
) -> int:
    parser = argparse.ArgumentParser(prog="python -m ecosystem_assistant.pr_review", description=__doc__)
    parser.add_argument("pull_request", type=Path, help="the pull request file (YAML, like prs/*/pr.yaml)")
    parser.add_argument("--workspace", type=Path, default=None,
                        help="the workspace to review (default: AGENT_DATA_ROOT or var/workspace)")
    parser.add_argument("--dry-run", action="store_true", help="work on a copy and only report what would change")
    args = parser.parse_args(argv)

    from ecosystem_assistant.agent.knowledge import DEFAULT_DATA_ROOT
    from ecosystem_assistant.agent.settings import AgentModelError
    from ecosystem_assistant.llm.port import LLMUnavailableError

    workspace = Path(args.workspace or os.environ.get("AGENT_DATA_ROOT") or DEFAULT_DATA_ROOT)
    if not (workspace / "company.yaml").is_file():
        write(f"There is no ecosystem data in {workspace}. Create the workspace with: "
              f"uv run python scripts/seed_workspace.py")
        return 2
    try:
        pr = load_pull_request(args.pull_request)
        report = asyncio.run(review_pull_request(pr, workspace, agent_opener, dry_run=args.dry_run))
    except (PullRequestError, AgentModelError, LLMUnavailableError) as error:
        write(f"ABORTED: {error}")
        return 2
    write(report.render())
    return 0


if __name__ == "__main__":
    sys.exit(main())
