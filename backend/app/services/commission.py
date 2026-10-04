"""Multi-level commission engine.

Rates (per product, admin-configurable, defaults per spec):
  visited           → Rs 0
  signed_up         → Rs 100
  trial_started     → Rs 300
  subscribed        → 20% of subscription amount, recurring monthly for the
                      lifetime of the subscription (renewal events).

Network cascade — company cost is constant (= base amount) no matter how
deep the network is:
  * The converting affiliate keeps 80% of the pool and passes 20% up to the
    affiliate who recruited them.
  * Each ancestor keeps 80% of what arrives and passes 20% further up.
  * The root affiliate keeps whatever reaches them.

Example (base Rs 100):  A alone → A:100.  A→B converts → B:80, A:20.
A→B→C converts → C:80, B:16, A:4. Totals always equal the base.
"""
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from ..models import (
    REFERRAL_STATUS_ORDER,
    AffiliateLink,
    Commission,
    Event,
    Product,
    ReferredUser,
    User,
)

KEEP_SHARE = Decimal("0.80")
TWO_PLACES = Decimal("0.01")

# Meridian event → referred-user status
EVENT_STATUS = {
    "visited": "visited",
    "signed_up": "signed_up",
    "trial_started": "trial",
    "subscribed": "subscribed",
    "subscription_renewed": "subscribed",
    "subscription_cancelled": "churned",
}

# Meridian event → commission type (None = no payout)
EVENT_COMMISSION = {
    "visited": None,
    "signed_up": "signup",
    "trial_started": "trial",
    "subscribed": "subscription",
    "subscription_renewed": "subscription_renewal",
    "subscription_cancelled": None,
}

ONE_TIME_TYPES = {"signup", "trial", "subscription"}


def q2(x: Decimal) -> Decimal:
    return x.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def current_period(dt: datetime | None = None) -> str:
    return (dt or datetime.utcnow()).strftime("%Y-%m")


def base_amount(event_type: str, product: Product, amount) -> Decimal:
    ctype = EVENT_COMMISSION.get(event_type)
    if ctype == "signup":
        return Decimal(product.signup_commission or 0)
    if ctype == "trial":
        return Decimal(product.trial_commission or 0)
    if ctype in ("subscription", "subscription_renewal"):
        sub = Decimal(str(amount)) if amount else Decimal(product.price or 0)
        return q2(sub * Decimal(product.subscription_pct or 0) / Decimal(100))
    return Decimal(0)


def ancestor_chain(db: Session, user: User) -> list[User]:
    """Users from the converting affiliate up to the network root."""
    ids = user.path_ids or [user.id]
    found = {u.id: u for u in db.query(User).filter(User.id.in_(ids)).all()}
    return [found[i] for i in reversed(ids) if i in found]


def distribute(
    db: Session,
    base: Decimal,
    converting_user: User,
    *,
    product_id: int,
    event_id: int | None,
    referred_user_id: int | None,
    commission_type: str,
    period: str,
) -> list[Commission]:
    chain = ancestor_chain(db, converting_user)
    pool = q2(base)
    out: list[Commission] = []
    for i, earner in enumerate(chain):
        is_last = i == len(chain) - 1
        share = pool if is_last else q2(pool * KEEP_SHARE)
        if share <= 0:
            break
        out.append(
            Commission(
                user_id=earner.id,
                source_user_id=converting_user.id,
                referred_user_id=referred_user_id,
                product_id=product_id,
                event_id=event_id,
                event_type=commission_type,
                amount=share,
                period=period,
            )
        )
        pool = q2(pool - share)
        if pool <= 0:
            break
    db.add_all(out)
    return out


def process_meridian_event(
    db: Session,
    product: Product,
    event_type: str,
    channel: str,
    external_id: str,
    email: str | None = None,
    amount=None,
    raw: dict | None = None,
) -> dict:
    """Ingest one webhook event from Meridian's product intelligence engine:
    update the referred user's funnel status, record the event, and create
    the commission cascade."""
    if event_type not in EVENT_STATUS:
        raise ValueError(f"Unknown event type '{event_type}'")

    link = (
        db.query(AffiliateLink)
        .filter(AffiliateLink.slug == channel, AffiliateLink.product_id == product.id)
        .first()
    )
    if not link:
        raise LookupError(f"No affiliate link for channel '{channel}' on this product")

    referred = (
        db.query(ReferredUser)
        .filter(ReferredUser.link_id == link.id, ReferredUser.external_id == str(external_id))
        .first()
    )
    if not referred:
        referred = ReferredUser(link_id=link.id, external_id=str(external_id), email=email)
        db.add(referred)
        db.flush()
    if email and not referred.email:
        referred.email = email

    new_status = EVENT_STATUS[event_type]
    if (
        new_status == "churned"
        or REFERRAL_STATUS_ORDER[new_status] > REFERRAL_STATUS_ORDER.get(referred.status, 0)
    ):
        referred.status = new_status
    if event_type in ("subscribed", "subscription_renewed") and amount:
        referred.subscription_amount = Decimal(str(amount))

    if event_type == "visited":
        link.visits = (link.visits or 0) + 1

    event = Event(link_id=link.id, referred_user_id=referred.id, type=event_type, payload=raw or {})
    db.add(event)
    db.flush()

    commissions: list[Commission] = []
    ctype = EVENT_COMMISSION[event_type]
    if ctype:
        period = current_period()
        duplicate = False
        if ctype in ONE_TIME_TYPES:
            duplicate = (
                db.query(Commission)
                .filter(
                    Commission.referred_user_id == referred.id,
                    Commission.event_type == ctype,
                )
                .first()
                is not None
            )
        elif ctype == "subscription_renewal":
            # One subscription payout per referred user per month, whether it
            # came from the initial "subscribed" event or an earlier renewal.
            duplicate = (
                db.query(Commission)
                .filter(
                    Commission.referred_user_id == referred.id,
                    Commission.event_type.in_(["subscription", "subscription_renewal"]),
                    Commission.period == period,
                )
                .first()
                is not None
            )
        base = base_amount(event_type, product, amount)
        if base > 0 and not duplicate:
            commissions = distribute(
                db,
                base,
                link.user,
                product_id=product.id,
                event_id=event.id,
                referred_user_id=referred.id,
                commission_type=ctype,
                period=period,
            )

    db.commit()
    return {
        "event_id": event.id,
        "link_id": link.id,
        "referred_user_id": referred.id,
        "status": referred.status,
        "commissions": [
            {"user_id": c.user_id, "amount": float(c.amount), "type": c.event_type}
            for c in commissions
        ],
    }
