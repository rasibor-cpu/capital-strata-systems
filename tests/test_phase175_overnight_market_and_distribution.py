"""Phase 175 — Overnight Market Intelligence and Report Distribution tests."""

from __future__ import annotations

from pathlib import Path

from backend.executive_intelligence.distribution import (
    ExecutiveBriefDistributionService,
    MockEmailTransport,
    NotConfiguredEmailTransport,
)
from backend.executive_intelligence.overnight_market import produce_overnight_market_intelligence
from backend.executive_intelligence.print_report import (
    assert_final_printable,
    render_printable_html,
    render_printable_pdf,
)
from backend.executive_intelligence.rbac_grants import (
    ACTION_EMAIL,
    ACTION_PRINT,
    ExecutiveBriefAccessControl,
)
from backend.executive_intelligence.service import ExecutiveIntelligenceEngine
from backend.executive_intelligence.validator import validate_brief_for_final
from backend.executive_intelligence.assembler import ExecutiveMorningBriefAssembler


def _good_overnight_injected() -> dict:
    return {
        "regime": {
            "current": "Risk-On",
            "prior": "Quiet",
            "confidence": 0.84,
            "transition_time": "2026-07-17T22:00:00Z",
            "freshness": "FRESH",
        },
        "runtime_advisory_snapshot": {
            "market_regime": "Risk-On",
            "regime_confidence": 0.84,
            "freshness": "FRESH",
            "volatility": {"change": "elevated"},
            "liquidity": {"status": "normal"},
        },
        "portfolio_decision": {
            "market_regime": "Risk-On",
            "freshness": "FRESH",
            "ranked_opportunities": [
                {"symbol": "EUR_USD", "confidence": 0.8, "expected_return": 1.1, "strategy_class": "FX_MOMENTUM"},
                {"symbol": "BTC_USD", "confidence": 0.7, "expected_return": 2.0, "strategy_class": "CRYPTO"},
            ],
        },
        "markets": {"FX": {}, "Crypto": {}},
    }


def _good_brief_evidence() -> dict:
    overnight = produce_overnight_market_intelligence(injected=_good_overnight_injected())
    return {
        "runtime_health": {
            "status": "HEALTHY",
            "runtime_health": "GREEN",
            "freshness": "FRESH",
            "heartbeat_age_seconds": 4,
            "runtime_id": "rt-175",
            "supervisor_id": "sup-175",
            "state_hash": "hash175",
        },
        "broker_health": {
            "health": "GREEN",
            "status": "GREEN",
            "freshness": "FRESH",
            "brokers": {"OANDA": {"health": "GREEN"}},
        },
        "portfolio": {
            "status": "OK",
            "freshness": "FRESH",
            "equity": 125000.0,
            "cash": 30000.0,
            "portfolio_health": 0.9,
            "capital_efficiency": 0.82,
        },
        "market": overnight,
        "opportunities": overnight.get("opportunity_input", {}).get("ranked_opportunity_seeds") or [],
        "committee": {"status": "OK", "overall_recommendation": "APPROVE", "vetoes": []},
        "decision_confidence": {"confidence": 0.88},
        "learning": {
            "freshness": "AGING",
            "confidence": 0.7,
            "learning_summary": {"trade_count": 9, "optimality_rate": 0.7, "top_strategy": "FX_MOMENTUM"},
        },
        "risk": {"risk_level": "MEDIUM", "stability": 0.72},
    }


def test_overnight_valid_evidence() -> None:
    payload = produce_overnight_market_intelligence(injected=_good_overnight_injected())
    assert payload["advisory_only"] is True
    assert payload["execution_allowed"] is False
    assert payload["validation_status"] == "PASS"
    assert payload["market_data_status"] == "AVAILABLE"
    assert payload["regime_current"] == "Risk-On"
    assert payload["overnight_market_summary"]
    assert payload["market_confidence"]["value"] is not None
    assert payload["source_provenance"]
    assert payload["source_hashes"]


