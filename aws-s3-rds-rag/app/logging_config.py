"""Logging setup. Never log secrets, passwords, or document contents."""

import logging


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        force=True,
    )
    for noisy in ("botocore", "boto3", "urllib3", "httpx", "httpcore", "sentence_transformers"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
