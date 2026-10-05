from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import (
    EVENT_KINDS,
    AffiliateLink,
    Commission,
    Product,
    ProductAssignment,
    ReferredUser,
    User,
)

router = APIRouter(prefix="/api/products", tags=["products"])


def _assigned_product(db: Session, user: User, product_id: int) -> Product:
    assignment = (
        db.query(ProductAssignment)
        .filter_by(product_id=product_id, user_id=user.id)
        .first()
    )
    if not assignment and user.role != "admin":
        raise HTTPException(404, "Product not found or not assigned to you")
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(404, "Product not found")
    return product


def _get_or_create_link(db: Session, user: User, product: Product) -> AffiliateLink:
    link = (
        db.query(AffiliateLink).filter_by(product_id=product.id, user_id=user.id).first()
    )
    if not link:
        link = AffiliateLink(product_id=product.id, user_id=user.id, slug=user.affiliate_id)
        db.add(link)
        db.commit()
        db.refresh(link)
    return link


def _link_stats(db: Session, link: AffiliateLink) -> dict:
    counts = dict(
        db.query(ReferredUser.status, func.count(ReferredUser.id))
        .filter(ReferredUser.link_id == link.id)
        .group_by(ReferredUser.status)
        .all()
    )
    earned = (
        db.query(func.coalesce(func.sum(Commission.amount), 0))
        .filter(
            Commission.user_id == link.user_id,
            Commission.source_user_id == link.user_id,
            Commission.product_id == link.product_id,
        )
        .scalar()
    )
    return {
        "visits": link.visits or 0,
        "signed_up": counts.get("signed_up", 0) + counts.get("trial", 0) + counts.get("subscribed", 0),
        "trial": counts.get("trial", 0),
        "subscribed": counts.get("subscribed", 0),
        "churned": counts.get("churned", 0),
        "direct_earnings": float(earned or 0),
    }


def _link_out(link: AffiliateLink, product: Product) -> dict:
    sep = "&" if "?" in product.url else "?"
    return {
        "id": link.id,
        "slug": link.slug,
        "referral_url": f"{product.url}{sep}channel={link.slug}",
    }


def _rules_out(product: Product) -> list[dict]:
    return [
        {"event": r.event, "type": r.type, "value": float(r.value or 0), "field": r.field}
        for r in sorted(
            product.rules, key=lambda r: EVENT_KINDS.index(r.event) if r.event in EVENT_KINDS else 99
        )
        if r.is_active
    ]


def _product_base(p: Product) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "description": p.description,
        "url": p.url,
        "currency": p.currency,
        "price": float(p.price or 0),
        "network_commission_pct": float(p.network_commission_pct or 0),
        "rules": _rules_out(p),
    }


@router.get("")
def my_products(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    assignments = (
        db.query(ProductAssignment).filter(ProductAssignment.user_id == user.id).all()
    )
    out = []
    for a in assignments:
        p = a.product
        # Referral links exist from the moment a product is assigned — the
        # dashboard shows them without any extra step.
        link = _get_or_create_link(db, user, p)
        item = _product_base(p)
        item["link"] = _link_out(link, p)
        item["stats"] = _link_stats(db, link)
        out.append(item)
    return out


@router.get("/{product_id}")
def product_detail(
    product_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    product = _assigned_product(db, user, product_id)
    link = _get_or_create_link(db, user, product)
    item = _product_base(product)
    item["link"] = _link_out(link, product)
    item["stats"] = _link_stats(db, link)
    return item


@router.post("/{product_id}/link")
def generate_link(
    product_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    product = _assigned_product(db, user, product_id)
    link = _get_or_create_link(db, user, product)
    return _link_out(link, product)


@router.get("/{product_id}/referrals")
def product_referrals(
    product_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    product = _assigned_product(db, user, product_id)
    link = _get_or_create_link(db, user, product)
    referred = (
        db.query(ReferredUser)
        .filter(ReferredUser.link_id == link.id)
        .order_by(ReferredUser.updated_at.desc())
        .all()
    )
    earned_by_ru = dict(
        db.query(Commission.referred_user_id, func.sum(Commission.amount))
        .filter(Commission.user_id == user.id, Commission.source_user_id == user.id)
        .group_by(Commission.referred_user_id)
        .all()
    )
    return [
        {
            "id": r.id,
            "external_id": r.external_id,
            "email": r.email,
            "name": (r.meta or {}).get("name"),
            "status": r.status,
            "subscription_amount": float(r.subscription_amount or 0),
            "meta": r.meta or {},
            "earned": float(earned_by_ru.get(r.id, 0) or 0),
            "first_seen": r.created_at.isoformat(),
            "last_update": r.updated_at.isoformat() if r.updated_at else None,
        }
        for r in referred
    ]
