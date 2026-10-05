from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_db
from ..deps import require_admin
from ..models import (
    EVENT_KINDS,
    AffiliateLink,
    Commission,
    IncentiveRule,
    PayoutRequest,
    Product,
    ProductAssignment,
    ReferredUser,
    User,
    gen_secret,
)
from ..schemas import AssignIn, ProductIn, ProductUpdate, RulesIn, UserCreateIn
from ..security import hash_password
from ..services.emailer import send_payout_processed
from ..services.identity import assign_affiliate_id
from ..services.payout import approve_payout, mark_payout_paid
from ..services.templates import default_event_templates, integration_prompt

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)])
settings = get_settings()

DEFAULT_RULES = [
    {"event": "visited", "type": "flat", "value": 0, "field": None},
    {"event": "signed_up", "type": "flat", "value": 100, "field": None},
    {"event": "trial", "type": "flat", "value": 300, "field": None},
    {"event": "subscribed", "type": "commission", "value": 20, "field": "params.subscription"},
    {"event": "renewal", "type": "commission", "value": 20, "field": "params.subscription"},
]


def product_out(p: Product) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "description": p.description,
        "url": p.url,
        "currency": p.currency,
        "price": float(p.price or 0),
        "network_commission_pct": float(p.network_commission_pct or 0),
        "event_templates": p.event_templates or default_event_templates(),
        "rules": [
            {
                "id": r.id,
                "event": r.event,
                "type": r.type,
                "value": float(r.value or 0),
                "field": r.field,
                "is_active": r.is_active,
            }
            for r in sorted(p.rules, key=lambda r: EVENT_KINDS.index(r.event) if r.event in EVENT_KINDS else 99)
        ],
        "is_active": p.is_active,
        "webhook_url": f"{settings.portal_base_url}/api/webhooks/meridian/{p.id}",
        "webhook_secret": p.webhook_secret,
    }


@router.post("/products")
def create_product(
    body: ProductIn, db: Session = Depends(get_db), admin: User = Depends(require_admin)
):
    product = Product(
        **body.model_dump(),
        event_templates=default_event_templates(),
        created_by=admin.id,
    )
    db.add(product)
    db.flush()
    # Sensible starter rules — fully editable from the console.
    for r in DEFAULT_RULES:
        db.add(IncentiveRule(product_id=product.id, **r))
    # The creating admin is the root of this product's network.
    db.add(ProductAssignment(product_id=product.id, user_id=admin.id))
    db.commit()
    db.refresh(product)
    return product_out(product)


@router.get("/products")
def list_products(db: Session = Depends(get_db)):
    return [product_out(p) for p in db.query(Product).order_by(Product.id.desc()).all()]


