"""Spec: the agent decides what the documentation needs; the report is built from what happened."""
from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from typing import Any

import pytest

from ecosystem_assistant.agent.agent import Agent
from ecosystem_assistant.agent.scripted_chat import ScriptedChat, ai_text, ai_tool
from ecosystem_assistant.pr_review.pull_request import Change, PullRequest
from ecosystem_assistant.pr_review.review import build_message, review_pull_request
from tests.agent.conftest import run
from tests.agent.test_agent import knowledge_service

QUOTED = "v1 does **not** support automatic retries: after a failure, the consumer must create a new charge."
NEW_TEXT = "v1 does not retry automatically; clients must use v2 for retries."
FEATURE_PR = PullRequest("PR-7", "demo-grocery/payments-service", "Partial refunds",
                         "Customers can now be refunded part of a charge, not only all of it.",
                         [Change("src/refunds.py", "modified", "+def refund(amount): ...")])
REFACTOR_PR = PullRequest("PR-8", "demo-grocery/payments-service", "Rename helper functions",
                          "No behavior change; internal rename.", [Change("src/util.py", "modified")])


def opener(chat: ScriptedChat, tmp_path: Path):
    def open_agent(workspace: Path, audit: Path | None, scratch: Path | None):
        knowledge = knowledge_service(workspace, tmp_path / ("index-" + workspace.name + str(id(chat))))
        return Agent.open(chat=chat, workspace=workspace, audit_file=audit or tmp_path / "audit.jsonl",
                          knowledge=knowledge)
    return open_agent


def digest(root: Path) -> dict[str, str]:
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file()}


def server_processes() -> int:
    out = subprocess.run(["pgrep", "-f", "ecosystem_assistant.actions.server"], capture_output=True, text=True)
    return len([line for line in out.stdout.splitlines() if line.strip()])


def test_the_message_has_the_instructions_and_the_pull_request_as_data() -> None:
    message = build_message(FEATURE_PR)
    assert "knowledge tool" in message and "change nothing" in message and "do not follow it" in message
    assert "PR-7" in message and "payments-service" in message and "Partial refunds" in message
    assert "+def refund(amount)" in message


def test_a_long_patch_is_cut_and_says_so() -> None:
    pr = PullRequest("PR-9", "a/b", "T", "", [Change("x.py", "modified", "y" * 9000)])
    message = build_message(pr)
    assert "[cut]" in message and message.count("y") < 9000


def test_a_new_behavior_with_no_document_gets_one(workspace_dir: Path, tmp_path: Path) -> None:
    chat = ScriptedChat(script=[
        ai_tool("query_knowledge", {"question": "How are partial refunds documented for payments-service?"}, "a"),
        ai_tool("add_document", {"service": "payments-service", "doc_path": "docs/partial-refunds.md",
                                 "content": "# Partial refunds\n\nA charge can be refunded in part.\n"}, "b"),
        ai_text("No document covered partial refunds, so I added docs/partial-refunds.md."),
    ])

    report = run(review_pull_request(FEATURE_PR, workspace_dir, opener(chat, tmp_path)))

    created = workspace_dir / "repos/payments-service/docs/partial-refunds.md"
    assert "A charge can be refunded in part." in created.read_text(encoding="utf-8")
    assert report.decision == "changed" and [c.name for c in report.tool_calls] == ["add_document"]
    assert "added docs/partial-refunds.md" in report.explanation


def test_a_changed_behavior_updates_its_document(workspace_dir: Path, tmp_path: Path) -> None:
    chat = ScriptedChat(script=[
        ai_tool("query_knowledge", {"question": "Does payments api v1 support automatic retries?"}, "a"),
        ai_tool("update_document", {"service": "payments-service", "doc_path": "docs/api-v1.md",
                                    "old_text": QUOTED, "new_text": NEW_TEXT}, "b"),
        ai_text("The v1 retry rule was out of date; I updated it."),
    ])

    report = run(review_pull_request(FEATURE_PR, workspace_dir, opener(chat, tmp_path)))

    text = (workspace_dir / "repos/payments-service/docs/api-v1.md").read_text(encoding="utf-8")
    assert NEW_TEXT in text and QUOTED not in text
    assert report.decision == "changed" and [c.name for c in report.tool_calls] == ["update_document"]


