from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage


def _get_env(name: str, default: str | None = None) -> str | None:
    v = os.getenv(name)
    if v is None:
        return default
    v = v.strip()
    return v if v else default


def _require(name: str) -> str:
    v = _get_env(name)
    if not v:
        raise RuntimeError(f"{name} not set")
    return v


def send_otp(
    to_email: str | None,
    subject: str,
    message: str,
) -> None:
    """
    Sends an OTP email.

    Design:
    - If to_email is None/empty, fallback to env OTP_TO_EMAIL.
    - If from email not specified, fallback to OTP_FROM_EMAIL, else OTP_SMTP_USER.
    - Fail-closed if required SMTP/env values are missing.

    Required env:
      OTP_SMTP_HOST   (e.g. smtp.gmail.com)
      OTP_SMTP_PORT   (e.g. 587)
      OTP_SMTP_USER   (e.g. rasibor@gmail.com)
      OTP_SMTP_PASS   (Gmail App Password)
      OTP_TO_EMAIL    (destination for this test)
    Optional env:
      OTP_FROM_EMAIL  (defaults to OTP_SMTP_USER)
    """

    # Destination
    dest = (to_email or "").strip()
    if not dest:
        dest = (_get_env("OTP_TO_EMAIL") or "").strip()
    if not dest:
        raise RuntimeError("OTP_TO_EMAIL not set (to_email is empty)")

    # SMTP settings
    host = _require("OTP_SMTP_HOST")
    port_str = _require("OTP_SMTP_PORT")
    user = _require("OTP_SMTP_USER")
    password = _require("OTP_SMTP_PASS")

    try:
        port = int(port_str)
    except ValueError as e:
        raise RuntimeError("OTP_SMTP_PORT must be an integer") from e

    from_email = (_get_env("OTP_FROM_EMAIL") or user).strip()
    if not from_email:
        from_email = user

    # Build email
    msg = EmailMessage()
    msg["From"] = from_email
    msg["To"] = dest
    msg["Subject"] = subject
    msg.set_content(message)

    # Send (STARTTLS)
    with smtplib.SMTP(host, port, timeout=20) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(user, password)
        server.send_message(msg)
