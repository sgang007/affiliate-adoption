from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_db
from ..deps import require_admin
from ..models import (
    AffiliateLink,
    Commission,
    Invoice,
    Product,
    ProductAssignment,
    ReferredUser,
    User,
    gen_secret,
)
from ..schemas import AssignIn, ProductIn, ProductUpdate, UserCreateIn
from ..security import hash_password
from ..services.payout import close_payout_cycle

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)])
settings = get_settings()


def product_out(p: Product) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "description": p.description,
        "url": p.url,
        "currency": p.currency,
        "price": float(p.price or 0),
        "signup_commission": float(p.signup_commission or 0),
        "trial_commission": float(p.trial_commission or 0),
        "subscription_pct": float(p.subscription_pct or 0),
        "is_active": p.is_active,
        "webhook_url": f"{settings.portal_base_url}/api/webhooks/meridian/{p.id}",
        "webhook_secret": p.webhook_secret,
    }


@router.post("/products")
def create_product(
    body: ProductIn, db: Session = Depends(get_db), admin: User = Depends(require_admin)
):
    product = Product(**body.model_dump(), created_by=admin.id)
    db.add(product)
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
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(product, k, v)
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
def create_affiliate(body: UserCreateIn, db: Session = Depends(get_db)):
    email = body.email.lower().strip()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(409, "Email already registered")
    user = User(
        email=email,
        name=body.name,
        hashed_password=hash_password(body.password),
        role="affiliate",
    )
    db.add(user)
    db.flush()
    user.path = str(user.id)  # root of their own network
    db.commit()
    return {"id": user.id, "email": user.email, "name": user.name}


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
            "parent_id": u.parent_id,
            "depth": u.depth,
            "is_active": u.is_active,
            "total_earned": float(earnings.get(u.id, 0) or 0),
        }
        for u in users
    ]


@router.get("/invoices")
def list_invoices(status: str | None = None, db: Session = Depends(get_db)):
    q = db.query(Invoice).order_by(Invoice.id.desc())
    if status:
        q = q.filter(Invoice.status == status)
    return [
        {
            "id": i.id,
            "number": i.number,
            "user": {"id": i.user.id, "name": i.user.name, "email": i.user.email,
                     "payout_details": i.user.payout_details or {}},
            "period": i.period,
            "total_amount": float(i.total_amount or 0),
            "status": i.status,
            "submitted_at": i.submitted_at.isoformat() if i.submitted_at else None,
            "paid_at": i.paid_at.isoformat() if i.paid_at else None,
        }
        for i in q.all()
    ]


@router.post("/payouts/close-cycle")
def close_cycle(db: Session = Depends(get_db)):
    return close_payout_cycle(db)


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
        "pending_invoices": db.query(func.count(Invoice.id))
        .filter(Invoice.status == "submitted")
        .scalar(),
    }
