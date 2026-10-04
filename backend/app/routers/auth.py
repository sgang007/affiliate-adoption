from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import Invite, ProductAssignment, User
from ..schemas import AcceptInviteIn, LoginIn, PayoutDetailsIn
from ..security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


def user_out(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "role": user.role,
        "parent_id": user.parent_id,
        "depth": user.depth,
        "payout_details": user.payout_details or {},
    }


@router.post("/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email.lower().strip()).first()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(401, "Invalid email or password")
    if not user.is_active:
        raise HTTPException(403, "Account disabled")
    return {"token": create_access_token(user.id, user.role), "user": user_out(user)}


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return user_out(user)


@router.put("/me/payout-details")
def update_payout_details(
    body: PayoutDetailsIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user.payout_details = {k: v for k, v in body.model_dump().items() if v}
    db.commit()
    return user_out(user)


@router.get("/invite/{token}")
def invite_info(token: str, db: Session = Depends(get_db)):
    invite = db.query(Invite).filter(Invite.token == token, Invite.accepted.is_(False)).first()
    if not invite:
        raise HTTPException(404, "Invite not found or already used")
    return {"email": invite.email, "inviter_name": invite.inviter.name}


@router.post("/accept-invite")
def accept_invite(body: AcceptInviteIn, db: Session = Depends(get_db)):
    invite = (
        db.query(Invite).filter(Invite.token == body.token, Invite.accepted.is_(False)).first()
    )
    if not invite:
        raise HTTPException(404, "Invite not found or already used")
    email = invite.email.lower().strip()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(409, "An account with this email already exists")

    parent = invite.inviter
    user = User(
        email=email,
        name=body.name,
        hashed_password=hash_password(body.password),
        role="affiliate",
        parent_id=parent.id,
    )
    db.add(user)
    db.flush()
    user.path = f"{parent.path}/{user.id}" if parent.path else str(user.id)

    # Sub-affiliates inherit access to every product their parent promotes.
    parent_assignments = (
        db.query(ProductAssignment).filter(ProductAssignment.user_id == parent.id).all()
    )
    for pa in parent_assignments:
        db.add(ProductAssignment(product_id=pa.product_id, user_id=user.id))

    invite.accepted = True
    db.commit()
    return {"token": create_access_token(user.id, user.role), "user": user_out(user)}