@router.patch("/products/{product_id}")
def update_product(product_id: int, body: ProductUpdate, db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(404, "Product not found")
    data = body.model_dump(exclude_none=True)
    templates = data.pop("event_templates", None)
    if templates is not None:
        unknown = set(templates) - set(EVENT_KINDS)
        if unknown:
            raise HTTPException(422, f"Unknown template events: {sorted(unknown)}")
        product.event_templates = {**(product.event_templates or {}), **templates}
    for k, v in data.items():
        setattr(product, k, v)
    db.commit()
    db.refresh(product)
    return product_out(product)


@router.put("/products/{product_id}/rules")
def upsert_rules(product_id: int, body: RulesIn, db: Session = Depends(get_db)):
    """Save the product's incentive rules in one atomic call."""
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(404, "Product not found")
    for r in body.rules:
        if r.event not in EVENT_KINDS:
            raise HTTPException(422, f"event must be one of {EVENT_KINDS}")
        if r.type not in ("flat", "commission"):
            raise HTTPException(422, "type must be 'flat' or 'commission'")
    for r in body.rules:
        rule = (
            db.query(IncentiveRule)
            .filter_by(product_id=product_id, event=r.event)
            .first()
        )
        if rule:
            rule.type, rule.value, rule.field = r.type, r.value, r.field
            rule.is_active = True
        else:
            db.add(IncentiveRule(product_id=product_id, **r.model_dump()))
    db.commit()
    db.refresh(product)
    return product_out(product)


@router.post("/products/{product_id}/rotate-secret")
def rotate_secret(product_id: int, db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(404, "Product not found")
    product.webhook_secret = gen_secret()
    db.commit()
    return product_out(product)


@router.get("/products/{product_id}/integration-prompt")
def get_integration_prompt(product_id: int, db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(404, "Product not found")
    url = f"{settings.portal_base_url}/api/webhooks/meridian/{product.id}"
    return {"prompt": integration_prompt(product, url)}


@router.post("/products/{product_id}/assign")
def assign_product(product_id: int, body: AssignIn, db: Session = Depends(get_db)):
    if not db.get(Product, product_id):
        raise HTTPException(404, "Product not found")
    if not db.get(User, body.user_id):
        raise HTTPException(404, "User not found")
    existing = (
        db.query(ProductAssignment)
        .filter_by(product_id=product_id, user_id=body.user_id)
        .first()
    )
    if existing:
        return {"ok": True, "already_assigned": True}
    db.add(ProductAssignment(product_id=product_id, user_id=body.user_id))
    db.commit()
    return {"ok": True}


@router.post("/users")
def create_affiliate(
    body: UserCreateIn, db: Session = Depends(get_db), admin: User = Depends(require_admin)
):
    """Create an affiliate directly under this admin (the network root)."""
    email = body.email.lower().strip()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(409, "Email already registered")
    user = User(
        email=email,
        name=body.name,
        hashed_password=hash_password(body.password),
        role="affiliate",
        parent_id=admin.id,
        affiliate_id=assign_affiliate_id(db, email),
    )
    db.add(user)
    db.flush()
    user.path = f"{admin.path}/{user.id}"
    # Inherit the admin's product portfolio.
    for pa in db.query(ProductAssignment).filter(ProductAssignment.user_id == admin.id).all():
        db.add(ProductAssignment(product_id=pa.product_id, user_id=user.id))
    db.commit()
    return {"id": user.id, "email": user.email, "name": user.name, "affiliate_id": user.affiliate_id}


@router.get("/users")
def list_users(db: Session = Depends(get_db)):
    users = db.query(User).order_by(User.id).all()
    earnings = dict(
        db.query(Commission.user_id, func.sum(Commission.amount)).group_by(Commission.user_id).all()
    )
    return [
        {
            "id": u.id,
            "email": u.email,
            "name": u.name,
            "role": u.role,
            "affiliate_id": u.affiliate_id,
            "parent_id": u.parent_id,
            "depth": u.depth,
            "is_active": u.is_active,
            "total_earned": float(earnings.get(u.id, 0) or 0),
        }
        for u in users
    ]


@router.get("/payout-requests")
def list_payout_requests(status: str | None = None, db: Session = Depends(get_db)):
    q = db.query(PayoutRequest).order_by(PayoutRequest.id.desc())
    if status:
        q = q.filter(PayoutRequest.status == status)
    return [
        {
            "id": r.id,
            "number": r.number,
            "user": {"id": r.user.id, "name": r.user.name, "email": r.user.email},
            "amount": float(r.amount or 0),
            "bank_details": r.bank_details or {},
            "status": r.status,
            "created_at": r.created_at.isoformat(),
            "approved_at": r.approved_at.isoformat() if r.approved_at else None,
            "paid_at": r.paid_at.isoformat() if r.paid_at else None,
        }
        for r in q.all()
    ]


@router.post("/payout-requests/{request_id}/approve")
def approve_request(request_id: int, db: Session = Depends(get_db)):
    try:
        req = approve_payout(db, request_id)
    except LookupError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(409, str(e))
    return {"id": req.id, "status": req.status}


@router.post("/payout-requests/{request_id}/mark-paid")
def pay_request(request_id: int, background: BackgroundTasks, db: Session = Depends(get_db)):
    try:
        req = mark_payout_paid(db, request_id)
    except LookupError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(409, str(e))
    background.add_task(
        send_payout_processed, req.user.email, req.user.name, float(req.amount), req.number
    )
    return {"id": req.id, "status": req.status}


@router.get("/overview")
def overview(db: Session = Depends(get_db)):
    total_commissions = db.query(func.coalesce(func.sum(Commission.amount), 0)).scalar()
    by_status = dict(
        db.query(ReferredUser.status, func.count(ReferredUser.id))
        .group_by(ReferredUser.status)
        .all()
    )
    return {
        "products": db.query(func.count(Product.id)).scalar(),
        "affiliates": db.query(func.count(User.id)).filter(User.role == "affiliate").scalar(),
        "links": db.query(func.count(AffiliateLink.id)).scalar(),
        "referred_users": by_status,
        "total_commissions": float(total_commissions or 0),
        "pending_payout_requests": db.query(func.count(PayoutRequest.id))
        .filter(PayoutRequest.status.in_(["requested", "approved"]))
        .scalar(),
    }
