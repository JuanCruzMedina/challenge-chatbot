"""Measure whether the agent routes each request to the right tools, without a judge model (design.md D-9).

Usage:
  uv run python scripts/eval_agent.py                        # the Ollama model, offline embeddings
  uv run python scripts/eval_agent.py --embedder minilm      # real embeddings (the model must be cached)
  uv run python scripts/eval_agent.py --min-rate 0.7         # exit code 1 below 70 %

The preview of edits is turned off here (`ACTIONS_CONFIRM_EDITS=off`): this evaluation measures which tool is chosen, in one turn.
Every turn runs in a fresh copy of the sample ecosystem with its own actions audit log, and a throwaway index, so
nothing a turn does can influence another and the project's own workspace and data are never touched.
A question, a greeting or an impossible request must not call any action tool. An action must call the expected
tool, succeed at least once, and leave the expected text in the expected file.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import re
import shutil
import sys
import tempfile
import time
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_ROOT = REPO_ROOT / "data" / "ecosystem"
DEFAULT_TURNS = REPO_ROOT / "evaluation" / "agent.yaml"
KNOWLEDGE_TOOL = "query_knowledge"


@dataclass(frozen=True)
class Verdict:
    passed: bool
    reasons: list[str] = field(default_factory=list)


def _words(text: str) -> list[str]:
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return re.findall(r"[a-z0-9]+", "".join(ch for ch in decomposed if not unicodedata.combining(ch)))


def _contains(words: list[str], fact: list[str]) -> bool:
    n = len(fact)
    return bool(fact) and any(words[i:i + n] == fact for i in range(len(words) - n + 1))


def _digest(root: Path) -> dict[str, str]:
    if not root.is_dir():
        return {}
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file()}


def grade(turn: dict[str, Any], reply: Any, workspace: Path, baseline: Path, audit: Path) -> Verdict:
    """Grade one turn: tools called, their success, the effect on the workspace and the facts in the reply."""
    kind, expect, allow = turn["kind"], turn["expect_tools"], turn.get("allow_tools", [])
    called: list[str] = []
    for record in reply.tool_calls:
        if record.name not in called:
            called.append(record.name)
    reasons: list[str] = []

    reported: set[str] = set()
    if kind not in ("action", "mixed"):
        for name in called:
            if name != KNOWLEDGE_TOOL:
                reasons.append(f"called the action tool {name} on a {kind} turn")
                reported.add(name)
    for name in called:
        if name not in expect and name not in allow and name not in reported:
            reasons.append(f"unexpected tool {name}")

    for name in expect:
        records = [r for r in reply.tool_calls if r.name == name]
        if not records:
            reasons.append(f"expected tool {name} was not called")
        elif all(r.error for r in records):
            reasons.append(f"expected tool {name} was called but never succeeded ({records[-1].result[:80]})")
    positions = [called.index(name) for name in expect if name in called]
    if positions != sorted(positions):
        reasons.append(f"expected tools were first called in the wrong order (expected {expect}, got {called})")

    effect = turn.get("expect_effect")
    if effect:
        target, before = workspace / effect["path"], baseline / effect["path"]
        if not target.is_file():
            reasons.append(f"the expected file {effect['path']} does not exist")
        else:
            text = target.read_text(encoding="utf-8")
            old = before.read_text(encoding="utf-8") if before.is_file() else ""
            for needed in effect.get("contains", []):
                if needed not in text:
                    reasons.append(f"the file {effect['path']} lacks {needed!r}")
                elif needed in old:
                    reasons.append(f"the effect {needed!r} was already in the file before the turn: the turn proves nothing")
            for gone in effect.get("absent", []):
                if gone in text:
                    reasons.append(f"the file {effect['path']} still contains {gone!r}")
    elif _digest(workspace) != _digest(baseline) or (audit.is_file() and audit.stat().st_size > 0):
        reasons.append("the turn changed the workspace but should have left it untouched")

    words = _words(reply.text)
    reasons += [f"the reply lacks {fact!r}" for fact in turn.get("expect_facts", []) if not _contains(words, _words(fact))]
    return Verdict(not reasons, reasons)


async def _run_turns(turns: list[dict[str, Any]], chat: Any, flow_llm: Any, embedder_name: str,
                     min_score: float | None) -> tuple[list[tuple[dict, Verdict, list[str], float]], str]:
    from ecosystem_assistant.agent.agent import Agent
    from ecosystem_assistant.agent.knowledge import KnowledgeService
    from ecosystem_assistant.knowledge.retrieval.embedders import embedder_by_name
    from ecosystem_assistant.knowledge.retrieval.index import RetrievalIndex

    results: list[tuple[dict, Verdict, list[str], float]] = []
    with tempfile.TemporaryDirectory(prefix="agent-eval-") as scratch_name:
        scratch = Path(scratch_name)
        index = RetrievalIndex(scratch / "index", embedder_by_name(embedder_name))
        for turn in turns:
            workspace, baseline = scratch / f"ws-{turn['id']}", scratch / f"base-{turn['id']}"
            audit = scratch / f"audit-{turn['id']}.jsonl"
            shutil.copytree(DATA_ROOT, workspace)
            shutil.copytree(DATA_ROOT, baseline)
            service = KnowledgeService(workspace, index, flow_llm, min_score=min_score)
            started = time.perf_counter()
            async with Agent.open(chat=chat, workspace=workspace, audit_file=audit, knowledge=service,
                                  extra_env={"ACTIONS_CONFIRM_EDITS": "off"}) as agent:
                reply = await agent.chat(turn["message"])
            elapsed = time.perf_counter() - started
            names: list[str] = []
            for record in reply.tool_calls:
                if record.name not in names:
                    names.append(record.name)
            results.append((turn, grade(turn, reply, workspace, baseline, audit), names, elapsed))
        return results, index.embedder.name


def main(argv: list[str] | None = None, chat: Any | None = None, flow_llm: Any | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--questions", type=Path, default=DEFAULT_TURNS, help="evaluation turns (YAML)")
    parser.add_argument("--embedder", default="hashing", help="hashing (offline) or minilm (the model must be cached)")
    parser.add_argument("--min-score", type=float, default=None, help="minimum passage score (default: per embedder)")
    parser.add_argument("--min-rate", type=float, default=0.0, help="exit with code 1 below this pass rate")
    args = parser.parse_args(argv)

    from ecosystem_assistant.agent.settings import AgentModelError, chat_model_from_env
    from ecosystem_assistant.llm.port import LLMUnavailableError
    from ecosystem_assistant.llm.settings import llm_from_env

    turns = yaml.safe_load(args.questions.read_text(encoding="utf-8"))["turns"]
    chat_model = chat if chat is not None else chat_model_from_env()
    try:
        results, embedder_name = asyncio.run(
            _run_turns(turns, chat_model, flow_llm if flow_llm is not None else llm_from_env(), args.embedder,
                       args.min_score))
    except (AgentModelError, LLMUnavailableError) as exc:
        print(f"ABORTED: {exc}")
        return 2

    by_kind: dict[str, list[bool]] = defaultdict(list)
    for turn, verdict, names, elapsed in results:
        by_kind[turn["kind"]].append(verdict.passed)
        print(f"{turn['id']:<4} {'PASS' if verdict.passed else 'FAIL'}  {turn['kind']:<11} {elapsed:>5.1f}s  "
              f"{','.join(names) or '-':<32} {turn['message'][:56]}")
        if verdict.reasons:
            print(f"      reasons: {'; '.join(verdict.reasons)}")
    passed = sum(v.passed for _t, v, _n, _e in results)
    rate = passed / len(results) if results else 0.0
    print("By kind: " + ", ".join(f"{kind} {sum(flags)}/{len(flags)}" for kind, flags in by_kind.items()))
    print(f"Pass rate: {passed}/{len(results)} = {rate:.2f} "
          f"(chat model: {getattr(chat_model, 'model', type(chat_model).__name__)}, embedder: {embedder_name})")
    if rate < args.min_rate:
        print(f"FAILED: the pass rate {rate:.2f} is below the minimum {args.min_rate:.2f}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
