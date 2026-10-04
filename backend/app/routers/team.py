from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_db
from ..deps import get_current_user
from ..models import Commission, Invite, User
from ..schemas import InviteIn
from ..services.emailer import send_invite

router = APIRouter(prefix="/api/team", tags=["team"])
settings = get_settings()


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
    return {"id": invite.id, "email": email, "invite_url": invite_url}


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
                "their_direct_earnings": float(their_direct or 0),
                "earned_for_me": float(my_share or 0),
            }
        )
    return out
