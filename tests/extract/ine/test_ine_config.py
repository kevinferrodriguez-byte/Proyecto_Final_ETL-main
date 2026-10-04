from fakes.ine_catalog import IneCatalog

AGE_GROUPS = {"56934": "Edad simple", "36643": "Edad", "36652": "Edad"}


def test_all_catalogued_tables_are_enabled_and_have_filters(tmp_path):
    config = IneCatalog(tmp_path).config

    assert config["enabled_tables"] == ["56934", "6566", "24309", "69758", "36643", "36652", "1407", "1414", "1415"]
    for table_id in config["enabled_tables"]:
        assert config["tables"][table_id]["filters"]


def test_56934_detail_includes_open_interval_and_excludes_only_overlaps(tmp_path):
    rules = IneCatalog(tmp_path).config["tables"]["56934"]["filters"]["Edad simple"]

    assert rules["include_labels"] == ["105 y más años"]
    assert rules["expected_value_count"] == 106
    assert set(rules["excluded_labels"]) == {"Todas las edades", "85 y más años", "100 y más años"}


def test_age_tables_request_total_only_in_separate_control_query(tmp_path):
    tables = IneCatalog(tmp_path).config["tables"]

    for table_id, age_group in AGE_GROUPS.items():
        controls = tables[table_id]["control_queries"]
        assert "Todas las edades" in tables[table_id]["filters"][age_group]["excluded_labels"]
        assert controls[0]["name"] == "total_edad"
        assert controls[0]["filters"][age_group] == {"values": ["Todas las edades"]}


def test_56934_requests_overlapping_open_intervals_only_as_separate_control(tmp_path):
    table = IneCatalog(tmp_path).config["tables"]["56934"]
    controls = {control["name"]: control["filters"]["Edad simple"] for control in table["control_queries"]}

    assert list(controls) == ["total_edad", "semiintervalos_edad"]
    assert controls["semiintervalos_edad"] == {"values": ["85 y más años", "100 y más años"]}


def test_6566_documents_unstable_entry_order_as_known_behavior(tmp_path):
    behaviors = IneCatalog(tmp_path).config["tables"]["6566"]["known_behaviors"]

    assert any("orden de las entradas varía" in behavior and "sha256" in behavior for behavior in behaviors)