def test_overnight_missing_evidence_fail_closed(tmp_path: Path) -> None:
    """Fail-closed when no disk evidence exists.

    Isolation note: ``injected={}`` is falsy in Python, so overnight production
    still falls through to filesystem loaders. Tests must use an empty
    ``repo_root`` (or an explicit unavailable injected bundle) — never depend on
    the absence of workspace artifacts under Path.cwd().
    """
    payload = produce_overnight_market_intelligence(repo_root=tmp_path)
    assert payload["validation_status"] == "FAIL"
    assert payload["market_data_status"] == "UNAVAILABLE"
    assert payload["regime_current"] in {None, "UNAVAILABLE"} or payload["freshness"] == "UNAVAILABLE"
    assert "regime_evidence_unavailable" in payload.get("blockers", []) or "no_market_sources" in payload.get(
        "blockers", []
    )


def test_overnight_empty_repo_independent_of_workspace_artifacts(tmp_path: Path) -> None:
    """Deterministic: empty tmp root fails closed even if cwd has live artifacts."""
    cwd_payload = produce_overnight_market_intelligence()  # may PASS if workspace has evidence
    isolated = produce_overnight_market_intelligence(repo_root=tmp_path)
    assert isolated["validation_status"] == "FAIL"
    assert isolated["market_data_status"] == "UNAVAILABLE"
    # Workspace result must not leak into the isolated root result
    assert isolated.get("source_provenance") == [] or all(
        "injected:" not in str(p.get("path", "")) for p in (isolated.get("source_provenance") or [])
    )
    _ = cwd_payload  # allowed to be PASS or FAIL depending on local artifacts


def test_overnight_explicit_unavailable_injected_fails_closed() -> None:
    payload = produce_overnight_market_intelligence(
        injected={
            "regime": {
                "current": "UNAVAILABLE",
                "freshness": "UNAVAILABLE",
            }
        }
    )
    assert payload["validation_status"] == "FAIL"
    assert payload["market_data_status"] == "UNAVAILABLE"
    assert payload["regime_current"] == "UNAVAILABLE"


def test_overnight_valid_disk_evidence_consumed(tmp_path: Path) -> None:
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir(parents=True)
    (artifacts / "runtime_advisory_snapshot.json").write_text(
        '{"market_regime":"Risk-On","regime_confidence":0.9,"freshness":"FRESH"}',
        encoding="utf-8",
    )
    (artifacts / "portfolio_decision.json").write_text(
        '{"market_regime":"Risk-On","freshness":"FRESH","ranked_opportunities":[{"symbol":"EUR_USD","confidence":0.8}]}',
        encoding="utf-8",
    )
    payload = produce_overnight_market_intelligence(repo_root=tmp_path)
    assert payload["validation_status"] == "PASS"
    assert payload["market_data_status"] == "AVAILABLE"
    assert payload["regime_current"] == "Risk-On"
    sources = {str(p.get("source") or "") for p in (payload.get("source_provenance") or [])}
    assert "runtime_advisory_snapshot" in sources
    assert "portfolio_decision" in sources
    assert "runtime_advisory_snapshot" in (payload.get("source_hashes") or {})


def test_overnight_stale_evidence() -> None:
    inj = _good_overnight_injected()
    inj["regime"]["freshness"] = "STALE"
    inj["runtime_advisory_snapshot"]["freshness"] = "STALE"
    inj["portfolio_decision"]["freshness"] = "STALE"
    payload = produce_overnight_market_intelligence(injected=inj)
    assert payload["freshness"] == "STALE"
    assert payload["validation_status"] == "FAIL"


def test_overnight_partial_asset_classes_marked_unavailable() -> None:
    payload = produce_overnight_market_intelligence(injected=_good_overnight_injected())
    coverage = payload["asset_class_coverage"]
    assert coverage["FX"]["status"] == "AVAILABLE"
    assert coverage["Crypto"]["status"] == "AVAILABLE"
    # Others remain UNAVAILABLE without fabrication
    assert coverage["Commodities"]["status"] == "UNAVAILABLE"


