"""CSS-118 Windows identity-probe hardening: longer timeout + fail-closed retry."""
from __future__ import annotations

import subprocess
from unittest.mock import patch

import pytest

from backend.certification.ov002_continuity import default_identity_probe


@pytest.mark.skipif(__import__("os").name != "nt", reason="Windows probe path only")
def test_windows_probe_retries_once_on_timeout_then_fails_closed():
    calls = {"n": 0}

    def boom(*args, **kwargs):
        calls["n"] += 1
        raise subprocess.TimeoutExpired(cmd=args[0] if args else "powershell", timeout=kwargs.get("timeout"))

    with patch("backend.certification.ov002_continuity.subprocess.run", side_effect=boom):
        assert default_identity_probe(__import__("os").getpid()) is None
    assert calls["n"] == 2


@pytest.mark.skipif(__import__("os").name != "nt", reason="Windows probe path only")
def test_windows_probe_uses_extended_timeout_kwarg():
    seen = {}

    def fake_run(*args, **kwargs):
        seen["timeout"] = kwargs.get("timeout")
        raise subprocess.TimeoutExpired(cmd="powershell", timeout=kwargs.get("timeout"))

    with patch("backend.certification.ov002_continuity.subprocess.run", side_effect=fake_run):
        assert default_identity_probe(__import__("os").getpid()) is None
    assert seen.get("timeout") == 45
