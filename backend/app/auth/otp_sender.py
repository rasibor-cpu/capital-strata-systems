"""
OTP Sender — REA Capital Trading Engine

Sends a 6-digit OTP to the configured destination email.

Env vars:
- OTP_SMTP_HOST, OTP_SMTP_PORT
- OTP_SMTP_USER, OTP_SMTP_PASS  (Gmail app password)
- OTP_FROM_EMAIL
- OTP_TO_EMAIL
"""

from __future__ import annotations

import smtplib
from email.message import EmailMessage

from .auth_config import (
    OTP_SMTP_HOST,
    OTP_SMTP_PORT,
    OTP_SMTP_USER,
    OTP_SMTP_PASS,
    OTP_FROM_EMAIL,
    OTP_TO_EMAIL,
)


def send_otp_email(otp_code: str, username: str) -> None:
    """
    Raises RuntimeError on failure.
    """
    if not OTP_TO_EMAIL:
        raise RuntimeError("OTP_TO_EMAIL not set (no destination email).")
    if not OTP_SMTP_HOST:
        raise RuntimeError("OTP_SMTP_HOST not set.")
    if not OTP_SMTP_USER:
        raise RuntimeError("OTP_SMTP_USER not set.")
    if not OTP_SMTP_PASS:
        raise RuntimeError("OTP_SMTP_PASS not set.")
    if not OTP_FROM_EMAIL:
        raise RuntimeError("OTP_FROM_EMAIL not set.")

    otp_code = (otp_code or "").strip()
    if len(otp_code) != 6 or not otp_code.isdigit():
        raise RuntimeError("Invalid OTP code format.")

    msg = EmailMessage()
    msg["Subject"] = "REA Trading Engine — Your Login OTP"
    msg["From"] = OTP_FROM_EMAIL
    msg["To"] = OTP_TO_EMAIL

    msg.set_content(
        f"Hello {username},\n\n"
        f"Your REA Trading Engine login OTP is: {otp_code}\n\n"
        f"If you did not request this, ignore this email.\n"
    )

    try:
        with smtplib.SMTP(OTP_SMTP_HOST, int(OTP_SMTP_PORT), timeout=20) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(OTP_SMTP_USER, OTP_SMTP_PASS)
            server.send_message(msg)
    except Exception as e:
        raise RuntimeError(f"SMTP send failed: {type(e).__name__}: {e}") from e
