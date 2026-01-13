import logging
import sys
from typing import Optional


class StdoutLogger:
    """
    Single-process stdout logger that actually works under Uvicorn/Gunicorn.

    - Uses the stdlib logging system (no duplicate handlers).
    - Ensures root logging is configured once (force=True) so INFO logs show up.
    - Keeps your existing API: .info/.warning/.error etc.
    """

    _configured: bool = False  # class-level guard

    @classmethod
    def configure(
        cls,
        *,
        level: int = logging.INFO,
        fmt: str = "%(asctime)s %(levelname)s [%(name)s] %(message)s",
        stream = sys.stdout,
        force: bool = True,
    ) -> None:
        """
        Configure root logging once. Call early (best) but safe to call multiple times.
        """
        if cls._configured:
            return

        logging.basicConfig(
            level=level,
            stream=stream,
            format=fmt,
            force=force,  # Python 3.8+: replace any handlers added by uvicorn
        )
        cls._configured = True

    def __init__(
        self,
        name: str = "logger",
        level: int = logging.INFO,
        fmt: Optional[str] = None,
        force_configure: bool = True,
    ):
        # Ensure root logging emits INFO (your “NO LOGS” issue)
        if force_configure:
            self.configure(level=level, fmt=fmt or "%(asctime)s %(levelname)s [%(name)s] %(message)s")

        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)

        # IMPORTANT: do NOT add your own handler if root is configured.
        # Otherwise you'll get duplicate lines.
        self.logger.propagate = True

    def debug(self, message): self.logger.debug(message)
    def info(self, message): self.logger.info(message)
    def warning(self, message): self.logger.warning(message)
    def error(self, message): self.logger.error(message)
    def critical(self, message): self.logger.critical(message)
