"""Incentive-rule engine and top-down network distribution.

Payables are computed from admin-configured IncentiveRules per event:
  flat        → fixed amount
  commission  → value% of a payload field (dot path, e.g. "params.subscription")

Distribution ("network commission", per product, default 20%):
  * Admins earn nothing; they are the network root.
  * Walk the branch TOP-DOWN from the admin's direct child toward the
    converting affiliate. Every intermediate ancestor takes
    network_commission_pct of the running pool; the converter keeps the rest.
  * Company cost is always exactly the computed payable.

Example — A(admin) → B → C → D, D converts, flat ₹300, 20% network:
  B: 20% × 300 = 60 · C: 20% × 240 = 48 · D: remainder = 192.  Total 300.
"""
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from ..models import (
    REFERRAL_STATUS_ORDER,
    AffiliateLink,
    Commission,
    Event,
    IncentiveRule,
    Product,
    ReferredUser,
    User,
)

TWO_PLACES = Decimal("0.01")

# Tolerant inbound-event normalization → canonical event kind
EVENT_ALIASES = {
    "visited": "visited",
    "visit": "visited",
    "signed_up": "signed_up",
    "signed up": "signed_up",
    "signup": "signed_up",
    "trial": "trial",
    "trial_started": "trial",
    "subscribed": "subscribed",
    "subscription_renewed": "subscribed",
    "cancelled": "cancelled",
    "subscription_cancelled": "cancelled",
}

STATUS_FOR = {
    "visited": "visited",
    "signed_up": "signed_up",
    "trial": "trial",
    "subscribed": "subscribed",
    "cancelled": "churned",
}

# Paid at most once per referred user, ever.
ONE_TIME_EVENTS = {"signed_up", "trial"}
# Paid at most once per referred user per month → recurring income while the
# product keeps sending the event (stops on cancellation).
MONTHLY_EVENTS = {"subscribed"}


def q2(x: Decimal) -> Decimal:
    return x.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def current_period(dt: datetime | None = None) -> str:
    return (dt or datetime.utcnow()).strftime("%Y-%m")


def resolve_field(payload: dict, path: str):
    """Walk a dot path ("params.subscription") into the message payload."""
    node = payload
    for part in (path or "").split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def compute_payable(db: Session, product: Product, event: str, payload: dict) -> Decimal:
    rule = (
        db.query(IncentiveRule)
        .filter(
            IncentiveRule.product_id == product.id,
            IncentiveRule.event == event,
            IncentiveRule.is_active.is_(True),
        )
        .first()
    )
    if not rule or rule.value is None:
        return Decimal(0)
    if rule.type == "flat":
        return q2(Decimal(rule.value))
    basis = resolve_field(payload, rule.field or "params.subscription")
    if basis is None:
        basis = product.price or 0
    try:
        basis_dec = Decimal(str(basis))
    except Exception:
        return Decimal(0)
    return q2(basis_dec * Decimal(rule.value) / Decimal(100))


def branch_below_admin(db: Session, converter: User) -> list[User]:
    """Users on the root→converter path, excluding admins, ordered top-down."""
    ids = converter.path_ids or [converter.id]
    found = {u.id: u for u in db.query(User).filter(User.id.in_(ids)).all()}
    return [found[i] for i in ids if i in found and found[i].role != "admin"]


def distribute(
    db: Session,
    payable: Decimal,
    converter: User,
    product: Product,
    *,
    event_id: int | None,
    referred_user_id: int | None,
    event_type: str,
    period: str,
) -> list[Commission]:
    chain = branch_below_admin(db, converter)
    if not chain or payable <= 0:
        return []
    pct = Decimal(product.network_commission_pct or 0) / Decimal(100)
    pool = q2(payable)
    out: list[Commission] = []
    for i, earner in enumerate(chain):
        is_converter = i == len(chain) - 1
        share = pool if is_converter else q2(pool * pct)
        if share <= 0:
            continue
        out.append(
            Commission(
                user_id=earner.id,
                source_user_id=converter.id,
                referred_user_id=referred_user_id,
                product_id=product.id,
                event_id=event_id,
                event_type=event_type,
                amount=share,
                period=period,
            )
        )
        pool = q2(pool - share)
        if pool <= 0:
            break
    db.add_all(out)
    return out


def process_product_event(
    db: Session,
    product: Product,
    channel: str,
    event_raw: str,
    payload: dict,
) -> dict:
    """Ingest one webhook message {channel, event, params} from the product:
    update the referred user's funnel status, record the event, compute the
    payable from the incentive rules, and distribute it down the branch."""
    event = EVENT_ALIASES.get((event_raw or "").lower().strip())
    if not event:
        raise ValueError(f"Unknown event type '{event_raw}'")

    link = (
        db.query(AffiliateLink)
        .filter(AffiliateLink.slug == channel, AffiliateLink.product_id == product.id)
        .first()
    )
    if not link:
        raise LookupError(f"No affiliate with channel '{channel}' on this product")

    params = payload.get("params") or {}
    external_id = str(payload.get("user_id") or params.get("email") or f"anon-{channel}")

    referred = (
        db.query(ReferredUser)
        .filter(ReferredUser.link_id == link.id, ReferredUser.external_id == external_id)
        .first()
    )
    if not referred:
        referred = ReferredUser(link_id=link.id, external_id=external_id)
        db.add(referred)
        db.flush()
    if params.get("email"):
        referred.email = params["email"]
    if params:
        referred.meta = {**(referred.meta or {}), **params}

    new_status = STATUS_FOR[event]
    if (
        new_status == "churned"
        or REFERRAL_STATUS_ORDER[new_status] > REFERRAL_STATUS_ORDER.get(referred.status, 0)
    ):
        referred.status = new_status
    if event == "subscribed" and params.get("subscription"):
        try:
            referred.subscription_amount = Decimal(str(params["subscription"]))
        except Exception:
            pass

    if event == "visited":
        link.visits = (link.visits or 0) + 1

    db_event = Event(link_id=link.id, referred_user_id=referred.id, type=event, payload=payload)
    db.add(db_event)
    db.flush()

    commissions: list[Commission] = []
    period = current_period()
    if event in ONE_TIME_EVENTS or event in MONTHLY_EVENTS:
        dupe_q = db.query(Commission).filter(
            Commission.referred_user_id == referred.id,
            Commission.event_type == event,
        )
        if event in MONTHLY_EVENTS:
            dupe_q = dupe_q.filter(Commission.period == period)
        if dupe_q.first() is None:
            payable = compute_payable(db, product, event, payload)
            commissions = distribute(
                db,
                payable,
                link.user,
                product,
                event_id=db_event.id,
                referred_user_id=referred.id,
                event_type=event,
                period=period,
            )

    db.commit()
    return {
        "event": event,
        "event_id": db_event.id,
        "link_id": link.id,
        "referred_user_id": referred.id,
        "status": referred.status,
        "commissions": [
            {"user_id": c.user_id, "amount": float(c.amount), "type": c.event_type}
            for c in commissions
        ],
    }
