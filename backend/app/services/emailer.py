"""Invite emails. Uses SMTP when configured, otherwise logs the invite link
(the API also returns the link so the flow works without email setup)."""
import logging
import smtplib
from email.message import EmailMessage

from ..config import get_settings

log = logging.getLogger("portal.email")
settings = get_settings()


def send_invite(to_email: str, inviter_name: str, invite_url: str) -> None:
    subject = f"{inviter_name} invited you to the Affiliate Adoption Portal"
    body = (
        f"Hi,\n\n{inviter_name} invited you to join their affiliate network.\n"
        f"Create your account here: {invite_url}\n\n"
        "You'll get your own referral links and earn commissions on every "
        "signup, trial and subscription you drive.\n"
    )
    if not settings.smtp_host:
        log.info("SMTP not configured — invite for %s: %s", to_email, invite_url)
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
        log.warning("Failed to send invite email to %s: %s", to_email, exc)
