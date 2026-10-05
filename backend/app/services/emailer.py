"""Invite emails. Uses SMTP when configured, otherwise logs the invite link
(the API also returns the link so the flow works without email setup)."""
import logging
import smtplib
from email.message import EmailMessage

from ..config import get_settings

log = logging.getLogger("portal.email")
settings = get_settings()


def _send(to_email: str, subject: str, body: str) -> None:
    if not settings.smtp_host:
        log.info("SMTP not configured — email to %s: %s\n%s", to_email, subject, body)
        return
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from
    msg["To"] = to_email
    msg.set_content(body)
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as server:
            server.starttls()
            if settings.smtp_user:
                server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(msg)
    except Exception as exc:
        log.warning("Failed to send email to %s: %s", to_email, exc)


def send_payout_processed(to_email: str, name: str, amount: float, number: str) -> None:
    _send(
        to_email,
        f"Your payout {number} has been processed",
        f"Hi {name},\n\nGood news — your payout request {number} for "
        f"Rs {amount:,.2f} has been paid to the account you provided.\n\n"
        "Keep sharing, keep earning!\n",
    )


def send_invite(to_email: str, inviter_name: str, invite_url: str) -> None:
    _send(
        to_email,
        f"{inviter_name} invited you to the Affiliate Adoption Portal",
        f"Hi,\n\n{inviter_name} invited you to join their affiliate network.\n"
        f"Create your account here: {invite_url}\n\n"
        "You'll get your own referral links and earn commissions on every "
        "signup, trial and subscription you drive.\n",
    )
