import os
import smtplib
from email.message import EmailMessage


SMTP_HOST = os.getenv("OTP_SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("OTP_SMTP_PORT", "587"))
SMTP_USER = os.getenv("OTP_SMTP_USER")
SMTP_PASS = os.getenv("OTP_SMTP_PASS")
OTP_FROM  = os.getenv("OTP_FROM_EMAIL", SMTP_USER)


def send_otp_email(*, to_email: str, otp_code: str) -> None:
    if not SMTP_USER or not SMTP_PASS:
        raise RuntimeError("SMTP credentials not configured")

    msg = EmailMessage()
    msg["From"] = OTP_FROM
    msg["To"] = to_email
    msg["Subject"] = "Your REA Capital Login Code"

    msg.set_content(
        f"""
Your REA Capital login verification code is:

    {otp_code}

This code expires in 5 minutes.

If you did not request this login, ignore this email.
"""
    )

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)
