from rich.console import Console
from rich.text import Text
from pathlib import Path
import logging
import time

APP_LOGGER_NAME = "src"
STYLES = {
    "INICIO": "bold cyan",
    "FIN": "bold cyan",
    "PASO": "bold cyan",
    "OK": "green",
    "ADVERTENCIA": "yellow",
    "ERROR": "bold red",
}
LEVEL_KINDS = {logging.WARNING: "ADVERTENCIA", logging.ERROR: "ERROR", logging.CRITICAL: "ERROR"}


class BlockConsoleHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.console = Console(highlight=False)
        self.error_console = Console(stderr=True, highlight=False)

    def emit(self, record):
        kind = getattr(record, "tipo", None) or LEVEL_KINDS.get(record.levelno)
        if kind not in STYLES:
            return
        try:
            self._render(kind, record.getMessage())
        except Exception:
            self.handleError(record)

    def _render(self, kind, message):
        style = STYLES[kind]
        if kind == "INICIO":
            self.console.print()
            self.console.rule(Text(f"{kind} | {message}"), style=style)
        elif kind == "FIN":
            self.console.print()
            self.console.rule(Text(f"{kind} | {message}"), style=style)
            self.console.print()
        elif kind == "PASO":
            self.console.print()
            self.console.print(Text(f"PASO | {message}", style=style))
        elif kind == "ERROR":
            self.error_console.print(Text(f"  ERROR | {message}", style=style))
        else:
            self.console.print(Text(f"  {kind} | {message}", style=style))


class BlockLogger:
    def __init__(self, name):
        self.logger = logging.getLogger(name)

    def start(self, message):
        self._log(logging.INFO, "INICIO", message)

    def end(self, message):
        self._log(logging.INFO, "FIN", message)

    def step(self, message):
        self._log(logging.INFO, "PASO", message)

    def ok(self, message):
        self._log(logging.INFO, "OK", message)

    def detail(self, message):
        self._log(logging.INFO, "DETALLE", message)

    def warn(self, message):
        self._log(logging.WARNING, "ADVERTENCIA", message)

    def error(self, message):
        self._log(logging.ERROR, "ERROR", message)

    def _log(self, level, kind, message):
        self.logger.log(level, message, extra={"tipo": kind})


def configure_logging(config):
    app_logger = logging.getLogger(APP_LOGGER_NAME)
    if app_logger.handlers:
        return app_logger

    log_file = Path(config["file"])
    log_file.parent.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter(config["format"], defaults={"tipo": "DETALLE"})
    formatter.converter = time.gmtime
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)

    app_logger.setLevel(config["level"])
    app_logger.addHandler(file_handler)
    app_logger.addHandler(BlockConsoleHandler())
    app_logger.propagate = False
    return app_logger


def get_logger(name):
    return BlockLogger(name)
