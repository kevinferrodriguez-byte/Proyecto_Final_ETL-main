import logging

from src.logger import APP_LOGGER_NAME, configure_logging, get_logger
from fakes.pipeline_context import reset_app_logger


def configure(tmp_path, level):
    log_file = tmp_path / "logs" / "etl.log"
    configure_logging({"level": level, "file": str(log_file), "format": "%(tipo)s | %(name)s | %(message)s"})
    return log_file


def flush():
    for handler in logging.getLogger(APP_LOGGER_NAME).handlers:
        handler.flush()


def test_configure_logging_is_idempotent_and_writes_every_block_to_file(tmp_path):
    try:
        log_file = configure(tmp_path, "INFO")
        configure(tmp_path, "INFO")
        module_logger = get_logger("src.extract.prueba")
        module_logger.start("Pipeline de prueba")
        module_logger.step("1/1 · Bronce")
        module_logger.ok("tabla descargada")
        module_logger.detail("sha256 abc")
        module_logger.warn("reintento 1/4")
        module_logger.error("fallo definitivo")
        module_logger.end("Pipeline terminado")
        flush()

        assert len(logging.getLogger(APP_LOGGER_NAME).handlers) == 2
        assert log_file.read_text(encoding="utf-8").splitlines() == [
            "INICIO | src.extract.prueba | Pipeline de prueba",
            "PASO | src.extract.prueba | 1/1 · Bronce",
            "OK | src.extract.prueba | tabla descargada",
            "DETALLE | src.extract.prueba | sha256 abc",
            "ADVERTENCIA | src.extract.prueba | reintento 1/4",
            "ERROR | src.extract.prueba | fallo definitivo",
            "FIN | src.extract.prueba | Pipeline terminado",
        ]
    finally:
        reset_app_logger()


def test_console_shows_readable_blocks_and_hides_technical_details(tmp_path, capsys):
    try:
        configure(tmp_path, "INFO")
        module_logger = get_logger("src.pipeline")
        module_logger.start("Pipeline de prueba")
        module_logger.step("1/1 · Bronce")
        module_logger.ok("tabla descargada")
        module_logger.detail("sha256 abc")
        module_logger.warn("reintento 1/4")
        module_logger.error("fallo definitivo")
        module_logger.end("Pipeline terminado")

        captured = capsys.readouterr()
        lines = captured.out.splitlines()
        assert any("INICIO | Pipeline de prueba" in line for line in lines)
        assert lines[lines.index("PASO | 1/1 · Bronce") - 1] == ""
        assert "  OK | tabla descargada" in lines
        assert "  ADVERTENCIA | reintento 1/4" in lines
        assert any("FIN | Pipeline terminado" in line for line in lines)
        assert "sha256 abc" not in captured.out
        assert "  ERROR | fallo definitivo" in captured.err.splitlines()
    finally:
        reset_app_logger()


def test_configured_level_filters_lower_messages(tmp_path):
    try:
        log_file = configure(tmp_path, "WARNING")
        module_logger = get_logger("src.extract.prueba")
        module_logger.ok("no se registra")
        module_logger.warn("sí se registra")
        flush()

        assert log_file.read_text(encoding="utf-8").splitlines() == ["ADVERTENCIA | src.extract.prueba | sí se registra"]
    finally:
        reset_app_logger()