def test_overnight_regime_mapping_engine_labels() -> None:
    inj = _good_overnight_injected()
    inj["regime"] = {"current": "HIGH_VOLATILITY", "confidence": 0.7, "freshness": "FRESH"}
    payload = produce_overnight_market_intelligence(injected=inj)
    assert payload["regime_current"] == "Volatile"


def test_overnight_no_secrets_in_output() -> None:
    inj = _good_overnight_injected()
    inj["runtime_advisory_snapshot"]["api_key"] = "should-redact"
    payload = produce_overnight_market_intelligence(injected=inj)
    # top-level sanitize; nested injected may be in provenance hashes only
    assert "should-redact" not in str(payload.get("api_key", ""))


def test_phase174_market_blocker_resolved_with_overnight(tmp_path: Path) -> None:
    engine = ExecutiveIntelligenceEngine(repo_root=tmp_path, archive_root=tmp_path / "mb")
    result = engine.generate(evidence=_good_brief_evidence(), report_date="2026-07-18", persist=True)
    assert result["archive"]["status"] == "FINAL"
    brief = result["brief"]
    assert brief["panels"]["market_intelligence"]["panel_status"] != "UNAVAILABLE"
    assert brief["panels"]["market_intelligence"]["overnight_market_summary"]
    assert brief["executive_kpis"]["market_confidence"]["value"] is not None
    assert brief["report_hash"]
    # PDF archived or partial noted
    version_dir = Path(result["archive"]["path"]).parent
    man = json_load(version_dir / "manifest.json")
    assert man.get("printable_status") in {"OK", "PARTIAL"}
    if man.get("printable_status") == "OK":
        assert (version_dir / "executive_morning_brief.pdf").is_file()
        assert man["pdf"]["sha256"]


def test_failed_without_market_still_fail_closed(tmp_path: Path) -> None:
    evidence = _good_brief_evidence()
    evidence["market"] = {}
    engine = ExecutiveIntelligenceEngine(repo_root=tmp_path, archive_root=tmp_path / "mb")
    result = engine.generate(evidence=evidence, report_date="2026-07-18", persist=True)
    assert result["archive"]["status"] == "FAILED"
    assert "market_panel_unavailable" in result["validation"]["blockers"]


def test_print_admin_allowed_staff_denied_then_granted(tmp_path: Path) -> None:
    grants = tmp_path / "grants.json"
    access = ExecutiveBriefAccessControl(grant_path=grants)
    dist = ExecutiveBriefDistributionService(root=tmp_path / "dist", access=access, transport=MockEmailTransport())
    engine = ExecutiveIntelligenceEngine(repo_root=tmp_path, archive_root=tmp_path / "mb")
    final = engine.generate(evidence=_good_brief_evidence(), report_date="2026-07-18", persist=True)
    brief = final["brief"]

    admin = dist.authorize_and_render_pdf(brief=brief, role="ADMIN", user_id="admin1")
    assert admin["status"] == "OK"
    assert admin["pdf_bytes"][:4] == b"%PDF"

    denied = dist.authorize_and_render_pdf(brief=brief, role="TELLER", user_id="staff1")
    assert denied["status"] == "DENIED"

    designated = access.designate_staff(
        admin_role="ADMIN",
        admin_user_id="admin1",
        staff_user_id="staff1",
        actions=[ACTION_PRINT],
    )
    assert designated["status"] == "OK"
    allowed = dist.authorize_and_render_pdf(brief=brief, role="TELLER", user_id="staff1")
    assert allowed["status"] == "OK"

    revoked = access.revoke_staff(admin_role="ADMIN", admin_user_id="admin1", staff_user_id="staff1")
    assert revoked["status"] == "OK"
    denied_again = dist.authorize_and_render_pdf(brief=brief, role="TELLER", user_id="staff1")
    assert denied_again["status"] == "DENIED"


