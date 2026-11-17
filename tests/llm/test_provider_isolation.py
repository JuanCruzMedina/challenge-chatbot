"""Spec: only the llm package touches the Anthropic SDK, and only the two settings modules choose a provider."""
from __future__ import annotations

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src" / "ecosystem_assistant"
SDK_MODULES = {"anthropic", "langchain_anthropic", "httpx2"}
PROVIDER_CHOOSERS = {SRC / "llm" / "settings.py", SRC / "agent" / "settings.py"}


def sdk_imports_outside_llm(root: Path = SRC) -> list[str]:
    found: list[str] = []
    for path in sorted(root.rglob("*.py")):
        if "llm" in path.relative_to(root).parts[:1]:
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"), filename=str(path))):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else (
                [node.module] if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module else [])
            found += [f"{path.relative_to(root)}: imports {n}" for n in names if n.split(".")[0] in SDK_MODULES]
    return found


def test_the_anthropic_sdk_is_imported_only_inside_the_llm_package() -> None:
    assert sdk_imports_outside_llm() == []


def test_the_detector_would_notice_an_import_outside_llm(tmp_path: Path) -> None:
    (tmp_path / "agent").mkdir()
    (tmp_path / "agent" / "bad.py").write_text("import anthropic\nfrom langchain_anthropic import ChatAnthropic\n",
                                               encoding="utf-8")
    (tmp_path / "llm").mkdir()
    (tmp_path / "llm" / "fine.py").write_text("import anthropic\n", encoding="utf-8")

    assert sdk_imports_outside_llm(tmp_path) == ["agent/bad.py: imports anthropic",
                                                 "agent/bad.py: imports langchain_anthropic"]


def test_only_the_two_settings_modules_read_the_provider_variable() -> None:
    readers = [p for p in sorted(SRC.rglob("*.py")) if "LLM_PROVIDER" in p.read_text(encoding="utf-8").replace(
        'Unknown LLM_PROVIDER', '').replace("``LLM_PROVIDER``", "")]
    assert set(readers) <= PROVIDER_CHOOSERS, [str(p.relative_to(SRC)) for p in readers]
