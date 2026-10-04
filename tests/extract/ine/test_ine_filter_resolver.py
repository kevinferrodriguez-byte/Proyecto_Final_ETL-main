import pytest

from src.extract.ine.ine_filter_resolver import IneFilterResolver
from fakes.fake_ine_api import FakeIneApi
from fakes.ine_catalog import AGE_GROUP_ID, SEX_GROUP_ID, IneCatalog


def test_resolver_selects_simple_ages_and_reuses_metadata_indexes(tmp_path):
    catalog = IneCatalog(tmp_path)
    api = FakeIneApi(catalog)
    resolver = IneFilterResolver(api)

    detail = resolver.resolve("56934", catalog.table_filters())
    control = resolver.resolve("56934", catalog.control_filters(0))
    open_intervals = resolver.resolve("56934", catalog.control_filters(1))

    assert detail[:3] == ["18:451", "18:452", "18:453"]
    assert detail[3:108] == [f"355:{15319 + age}" for age in range(105)]
    assert detail[108:] == ["357:311059"]
    assert control == ["18:451", "18:452", "18:453", "356:15668"]
    assert open_intervals == ["18:451", "18:452", "18:453", "357:15100", "357:15071"]
    assert api.calls[("groups", "56934")] == 1
    assert api.calls[("group_values", "56934", AGE_GROUP_ID)] == 1
    assert api.calls[("group_values", "56934", SEX_GROUP_ID)] == 1
    assert [api.calls[("variable", variable_id)] for variable_id in (355, 356, 357)] == [1, 1, 1]


def test_resolver_rejects_unknown_group(tmp_path):
    resolver = IneFilterResolver(FakeIneApi(IneCatalog(tmp_path)))

    with pytest.raises(ValueError, match="El grupo 'Provincia' no existe"):
        resolver.resolve("56934", {"Provincia": {"values": ["Total"]}})


def test_resolver_rejects_unknown_label(tmp_path):
    resolver = IneFilterResolver(FakeIneApi(IneCatalog(tmp_path)))

    with pytest.raises(ValueError, match="El valor 'Ambos sexos' no existe"):
        resolver.resolve("56934", {"Sexo": {"values": ["Ambos sexos"]}})


def test_resolver_rejects_unexpected_value_count(tmp_path):
    resolver = IneFilterResolver(FakeIneApi(IneCatalog(tmp_path)))
    rules = {"include_values_from_variable": "Valores simples de edad", "expected_value_count": 104}

    with pytest.raises(ValueError, match="resolvió 105 valores; se esperaban 104"):
        resolver.resolve("56934", {"Edad simple": rules})
