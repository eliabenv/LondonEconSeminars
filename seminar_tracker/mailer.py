from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage


def smtp_is_configured() -> bool:
    required = [
        "SEMINAR_SMTP_HOST",
        "SEMINAR_EMAIL_FROM",
        "SEMINAR_EMAIL_TO",
    ]
    return all(os.getenv(name) for name in required)


def send_email(subject: str, text_body: str, html_body: str) -> None:
    host = os.getenv("SEMINAR_SMTP_HOST")
    sender = os.getenv("SEMINAR_EMAIL_FROM")
    recipient = os.getenv("SEMINAR_EMAIL_TO")
    if not host or not sender or not recipient:
        raise ValueError("SMTP settings are incomplete. See README.md for required variables.")

    port = int(os.getenv("SEMINAR_SMTP_PORT", "587"))
    username = os.getenv("SEMINAR_SMTP_USERNAME")
    password = os.getenv("SEMINAR_SMTP_PASSWORD")
    use_ssl = os.getenv("SEMINAR_SMTP_SSL", "false").lower() == "true"
    use_starttls = os.getenv("SEMINAR_SMTP_STARTTLS", "true").lower() == "true"

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = recipient
    message.set_content(text_body)
    message.add_alternative(html_body, subtype="html")

    smtp_cls = smtplib.SMTP_SSL if use_ssl else smtplib.SMTP
    with smtp_cls(host, port) as client:
        client.ehlo()
        if use_starttls and not use_ssl:
            client.starttls()
            client.ehlo()
        if username:
            client.login(username, password or "")
        client.send_message(message)

