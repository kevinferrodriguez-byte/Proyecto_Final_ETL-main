from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq
import pytest

from src.utils.dataset_writer import DatasetWriter
from src.transform.demografia_schema import DemografiaSchema
from fakes.demografia_rows import valid_frame
from fakes.ine_payloads import load_config


def output_config():
    return load_config()["output"]


def test_writer_uses_configured_format_and_compression_and_preserves_schema(tmp_path):
    schema = DemografiaSchema()
    config = output_config()

    path = Path(DatasetWriter(config, tmp_path).write(valid_frame(), schema, "stg_prueba"))

    assert path == tmp_path / f"stg_prueba.{config['format']}"
    assert pq.ParquetFile(path).metadata.row_group(0).column(0).compression == config["compression"].upper()
    restored = pd.read_parquet(path)
    schema.validate(restored)
    pd.testing.assert_frame_equal(restored, valid_frame())
    assert sorted(item.name for item in tmp_path.iterdir()) == ["stg_prueba.parquet"]


def test_writer_rejects_frame_outside_schema_without_writing(tmp_path):
    frame = valid_frame().drop(columns=["escenario"])

    with pytest.raises(ValueError, match="faltan columnas: escenario"):
        DatasetWriter(output_config(), tmp_path).write(frame, DemografiaSchema(), "stg_prueba")

    assert list(tmp_path.iterdir()) == []


def test_writer_rejects_unsupported_output_format(tmp_path):
    with pytest.raises(ValueError, match="formato de salida 'csv' no está soportado"):
        DatasetWriter({"format": "csv", "compression": "snappy"}, tmp_path)
