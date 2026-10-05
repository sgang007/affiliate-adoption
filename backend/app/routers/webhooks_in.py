"""Public endpoint: the inbound product webhook (Meridian's product
intelligence engine). Attribution rides entirely on the ?channel= query
param that the product cookies and stamps onto its users as referrer_id."""
import hashlib
import hmac

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Product
from ..schemas import ProductEvent
from ..services.commission import process_product_event

router = APIRouter(tags=["public"])


def _verify_signature(secret: str, raw_body: bytes, signature: str | None) -> bool:
    if not secret:
        return True  # dev mode: no secret configured
    if not signature:
        return False
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


@router.post("/api/webhooks/meridian/{product_id}")
async def product_webhook(
    product_id: int,
    body: ProductEvent,
    request: Request,
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
        result = process_product_event(
            db,
            product,
            channel=body.channel,
            event_raw=body.event,
            payload=body.model_dump(),
        )
    except ValueError as e:
        raise HTTPException(422, str(e))
    except LookupError as e:
        raise HTTPException(404, str(e))

    return {"ok": True, **result}
