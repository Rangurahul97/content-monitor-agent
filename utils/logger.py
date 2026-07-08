"""
Colored logging utility for the Content Monitor Agent.

Provides ``setup_logger`` for full logger configuration (console colours
via *colorama*, optional file handler) and ``get_logger`` as a thin
convenience wrapper.
"""

import logging
import sys
from typing import Optional

try:
    from colorama import Fore, Style, init as colorama_init

    colorama_init(autoreset=True)
    _COLORAMA_AVAILABLE = True
except ImportError:
    _COLORAMA_AVAILABLE = False


# ------------------------------------------------------------------
# Colour map (gracefully degrades when colorama is absent)
# ------------------------------------------------------------------

if _COLORAMA_AVAILABLE:
    _LEVEL_COLOURS: dict[int, str] = {
        logging.DEBUG: Fore.CYAN,
        logging.INFO: Fore.GREEN,
        logging.WARNING: Fore.YELLOW,
        logging.ERROR: Fore.RED,
        logging.CRITICAL: Fore.RED + Style.BRIGHT,
    }
else:
    _LEVEL_COLOURS = {}


# ------------------------------------------------------------------
# Custom formatter
# ------------------------------------------------------------------

class _ColouredFormatter(logging.Formatter):
    """Formatter that injects ANSI colour codes around the log level."""

    _BASE_FMT = "[%(asctime)s] [%(levelname)-8s] [%(name)s] %(message)s"
    _DATE_FMT = "%H:%M:%S"

    def __init__(self, use_colour: bool = True) -> None:
        super().__init__(fmt=self._BASE_FMT, datefmt=self._DATE_FMT)
        self.use_colour = use_colour and _COLORAMA_AVAILABLE

    def format(self, record: logging.LogRecord) -> str:
        if self.use_colour:
            colour = _LEVEL_COLOURS.get(record.levelno, "")
            reset = Style.RESET_ALL if _COLORAMA_AVAILABLE else ""
            record.levelname = f"{colour}{record.levelname}{reset}"
            record.msg = f"{colour}{record.msg}{reset}"
        return super().format(record)


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------

def setup_logger(
    name: str,
    level: str = "INFO",
    log_file: Optional[str] = None,
) -> logging.Logger:
    """Create and configure a named logger with coloured console output.

    Args:
        name: Logger name (typically ``__name__`` of the calling module).
        level: Logging level string — one of
            ``"DEBUG"``, ``"INFO"``, ``"WARNING"``, ``"ERROR"``, ``"CRITICAL"``.
        log_file: If provided, an additional ``FileHandler`` is attached
            that writes **plain** (non-coloured) log lines.

    Returns:
        The configured :class:`logging.Logger` instance.
    """
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    logger = logging.getLogger(name)
    logger.setLevel(numeric_level)

    # Avoid adding duplicate handlers when called more than once.
    if logger.handlers:
        return logger

    # ---- Console handler (with colour) ----
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(_ColouredFormatter(use_colour=True))
    logger.addHandler(console_handler)

    # ---- File handler (plain text) ----
    if log_file:
        try:
            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_handler.setLevel(numeric_level)
            file_handler.setFormatter(_ColouredFormatter(use_colour=False))
            logger.addHandler(file_handler)
        except OSError as exc:
            logger.warning("Could not open log file %s: %s", log_file, exc)

    return logger


def get_logger(name: str) -> logging.Logger:
    """Return an existing logger or create one with default settings.

    This is a convenience shortcut — if a logger with *name* already has
    handlers it is returned as-is; otherwise ``setup_logger`` is called
    with the defaults (``INFO`` level, console-only).

    Args:
        name: Logger name.

    Returns:
        A ready-to-use :class:`logging.Logger`.
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        return setup_logger(name)
    return logger
