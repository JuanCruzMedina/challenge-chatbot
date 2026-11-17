"""Spec: every routing evaluation turn points at tools and files that exist."""
from __future__ import annotations

from pathlib import Path

import yaml

from tests.agent.helpers import real_mcp_tool_names
from tests.data.helpers import SAMPLE

EVAL_SET = Path(__file__).resolve().parents[2] / "evaluation" / "agent.yaml"
KINDS = {"question", "action", "mixed", "chat", "unsupported"}


def _turns() -> list[dict]:
    return yaml.safe_load(EVAL_SET.read_text(encoding="utf-8"))["turns"]


def test_the_set_is_well_formed_and_covers_every_kind() -> None:
    turns = _turns()
    ids = [t["id"] for t in turns]
    assert len(turns) >= 14 and len(ids) == len(set(ids))
    assert {t["kind"] for t in turns} == KINDS
    assert all(t["message"].strip() and "expect_tools" in t for t in turns)


def test_every_tool_named_exists_after_discovery(tmp_path: Path) -> None:
    known = {"query_knowledge", *real_mcp_tool_names(tmp_path)}
    for turn in _turns():
        for name in [*turn["expect_tools"], *turn.get("allow_tools", [])]:
            assert name in known, f"{turn['id']}: {name} is not a tool of the agent"


def test_the_kinds_have_the_tools_and_effects_they_promise() -> None:
    for turn in _turns():
        kind, expected = turn["kind"], turn["expect_tools"]
        if kind == "question":
            assert expected == ["query_knowledge"] and "expect_effect" not in turn, turn["id"]
        elif kind == "action":
            assert len(expected) == 1 and expected[0] != "query_knowledge" and "expect_effect" in turn, turn["id"]
        elif kind == "mixed":
            assert expected[0] == "query_knowledge" and len(expected) == 2 and "expect_effect" in turn, turn["id"]
        else:  # chat and unsupported change nothing and need no write tool
            assert "expect_effect" not in turn and all(t == "query_knowledge" for t in expected), turn["id"]


def test_every_effect_targets_an_existing_service_and_names_what_to_check() -> None:
    services = {p.name for p in (SAMPLE / "repos").iterdir() if p.is_dir()}
    for turn in _turns():
        effect = turn.get("expect_effect")
        if not effect:
            continue
        parts = effect["path"].split("/")
        assert parts[0] == "repos" and parts[1] in services and effect["path"].endswith(".md"), turn["id"]
        assert effect["contains"], turn["id"]


def test_effects_that_edit_an_existing_document_start_from_text_that_is_there() -> None:
    for turn in _turns():
        effect = turn.get("expect_effect") or {}
        for forbidden in effect.get("absent", []):
            document = SAMPLE / effect["path"]
            assert document.is_file(), turn["id"]
            assert forbidden in document.read_text(encoding="utf-8"), f"{turn['id']}: {forbidden!r} is not there to remove"


def test_the_facts_expected_in_replies_really_appear_in_the_data() -> None:
    corpus = "\n".join(p.read_text(encoding="utf-8").lower() for p in SAMPLE.rglob("*") if p.suffix in {".md", ".yaml"})
    for turn in _turns():
        for fact in turn.get("expect_facts", []):
            assert fact.lower().replace(" ", "-") in corpus or fact.lower() in corpus, f"{turn['id']}: {fact!r}"
