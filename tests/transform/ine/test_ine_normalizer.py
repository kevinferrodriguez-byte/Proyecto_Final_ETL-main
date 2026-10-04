from datetime import date

import pytest

from src.transform.ine.ine_normalizer import IneNormalizer
from fakes.ine_payloads import (
    births_deaths,
    load_config,
    migration_69758,
    point,
    population_series,
    projection_series,
    series,
)


def normalizer():
    config = load_config()
    return IneNormalizer(config["sources"]["ine"], config["silver"]["ine"])


def payload(table_id, query="detalle"):
    return {"table_id": table_id, "query": query, "run_id": "ine_20260926T034207.292244Z"}


def test_population_series_are_described_from_metadata():
    rows = [
        population_series("ECP1", "hombres", "1 año", [point(2025, 10.0)]),
        population_series("ECP2", "mujeres", "105 y más años", [point(2025, 3.0)]),
    ]

    frame = normalizer().normalize(payload("56934"), rows)

    assert frame["sexo"].tolist() == ["hombres", "mujeres"]
    assert frame["tipo_edad"].tolist() == ["simple", "tramo_abierto"]
    assert frame["edad_min"].tolist() == [1, 105]
    assert frame["edad_max"].isna().tolist() == [False, True]
    assert frame["edad_max"].iloc[0] == 1
    assert frame["fecha_referencia"].tolist() == [date(2025, 1, 1), date(2025, 1, 1)]
    assert frame["anyo"].tolist() == [2025, 2025]
    assert set(frame["territorio"]) == {"ES"}
    assert set(frame["metrica"]) == {"poblacion"}
    assert set(frame["unidad"]) == {"personas"}
    assert set(frame["estado_dato"]) == {"observado"}
    assert set(frame["escenario"]) == {"observado"}
    assert set(frame["run_id"]) == {"ine_20260926T034207.292244Z"}
    assert not frame["es_control"].any()


def test_control_query_rows_start_as_control_and_total_age_is_mapped():
    rows = [population_series("ECP320", "total", "Todas las edades", [point(2025, 100.0)])]

    frame = normalizer().normalize(payload("56934", "total_edad"), rows)

    assert frame[["tipo_edad", "edad_min", "es_control"]].values.tolist() == [["total", 0, True]]
    assert frame["edad_max"].isna().all()


def test_scenarios_are_mapped_to_snake_case_and_projections_are_projected():
    rows = [
        projection_series("P1", "total", "0 años", [point(2030, 5.0)], "Fecundidad y saldo migratorio altos"),
        projection_series("P2", "total", "0 años", [point(2030, 6.0)], "Central"),
    ]

    frame = normalizer().normalize(payload("36652"), rows)

    assert frame["escenario"].tolist() == ["fecundidad_y_saldo_migratorio_altos", "central"]
    assert set(frame["estado_dato"]) == {"proyectado"}


def test_36643_uses_central_scenario_from_configuration():
    rows = [projection_series("P3", "total", "100 y más años", [point(2030, 7.0)])]

    frame = normalizer().normalize(payload("36643"), rows)

    assert frame[["escenario", "tipo_edad", "edad_min"]].values.tolist() == [["central", "tramo_abierto", 100]]


def test_ambos_sexos_maps_to_total_and_implicit_dimensions_are_applied():
    frame = normalizer().normalize(payload("69758"), migration_69758([point(2021, -1200.0)]))

    assert frame[["sexo", "territorio", "tipo_edad", "edad_etiqueta_original"]].values.tolist() == [
        ["total", "ES", "total", "Todas las edades"]
    ]
    assert frame[["metrica", "unidad"]].values.tolist() == [["saldo_migratorio_exterior", "migraciones"]]


def test_births_and_deaths_keep_their_original_units():
    rows = births_deaths({"Nacimiento": [point(2024, 320000.0)], "Defunción": [point(2024, 430000.0)]})

    frame = normalizer().normalize(payload("6566"), rows)

    assert frame[["metrica", "unidad"]].values.tolist() == [["nacimientos", "nacimientos"], ["defunciones", "defunciones"]]


def test_identical_duplicated_series_are_accepted_for_later_deduplication():
    rows = births_deaths({"Nacimiento": [point(2024, 1.0)]}) * 3

    frame = normalizer().normalize(payload("6566"), rows)

    assert len(frame) == 3


def test_unknown_sex_label_is_an_explicit_error():
    rows = [series("ECP1", [(349, "Total Nacional"), (18, "Varones"), (260, "Población"), (355, "0 años"), (3, "Número")], [point(2025, 1.0)])]

    with pytest.raises(ValueError, match="Etiquetas de sexo desconocidas en la tabla INE 56934: Varones"):
        normalizer().normalize(payload("56934"), rows)


