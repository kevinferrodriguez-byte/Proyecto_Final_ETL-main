from datetime import date
from pathlib import Path
import json

import pandas as pd
import pytest

from src.transform.eurostat.eurostat_normalizer import EurostatNormalizer
from src.transform.eurostat.eurostat_transform import EurostatTransform
from src.transform.eurostat.jsonstat_parser import JsonStatParser
from fakes.fake_eurostat import FakeEurostatBronze, default_payloads, eurostat_config, series_payload
from fakes.ine_payloads import load_config

RUN = "eurostat_20260929T120000.000000Z"
STARTED = "2026-09-29T12:00:00.000000Z"


def normalize(dataset_id, payload):
    normalizer = EurostatNormalizer(load_config()["sources"]["eurostat"])
    reference = {"dataset_id": dataset_id, "run_id": RUN, "source_updated": payload["updated"]}
    return normalizer.normalize(reference, JsonStatParser().parse(payload))


def test_metrics_units_dates_and_provisional_flags_are_mapped():
    frame = normalize("gasto_pensiones", default_payloads()["gasto_pensiones"])

    assert set(frame["metrica"]) == {"gasto_pensiones", "gasto_pensiones_pib_publicado"}
    assert set(frame.loc[frame["metrica"].eq("gasto_pensiones"), "unidad"]) == {"millones_eur"}
    assert frame["fecha_referencia"].iloc[0] == date(1995, 12, 31)

    pib = normalize("pib", default_payloads()["pib"])
    assert set(pib.loc[pib["anyo"].ge(2023), "estado_dato"]) == {"provisional"}
    assert set(pib.loc[pib["anyo"].lt(2023), "estado_dato"]) == {"observado"}


def test_population_is_a_stock_at_1_january():
    frame = normalize("poblacion_control", default_payloads()["poblacion_control"])

    assert set(frame["tipo_medida"]) == {"stock_1_enero"}
    assert frame["fecha_referencia"].iloc[0] == date(1971, 1, 1)


def test_undocumented_flag_is_rejected():
    payload = series_payload([("na_item", "B1GQ")], "unit", ["CP_MEUR"], [2020], lambda metric, year: 1.0, lambda metric, year: "u")

    with pytest.raises(ValueError, match="flags sin estado documentado"):
        normalize("pib", payload)


def test_unexpected_extra_category_is_rejected():
    payload = series_payload([("na_item", "B1GQ")], "unit", ["CP_MEUR"], [2020], lambda metric, year: 1.0)
    payload["dimension"]["na_item"]["category"]["index"] = {"B1GQ": 0, "P3": 1}
    payload["size"][1] = 2
    payload["value"] = {"0": 1.0, "1": 2.0}

    with pytest.raises(ValueError, match="varias categorías"):
        normalize("pib", payload)


def test_silver_writes_long_macro_dataset_with_manifest_and_quality_report(tmp_path):
    config = eurostat_config(tmp_path)
    FakeEurostatBronze(config).run(RUN, STARTED)

    result = EurostatTransform(config).run({"ok": True})

    frame = pd.read_parquet(result["path"])
    assert Path(result["path"]).name == "stg_macro_anual.parquet"
    assert set(frame["metrica"]) == {"pib", "gasto_pensiones", "gasto_pensiones_pib_publicado", "poblacion_1_enero"}
    assert not frame.duplicated(["dataset_id", "metrica", "territorio", "anyo"]).any()
    manifest = json.loads(Path(result["manifest_path"]).read_text(encoding="utf-8"))
    assert manifest["bronze_run_ids"] == [RUN]
    report = json.loads(Path(result["quality_report_path"]).read_text(encoding="utf-8"))
    assert report["estado"] == "aprobado"


def test_silver_rejects_insufficient_coverage_and_writes_no_parquet(tmp_path):
    config = eurostat_config(tmp_path)
    FakeEurostatBronze(config).run(RUN, STARTED, default_payloads(pib_years=range(2015, 2026)))

    with pytest.raises(ValueError, match="completitud"):
        EurostatTransform(config).run({"ok": True})

    assert not list(Path(config["silver"]["eurostat"]["output_path"]).glob("*.parquet"))


def test_silver_refuses_bronze_without_green_integrity(tmp_path):
    config = eurostat_config(tmp_path)
    FakeEurostatBronze(config).run(RUN, STARTED)

    with pytest.raises(RuntimeError, match="integridad"):
        EurostatTransform(config).run({"ok": False})
