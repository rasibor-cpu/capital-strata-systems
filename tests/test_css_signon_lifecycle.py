import pytest

from dashboard.auth.css_sign_on import _resolve_gui_login_result


def test_pending_gui_lifecycle_is_not_classified_as_operator_cancellation():
    with pytest.raises(RuntimeError, match="CSS_SIGN_ON_UI_TERMINATED"):
        _resolve_gui_login_result({"ctx": None, "cancelled": False})


def test_successful_gui_lifecycle_returns_authenticated_context():
    context = {"user_id": "00000", "role": "SUPER_USER"}
    assert _resolve_gui_login_result({"ctx": context, "cancelled": False}) is context


def test_explicit_gui_cancellation_remains_fail_closed_cancellation():
    with pytest.raises(KeyboardInterrupt, match="CSS_SIGN_ON_CANCELLED"):
        _resolve_gui_login_result(
            {"ctx": None, "cancelled": True, "cancel_reason": "operator_exit"}
        )


def test_malformed_gui_result_fails_closed_as_ui_termination():
    with pytest.raises(RuntimeError, match="CSS_SIGN_ON_UI_TERMINATED"):
        _resolve_gui_login_result({"ctx": "not-a-context", "cancelled": False})