def test_unknown_scenario_label_is_an_explicit_error():
    rows = [projection_series("P1", "total", "0 años", [point(2030, 5.0)], "Migración extrema")]

    with pytest.raises(ValueError, match="Etiquetas de escenario desconocidas.*Migración extrema"):
        normalizer().normalize(payload("36652"), rows)


def test_unrecognized_age_label_is_an_explicit_error():
    rows = [series("ECP1", [(349, "Total Nacional"), (18, "Total"), (260, "Población"), (357, "100 y mas"), (3, "Número")], [point(2025, 1.0)])]

    with pytest.raises(ValueError, match="Etiquetas de edad no reconocidas como tramo_abierto.*100 y mas"):
        normalizer().normalize(payload("56934"), rows)


def test_unconfigured_variable_is_an_explicit_error():
    rows = [population_series("ECP1", "total", "0 años", [point(2025, 1.0)], [(141, "Española")])]

    with pytest.raises(ValueError, match=r"variables no configuradas en MetaData: \[141\]"):
        normalizer().normalize(payload("56934"), rows)


def test_series_without_metadata_is_an_explicit_error():
    rows = [population_series("ECP1", "total", "0 años", [point(2025, 1.0)])]
    rows[0]["MetaData"] = []

    with pytest.raises(ValueError, match="no trae MetaData"):
        normalizer().normalize(payload("56934"), rows)


def test_missing_required_dimension_is_an_explicit_error():
    rows = [series("ECP1", [(349, "Total Nacional"), (260, "Población"), (355, "0 años"), (3, "Número")], [point(2025, 1.0)])]

    with pytest.raises(ValueError, match="La dimensión sexo falta"):
        normalizer().normalize(payload("56934"), rows)


def test_unmapped_fk_tipo_dato_is_an_explicit_error():
    rows = [population_series("ECP1", "total", "0 años", [point(2025, 1.0)])]
    rows[0]["Data"][0]["FK_TipoDato"] = 2

    with pytest.raises(ValueError, match=r"FK_TipoDato sin mapeo documentado: \[2\]"):
        normalizer().normalize(payload("56934"), rows)


def test_secret_value_is_an_explicit_error():
    rows = [population_series("ECP1", "total", "0 años", [point(2025, None)])]
    rows[0]["Data"][0]["Secreto"] = True

    with pytest.raises(ValueError, match="1 datos secretos"):
        normalizer().normalize(payload("56934"), rows)


def test_null_value_is_allowed_only_for_simple_ages():
    simple = normalizer().normalize(payload("56934"), [population_series("ECP1", "total", "101 años", [point(2005, None)])])

    assert simple["valor"].isna().all()
    with pytest.raises(ValueError, match="valores nulos fuera de edades simples"):
        normalizer().normalize(payload("56934"), [population_series("ECP2", "total", "100 y más años", [point(2005, None)])])


def test_conflicting_metadata_for_same_series_is_an_explicit_error():
    rows = births_deaths({"Nacimiento": [point(2024, 1.0)]})
    conflicting = births_deaths({"Defunción": [point(2024, 1.0)]})[0]
    conflicting["COD"] = rows[0]["COD"]

    with pytest.raises(ValueError, match="misma serie con MetaData distinta"):
        normalizer().normalize(payload("6566"), rows + [conflicting])


def test_fertility_indicator_is_a_published_national_total_without_age_or_sex():
    from fakes.ine_payloads import fertility_1407

    frame = normalizer().normalize(payload("1407"), fertility_1407([point(2024, 1.1), point(2023, 1.12)]))

    assert set(frame["metrica"]) == {"indicador_coyuntural_fecundidad"}
    assert set(frame["unidad"]) == {"hijos_por_mujer"}
    assert frame[["sexo", "tipo_edad", "edad_min"]].drop_duplicates().values.tolist() == [["total", "total", 0]]
    assert frame["valor"].tolist() == [1.1, 1.12]


def test_life_expectancy_keeps_sex_and_treats_the_reference_age_as_a_constant():
    from fakes.ine_payloads import life_expectancy

    rows = life_expectancy("1415", {"ambos": [point(2024, 21.87)], "hombres": [point(2024, 19.87)], "mujeres": [point(2024, 23.64)]})

    frame = normalizer().normalize(payload("1415"), rows)

    assert set(frame["metrica"]) == {"esperanza_vida_65"}
    assert set(frame["unidad"]) == {"anos"}
    assert sorted(frame["sexo"]) == ["hombres", "mujeres", "total"]
    assert set(frame["tipo_edad"]) == {"total"}


def test_life_expectancy_rejects_an_unexpected_reference_age():
    from fakes.ine_payloads import life_expectancy

    rows = life_expectancy("1414", {"ambos": [point(2024, 84.0)]})
    rows[0]["MetaData"][4]["Nombre"] = "1 año"

    with pytest.raises(ValueError, match="355"):
        normalizer().normalize(payload("1414"), rows)
