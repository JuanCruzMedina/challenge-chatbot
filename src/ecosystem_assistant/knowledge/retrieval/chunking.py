"""Split a markdown document into section chunks (design.md D-4).

Pure functions: they take the path and the text and know nothing about services, clients or the
graph (that metadata is added in ``documents.py``).
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any

import yaml

MAX_CHARS = 1200

_FRONT_MATTER = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n", re.DOTALL)
_HEADING = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t]*#*[ \t]*$")
_FENCE = re.compile(r"^\s*(```|~~~)")


@dataclass(frozen=True)
class Chunk:
    id: str             # "<relative path>#<n>", deterministic
    path: str           # relative path of the document
    title: str          # first heading of the document, or the file name without extension
    heading_path: str   # "Title > Section > Subsection"
    body: str           # the text of the section (or part of it), without the heading path
    text: str           # heading path, a blank line and the body: what is embedded and shown
    status: str         # "current" or "obsolete"
    content_hash: str   # sha256 of the whole file, shared by all chunks of the file
    index: int          # position of the chunk in the document


@dataclass(frozen=True)
class ParsedDocument:
    title: str
    status: str
    extra: dict[str, Any]
    body: str


def file_hash(raw_text: str) -> str:
    return hashlib.sha256(raw_text.encode("utf-8")).hexdigest()


def parse_document(path: str, raw_text: str) -> ParsedDocument:
    """Read the front matter (status) and find the title; the body has no front matter."""
    status, extra, body = "current", {}, raw_text
    front = _FRONT_MATTER.match(raw_text)
    if front:
        meta = yaml.safe_load(front.group(1)) or {}
        if str(meta.get("status", "")).lower() == "obsolete":
            status = "obsolete"
            extra = {k: meta[k] for k in ("obsolete_reason", "replaced_by") if k in meta}
        body = raw_text[front.end():]
    title = next((h[1] for h in _headings(body)), PurePosixPath(path).stem)
    return ParsedDocument(title=title, status=status, extra=extra, body=body)


def _headings(body: str):
    """Yield ``(level, text, line_index)`` of the headings that are not inside fenced code."""
    in_fence = False
    for number, line in enumerate(body.splitlines()):
        if _FENCE.match(line):
            in_fence = not in_fence
            continue
        if not in_fence:
            match = _HEADING.match(line)
            if match:
                yield len(match.group(1)), match.group(2).strip(), number


def chunk_document(path: str, raw_text: str) -> list[Chunk]:
    """One chunk per section with text of its own; long sections are split at paragraph boundaries."""
    doc = parse_document(path, raw_text)
    digest = file_hash(raw_text)
    lines = doc.body.splitlines()

    sections: list[tuple[str, list[str]]] = []  # (heading path, lines of the section)
    stack: list[tuple[int, str]] = []
    current_path, current_lines = doc.title, []
    heading_at = {number: (level, text) for level, text, number in _headings(doc.body)}
    for number, line in enumerate(lines):
        if number in heading_at:
            sections.append((current_path, current_lines))
            level, text = heading_at[number]
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, text))
            current_path, current_lines = " > ".join(t for _l, t in stack), []
        else:
            current_lines.append(line)
    sections.append((current_path, current_lines))

    chunks: list[Chunk] = []
    for heading_path, section_lines in sections:
        section = "\n".join(section_lines).strip()
        if not section:
            continue
        for body in _split_long(section):
            chunks.append(Chunk(
                id=f"{path}#{len(chunks)}", path=path, title=doc.title, heading_path=heading_path,
                body=body, text=f"{heading_path}\n\n{body}", status=doc.status,
                content_hash=digest, index=len(chunks),
            ))
    return chunks


def _paragraphs(section: str) -> list[str]:
    """Blocks separated by blank lines; a fenced code block is never split, blank lines included."""
    blocks: list[list[str]] = [[]]
    in_fence = False
    for line in section.splitlines():
        if _FENCE.match(line):
            in_fence = not in_fence
        if not line.strip() and not in_fence:
            if blocks[-1]:
                blocks.append([])
            continue
        blocks[-1].append(line)
    return ["\n".join(b) for b in blocks if b]


def _split_long(section: str) -> list[str]:
    if len(section) <= MAX_CHARS:
        return [section]
    parts: list[str] = []
    current = ""
    for paragraph in _paragraphs(section):
        candidate = f"{current}\n\n{paragraph}" if current else paragraph
        if current and len(candidate) > MAX_CHARS:
            parts.append(current)
            current = paragraph
        else:
            current = candidate
    if current:
        parts.append(current)
    return parts
