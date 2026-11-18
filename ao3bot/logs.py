"""Logging setup. Secrets (the AO3 password) are replaced with *** in every log line."""

from __future__ import annotations

import logging
import sys


class RedactingFormatter(logging.Formatter):
    def __init__(self, fmt: str, secrets: list[str]):
        super().__init__(fmt)
        self._secrets = [s for s in secrets if s]

    def format(self, record: logging.LogRecord) -> str:
        text = super().format(record)  # includes any traceback
        for secret in self._secrets:
            text = text.replace(secret, "***")
        return text


def setup_logging(verbose: bool = False, secrets: list[str] | None = None) -> None:
    """Send logs to stderr (journald on the Pi). Safe to call again once secrets are known."""
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(
        RedactingFormatter("%(asctime)s %(levelname)s %(name)s: %(message)s", secrets or [])
    )
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(logging.DEBUG if verbose else logging.INFO)
