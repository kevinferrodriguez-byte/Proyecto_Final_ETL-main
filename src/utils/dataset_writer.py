from pathlib import Path
import os

from src.logger import get_logger

SUPPORTED_FORMATS = frozenset({"parquet"})


class DatasetWriter:
    def __init__(self, output_config, directory):
        if output_config["format"] not in SUPPORTED_FORMATS:
            raise ValueError(
                f"El formato de salida '{output_config['format']}' no está soportado; "
                f"use uno de: {', '.join(sorted(SUPPORTED_FORMATS))} en output.format de config/config.yaml."
            )
        self.format = output_config["format"]
        self.compression = output_config["compression"]
        self.directory = Path(directory)
        self.logger = get_logger(__name__)

    def write(self, frame, schema, name):
        schema.validate(frame)
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.directory / f"{name}.{self.format}"
        temporary_path = self.directory / f".{name}.{self.format}.tmp"
        try:
            frame.to_parquet(temporary_path, engine="pyarrow", compression=self.compression, index=False)
            os.replace(temporary_path, path)
        except (OSError, ValueError):
            temporary_path.unlink(missing_ok=True)
            raise
        self.logger.detail(f"Conjunto guardado: {path} ({len(frame)} filas, compresión {self.compression})")
        return str(path)
