"""Measure how often the right document is among the top results of the retrieval index.

Usage:
  uv run python scripts/eval_retrieval.py                          # offline embedder, committed sample data
  ALLOW_MODEL_DOWNLOAD=1 uv run python scripts/eval_retrieval.py --embedder minilm
  uv run python scripts/eval_retrieval.py --min-hit-rate 0.7       # exit code 1 below 70 %

It builds a throwaway index (never the project's ``var/index``), runs every question of the
evaluation set, and counts a hit when an expected document is among the top ``--k`` distinct documents.
"""
from __future__ import annotations

import argparse
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ROOT = REPO_ROOT / "data" / "ecosystem"
DEFAULT_QUESTIONS = REPO_ROOT / "evaluation" / "retrieval.yaml"


@dataclass(frozen=True)
class QuestionResult:
    id: str
    question: str
    rank: int | None  # position of the first expected document among the distinct documents, if found
    hit: bool


def evaluate(root: Path, questions_file: Path, embedder_name: str, k: int = 3) -> list[QuestionResult]:
    from ecosystem_assistant.knowledge.retrieval.embedders import embedder_by_name
    from ecosystem_assistant.knowledge.retrieval.index import RetrievalIndex
    from ecosystem_assistant.knowledge.retrieval.search import MAX_RESULTS

    questions = yaml.safe_load(questions_file.read_text(encoding="utf-8"))["questions"]
    with tempfile.TemporaryDirectory(prefix="retrieval-eval-") as scratch:
        index = RetrievalIndex(Path(scratch), embedder_by_name(embedder_name))
        index.sync(root)
        results: list[QuestionResult] = []
        for item in questions:
            documents: list[str] = []
            for hit in index.search(item["question"], k=MAX_RESULTS):
                if hit.citation.path not in documents:
                    documents.append(hit.citation.path)
            ranks = [documents.index(p) + 1 for p in item["expected"] if p in documents]
            rank = min(ranks) if ranks else None
            results.append(QuestionResult(item["id"], item["question"], rank, rank is not None and rank <= k))
        return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="data root to index")
    parser.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS, help="evaluation set (YAML)")
    parser.add_argument("--embedder", default="hashing", help="hashing (offline) or minilm (needs the model)")
    parser.add_argument("--k", type=int, default=3, help="a hit needs an expected document in the top k documents")
    parser.add_argument("--min-hit-rate", type=float, default=0.0, help="exit with code 1 below this rate")
    args = parser.parse_args(argv)

    results = evaluate(args.root, args.questions, args.embedder, args.k)
    for r in results:
        verdict, rank = ("HIT ", f"rank {r.rank}") if r.hit else ("MISS", f"rank {r.rank}" if r.rank else "-")
        print(f"{r.id:<8} {verdict} {rank:<8} {r.question}")
    hits = sum(r.hit for r in results)
    rate = hits / len(results) if results else 0.0
    print(f"Hit rate @{args.k}: {hits}/{len(results)} = {rate:.2f} (embedder: {args.embedder})")
    if rate < args.min_hit_rate:
        print(f"FAILED: the hit rate {rate:.2f} is below the minimum {args.min_hit_rate:.2f}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
