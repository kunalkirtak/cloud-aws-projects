"""Application configuration loaded from environment variables.

No secrets are hard-coded here. Values are read from the process
environment (optionally populated from a local .env file via
python-dotenv) with sensible defaults for local development.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    # python-dotenv is optional at runtime; environment variables set
    # directly (e.g. by Docker or systemd) still work without it.
    pass


@dataclass(frozen=True)
class Settings:
    """Immutable application settings."""

    app_name: str = os.getenv("APP_NAME", "AWS EC2 AI Chatbot")
    environment: str = os.getenv("ENVIRONMENT", "development")
    knowledge_base_path: str = os.getenv("KNOWLEDGE_BASE_PATH", "data/knowledge_base.json")
    max_results: int = int(os.getenv("MAX_RESULTS", "3"))


settings = Settings()
