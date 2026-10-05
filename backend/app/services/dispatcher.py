"""Outbound webhook dispatcher.

Every affiliate can register callback endpoints (per event type, per product,
in their preferred format) and receives a signed notification whenever one of
their referred users moves through the funnel — including network overrides
earned from descendants' conversions.
"""
import hashlib
import hmac
import json
import logging

import httpx
from sqlalchemy.orm import Session

from ..models import AffiliateLink, ReferredUser, WebhookEndpoint

log = logging.getLogger("portal.webhooks")

# Events arrive here already normalized by the commission engine.
EVENT_NAME = {
    "visited": "visited",
    "signed_up": "signed_up",
    "trial": "trial",
    "subscribed": "subscribed",
    "renewal": "renewal",
    "cancelled": "churned",
}


def build_deliveries(
    db: Session,
    inbound_event: str,
    link: AffiliateLink,
    referred: ReferredUser | None,
    commissions: list[dict],
) -> list[dict]:
    event_name = EVENT_NAME.get(inbound_event, inbound_event)
    earner_ids = {c["user_id"] for c in commissions} | {link.user_id}

    endpoints = (
        db.query(WebhookEndpoint)
        .filter(
            WebhookEndpoint.is_active.is_(True),
            WebhookEndpoint.user_id.in_(earner_ids),
            WebhookEndpoint.event_type.in_([event_name, "all"]),
        )
        .all()
    )

    deliveries = []
    for ep in endpoints:
        if ep.product_id and ep.product_id != link.product_id:
            continue
        my_commissions = [c for c in commissions if c["user_id"] == ep.user_id]
        payload = {
            "event": event_name,
            "product_id": link.product_id,
            "channel": link.slug,
            "referred_user": {
                "external_id": referred.external_id if referred else None,
                "email": referred.email if referred else None,
                "status": referred.status if referred else None,
            },
            "commissions_earned": my_commissions,
            "is_direct": link.user_id == ep.user_id,
        }
        if ep.format == "form":
            body = {
                "event": payload["event"],
                "product_id": str(payload["product_id"]),
                "channel": payload["channel"],
                "referred_external_id": payload["referred_user"]["external_id"] or "",
                "referred_status": payload["referred_user"]["status"] or "",
                "amount_earned": str(sum(c["amount"] for c in my_commissions)),
            }
            content_type = "application/x-www-form-urlencoded"
        else:
            body = payload
            content_type = "application/json"
        raw = json.dumps(body, sort_keys=True).encode()
        signature = hmac.new((ep.secret or "").encode(), raw, hashlib.sha256).hexdigest()
        deliveries.append(
            {
                "url": ep.url,
                "format": ep.format,
                "body": body,
                "headers": {
                    "X-Portal-Event": event_name,
                    "X-Portal-Signature": signature,
                    "Content-Type": content_type,
                },
            }
        )
    return deliveries


def send_deliveries(deliveries: list[dict]) -> None:
    """Fire-and-forget delivery (run via FastAPI BackgroundTasks)."""
    if not deliveries:
        return
    with httpx.Client(timeout=5.0) as client:
        for d in deliveries:
            try:
                if d["format"] == "form":
                    client.post(d["url"], data=d["body"], headers=d["headers"])
                else:
                    client.post(d["url"], json=d["body"], headers=d["headers"])
            except Exception as exc:  # delivery failures must never break ingestion
                log.warning("Webhook delivery to %s failed: %s", d["url"], exc)
