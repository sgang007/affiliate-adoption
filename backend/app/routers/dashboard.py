from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import AffiliateLink, Commission, ReferredUser, User
from ..services.commission import current_period

router = APIRouter(prefix="/api", tags=["dashboard"])


def _descendants(db: Session, user: User) -> list[User]:
    return (
        db.query(User)
        .filter(User.path.like(f"{user.path}/%"))
        .order_by(User.path)
        .all()
    )


@router.get("/dashboard")
def dashboard(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    period = current_period()

    def sum_where(*criteria):
        return float(
            db.query(func.coalesce(func.sum(Commission.amount), 0))
            .filter(Commission.user_id == user.id, *criteria)
            .scalar()
            or 0
        )

    total = sum_where()
    direct = sum_where(Commission.source_user_id == user.id)
    this_month = sum_where(Commission.period == period)
    pending = sum_where(Commission.status == "pending")
    paid = sum_where(Commission.status == "paid")

    link_ids = [
        l.id for l in db.query(AffiliateLink).filter(AffiliateLink.user_id == user.id).all()
    ]
    counts = {"visited": 0, "signed_up": 0, "trial": 0, "subscribed": 0, "churned": 0}
    visits = 0
    if link_ids:
        rows = (
            db.query(ReferredUser.status, func.count(ReferredUser.id))
            .filter(ReferredUser.link_id.in_(link_ids))
            .group_by(ReferredUser.status)
            .all()
        )
        for status, n in rows:
            counts[status] = n
        visits = (
            db.query(func.coalesce(func.sum(AffiliateLink.visits), 0))
            .filter(AffiliateLink.id.in_(link_ids))
            .scalar()
            or 0
        )

    team_size = len(_descendants(db, user))
    return {
        "earnings": {
            "total": total,
            "direct": direct,
            "network": round(total - direct, 2),
            "this_month": this_month,
            "pending": pending,
            "paid": paid,
        },
        "funnel": {
            "visits": int(visits),
            "signed_up": counts["signed_up"] + counts["trial"] + counts["subscribed"],
            "trial": counts["trial"],
            "subscribed": counts["subscribed"],
            "churned": counts["churned"],
        },
        "network_size": team_size,
        "period": period,
    }


@router.get("/network")
def network(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """The affiliate's network tree with, per member: their own direct
    earnings and how much of MY earnings came from them (override share)."""
    descendants = _descendants(db, user)
    all_ids = [user.id] + [d.id for d in descendants]

    direct_earnings = dict(
        db.query(Commission.user_id, func.sum(Commission.amount))
        .filter(Commission.user_id.in_(all_ids), Commission.source_user_id == Commission.user_id)
        .group_by(Commission.user_id)
        .all()
    )
    my_share_from = dict(
        db.query(Commission.source_user_id, func.sum(Commission.amount))
        .filter(Commission.user_id == user.id)
        .group_by(Commission.source_user_id)
        .all()
    )

    nodes = {user.id: _node(user, user, direct_earnings, my_share_from)}
    for d in descendants:
        nodes[d.id] = _node(d, user, direct_earnings, my_share_from)
    for d in descendants:
        parent = nodes.get(d.parent_id)
        if parent:
            parent["children"].append(nodes[d.id])

    members = [nodes[d.id] for d in descendants]
    return {
        "tree": nodes[user.id],
        "members": [{k: v for k, v in m.items() if k != "children"} for m in members],
        "network_earnings": round(
            sum(float(v or 0) for k, v in my_share_from.items() if k != user.id), 2
        ),
    }


def _node(u: User, me: User, direct_earnings: dict, my_share_from: dict) -> dict:
    return {
        "id": u.id,
        "name": u.name,
        "email": u.email,
        "depth": max(len(u.path_ids) - len(me.path_ids), 0),
        "direct_earnings": float(direct_earnings.get(u.id, 0) or 0),
        "earned_for_me": float(my_share_from.get(u.id, 0) or 0) if u.id != me.id else 0.0,
        "children": [],
    }
