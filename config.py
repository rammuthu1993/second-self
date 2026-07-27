"""Shared configuration for SecondSelf."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent

load_dotenv(PROJECT_ROOT / ".env")

# Directories
RAW_DIR = PROJECT_ROOT / "raw"
WIKI_DIR = PROJECT_ROOT / "wiki"
DATA_DIR = PROJECT_ROOT / "data"
ASSETS_DIR = PROJECT_ROOT / "assets"
FILES_DIR = ASSETS_DIR / "files"
EMBEDDINGS_DIR = DATA_DIR / "embeddings"
GRAPH_PATH = DATA_DIR / "graph.json"
INDEX_PATH = DATA_DIR / "index.json"

# PARA wiki subfolders
PARA_CATEGORIES = ("Projects", "Areas", "Resources", "Archives")

# Tunables
SIMILARITY_THRESHOLD = 0.72
RAG_TOP_K = 5
RAG_MIN_SCORE = 0.45
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
LLM_MODEL = "llama3-8b-8192"

# Secrets
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")


def ensure_directories() -> None:
    """Create all required project directories if they do not exist."""
    dirs = [
        RAW_DIR,
        WIKI_DIR,
        DATA_DIR,
        EMBEDDINGS_DIR,
        FILES_DIR,
        *(WIKI_DIR / category for category in PARA_CATEGORIES),
    ]
    for directory in dirs:
        directory.mkdir(parents=True, exist_ok=True)


def validate_groq_api_key() -> None:
    """Raise if GROQ_API_KEY is missing (for classify/ask modules)."""
    if not GROQ_API_KEY or GROQ_API_KEY == "your_key_here":
        raise ValueError(
            "GROQ_API_KEY not set. Copy .env.example to .env and add your key."
        )
