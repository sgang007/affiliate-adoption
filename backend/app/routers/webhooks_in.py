"""Public endpoints: the referral tracking redirect and the inbound
Meridian product-intelligence-engine webhook."""
import hashlib
import hmac

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import AffiliateLink, Event, Product, ReferredUser
from ..schemas import MeridianEvent
from ..services.commission import process_meridian_event
from ..services.dispatcher import build_deliveries, send_deliveries

router = APIRouter(tags=["public"])

COOKIE_MAX_AGE = 60 * 60 * 24 * 90  # 90 days attribution window


@router.get("/r/{slug}")
def referral_redirect(slug: str, db: Session = Depends(get_db)):
    """Tracking hop: records the visit, pins the channel cookie, and sends
    the visitor to the product with ?channel=<slug> appended so Meridian can
    attribute every later event to this affiliate."""
    link = db.query(AffiliateLink).filter(AffiliateLink.slug == slug).first()
    if not link or not link.product.is_active:
        raise HTTPException(404, "Referral link not found")
    link.visits = (link.visits or 0) + 1
    db.add(Event(link_id=link.id, type="link_visit", payload={}))
    db.commit()

    sep = "&" if "?" in link.product.url else "?"
    target = f"{link.product.url}{sep}channel={slug}"
    response = RedirectResponse(target, status_code=302)
    response.set_cookie(
        "channel", slug, max_age=COOKIE_MAX_AGE, httponly=False, samesite="lax"
    )
    return response


def _verify_signature(secret: str, raw_body: bytes, signature: str | None) -> bool:
    if not secret:
        return True  # dev mode: no secret configured
    if not signature:
        return False
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


@router.post("/api/webhooks/meridian/{product_id}")
async def meridian_webhook(
    product_id: int,
    body: MeridianEvent,
    request: Request,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(404, "Product not found")

    raw = await request.body()
    signature = request.headers.get("X-Meridian-Signature")
    if not _verify_signature(product.webhook_secret or "", raw, signature):
        raise HTTPException(401, "Invalid webhook signature")

    try:
        result = process_meridian_event(
            db,
            product,
            event_type=body.event,
            channel=body.channel,
            external_id=body.user_id or "anonymous",
            email=body.email,
            amount=body.amount,
            raw=body.model_dump(),
        )
    except ValueError as e:
        raise HTTPException(422, str(e))
    except LookupError as e:
        raise HTTPException(404, str(e))

    # Fan out to the affiliates' own configured callback endpoints.
    link = db.get(AffiliateLink, result["link_id"])
    referred = db.get(ReferredUser, result["referred_user_id"])
    deliveries = build_deliveries(db, body.event, link, referred, result["commissions"])
    if deliveries:
        background.add_task(send_deliveries, deliveries)

    return {"ok": True, **result, "callbacks_scheduled": len(deliveries)}