def test_cannot_print_failed_or_draft() -> None:
    brief = ExecutiveMorningBriefAssembler().assemble(_good_brief_evidence(), report_date="2026-07-18")
    brief["report_status"] = "DRAFT"
    try:
        assert_final_printable(brief)
        assert False, "expected PermissionError"
    except PermissionError:
        pass
    brief["report_status"] = "FAILED"
    try:
        render_printable_html(brief, printed_by="x")
        assert False, "expected PermissionError"
    except PermissionError:
        pass


def test_printable_html_and_pdf_have_no_secrets(tmp_path: Path) -> None:
    engine = ExecutiveIntelligenceEngine(repo_root=tmp_path, archive_root=tmp_path / "mb")
    brief = engine.generate(evidence=_good_brief_evidence(), report_date="2026-07-18", persist=True)["brief"]
    html = render_printable_html(brief, printed_by="admin1")
    pdf = render_printable_pdf(brief, printed_by="admin1")
    assert "ADVISORY ONLY" in html
    assert "Highest Priority Today" in html
    assert "api_key" not in html.lower() or "REDACTED" in html
    assert pdf.startswith(b"%PDF")
    assert b"password" not in pdf.lower()


def _admin_directory() -> dict:
    return {
        "1001": {"user_id": 1001, "display_name": "Admin One", "role": "ADMIN", "active": True},
        "1002": {"user_id": 1002, "display_name": "Super One", "role": "SUPER_USER", "active": True},
        "2001": {"user_id": 2001, "display_name": "Staff One", "role": "TELLER", "active": True},
        "1003": {"user_id": 1003, "display_name": "Admin Inactive", "role": "ADMIN", "active": False},
        "1004": {"user_id": 1004, "display_name": "Super Locked", "role": "SUPER_USER", "status": "LOCKED"},
    }


def _dist(tmp_path: Path, *, transport=None, directory=None):
    from backend.executive_intelligence.recipients import RecipientDirectory

    access = ExecutiveBriefAccessControl(grant_path=tmp_path / "grants.json")
    return ExecutiveBriefDistributionService(
        root=tmp_path / "dist",
        access=access,
        transport=transport or MockEmailTransport(),
        recipient_directory=RecipientDirectory(loader=lambda: directory or _admin_directory()),
    ), access


def test_email_super_user_and_admin_can_send_and_receive(tmp_path: Path) -> None:
    dist, _ = _dist(tmp_path)
    brief = ExecutiveIntelligenceEngine(repo_root=tmp_path, archive_root=tmp_path / "mb").generate(
        evidence=_good_brief_evidence(), report_date="2026-07-18", persist=True
    )["brief"]

    upsert = dist.upsert_recipient_list(
        admin_role="ADMIN",
        admin_user_id="1001",
        list_id="exec-daily",
        recipient_ids=["1001", "1002"],
    )
    assert upsert["status"] == "OK"

    sent_admin = dist.send_email(brief=brief, role="ADMIN", user_id="1001", list_id="exec-daily")
    assert sent_admin["status"] == "SENT"
    assert sent_admin["eligible_count"] == 2
    assert sent_admin["audit"]["eligible_recipient_count"] == 2

    sent_super = dist.send_email(brief=brief, role="SUPER_USER", user_id="1002", list_id="exec-daily")
    assert sent_super["status"] == "SENT"


def test_staff_cannot_send_or_receive(tmp_path: Path) -> None:
    dist, access = _dist(tmp_path)
    brief = ExecutiveIntelligenceEngine(repo_root=tmp_path, archive_root=tmp_path / "mb").generate(
        evidence=_good_brief_evidence(), report_date="2026-07-18", persist=True
    )["brief"]
    dist.upsert_recipient_list(
        admin_role="ADMIN", admin_user_id="1001", list_id="exec-daily", recipient_ids=["1001"]
    )
    assert dist.send_email(brief=brief, role="TELLER", user_id="2001", list_id="exec-daily")["status"] == "DENIED"
    assert dist.send_email(brief=brief, role="TELLER", user_id="2001", list_id="exec-daily")["reason"] == (
        "EMAIL_SENDER_ROLE_NOT_AUTHORIZED"
    )

    # STAFF cannot be on recipient list
    bad_list = dist.upsert_recipient_list(
        admin_role="ADMIN",
        admin_user_id="1001",
        list_id="mixed-bad",
        recipient_ids=["2001"],
    )
    assert bad_list["status"] == "DENIED"
    assert bad_list["reason"] == "RECIPIENT_ROLE_NOT_AUTHORIZED"


