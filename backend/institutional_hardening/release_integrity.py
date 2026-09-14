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


def write_release_manifest(
    output_path: str | Path,
    files: list[str | Path],
    *,
    validation_commands: list[str],
) -> dict:
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = build_release_manifest(files, validation_commands=validation_commands)
    temp = target.with_suffix(target.suffix + ".tmp")
    temp.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    temp.replace(target)
    return payload


def build_pcnrass_release_summary(
    *,
    manifest: dict,
    compile_passed: bool,
    focused_tests_passed: bool,
    full_regression_passed: bool,
    governance_passed: bool,
) -> dict:
    checks = {
        "compile": bool(compile_passed),
        "focused_tests": bool(focused_tests_passed),
        "full_regression": bool(full_regression_passed),
        "governance": bool(governance_passed),
        "manifest_present": bool(manifest.get("manifest_sha256")),
    }
    return {
        "schema_version": "css.pcnrass_release_summary.v1",
        "status": "PASS" if all(checks.values()) else "BLOCKED",
        "checks": checks,
        "manifest_sha256": manifest.get("manifest_sha256"),
        "execution_authority_changed": False,
    }
