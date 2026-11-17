"""Spec: the command is usable from CI (exit codes, dry run, no leftover server)."""
from __future__ import annotations

import subprocess
from pathlib import Path

from ecosystem_assistant.agent.scripted_chat import ScriptedChat, ai_text
from ecosystem_assistant.pr_review.__main__ import main
from tests.data.helpers import SAMPLE
from tests.pr_review.test_review import opener, server_processes

SAMPLE_PR = Path(SAMPLE) / "prs" / "pr-101-payments-api-v2" / "pr.yaml"


def test_a_missing_workspace_exits_with_2_and_the_seed_command(tmp_path: Path) -> None:
    printed: list[str] = []

    code = main([str(SAMPLE_PR), "--workspace", str(tmp_path / "nowhere")], write=printed.append)

    assert code == 2 and any("uv run python scripts/seed_workspace.py" in line for line in printed)


def test_an_invalid_pull_request_file_exits_with_2_and_names_the_field(workspace_dir: Path, tmp_path: Path) -> None:
    bad = tmp_path / "pr.yaml"
    bad.write_text("repo: a/b\ntitle: T\n")
    printed: list[str] = []

    code = main([str(bad), "--workspace", str(workspace_dir)], write=printed.append)

    assert code == 2 and any("'id'" in line for line in printed)


def test_a_review_prints_the_report_and_exits_0_without_leaving_a_server(workspace_dir: Path, tmp_path: Path) -> None:
    chat = ScriptedChat(script=[ai_text("The PR needs no documentation change.")])
    printed: list[str] = []
    servers = server_processes()

    code = main([str(SAMPLE_PR), "--workspace", str(workspace_dir), "--dry-run"],
                agent_opener=opener(chat, tmp_path), write=printed.append)

    assert code == 0
    assert "PR-101" in printed[0] and "no documentation change" in printed[0] and "dry run" in printed[0]
    assert server_processes() == servers


def test_an_unusable_model_exits_with_2(workspace_dir: Path, tmp_path: Path) -> None:
    from ecosystem_assistant.agent.settings import AgentModelError

    chat = ScriptedChat(script=[AgentModelError("Cannot reach the model. Start it with `ollama serve`.")])
    printed: list[str] = []

    code = main([str(SAMPLE_PR), "--workspace", str(workspace_dir)], agent_opener=opener(chat, tmp_path),
                write=printed.append)

    assert code == 2 and any("ABORTED" in line and "ollama serve" in line for line in printed)


def test_the_module_runs_as_a_command() -> None:
    out = subprocess.run(["uv", "run", "python", "-m", "ecosystem_assistant.pr_review", "--help"],
                         capture_output=True, text=True, timeout=120)
    assert out.returncode == 0 and "--dry-run" in out.stdout
