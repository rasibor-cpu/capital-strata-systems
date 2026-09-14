from __future__ import annotations

import hashlib
import json
from pathlib import Path


def sha256_file(path: str | Path) -> str:
    target = Path(path)
    digest = hashlib.sha256()
    with target.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_release_manifest(files: list[str | Path], *, validation_commands: list[str]) -> dict:
    rows = []
    for item in sorted((Path(p) for p in files), key=lambda p: str(p)):
        rows.append({
            "path": str(item),
            "sha256": sha256_file(item),
            "size_bytes": item.stat().st_size,
        })
    payload = {
        "schema_version": "css.release_integrity.v1",
        "files": rows,
        "validation_commands": list(validation_commands),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    payload["manifest_sha256"] = hashlib.sha256(canonical).hexdigest()
    return payload
