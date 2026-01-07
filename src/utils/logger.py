"""Logging system with Rich console and file output."""

from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from rich.console import Console
from rich.logging import RichHandler
from rich.theme import Theme

if TYPE_CHECKING:
    from src.utils.config_loader import LoggingConfig

# Custom theme for console output
CUSTOM_THEME = Theme({
    "info": "cyan",
    "warning": "yellow",
    "error": "red bold",
    "critical": "red bold reverse",
    "debug": "dim",
    "success": "green bold",
})

# Global console instance
console = Console(theme=CUSTOM_THEME)


class ColoredFormatter(logging.Formatter):
    """Formatter for file output with detailed timestamps."""

    def format(self, record: logging.LogRecord) -> str:
        record.levelname = f"[{record.levelname:^8}]"
        return super().format(record)


def setup_logger(
    name: str = "ensemble",
    log_dir: str | Path = "logs",
    level: str = "INFO",
    console_output: bool = True,
    file_output: bool = True,
) -> logging.Logger:
    """Set up logger with Rich console and file handlers.

    Args:
        name: Logger name
        log_dir: Directory for log files
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        console_output: Enable console output
        file_output: Enable file output

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))

    # Clear existing handlers
    logger.handlers.clear()

    # Console handler with Rich formatting
    if console_output:
        rich_handler = RichHandler(
            console=console,
            show_time=True,
            show_path=False,
            rich_tracebacks=True,
            tracebacks_show_locals=True,
            markup=True,
        )
        rich_handler.setLevel(getattr(logging, level.upper()))
        rich_handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(rich_handler)

    # File handler
    if file_output:
        log_dir = Path(log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_dir / f"ensemble_{timestamp}.log"

        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)  # File captures all levels
        file_handler.setFormatter(
            ColoredFormatter(
                "%(asctime)s %(levelname)s %(name)s:%(lineno)d - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        logger.addHandler(file_handler)

    return logger


def get_logger(name: str = "ensemble") -> logging.Logger:
    """Get existing logger or create default one.

    Args:
        name: Logger name

    Returns:
        Logger instance
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        return setup_logger(name)
    return logger


class LogContext:
    """Context manager for logging a phase or section."""

    def __init__(self, logger: logging.Logger, phase_name: str):
        self.logger = logger
        self.phase_name = phase_name
        self.start_time: datetime | None = None

    def __enter__(self) -> "LogContext":
        self.start_time = datetime.now()
        self.logger.info(f"{'='*50}")
        self.logger.info(f"Starting: {self.phase_name}")
        self.logger.info(f"{'='*50}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        elapsed = datetime.now() - self.start_time
        if exc_type is None:
            self.logger.info(f"Completed: {self.phase_name} ({elapsed.total_seconds():.1f}s)")
        else:
            self.logger.error(f"Failed: {self.phase_name} - {exc_val}")
        return False


def log_progress(logger: logging.Logger, current: int, total: int, item: str = "") -> None:
    """Log progress update.

    Args:
        logger: Logger instance
        current: Current progress
        total: Total items
        item: Current item description
    """
    pct = (current / total) * 100 if total > 0 else 0
    msg = f"Progress: {current}/{total} ({pct:.1f}%)"
    if item:
        msg += f" - {item}"
    logger.info(msg)


def log_memory(logger: logging.Logger) -> None:
    """Log current memory usage."""
    try:
        import torch
        if torch.cuda.is_available():
            allocated = torch.cuda.memory_allocated() / 1024**3
            reserved = torch.cuda.memory_reserved() / 1024**3
            logger.debug(f"GPU Memory: {allocated:.2f}GB allocated, {reserved:.2f}GB reserved")
    except ImportError:
        pass

    try:
        import psutil
        process = psutil.Process()
        mem_info = process.memory_info()
        logger.debug(f"RAM Usage: {mem_info.rss / 1024**3:.2f}GB")
    except ImportError:
        pass
