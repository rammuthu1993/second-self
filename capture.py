"""Capture CLI for SecondSelf — create raw captures (note, link, file).

Usage:
    python capture.py note "Your note text"
    python capture.py link "https://example.com/article"
    python capture.py file "C:\full\path\to\document.pdf"

Writes markdown files to raw/ with YAML frontmatter including:
  - id
  - captured_at
  - type
  - source
  - status: unprocessed

File captures are copied into assets/files/ and text is extracted from PDFs when possible.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path
from typing import Optional

import requests

from config import FILES_DIR, RAW_DIR, ensure_directories
from utils.ids import generate_id, timestamp_now, capture_filename, slugify, short_id
from utils.markdown import write_note


def _write_raw(markdown_path: Path, frontmatter: dict, body: str) -> None:
    write_note(markdown_path, frontmatter, body)
    print(f"Wrote raw capture: {markdown_path}")


def capture_note(text: str, source: str = "cli") -> Path:
    note_id = generate_id()
    fname = capture_filename(note_id=note_id) + ".md"
    path = RAW_DIR / fname

    frontmatter = {
        "id": note_id,
        "captured_at": timestamp_now(),
        "type": "note",
        "source": source,
        "status": "unprocessed",
    }

    body = text.strip() + "\n"
    ensure_directories()
    _write_raw(path, frontmatter, body)
    return path


def _fetch_title(url: str, timeout: float = 5.0) -> Optional[str]:
    try:
        resp = requests.get(url, timeout=timeout, headers={"User-Agent": "SecondSelfBot/1.0"})
        resp.raise_for_status()
        # crude title extraction
        text = resp.text
        start = text.lower().find("<title>")
        if start != -1:
            start += len("<title>")
            end = text.lower().find("</title>", start)
            if end != -1:
                return text[start:end].strip()
    except Exception:
        return None
    return None


def capture_link(url: str, source: str = "cli") -> Path:
    note_id = generate_id()
    fname = capture_filename(note_id=note_id) + ".md"
    path = RAW_DIR / fname

    title = _fetch_title(url) or ""
    frontmatter = {
        "id": note_id,
        "captured_at": timestamp_now(),
        "type": "link",
        "source": source,
        "status": "unprocessed",
        "url": url,
    }

    body_lines = []
    if title:
        body_lines.append(f"# {title}")
    body_lines.append(f"{url}")
    body = "\n\n".join(body_lines) + "\n"

    ensure_directories()
    _write_raw(path, frontmatter, body)
    return path


def _extract_pdf_text(src: Path) -> str:
    try:
        from pypdf import PdfReader
    except Exception:
        # pypdf not installed or failed — fall back
        return ""

    try:
        reader = PdfReader(str(src))
        pages = []
        for p in reader.pages:
            try:
                pages.append(p.extract_text() or "")
            except Exception:
                # skip pages that fail
                pages.append("")
        return "\n\n".join(pages).strip()
    except Exception:
        return ""


def capture_file(file_path: str, source: str = "cli") -> Path:
    src = Path(file_path).expanduser().resolve()
    if not src.exists():
        print(f"Error: file not found: {src}")
        raise FileNotFoundError(src)

    note_id = generate_id()
    fname = capture_filename(note_id=note_id) + ".md"
    path = RAW_DIR / fname

    ensure_directories()

    # copy to assets/files with a short-id prefix
    dest_name = f"{short_id(note_id)}_{src.name}"
    dest = FILES_DIR / dest_name
    try:
        shutil.copy2(src, dest)
    except Exception as e:
        print(f"Warning: failed to copy file to assets: {e}")

    frontmatter = {
        "id": note_id,
        "captured_at": timestamp_now(),
        "type": "file",
        "source": source,
        "status": "unprocessed",
        "filename": dest_name,
        "original_path": str(src),
    }

    body = ""
    # try to extract text for PDFs
    if src.suffix.lower() in (".pdf",):
        extracted = _extract_pdf_text(src)
        if extracted:
            body = extracted + "\n"
        else:
            body = f"[Binary file copied to assets/files/{dest_name}]\n"
    else:
        # attempt to read small text files
        try:
            body = src.read_text(encoding="utf-8") + "\n"
        except Exception:
            body = f"[Binary file copied to assets/files/{dest_name}]\n"

    _write_raw(path, frontmatter, body)
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser("capture", description="Capture notes, links, and files into raw/")
    sub = parser.add_subparsers(dest="cmd")

    p_note = sub.add_parser("note", help="Capture a quick note")
    p_note.add_argument("text", help="Note text", nargs="+")

    p_link = sub.add_parser("link", help="Capture a web link")
    p_link.add_argument("url", help="URL to capture")

    p_file = sub.add_parser("file", help="Capture a local file")
    p_file.add_argument("path", help="Path to local file")

    args = parser.parse_args(argv)

    if args.cmd == "note":
        text = " ".join(args.text)
        try:
            p = capture_note(text)
            print(p)
            return 0
        except Exception as e:
            print(f"Failed to capture note: {e}")
            return 2

    if args.cmd == "link":
        try:
            p = capture_link(args.url)
            print(p)
            return 0
        except Exception as e:
            print(f"Failed to capture link: {e}")
            return 2

    if args.cmd == "file":
        try:
            p = capture_file(args.path)
            print(p)
            return 0
        except FileNotFoundError:
            return 3
        except Exception as e:
            print(f"Failed to capture file: {e}")
            return 2

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
