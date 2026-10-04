from src.utils.documentacion import documents, load_config


def test_generated_documents_match_code_and_configuration():
    stale = [path.name for path, content in documents(load_config()).items() if not path.exists() or path.read_text(encoding="utf-8") != content]

    assert not stale, f"Ejecute python -m src.utils.documentacion; desactualizados: {stale}"