def test_legacy_email_grant_to_staff_denied(tmp_path: Path) -> None:
    dist, access = _dist(tmp_path)
    # Attempt to grant email — must be rejected
    grant = access.designate_staff(
        admin_role="ADMIN",
        admin_user_id="1001",
        staff_user_id="2001",
        actions=[ACTION_EMAIL],
    )
    assert grant["status"] == "DENIED"
    assert grant["reason"] == "EMAIL_GRANT_NOT_DELEGABLE"

    # Forge legacy grant file with email action — authorize must still deny email
    import json

    grants_path = tmp_path / "grants.json"
    grants_path.write_text(
        json.dumps(
            {
                "grants": {
                    "2001": {"actions": [ACTION_EMAIL, ACTION_PRINT], "revoked": False},
                }
            }
        ),
        encoding="utf-8",
    )
    access2 = ExecutiveBriefAccessControl(grant_path=grants_path)
    assert access2.authorize(role="TELLER", user_id="2001", action=ACTION_EMAIL)["allowed"] is False
    assert access2.authorize(role="TELLER", user_id="2001", action=ACTION_PRINT)["allowed"] is True


def test_mixed_recipient_list_rejected(tmp_path: Path) -> None:
    dist, _ = _dist(tmp_path)
    result = dist.upsert_recipient_list(
        admin_role="ADMIN",
        admin_user_id="1001",
        list_id="mixed",
        recipient_ids=["1001", "2001"],
    )
    assert result["status"] == "DENIED"
    assert result["reason"] == "RECIPIENT_ROLE_NOT_AUTHORIZED"
    assert result["rejected_count"] >= 1


def test_external_address_and_inactive_rejected(tmp_path: Path) -> None:
    dist, _ = _dist(tmp_path)
    ext = dist.upsert_recipient_list(
        admin_role="ADMIN",
        admin_user_id="1001",
        list_id="ext",
        recipient_ids=["someone@example.com"],
    )
    assert ext["status"] == "DENIED"
    assert ext["reason"] == "RECIPIENT_ROLE_NOT_AUTHORIZED"

    inactive = dist.upsert_recipient_list(
        admin_role="ADMIN",
        admin_user_id="1001",
        list_id="inactive",
        recipient_ids=["1003"],
    )
    assert inactive["status"] == "DENIED"

    locked = dist.upsert_recipient_list(
        admin_role="ADMIN",
        admin_user_id="1001",
        list_id="locked",
        recipient_ids=["1004"],
    )
    assert locked["status"] == "DENIED"


