import json

import pytest

from backend.commercialization.production_evidence_staging import (
    stage_validated_production_evidence,
)
from tests.test_production_evidence_handoff import _package


def test_valid_package_is_staged_immutably_with_manifest(tmp_path):
    payload = _package()
    staged = stage_validated_production_evidence(
        payload=payload,
        output_dir=tmp_path,
    )
    package = json.loads(
        __import__("pathlib").Path(staged.package_path).read_text(
            encoding="utf-8"
        )
    )
    manifest = json.loads(
        __import__("pathlib").Path(staged.manifest_path).read_text(
            encoding="utf-8"
        )
    )
    assert package["package_id"] == "PROD-EVIDENCE-001"
    assert manifest["package_sha256"] == staged.sha256
    assert manifest["valid_for_review"] is True
    assert manifest["production_authorized"] is False

    with pytest.raises(FileExistsError):
        stage_validated_production_evidence(
            payload=payload,
            output_dir=tmp_path,
        )


def test_invalid_package_cannot_be_staged(tmp_path):
    payload = _package()
    payload["evidence"]["PAYMENT_PROVIDER"]["environment"] = "sandbox"
    with pytest.raises(ValueError, match="not valid for review"):
        stage_validated_production_evidence(
            payload=payload,
            output_dir=tmp_path,
        )
