"""Run the agent on a pull request and report what happened (design.md D-1, D-3, D-4)."""
from __future__ import annotations

import difflib
import json
import shutil
import tempfile
from collections.abc import Callable, Mapping
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ecosystem_assistant.agent.knowledge import TOOL_NAME as KNOWLEDGE_TOOL
from ecosystem_assistant.agent.records import ToolCallRecord
from ecosystem_assistant.pr_review.prompts import REVIEW_INSTRUCTIONS
from ecosystem_assistant.pr_review.pull_request import PullRequest

MAX_PATCH_CHARS = 4000
MAX_TOTAL_PATCH_CHARS = 12000

# Opens an agent on a workspace: (workspace, audit file or None, scratch folder or None, environment of the actions
# server) -> async context manager.
AgentOpener = Callable[[Path, Path | None, Path | None, Mapping[str, str]], AbstractAsyncContextManager[Any]]


def server_environment(pr: PullRequest) -> dict[str, str]:
    """What the actions server is told for a review: write only the PR's service, and do not wait for confirmation.

    The server enforces it, so a PR text that asks for more cannot get it, whatever the model does.
    """
    return {"ACTIONS_ALLOWED_SERVICES": pr.service, "ACTIONS_CONFIRM_EDITS": "off"}


def call_status(record: ToolCallRecord) -> str:
    """``failed`` for a tool error, ``conflict`` when the result says nothing was written, ``ok`` otherwise.

    It reads the result's own ``outcome`` field; it knows no tool by name.
    """
    if record.error:
        return "failed"
    try:
        payload = json.loads(record.result)
    except ValueError:
        return "ok"
    return "conflict" if isinstance(payload, dict) and payload.get("outcome") == "conflict" else "ok"


@dataclass
class ReviewReport:
    pr_id: str
    decision: str                                    # "changed" or "no_change", derived from the files
    tool_calls: list[ToolCallRecord] = field(default_factory=list)   # every call but the knowledge tool
    diffs: dict[str, str] = field(default_factory=dict)              # path -> unified diff
    explanation: str = ""                            # the model's own words
    dry_run: bool = False

    @property
    def wrote_nothing(self) -> int:
        """How many tool calls did not write anything (failed or conflict)."""
        return len([c for c in self.tool_calls if call_status(c) != "ok"])

    def to_dict(self) -> dict[str, Any]:
        return {"pr_id": self.pr_id, "decision": self.decision, "dry_run": self.dry_run,
                "tool_calls": [{**c.to_dict(), "status": call_status(c)} for c in self.tool_calls],
                "diffs": dict(self.diffs), "explanation": self.explanation}

    def render(self) -> str:
        head = f"{self.pr_id}: " + ("documentation changed" if self.decision == "changed" else "no documentation change")
        lines = [head + (" (dry run: nothing was written for real)" if self.dry_run else "")]
        for call in self.tool_calls:
            status = call_status(call)
            lines.append(f"  - {call.name}" + ("" if status == "ok" else f" ({status})"))
        if self.wrote_nothing:
            lines.append(f"  {self.wrote_nothing} {'call' if self.wrote_nothing == 1 else 'calls'} wrote nothing")
        for diff in self.diffs.values():
            lines += ["", diff.rstrip()]
        lines += ["", f"Model's explanation: {self.explanation or '(none)'}"]
        return "\n".join(lines)


def build_message(pr: PullRequest) -> str:
    """The review instructions followed by the pull request, as data."""
    lines = [REVIEW_INSTRUCTIONS, f"PULL REQUEST {pr.id}", f"Service: {pr.service} (repository {pr.repo})",
             f"Title: {pr.title}", f"Description: {pr.description or '(none)'}", "Changed files:"]
    remaining = MAX_TOTAL_PATCH_CHARS
    for change in pr.changes:
        lines.append(f"- {change.path} ({change.status})")
        if change.patch and remaining > 0:
            shown = change.patch[: min(MAX_PATCH_CHARS, remaining)]
            remaining -= len(shown)
            cut = " [cut]" if len(shown) < len(change.patch) else ""
            lines.append(f"  patch{cut}:\n{shown}")
    return "\n".join(lines)


def snapshot(root: Path) -> dict[str, str]:
    """Every markdown file of the workspace by relative path (hidden folders skipped)."""
    found: dict[str, str] = {}
    for path in sorted(root.rglob("*.md")):
        relative = path.relative_to(root)
        if path.is_file() and not any(part[:1] == "." for part in relative.parts):
            found[relative.as_posix()] = path.read_text(encoding="utf-8")
    return found


def diffs_between(before: dict[str, str], after: dict[str, str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for path in sorted(set(before) | set(after)):
        old, new = before.get(path), after.get(path)
        if old == new:
            continue
        out[path] = "".join(difflib.unified_diff(
            (old or "").splitlines(keepends=True), (new or "").splitlines(keepends=True),
            fromfile=f"a/{path}" if old is not None else "/dev/null",
            tofile=f"b/{path}" if new is not None else "/dev/null",
        ))
    return out


async def review_pull_request(
    pr: PullRequest, workspace: Path, agent_open: AgentOpener, dry_run: bool = False
) -> ReviewReport:
    """Give ``pr`` to the agent and report the tool calls, the changed documents and the model's explanation.

    With ``dry_run`` the agent works on a copy of ``workspace`` that is deleted afterwards.
    """
    workspace = Path(workspace)
    if not dry_run:
        return await _run(pr, workspace, None, None, agent_open, dry_run=False)
    with tempfile.TemporaryDirectory(prefix="pr-review-") as scratch_name:
        scratch = Path(scratch_name)
        copy = scratch / "workspace"
        shutil.copytree(workspace, copy)
        return await _run(pr, copy, scratch / "audit.jsonl", scratch, agent_open, dry_run=True)


async def _run(pr: PullRequest, root: Path, audit: Path | None, scratch: Path | None,
               agent_open: AgentOpener, dry_run: bool) -> ReviewReport:
    before = snapshot(root)
    async with agent_open(root, audit, scratch, server_environment(pr)) as agent:
        reply = await agent.chat(build_message(pr))
    diffs = diffs_between(before, snapshot(root))
    return ReviewReport(
        pr_id=pr.id,
        decision="changed" if diffs else "no_change",
        tool_calls=[c for c in reply.tool_calls if c.name != KNOWLEDGE_TOOL],
        diffs=diffs,
        explanation=reply.text.strip(),
        dry_run=dry_run,
    )
