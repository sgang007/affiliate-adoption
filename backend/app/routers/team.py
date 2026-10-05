from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_db
from ..deps import get_current_user
from ..models import AffiliateLink, Commission, Invite, ReferredUser, User
from ..schemas import InviteIn
from ..services.emailer import email_configured, send_invite

router = APIRouter(prefix="/api/team", tags=["team"])
settings = get_settings()


def _funnel_stats(db: Session, user_id: int) -> dict:
    """A member's own acquisition numbers across all their links."""
    link_ids = [
        l.id for l in db.query(AffiliateLink).filter(AffiliateLink.user_id == user_id).all()
    ]
    stats = {"visits": 0, "signed_up": 0, "trial": 0, "subscribed": 0}
    if not link_ids:
        return stats
    stats["visits"] = int(
        db.query(func.coalesce(func.sum(AffiliateLink.visits), 0))
        .filter(AffiliateLink.id.in_(link_ids))
        .scalar()
        or 0
    )
    rows = (
        db.query(ReferredUser.status, func.count(ReferredUser.id))
        .filter(ReferredUser.link_id.in_(link_ids))
        .group_by(ReferredUser.status)
        .all()
    )
    counts = dict(rows)
    stats["signed_up"] = (
        counts.get("signed_up", 0) + counts.get("trial", 0) + counts.get("subscribed", 0)
    )
    stats["trial"] = counts.get("trial", 0)
    stats["subscribed"] = counts.get("subscribed", 0)
    return stats


@router.post("/invite")
def invite_affiliate(
    body: InviteIn,
    background: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    email = body.email.lower().strip()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(409, "This email already has an account")
    invite = Invite(email=email, inviter_id=user.id)
    db.add(invite)
    db.commit()
    db.refresh(invite)
    invite_url = f"{settings.frontend_url}/join/{invite.token}"
    background.add_task(send_invite, email, user.name, invite_url)
    return {
        "id": invite.id,
        "email": email,
        "invite_url": invite_url,
        "email_sent": email_configured(),
    }


@router.get("/invites")
def list_invites(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    invites = (
        db.query(Invite).filter(Invite.inviter_id == user.id).order_by(Invite.id.desc()).all()
    )
    return [
        {
            "id": i.id,
            "email": i.email,
            "accepted": i.accepted,
            "invite_url": f"{settings.frontend_url}/join/{i.token}",
            "created_at": i.created_at.isoformat(),
        }
        for i in invites
    ]


@router.get("")
def my_team(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    children = db.query(User).filter(User.parent_id == user.id).all()
    out = []
    for c in children:
        subtree_ids = [
            u.id for u in db.query(User.id, User.path).filter(User.path.like(f"{c.path}%")).all()
        ]
        my_share = (
            db.query(func.coalesce(func.sum(Commission.amount), 0))
            .filter(Commission.user_id == user.id, Commission.source_user_id.in_(subtree_ids))
            .scalar()
        )
        their_direct = (
            db.query(func.coalesce(func.sum(Commission.amount), 0))
            .filter(Commission.user_id == c.id, Commission.source_user_id == c.id)
            .scalar()
        )
        out.append(
            {
                "id": c.id,
                "name": c.name,
                "email": c.email,
                "joined": c.created_at.isoformat(),
                "subtree_size": len(subtree_ids),
                "stats": _funnel_stats(db, c.id),
                "their_direct_earnings": float(their_direct or 0),
                "earned_for_me": float(my_share or 0),
            }
        )
    return out
