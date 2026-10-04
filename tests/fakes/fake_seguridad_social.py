from pathlib import Path
import hashlib

from src.transform.seguridad_social.afiliados_parser import AfiliadosParser
from src.transform.seguridad_social.pensiones_parser import PensionesParser
from src.transform.seguridad_social.seguridad_social_schema import AfiliadosSchema, PensionesSchema
from src.utils.run_manifest import RunManifest
from fakes.ine_payloads import load_config
from fakes.seguridad_social_workbooks import afiliados_rows, afiliados_workbook, grid, pensiones_rows, pensiones_workbook

FILE_IDS = ("afiliados_alta", "pensionistas_nomina")


def seguridad_social_config(root, config=None):
    config = config or load_config()
    bronze = root / "data" / "bronze" / "seguridad_social"
    silver = root / "data" / "silver" / "mercado_laboral_pensiones"
    source = config["sources"]["seguridad_social"]
    source["storage"] = {
        "payloads_path": str(bronze),
        "manifests_path": str(bronze / "manifests"),
        "unmanifested_path": str(bronze / "_sin_manifiesto"),
    }
    for file_id, file in source["files"].items():
        file["url"] = f"https://seg-social.test/{file_id}.xlsx"
    silver_config = config["silver"]["seguridad_social"]
    silver_config["output_path"] = str(silver)
    silver_config["manifests_path"] = str(silver / "manifests")
    config["indicadores"]["output_path"] = str(root / "data" / "gold" / "indicadores")
    config["indicadores"]["pensiones"]["manifests_path"] = str(root / "data" / "gold" / "indicadores" / "manifests_pensiones")
    silver_config["afiliados"]["periods"]["expected_start"] = "2016-01"
    return config


def default_contents():
    return {"afiliados_alta": afiliados_workbook(), "pensionistas_nomina": pensiones_workbook()}


class FakeSeguridadSocialBronze:
    def __init__(self, config):
        storage = config["sources"]["seguridad_social"]["storage"]
        self.storage = storage
        self.root = Path(storage["payloads_path"])
        self.manifest = RunManifest(storage["manifests_path"])

    def run(self, run_id, started_at, contents=None, status="completada"):
        contents = default_contents() if contents is None else contents
        self.root.mkdir(parents=True, exist_ok=True)
        entries = []
        for file_id, content in contents.items():
            path = self.root / f"{file_id}_{run_id}.xlsx"
            path.write_bytes(content)
            entries.append(
                {
                    "file_id": file_id,
                    "path": self.manifest.relative_path(path),
                    "sha256": hashlib.sha256(content).hexdigest(),
                    "size_bytes": len(content),
                }
            )
        self.manifest.write({"run_id": run_id, "status": status, "started_at_utc": started_at, "payloads": entries})
        return entries


def typed(frame, schema, file_id, run_id="seguridad_social_1"):
    frame = frame.assign(fuente="Seguridad Social", archivo_id=file_id, run_id=run_id, territorio="ES", estado_dato="observado")
    return frame[schema.columns()].astype(schema.dtypes)


def afiliados_frame(rows=None):
    config = load_config()["silver"]["seguridad_social"]["afiliados"]
    return typed(AfiliadosParser(config).parse(grid(rows or afiliados_rows())), AfiliadosSchema(), "afiliados_alta")


def pensiones_frame(rows=None):
    config = load_config()["silver"]["seguridad_social"]["pensiones"]
    return typed(PensionesParser(config).parse(grid(rows or pensiones_rows()))["frame"], PensionesSchema(), "pensionistas_nomina")


def importe_frame(rows=None):
    from fakes.seguridad_social_workbooks import importe_rows
    from src.transform.seguridad_social.seguridad_social_schema import ImporteSchema

    config = load_config()["silver"]["seguridad_social"]["importe"]
    parsed = PensionesParser(config).parse(grid(rows or importe_rows()))["frame"].assign(unidad=config["unidad"])
    return typed(parsed, ImporteSchema(), "pensionistas_nomina")
