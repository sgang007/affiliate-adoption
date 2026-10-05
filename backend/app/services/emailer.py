"""Transactional email: invites and payout confirmations.

Delivery order: Resend API (set RESEND_API_KEY) → SMTP → console log.
The invite flow never depends on delivery — the UI always shows the link.
"""
import logging
import smtplib
from email.message import EmailMessage

import httpx

from ..config import get_settings

log = logging.getLogger("portal.email")
settings = get_settings()

RESEND_URL = "https://api.resend.com/emails"


def email_configured() -> bool:
    return bool(settings.resend_api_key or settings.smtp_host)


def _send_resend(to_email: str, subject: str, body: str) -> None:
    resp = httpx.post(
        RESEND_URL,
        headers={"Authorization": f"Bearer {settings.resend_api_key}"},
        json={
            "from": settings.email_from,
            "to": [to_email],
            "subject": subject,
            "text": body,
        },
        timeout=10,
    )
    resp.raise_for_status()
    log.info("Resend accepted email to %s (%s)", to_email, resp.json().get("id"))


def _send_smtp(to_email: str, subject: str, body: str) -> None:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.email_from
    msg["To"] = to_email
    msg.set_content(body)
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as server:
        server.starttls()
        if settings.smtp_user:
            server.login(settings.smtp_user, settings.smtp_password)
        server.send_message(msg)


def _send(to_email: str, subject: str, body: str) -> None:
    try:
        if settings.resend_api_key:
            _send_resend(to_email, subject, body)
        elif settings.smtp_host:
            _send_smtp(to_email, subject, body)
        else:
            log.info("Email not configured — to %s: %s\n%s", to_email, subject, body)
    except Exception as exc:
        log.warning("Failed to send email to %s: %s", to_email, exc)


def send_invite(to_email: str, inviter_name: str, invite_url: str) -> None:
    _send(
        to_email,
        f"{inviter_name} invited you to the Affiliate Adoption Portal",
        f"Hi,\n\n{inviter_name} invited you to join their affiliate network.\n"
        f"Create your account here: {invite_url}\n\n"
        "You'll get your own referral links and earn commissions on every "
        "signup, trial and subscription you drive.\n",
    )


def send_payout_processed(to_email: str, name: str, amount: float, number: str) -> None:
    _send(
        to_email,
        f"Your payout {number} has been processed",
        f"Hi {name},\n\nGood news — your payout request {number} for "
        f"Rs {amount:,.2f} has been paid to the account you provided.\n\n"
        "Keep sharing, keep earning!\n",
    )
