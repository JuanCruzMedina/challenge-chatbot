"""Measure the informational flow end to end, without a judge model (design.md D-10).

Usage:
  uv run python scripts/eval_flow.py                      # the model chosen by LLM_PROVIDER (default: Ollama)
  uv run python scripts/eval_flow.py --embedder minilm    # real embeddings (the model must be cached)
  uv run python scripts/eval_flow.py --min-rate 0.7       # exit code 1 below 70 %

A graded question passes when the answer is `answered` and grounded, cites the expected source files and states
every key fact (matched by whole words, ignoring case and separators: `fleet-tracker` matches "Fleet Tracker"). `unknown` questions pass on `insufficient_evidence`; `absent` ones also pass when the answer says the
information is missing (a simple wording check, the weakest grade). It builds a throwaway index, never `var/index`.
"""
from __future__ import annotations

import argparse
import re
import sys
import tempfile
import unicodedata
from dataclasses import dataclass, field
from itertools import chain
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ROOT = REPO_ROOT / "data" / "ecosystem"
DEFAULT_QUESTIONS = REPO_ROOT / "evaluation" / "flow.yaml"
ABSENCE = re.compile(
    r"no information|not (found|mentioned|stated|specified|documented|available)|does not (say|state|mention|specify)"
    r"|do not (know|have)|could not find|cannot find|there is no|is no |isn't|missing|insufficient",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Verdict:
    passed: bool
    reasons: list[str] = field(default_factory=list)


def grade(item: dict[str, Any], answer: Any) -> Verdict:
    """Grade one answer against its evaluation item. Pure: it only reads the answer."""
    kind = item["kind"]
    if kind == "unknown":
        ok = answer.status == "insufficient_evidence"
        return Verdict(ok, [] if ok else [f"expected insufficient_evidence, got {answer.status}"])
    if kind == "absent":
        ok = answer.status == "insufficient_evidence" or bool(ABSENCE.search(answer.text))
        return Verdict(ok, [] if ok else ["the answer neither reports insufficient evidence nor says the information is missing"])

    reasons: list[str] = []
    if answer.status != "answered":
        reasons.append(f"status is {answer.status}, expected answered")
    if not answer.grounded:
        reasons.append("the answer is not grounded (no valid citation)")
    cited = set(chain.from_iterable(c.sources for c in answer.citations))
    expected = item.get("expect_sources", [])
    if item.get("source_mode", "any") == "all":
        missing = [source for source in expected if source not in cited]
        if missing:
            reasons.append(f"expected source(s) not cited: {', '.join(missing)}")
    elif expected and not any(source in cited for source in expected):
        reasons.append(f"none of the expected sources was cited ({', '.join(expected)})")
    words = _words(answer.text)
    reasons += [f"missing fact {fact!r}" for fact in item.get("expect_facts", []) if not _contains(words, _words(fact))]
    return Verdict(not reasons, reasons)


def _words(text: str) -> list[str]:
    """Lowercase alphanumeric words: 'Fleet Tracker', 'fleet-tracker' and 'FLEET_TRACKER' all give the same words."""
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return re.findall(r"[a-z0-9]+", "".join(ch for ch in decomposed if not unicodedata.combining(ch)))


def _contains(words: list[str], fact: list[str]) -> bool:
    """True when the fact's words appear in the answer as whole words, adjacent and in order."""
    n = len(fact)
    return bool(fact) and any(words[i:i + n] == fact for i in range(len(words) - n + 1))


def main(argv: list[str] | None = None, llm: Any | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="data root")
    parser.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS, help="evaluation set (YAML)")
    parser.add_argument("--embedder", default="hashing", help="hashing (offline) or minilm (the model must be cached)")
    parser.add_argument("--min-score", type=float, default=None, help="minimum passage score (default: per embedder)")
    parser.add_argument("--min-rate", type=float, default=0.0, help="exit with code 1 below this pass rate")
    args = parser.parse_args(argv)

    from ecosystem_assistant.knowledge.flow.graph import InformationalFlow
    from ecosystem_assistant.knowledge.graph.build import build_graph
    from ecosystem_assistant.knowledge.retrieval.embedders import embedder_by_name
    from ecosystem_assistant.knowledge.retrieval.index import RetrievalIndex
    from ecosystem_assistant.llm.port import LLMUnavailableError
    from ecosystem_assistant.llm.settings import llm_from_env

    model = llm if llm is not None else llm_from_env()
    questions = yaml.safe_load(args.questions.read_text(encoding="utf-8"))["questions"]
    embedder = embedder_by_name(args.embedder)
    graph = build_graph(args.root)

    passed = 0
    with tempfile.TemporaryDirectory(prefix="flow-eval-") as scratch:
        index = RetrievalIndex(Path(scratch), embedder)
        index.sync(args.root, graph)
        flow = InformationalFlow(graph, index, model, min_score=args.min_score)
        for item in questions:
            try:
                verdict = grade(item, flow.ask(item["question"]))
            except LLMUnavailableError as exc:
                print(f"ABORTED: {exc}")
                return 2
            except Exception as exc:  # noqa: BLE001 - one broken question must not hide the others
                verdict = Verdict(False, [f"error: {type(exc).__name__}: {exc}"])
            passed += verdict.passed
            print(f"{item['id']:<5} {'PASS' if verdict.passed else 'FAIL'}  {item['kind']:<9} {item['question'][:72]}")
            if verdict.reasons:
                print(f"      reasons: {'; '.join(verdict.reasons)}")
        min_score = flow.min_score

    rate = passed / len(questions) if questions else 0.0
    print(f"Pass rate: {passed}/{len(questions)} = {rate:.2f} "
          f"(llm: {model.name}, embedder: {embedder.name}, min_score: {min_score})")
    if rate < args.min_rate:
        print(f"FAILED: the pass rate {rate:.2f} is below the minimum {args.min_rate:.2f}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
