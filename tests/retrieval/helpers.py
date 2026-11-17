"""Helpers for the retrieval tests."""
from __future__ import annotations

from pathlib import Path

from ecosystem_assistant.knowledge.retrieval.embedders import HashingEmbedder
from tests.data.fixture import write_text


class CountingEmbedder(HashingEmbedder):
    """The offline embedder that remembers every text it was asked to embed."""

    def __init__(self) -> None:
        self.seen: list[str] = []

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.seen.extend(texts)
        return super().embed(texts)


def populate(root: Path) -> None:
    """Give the synthetic dataset documents with real text (the shared ones hold only a title)."""
    write_text(root / "repos" / "svc-a1" / "docs" / "api.md",
               "# a1-api\n\n## Endpoints\nlists the widgets of the catalog\n\n## Rules\nwidgets are limited to fifty per page\n")
    write_text(root / "repos" / "svc-a1" / "README.md", "# svc-a1\n\nService a1 stores widgets for client a.\n")
    write_text(root / "repos" / "svc-a2" / "README.md",
               "# svc-a2\n\nService a2 consumes the a1 api to show widgets.\n")
    write_text(root / "repos" / "svc-b1" / "README.md", "# svc-b1\n\nService b1 guards the safety rules for client b.\n")
    write_text(root / "clients" / "client-a" / "product" / "vision.md",
               "# Vision client-a\n\nClient A wants speed above all, and fast widgets.\n")
    write_text(root / "clients" / "client-b" / "product" / "vision.md",
               "# Vision client-b\n\nClient B wants safety above all, and audited rules.\n")
    write_text(root / "company" / "overview.md", "# Demo Studio\n\nTwo invented clients and three applications.\n")
