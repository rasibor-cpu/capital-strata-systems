from pathlib import Path

SOURCE = Path("scripts/css_live_dashboard.py")


def _source() -> str:
    return SOURCE.read_text(encoding="utf-8")


def _startup_cancel_block() -> str:
    text = _source()
    function_start = text.index("def authenticate_startup_user(")
    start = text.index("    except KeyboardInterrupt:", function_start)
    end = text.index("    except SystemExit:", start)
    return text[start:end]


def test_r5_startup_cancel_exits_cleanly():
    assert "raise SystemExit(0)" in _startup_cancel_block()


def test_r5_startup_cancel_has_no_bare_raise():
    lines = [line.strip() for line in _startup_cancel_block().splitlines()]
    assert "raise" not in lines


def test_r5_startup_cancel_has_distinct_audit_event():
    block = _startup_cancel_block()
    assert 'audit_ledger.record(' in block
    assert '"login_cancelled"' in block


def test_r5_startup_cancel_records_reason():
    assert '"reason": "operator_sign_on_cancelled"' in _startup_cancel_block()


def test_r5_startup_cancel_records_runtime_origin():
    block = _startup_cancel_block()
    assert "origin = runtime_origin_context()" in block
    assert "**origin" in block


def test_r5_startup_cancel_preserves_settlement():
    assert "pcnrass_close_session_to_account()" in _startup_cancel_block()


def test_r5_systemexit_passthrough_remains():
    text = _source()
    assert "    except SystemExit:\n        raise" in text


def test_r5_generic_failure_handler_remains():
    text = _source()
    function_start = text.index("def authenticate_startup_user(")
    function_tail = text[function_start:]
    assert "    except Exception as e:" in function_tail


def test_r5_runtime_keyboard_interrupt_handler_is_still_separate():
    assert _source().count("except KeyboardInterrupt:") >= 2