"""Validate and inspect the knowledge base file.

Run with:
    python scripts/seed_data.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
KB_PATH = ROOT_DIR / "data" / "knowledge_base.json"
REQUIRED_FIELDS = {"id", "title", "content"}


def main() -> int:
    if not KB_PATH.exists():
        print(f"Knowledge base file not found: {KB_PATH}")
        return 1

    try:
        documents = json.loads(KB_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"Invalid JSON in knowledge base: {exc}")
        return 1

    if not isinstance(documents, list) or not documents:
        print("Knowledge base must be a non-empty JSON list.")
        return 1

    for index, doc in enumerate(documents):
        missing = REQUIRED_FIELDS - set(doc.keys())
        if missing:
            print(f"Document at index {index} is missing fields: {missing}")
            return 1

    print(f"Knowledge base OK: {len(documents)} document(s) loaded from {KB_PATH}")
    for doc in documents:
        print(f"  - {doc['id']}: {doc['title']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
