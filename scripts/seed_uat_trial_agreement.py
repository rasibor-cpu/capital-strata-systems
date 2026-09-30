"""Seed the deterministic DEVELOPMENT/UAT governing trial agreement.

Operator UAT of the web ``/trial-contract`` flow needs a governing commercial
agreement to exist; agreement validation is (correctly) fail-closed, so a
fresh runtime database rejects every enrollment with "governing commercial
agreement is missing". This inserts exactly one clearly-labelled UAT agreement
through the same append-only repository the product uses
(``TrialContractRepository.create_agreement``) -- nothing else.

Guards:
  * refuses unless ``CSS_ENV`` is development/dev/local/uat (never production);
  * idempotent: an identical existing agreement is left as is;
  * refuses if an agreement with the same id/version but different terms
    already exists (agreements are append-only evidence, never rewritten).

Usage:
    set CSS_ENV=development
    python -m scripts.seed_uat_trial_agreement [--db data/css_runtime.db]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import backend.app.persistence.db as db  # noqa: E402
from backend.commercialization.trial_contract import CommercialAgreementSnapshot  # noqa: E402

UAT_ENVIRONMENTS = {"development", "dev", "local", "uat"}

UAT_AGREEMENT = CommercialAgreementSnapshot(
    agreement_id="UAT-AGR-001",
    agreement_version="v1",
    jurisdiction_code="CA-ON",
    pricing_plan_id="UAT-PLAN-001",
    pricing_summary=(
        "UAT ONLY: CSS earns a performance fee only on profitable trades attributable to "
        "accepted CSS advice, and only once any prior loss is fully recovered."
    ),
    trial_duration_days=30,
    automatic_conversion_disclosure=(
        "UAT ONLY: the trial converts to the paid plan after 30 days unless cancelled "
        "before expiry. No payment is executed in UAT."
    ),
    effective_from="2026-01-01T00:00:00Z",
    evidence_refs=("uat:seed:trial-agreement:v1",),
)


def _row_matches(row, agreement: CommercialAgreementSnapshot) -> bool:
    return (
        row["jurisdiction_code"] == agreement.jurisdiction_code
        and row["pricing_plan_id"] == agreement.pricing_plan_id
        and row["pricing_summary"] == agreement.pricing_summary
        and int(row["trial_duration_days"]) == agreement.trial_duration_days
        and row["automatic_conversion_disclosure"] == agreement.automatic_conversion_disclosure
        and row["effective_from"] == agreement.effective_from
        and tuple(json.loads(row["evidence_refs_json"])) == agreement.evidence_refs
    )


def seed(db_path: Path) -> str:
    """Returns "CREATED" or "ALREADY_PRESENT"; raises RuntimeError on refusal."""
    env = os.environ.get("CSS_ENV", "").strip().lower()
    if env not in UAT_ENVIRONMENTS:
        raise RuntimeError(
            f"refusing to seed UAT data: CSS_ENV must be one of {sorted(UAT_ENVIRONMENTS)} (got {env or 'unset'!r})"
        )
    db.close_connection()
    db.DEFAULT_DB_PATH = Path(db_path)
    from backend.app.persistence.services.persistence_service import PersistenceService

    service = PersistenceService()
    existing = service.trial_contracts.get_agreement(UAT_AGREEMENT.agreement_id, UAT_AGREEMENT.agreement_version)
    if existing is not None:
        if not _row_matches(existing, UAT_AGREEMENT):
            raise RuntimeError(
                f"{UAT_AGREEMENT.agreement_id} {UAT_AGREEMENT.agreement_version} already exists with different "
                "terms; agreements are append-only and will not be rewritten"
            )
        return "ALREADY_PRESENT"
    service.trial_contracts.create_agreement(UAT_AGREEMENT)
    return "CREATED"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed the deterministic UAT trial agreement.")
    parser.add_argument("--db", type=Path, default=db.DEFAULT_DB_PATH, help="runtime DB (default: data/css_runtime.db)")
    args = parser.parse_args(argv)
    try:
        outcome = seed(args.db)
    except RuntimeError as exc:
        print(f"[refused] {exc}")
        return 2
    print(f"[{outcome.lower()}] {UAT_AGREEMENT.agreement_id} {UAT_AGREEMENT.agreement_version} in {args.db}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
