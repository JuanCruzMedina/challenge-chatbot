"""Measure whether the pull request review leaves the documentation right, without a judge model (design.md D-6).

Usage:
  uv run python scripts/eval_pr_review.py                       # the model chosen by LLM_PROVIDER (default: Ollama)
  LLM_PROVIDER=anthropic uv run python scripts/eval_pr_review.py --min-rate 0.7

Every case runs in a fresh copy of the sample ecosystem with its own audit log and a throwaway index, so the project's
own workspace is never touched. Grading looks only at the markdown files, never at the model's words:
  new        a new markdown file of the service mentions every phrase expected
  update     the old statement is gone and a new one is there
  unchanged  no markdown file changed
"""
from __future__ import annotations

import argparse
import asyncio
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
DEFAULT_CASES = REPO_ROOT / "evaluation" / "pr_review.yaml"


@dataclass(frozen=True)
class Verdict:
    passed: bool
    reasons: list[str] = field(default_factory=list)


def _words(text: str) -> list[str]:
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return re.findall(r"[a-z0-9]+", "".join(ch for ch in decomposed if not unicodedata.combining(ch)))


def _contains(text: str, phrase: str) -> bool:
    words, wanted = _words(text), _words(phrase)
    n = len(wanted)
    return bool(wanted) and any(words[i:i + n] == wanted for i in range(len(words) - n + 1))


def grade(case: dict[str, Any], before: dict[str, str], after: dict[str, str], service: str) -> Verdict:
    """Grade one case from the markdown files before and after the review."""
    kind, expect = case["kind"], case.get("expect") or {}
    reasons: list[str] = []
    changed = sorted(p for p in set(before) | set(after) if before.get(p) != after.get(p))
    if kind == "unchanged":
        if changed:
            reasons.append(f"the review changed documentation that did not need it: {', '.join(changed)}")
    elif kind == "new":
        folder = f"repos/{service}/"
        created = [p for p in after if p not in before and p.startswith(folder)]
        if not created:
            reasons.append(f"no new markdown file was created under {folder}")
        for phrase in expect.get("new_mentions", []):
            if not any(_contains(after[p], phrase) for p in created):
                reasons.append(f"no new document mentions {phrase!r}")
    elif kind == "update":
        path = expect["path"]
        old, new = before.get(path, ""), after.get(path, "")
        if not _contains(old, expect["removed"]):
            reasons.append(f"the statement to replace was not in {path} before the review: the case proves nothing")
        elif _contains(new, expect["removed"]):
            reasons.append(f"{path} still says {expect['removed']!r}")
        added = [p for p in expect.get("added_any", []) if not _contains(old, p) and _contains(new, p)]
        if not added:
            reasons.append(f"{path} has none of the expected new statements {expect.get('added_any')}")
    else:
        reasons.append(f"unknown case kind {kind!r}")
    return Verdict(not reasons, reasons)


async def _run_cases(cases: list[dict[str, Any]], chat: Any, flow_llm: Any, embedder_name: str,
                     min_score: float | None) -> list[tuple[dict[str, Any], Verdict, Any, float]]:
    from ecosystem_assistant.agent.agent import Agent
    from ecosystem_assistant.agent.knowledge import KnowledgeService
    from ecosystem_assistant.knowledge.retrieval.embedders import embedder_by_name
    from ecosystem_assistant.knowledge.retrieval.index import RetrievalIndex
    from ecosystem_assistant.pr_review.pull_request import parse_pull_request
    from ecosystem_assistant.pr_review.review import review_pull_request, snapshot

    results = []
    with tempfile.TemporaryDirectory(prefix="pr-review-eval-") as scratch_name:
        scratch = Path(scratch_name)
        index = RetrievalIndex(scratch / "index", embedder_by_name(embedder_name))
        for case in cases:
            workspace = scratch / f"ws-{case['id']}"
            shutil.copytree(DATA_ROOT, workspace)
            pr = parse_pull_request(case["pr"], case["id"])
            before = snapshot(workspace)

            def opener(root: Path, audit: Path | None, _scratch: Path | None) -> Any:
                service = KnowledgeService(root, index, flow_llm, min_score=min_score)
                return Agent.open(chat=chat, workspace=root, audit_file=scratch / f"audit-{case['id']}.jsonl",
                                  knowledge=service)

            started = time.perf_counter()
            report = await review_pull_request(pr, workspace, opener)
            elapsed = time.perf_counter() - started
            results.append((case, grade(case, before, snapshot(workspace), pr.service), report, elapsed))
        return results


def main(argv: list[str] | None = None, chat: Any | None = None, flow_llm: Any | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES, help="evaluation cases (YAML)")
    parser.add_argument("--embedder", default="hashing", help="hashing (offline) or minilm (the model must be cached)")
    parser.add_argument("--min-score", type=float, default=None, help="minimum passage score (default: per embedder)")
    parser.add_argument("--min-rate", type=float, default=0.0, help="exit with code 1 below this pass rate")
    args = parser.parse_args(argv)

    from ecosystem_assistant.agent.settings import AgentModelError, chat_model_from_env
    from ecosystem_assistant.llm.port import LLMUnavailableError
    from ecosystem_assistant.llm.settings import llm_from_env

    cases = yaml.safe_load(args.cases.read_text(encoding="utf-8"))["cases"]
    chat_model = chat if chat is not None else chat_model_from_env()
    try:
        results = asyncio.run(_run_cases(cases, chat_model, flow_llm if flow_llm is not None else llm_from_env(),
                                         args.embedder, args.min_score))
    except (AgentModelError, LLMUnavailableError) as exc:
        print(f"ABORTED: {exc}")
        return 2

    by_kind: dict[str, list[bool]] = defaultdict(list)
    for case, verdict, report, elapsed in results:
        by_kind[case["kind"]].append(verdict.passed)
        print(f"{case['id']:<4} {'PASS' if verdict.passed else 'FAIL'}  {case['kind']:<10} {elapsed:>5.1f}s  "
              f"{report.decision:<10} {case['pr']['title'][:56]}")
        if verdict.reasons:
            print(f"      reasons: {'; '.join(verdict.reasons)}")
    passed = sum(v.passed for _c, v, _r, _e in results)
    rate = passed / len(results) if results else 0.0
    print("By kind: " + ", ".join(f"{kind} {sum(flags)}/{len(flags)}" for kind, flags in by_kind.items()))
    print(f"Pass rate: {passed}/{len(results)} = {rate:.2f} "
          f"(chat model: {getattr(chat_model, 'model', type(chat_model).__name__)}, embedder: {args.embedder})")
    if rate < args.min_rate:
        print(f"FAILED: the pass rate {rate:.2f} is below the minimum {args.min_rate:.2f}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
