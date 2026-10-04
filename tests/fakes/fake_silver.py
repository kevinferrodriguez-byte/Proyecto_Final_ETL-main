from pathlib import Path
import hashlib

from src.utils.dataset_writer import DatasetWriter
from src.utils.run_manifest import RunManifest
from src.transform.demografia_schema import DemografiaSchema
from fakes.silver_samples import silver_frame

DATASET = "stg_poblacion_anual"


class FakeSilver:
    def __init__(self, root):
        self.root = root
        self.manifest = RunManifest(root / "manifests")

    def publish(self, run_id, started_at, rows, status="completada"):
        path = Path(DatasetWriter({"format": "parquet", "compression": "snappy"}, self.root).write(silver_frame(rows), DemografiaSchema(), DATASET))
        content = path.read_bytes()
        self.manifest.write(
            {
                "run_id": run_id,
                "status": status,
                "started_at_utc": started_at,
                "payloads": [
                    {
                        "dataset": DATASET,
                        "path": self.manifest.relative_path(path),
                        "sha256": hashlib.sha256(content).hexdigest(),
                        "size_bytes": len(content),
                    }
                ],
            }
        )
        return path
