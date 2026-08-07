"""SMTP email sending via Python's stdlib. Config comes from st.secrets / env.
"""

from __future__ import annotations

import smtplib
from email.message import EmailMessage


def send_email(cfg: dict, to_addr: str, subject: str, body: str) -> tuple[bool, str]:
    if not cfg.get("host") or not cfg.get("user") or not cfg.get("password"):
        return False, "SMTP not configured: host/user/password missing in secrets"
    if not cfg.get("from_addr"):
        return False, "SMTP from_addr missing in secrets"
    if not to_addr:
        return False, "Lead has no email address set"

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"{cfg.get('from_name') or 'CircuCity'} <{cfg['from_addr']}>"
    msg["To"] = to_addr
    msg.set_content(body)

    try:
        with smtplib.SMTP(cfg["host"], cfg["port"], timeout=30) as server:
            server.starttls()
            server.login(cfg["user"], cfg["password"])
            server.send_message(msg)
        return True, "Sent"
    except Exception as exc:  # network, auth, DNS errors all end up here
        return False, f"Send failed: {exc}"