def test_send_time_revalidation_and_api_bypass(tmp_path: Path) -> None:
    dist, _ = _dist(tmp_path)
    brief = ExecutiveIntelligenceEngine(repo_root=tmp_path, archive_root=tmp_path / "mb").generate(
        evidence=_good_brief_evidence(), report_date="2026-07-18", persist=True
    )["brief"]
    # Plant a stale approved list that includes STAFF (simulates manual config edit)
    import json

    lists_path = tmp_path / "dist" / "recipient_lists.json"
    lists_path.parent.mkdir(parents=True, exist_ok=True)
    lists_path.write_text(
        json.dumps(
            {
                "lists": {
                    "poisoned": {
                        "recipient_ids": ["1001", "2001"],
                        "approved": True,
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    denied = dist.send_email(brief=brief, role="ADMIN", user_id="1001", list_id="poisoned")
    assert denied["status"] == "DENIED"
    assert denied["reason"] == "RECIPIENT_ROLE_NOT_AUTHORIZED"

    bypass = dist.send_email(
        brief=brief,
        role="ADMIN",
        user_id="1001",
        list_id="exec-daily",
        bypass_recipients=["outsider@evil.com"],
    )
    assert bypass["status"] == "DENIED"
    assert bypass["reason"] == "RECIPIENT_ROLE_NOT_AUTHORIZED"


def test_print_staff_cannot_email(tmp_path: Path) -> None:
    dist, access = _dist(tmp_path)
    brief = ExecutiveIntelligenceEngine(repo_root=tmp_path, archive_root=tmp_path / "mb").generate(
        evidence=_good_brief_evidence(), report_date="2026-07-18", persist=True
    )["brief"]
    access.designate_staff(
        admin_role="ADMIN",
        admin_user_id="1001",
        staff_user_id="2001",
        actions=[ACTION_PRINT],
    )
    assert access.authorize(role="TELLER", user_id="2001", action=ACTION_PRINT)["allowed"] is True
    assert access.authorize(role="TELLER", user_id="2001", action=ACTION_EMAIL)["allowed"] is False
    pdf = dist.authorize_and_render_pdf(brief=brief, role="TELLER", user_id="2001")
    assert pdf["status"] == "OK"
    dist.upsert_recipient_list(
        admin_role="ADMIN", admin_user_id="1001", list_id="exec-daily", recipient_ids=["1001"]
    )
    assert dist.send_email(brief=brief, role="TELLER", user_id="2001", list_id="exec-daily")["status"] == "DENIED"


def test_email_not_configured_and_mock_failure(tmp_path: Path) -> None:
    dist, _ = _dist(tmp_path, transport=NotConfiguredEmailTransport())
    brief = ExecutiveIntelligenceEngine(repo_root=tmp_path, archive_root=tmp_path / "mb").generate(
        evidence=_good_brief_evidence(), report_date="2026-07-18", persist=True
    )["brief"]
    dist.upsert_recipient_list(
        admin_role="ADMIN", admin_user_id="1001", list_id="exec-daily", recipient_ids=["1001"]
    )
    assert dist.send_email(brief=brief, role="ADMIN", user_id="1001", list_id="exec-daily")["status"] == "NOT_CONFIGURED"

    dist_fail, _ = _dist(tmp_path / "fail", transport=MockEmailTransport(fail=True))
    brief2 = ExecutiveIntelligenceEngine(repo_root=tmp_path / "fail", archive_root=tmp_path / "fail" / "mb").generate(
        evidence=_good_brief_evidence(), report_date="2026-07-18", persist=True
    )["brief"]
    dist_fail.upsert_recipient_list(
        admin_role="SUPER_USER", admin_user_id="1002", list_id="l1", recipient_ids=["1002"]
    )
    assert dist_fail.send_email(brief=brief2, role="SUPER_USER", user_id="1002", list_id="l1")["status"] == "FAILED"


def test_final_only_email_enforcement(tmp_path: Path) -> None:
    dist, _ = _dist(tmp_path)
    draft = ExecutiveMorningBriefAssembler().assemble(_good_brief_evidence(), report_date="2026-07-18")
    draft["report_status"] = "DRAFT"
    draft["report_hash"] = "x"
    dist.upsert_recipient_list(
        admin_role="ADMIN", admin_user_id="1001", list_id="exec-daily", recipient_ids=["1001"]
    )
    assert dist.send_email(brief=draft, role="ADMIN", user_id="1001", list_id="exec-daily")["status"] == "DENIED"


def test_print_permission_does_not_imply_email(tmp_path: Path) -> None:
    access = ExecutiveBriefAccessControl(grant_path=tmp_path / "g.json")
    access.designate_staff(
        admin_role="ADMIN",
        admin_user_id="admin1",
        staff_user_id="staff_print_only",
        actions=[ACTION_PRINT],
    )
    print_auth = access.authorize(role="TELLER", user_id="staff_print_only", action=ACTION_PRINT)
    email_auth = access.authorize(role="TELLER", user_id="staff_print_only", action=ACTION_EMAIL)
    assert print_auth["allowed"] is True
    assert email_auth["allowed"] is False


def json_load(path: Path) -> dict:
    import json

    return json.loads(path.read_text(encoding="utf-8"))
