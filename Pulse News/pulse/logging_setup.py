"""Structured-ish logging with rotating files and a console stream."""
from __future__ import annotations

import logging
import logging.handlers
import sys
import threading

from .config import settings

_configured = False
_lock = threading.Lock()
_FORMAT = "%(asctime)s %(levelname)-7s %(name)-12s %(message)s"


class _ColorFormatter(logging.Formatter):
    COLORS = {
        "DEBUG": "\033[38;5;244m",
        "INFO": "\033[38;5;39m",
        "WARNING": "\033[38;5;214m",
        "ERROR": "\033[38;5;203m",
        "CRITICAL": "\033[1;38;5;196m",
    }

    def format(self, record: logging.LogRecord) -> str:
        text = super().format(record)
        if sys.stderr.isatty():
            color = self.COLORS.get(record.levelname)
            if color:
                return f"{color}{text}\033[0m"
        return text


def configure() -> None:
    global _configured
    with _lock:
        if _configured:
            return
        settings.ensure_dirs()
        root = logging.getLogger("pulse")
        root.setLevel(logging.INFO)
        root.propagate = False
        stream = logging.StreamHandler(sys.stderr)
        stream.setFormatter(_ColorFormatter(_FORMAT, "%H:%M:%S"))
        root.addHandler(stream)
        try:
            file_handler = logging.handlers.RotatingFileHandler(
                settings.log_dir / "pulse.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8"
            )
            file_handler.setFormatter(logging.Formatter(_FORMAT))
            root.addHandler(file_handler)
        except OSError:
            pass
        _configured = True


def get_logger(name: str = "app") -> logging.Logger:
    configure()
    return logging.getLogger(f"pulse.{name}")