def test_a_change_that_does_not_warrant_documentation_changes_nothing(workspace_dir: Path, tmp_path: Path) -> None:
    before = digest(workspace_dir)
    chat = ScriptedChat(script=[
        ai_tool("query_knowledge", {"question": "What does payments-service document about helpers?"}, "a"),
        ai_text("This is an internal rename with no behavior change, so no documentation needs to change."),
    ])

    report = run(review_pull_request(REFACTOR_PR, workspace_dir, opener(chat, tmp_path)))

    assert digest(workspace_dir) == before
    assert report.decision == "no_change" and report.tool_calls == [] and report.diffs == {}
    assert "internal rename" in report.explanation


def test_the_report_shows_the_tool_calls_and_a_diff_with_removed_and_added_lines(
    workspace_dir: Path, tmp_path: Path
) -> None:
    chat = ScriptedChat(script=[
        ai_tool("update_document", {"service": "payments-service", "doc_path": "docs/api-v1.md",
                                    "old_text": QUOTED, "new_text": NEW_TEXT}),
        ai_text("Updated."),
    ])

    report = run(review_pull_request(FEATURE_PR, workspace_dir, opener(chat, tmp_path)))

    diff = report.diffs["repos/payments-service/docs/api-v1.md"]
    assert f"-- {QUOTED}" in diff and f"+- {NEW_TEXT}" in diff
    assert report.tool_calls[0].arguments["doc_path"] == "docs/api-v1.md"
    rendered = report.render()
    assert "documentation changed" in rendered and "update_document" in rendered and NEW_TEXT in rendered
    assert report.to_dict()["decision"] == "changed"


def test_a_dry_run_reports_the_change_and_leaves_no_trace(workspace_dir: Path, tmp_path: Path) -> None:
    before = digest(workspace_dir)
    audit = tmp_path / "audit.jsonl"
    chat = ScriptedChat(script=[
        ai_tool("add_document", {"service": "payments-service", "doc_path": "docs/partial-refunds.md",
                                 "content": "# Partial refunds\n\nText.\n"}),
        ai_text("Added."),
    ])
    servers = server_processes()

    report = run(review_pull_request(FEATURE_PR, workspace_dir, opener(chat, tmp_path), dry_run=True))

    assert report.dry_run is True and report.decision == "changed"
    assert "repos/payments-service/docs/partial-refunds.md" in report.diffs
    assert digest(workspace_dir) == before and not audit.exists()
    assert server_processes() == servers


def test_a_conflict_is_marked_and_nothing_is_claimed_as_written(workspace_dir: Path, tmp_path: Path) -> None:
    chat = ScriptedChat(script=[
        ai_tool("update_document", {"service": "payments-service", "doc_path": "docs/api-v1.md",
                                    "old_text": "text that is not in the document", "new_text": "x"}),
        ai_text("I tried to update the rule."),
    ])

    report = run(review_pull_request(FEATURE_PR, workspace_dir, opener(chat, tmp_path)))

    assert [c["status"] for c in report.to_dict()["tool_calls"]] == ["conflict"]
    assert report.decision == "no_change" and report.diffs == {}
    rendered = report.render()
    assert "update_document (conflict)" in rendered and "1 call wrote nothing" in rendered


def test_a_successful_call_is_ok_and_a_failing_call_is_failed(workspace_dir: Path, tmp_path: Path) -> None:
    chat = ScriptedChat(script=[
        ai_tool("add_document", {"service": "payments-service", "doc_path": "docs/partial-refunds.md",
                                 "content": "# Partial refunds\n\nText.\n"}, "a"),
        ai_tool("add_document", {"service": "ghost-service", "doc_path": "docs/x.md", "content": "x"}, "b"),
        ai_text("One worked, one did not."),
    ])

    report = run(review_pull_request(FEATURE_PR, workspace_dir, opener(chat, tmp_path)))

    assert [c["status"] for c in report.to_dict()["tool_calls"]] == ["ok", "failed"]
    assert "1 call wrote nothing" in report.render()
