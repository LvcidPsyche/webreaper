"""Structured logging configuration for WebReaper.

Writes timestamped JSON to ~/.webreaper/logs/webreaper.log (rotating, 10MB, 5 backups)
and human-readable output to console via stdlib logging.

Log level controlled by WEBREAPER_LOG_LEVEL env var (default: INFO).
"""

import logging
import logging.handlers
import os
import sys
from pathlib import Path

import structlog


def _get_log_dir() -> Path:
    log_dir = Path(os.path.expanduser("~/.webreaper/logs"))
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def configure_logging():
    """Set up structlog + stdlib logging. Call once at startup."""
    level_name = os.getenv("WEBREAPER_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    log_dir = _get_log_dir()
    log_file = log_dir / "webreaper.log"

    # ── stdlib handler: rotating JSON file ─────────────────────
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(level)

    # ── stdlib handler: console ─────────────────────────────────
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(level)

    logging.basicConfig(
        level=level,
        format="%(message)s",
        handlers=[file_handler, console_handler],
    )

    # ── structlog processors ────────────────────────────────────
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    structlog.configure(
        processors=shared_processors + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Attach structlog JSON renderer to the file handler
    json_formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.JSONRenderer(),
        ],
        foreign_pre_chain=shared_processors,
    )
    file_handler.setFormatter(json_formatter)

    # Human-readable formatter for console
    console_formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.dev.ConsoleRenderer(),
        ],
        foreign_pre_chain=shared_processors,
    )
    console_handler.setFormatter(console_formatter)


def get_logger(name: str):
    """Get a structlog logger bound to the given name."""
    return structlog.get_logger(name)
