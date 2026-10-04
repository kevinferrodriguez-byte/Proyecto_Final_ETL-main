from pathlib import Path

import pandas as pd
import pytest

from src.eda.bronce_a_dataframe import eurostat_a_dataframe, ine_a_dataframe, seguridad_social_a_dataframes, ultimo_manifiesto
from fakes.fake_bronze import FakeBronze, minimal_payloads
from fakes.fake_eurostat import FakeEurostatBronze, eurostat_config
from fakes.fake_seguridad_social import FakeSeguridadSocialBronze, seguridad_social_config


def test_latest_completed_manifest_is_chosen_and_failed_runs_are_ignored(tmp_path):
    bronze = FakeBronze(tmp_path / "ine")
    bronze.run("ine_1", "2026-01-01T00:00:00Z", minimal_payloads())
    bronze.run("ine_2", "2026-02-01T00:00:00Z", minimal_payloads())
    bronze.run("ine_3", "2026-03-01T00:00:00Z", minimal_payloads(), status="fallida")

    path, manifest = ultimo_manifiesto(tmp_path / "ine" / "manifests")

    assert manifest["run_id"] == "ine_2"
    assert Path(path).name == "ine_2.manifest.json"


def test_ine_frame_has_one_row_per_raw_observation_without_cleaning(tmp_path):
    payloads = minimal_payloads()
    FakeBronze(tmp_path / "ine").run("ine_1", "2026-01-01T00:00:00Z", payloads)

    frame = ine_a_dataframe(tmp_path / "ine" / "manifests")

    assert len(frame) == sum(len(serie["Data"]) for series in payloads.values() for serie in series)
    assert frame.attrs["run_id"] == "ine_1"
    # Sin filtrar: conserva la observación de 1 de julio (Plata solo usa el 1 de enero) y las copias de la tabla 6566.
    poblacion = frame[(frame["tabla_id"] == "56934") & (frame["edad"] == "0 años")]
    assert sorted(poblacion["Valor"]) == [10.0, 11.0]
    assert frame[frame["tabla_id"] == "6566"].duplicated(["COD", "Fecha"]).sum() == len(payloads[("6566", "detalle")]) // 2
    assert set(frame.loc[frame["tabla_id"] == "56934", "tipo_variable_edad"]) == {"edad simple", "todas las edades", "tramo abierto"}
    assert {"territorio", "sexo", "concepto", "edad", "escenario_o_tipo_saldo", "Fecha", "Anyo", "Valor"} <= set(frame.columns)


def test_seguridad_social_frames_keep_every_row_under_the_header(tmp_path):
    config = seguridad_social_config(tmp_path)
    FakeSeguridadSocialBronze(config).run("seguridad_social_1", "2026-01-01T00:00:00Z")
    source = config["sources"]["seguridad_social"]

    frames = seguridad_social_a_dataframes(source["storage"]["manifests_path"], source)

    afiliados, pensiones = frames["afiliados"], frames["pensiones"]
    assert list(afiliados.columns[:3]) == ["Periodo", "REGIMEN GENERAL | Régimen General (1)", "REGIMEN GENERAL | Sistema Especial Agrario (2)"]
    assert "TOTAL SISTEMA" in afiliados.columns
    # 128 meses + la nota al pie: la nota se conserva porque el EDA debe verla.
    assert len(afiliados) == 129
    assert afiliados["Periodo"].iloc[-1].startswith("(1) No incluye")
    assert afiliados["TOTAL SISTEMA"].isna().sum() == 1
    assert set(pensiones["hoja"]) == {"Nº Pens. Clases", "Importe €"}
    assert {"PERIODO", "MES", "TOTAL"} <= set(pensiones.columns)
    numero = pensiones[pensiones["hoja"] == "Nº Pens. Clases"]
    # Se conservan la sección de porcentajes (texto en una columna numérica) y los meses aún sin publicar (vacíos).
    assert numero["INCAPACIDAD PERMANENTE"].eq("% de variación anual").sum() == 1
    assert numero.loc[numero["MES"] == "Oct", "TOTAL"].isna().tolist() == [False, True]  # oct-2025 publicado; oct-2026 vacío
    assert afiliados.attrs["run_id"] == pensiones.attrs["run_id"] == "seguridad_social_1"


def test_eurostat_frame_decodes_every_value_and_keeps_flags_and_source_version(tmp_path):
    config = eurostat_config(tmp_path)
    FakeEurostatBronze(config).run("eurostat_1", "2026-01-01T00:00:00Z")

    frame = eurostat_a_dataframe(config["sources"]["eurostat"]["storage"]["manifests_path"])

    assert list(frame.columns[:2]) == ["dataset_id", "codigo_eurostat"]
    assert frame.groupby("dataset_id").size().to_dict() == {"gasto_pensiones": 60, "pib": 31, "poblacion_control": 55}
    pib = frame[frame["dataset_id"] == "pib"]
    assert set(pib.loc[pib["time"] >= "2023", "flag"]) == {"p"}
    assert pib.loc[pib["time"] < "2023", "flag"].isna().all()
    assert set(frame["version_fuente"]) == {"2026-09-29T11:00:00+0200"}


def test_missing_completed_manifest_is_reported(tmp_path):
    (tmp_path / "manifests").mkdir()

    with pytest.raises(ValueError, match="No hay manifiestos completados"):
        ultimo_manifiesto(tmp_path / "manifests")
