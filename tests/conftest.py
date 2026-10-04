import pytest

from src.pipeline import Pipeline
from fakes.pipeline_context import PipelineContext, reset_app_logger


@pytest.fixture(scope="session")
def built_pipeline(tmp_path_factory):
    """Ejecuta una vez el pipeline completo (desde Plata) sobre los dobles de Bronce de las tres fuentes."""
    context = PipelineContext(tmp_path_factory.mktemp("pipeline_completo"))
    context.publish_bronze()
    try:
        results = Pipeline(context.config).run("plata")
    finally:
        reset_app_logger()
    return {"context": context, "results": results, "config": context.config, "root": context.root}
