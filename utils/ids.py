"""ID, timestamp, and slug helpers."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone


def generate_id() -> str:
    """Return a new UUID4 string."""
    return str(uuid.uuid4())


def short_id(full_id: str, length: int = 8) -> str:
    """Return a short prefix of a UUID for filenames."""
    return full_id.replace("-", "")[:length]


def timestamp_now() -> str:
    """Return current local time as ISO8601 string."""
    return datetime.now().astimezone().isoformat()


def capture_filename(captured_at: datetime | None = None, note_id: str | None = None) -> str:
    """
    Build a raw capture filename stem: YYYYMMDD_HHMMSS_{short_id}.

    Example: 20260722_143022_a1b2c3d4
    """
    when = captured_at or datetime.now().astimezone()
    uid = short_id(note_id or generate_id())
    return f"{when.strftime('%Y%m%d_%H%M%S')}_{uid}"


def slugify(text: str, max_length: int = 60) -> str:
    """Convert text to a filesystem-safe slug."""
    slug = text.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_-]+", "-", slug).strip("-")
    if not slug:
        slug = "note"
    return slug[:max_length].rstrip("-")
