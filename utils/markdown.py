"""YAML frontmatter helpers for markdown notes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

FRONTMATTER_DELIMITER = "---"


def split_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """
    Parse YAML frontmatter and body from markdown content.

    Returns (frontmatter dict, body string). If no frontmatter, returns ({}, content).
    """
    text = content.lstrip("\ufeff")
    if not text.startswith(FRONTMATTER_DELIMITER):
        return {}, text

    parts = text.split(FRONTMATTER_DELIMITER, 2)
    if len(parts) < 3:
        return {}, text

    frontmatter_raw = parts[1].strip()
    body = parts[2].lstrip("\n")
    if not frontmatter_raw:
        return {}, body

    parsed = yaml.safe_load(frontmatter_raw)
    if parsed is None:
        return {}, body
    if not isinstance(parsed, dict):
        raise ValueError("Frontmatter must be a YAML mapping")

    return parsed, body


def compose_markdown(frontmatter: dict[str, Any], body: str) -> str:
    """Combine frontmatter dict and body into a markdown file string."""
    yaml_block = yaml.safe_dump(
        frontmatter,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    ).strip()
    body = body.strip()
    if body:
        return f"{FRONTMATTER_DELIMITER}\n{yaml_block}\n{FRONTMATTER_DELIMITER}\n\n{body}\n"
    return f"{FRONTMATTER_DELIMITER}\n{yaml_block}\n{FRONTMATTER_DELIMITER}\n"


def read_note(path: Path) -> tuple[dict[str, Any], str]:
    """Read a markdown note file and return (frontmatter, body)."""
    content = path.read_text(encoding="utf-8")
    return split_frontmatter(content)


def write_note(path: Path, frontmatter: dict[str, Any], body: str) -> None:
    """Write a markdown note with YAML frontmatter."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(compose_markdown(frontmatter, body), encoding="utf-8")
