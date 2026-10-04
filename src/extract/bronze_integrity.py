from pathlib import Path
import hashlib
import json

PROBLEM_KEYS = ("orphans", "missing", "mismatches", "duplicates", "invalid_manifests")


class BronzeIntegrityChecker:
    def __init__(self, payloads_path, manifests_path, excluded_paths):
        self.payloads_path = Path(payloads_path).resolve()
        self.manifests_path = Path(manifests_path).resolve()
        self.excluded_paths = [self.manifests_path] + [Path(path).resolve() for path in excluded_paths]

    def check(self):
        references = {}
        invalid_manifests = []
        manifest_paths = sorted(self.manifests_path.glob("*.manifest.json")) if self.manifests_path.is_dir() else []
        for manifest_path in manifest_paths:
            payloads = self._read_payloads(manifest_path)
            if payloads is None:
                invalid_manifests.append(manifest_path.name)
                continue
            for entry in payloads:
                path = (manifest_path.parent / entry["path"]).resolve()
                references.setdefault(path, []).append({"manifest": manifest_path.name, "entry": entry})

        payload_paths = self._payload_paths()
        missing = []
        mismatches = []
        for path, refs in references.items():
            if not path.is_file():
                missing.extend({"payload": self._label(path), "manifest": ref["manifest"]} for ref in refs)
                continue
            actual = self._fingerprint(path)
            mismatches.extend(
                self._mismatch(path, ref, actual)
                for ref in refs
                if (ref["entry"].get("size_bytes"), ref["entry"].get("sha256")) != (actual["size_bytes"], actual["sha256"])
            )

        report = {
            "payloads_checked": len(payload_paths),
            "manifests_checked": len(manifest_paths),
            "orphans": sorted(self._label(path) for path in payload_paths if path not in references),
            "missing": missing,
            "mismatches": mismatches,
            "duplicates": [
                {"payload": self._label(path), "manifests": [ref["manifest"] for ref in refs]}
                for path, refs in references.items()
                if len(refs) > 1
            ],
            "invalid_manifests": invalid_manifests,
        }
        report["ok"] = not any(report[key] for key in PROBLEM_KEYS)
        return report

    def _payload_paths(self):
        if not self.payloads_path.is_dir():
            return set()
        return {
            path.resolve()
            for path in self.payloads_path.rglob("*")
            if path.is_file() and not self._is_excluded(path.resolve())
        }

    def _is_excluded(self, path):
        return any(path.is_relative_to(excluded) for excluded in self.excluded_paths)

    def _read_payloads(self, manifest_path):
        try:
            payloads = json.loads(manifest_path.read_bytes())["payloads"]
        except (OSError, ValueError, KeyError, TypeError):
            return None
        if not isinstance(payloads, list) or not all(isinstance(entry, dict) and "path" in entry for entry in payloads):
            return None
        return payloads

    def _fingerprint(self, path):
        with path.open("rb") as file:
            sha256 = hashlib.file_digest(file, "sha256").hexdigest()
        return {"size_bytes": path.stat().st_size, "sha256": sha256}

    def _mismatch(self, path, ref, actual):
        return {
            "payload": self._label(path),
            "manifest": ref["manifest"],
            "expected_size_bytes": ref["entry"].get("size_bytes"),
            "actual_size_bytes": actual["size_bytes"],
            "expected_sha256": ref["entry"].get("sha256"),
            "actual_sha256": actual["sha256"],
        }

    def _label(self, path):
        if path.is_relative_to(self.payloads_path):
            return path.relative_to(self.payloads_path).as_posix()
        return path.as_posix()
