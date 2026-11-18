"""Read and write the ``about`` field of a document's front matter, touching nothing else.

The field is a list of names (services, APIs or events). Editing is by lines so that every other field, its order and
its comments stay exactly as they were, and the line ending style of the file is kept.
"""
from __future__ import annotations

import json
import re

import yaml

_FRONT_MATTER = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n", re.DOTALL)


def get_about(text: str) -> list[str]:
    """The names in the ``about`` field, or an empty list when there is none or the front matter cannot be read."""
    front = _FRONT_MATTER.match(text)
    if not front:
        return []
    try:
        meta = yaml.safe_load(front.group(1)) or {}
    except yaml.YAMLError:
        return []
    about = meta.get("about") if isinstance(meta, dict) else None
    items = [about] if isinstance(about, str) else about if isinstance(about, list) else []
    return [str(item) for item in items if str(item).strip()]


def set_about(text: str, names: list[str]) -> str:
    """The text with its ``about`` field replaced by ``names``; an empty list removes the field.

    A document with no front matter gets one. A front matter left with no field at all is removed.
    """
    newline = "\r\n" if "\r\n" in text else "\n"
    front = _FRONT_MATTER.match(text)
    lines = front.group(1).splitlines() if front else []
    body = text[front.end():] if front else text

    kept: list[str] = []
    skipping = False
    for line in lines:
        if line.startswith("about:"):
            skipping = True  # the field and the lines of its list, in either YAML style
            continue
        if skipping and (line[:1] in (" ", "\t") or line.startswith("- ") or line.strip() == "-"):
            continue
        skipping = False
        kept.append(line)
    if names:
        kept.append("about: " + json.dumps(list(names), ensure_ascii=False))
    if not kept:
        return body
    return f"---{newline}{newline.join(kept)}{newline}---{newline}{body}"
