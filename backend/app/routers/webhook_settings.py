from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user, require_admin
from ..models import User, WebhookEndpoint
from ..schemas import WebhookSettingIn, WebhookSettingUpdate

# Outbound callback configuration is part of the admin's product-setup
# workflow; affiliates never see or manage webhooks.
router = APIRouter(
    prefix="/api/webhook-settings",
    tags=["webhook-settings"],
    dependencies=[Depends(require_admin)],
)

VALID_EVENTS = {"all", "visited", "signed_up", "trial", "subscribed", "renewal"}
VALID_FORMATS = {"json", "form"}


def ep_out(ep: WebhookEndpoint) -> dict:
    return {
        "id": ep.id,
        "url": ep.url,
        "event_type": ep.event_type,
        "format": ep.format,
        "product_id": ep.product_id,
        "secret": ep.secret,
        "is_active": ep.is_active,
    }


@router.get("")
def list_settings(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    eps = db.query(WebhookEndpoint).filter(WebhookEndpoint.user_id == user.id).all()
    return [ep_out(e) for e in eps]


@router.post("")
def create_setting(
    body: WebhookSettingIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if body.event_type not in VALID_EVENTS:
        raise HTTPException(422, f"event_type must be one of {sorted(VALID_EVENTS)}")
    if body.format not in VALID_FORMATS:
        raise HTTPException(422, f"format must be one of {sorted(VALID_FORMATS)}")
    ep = WebhookEndpoint(user_id=user.id, **body.model_dump())
    db.add(ep)
    db.commit()
    db.refresh(ep)
    return ep_out(ep)


@router.patch("/{setting_id}")
def update_setting(
    setting_id: int,
    body: WebhookSettingUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ep = db.get(WebhookEndpoint, setting_id)
    if not ep or ep.user_id != user.id:
        raise HTTPException(404, "Webhook setting not found")
    data = body.model_dump(exclude_none=True)
    if "event_type" in data and data["event_type"] not in VALID_EVENTS:
        raise HTTPException(422, f"event_type must be one of {sorted(VALID_EVENTS)}")
    if "format" in data and data["format"] not in VALID_FORMATS:
        raise HTTPException(422, f"format must be one of {sorted(VALID_FORMATS)}")
    for k, v in data.items():
        setattr(ep, k, v)
    db.commit()
    return ep_out(ep)


@router.delete("/{setting_id}")
def delete_setting(
    setting_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    ep = db.get(WebhookEndpoint, setting_id)
    if not ep or ep.user_id != user.id:
        raise HTTPException(404, "Webhook setting not found")
    db.delete(ep)
    db.commit()
    return {"ok": True}
