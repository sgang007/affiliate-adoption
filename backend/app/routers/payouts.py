from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import Commission, PayoutRequest, Product, User
from ..schemas import PayoutRequestIn
from ..services.payout import create_payout_request

router = APIRouter(prefix="/api/payouts", tags=["payouts"])


@router.get("")
def my_payouts(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    def total(status: str | None = None):
        q = db.query(func.coalesce(func.sum(Commission.amount), 0)).filter(
            Commission.user_id == user.id
        )
        if status:
            q = q.filter(Commission.status == status)
        return float(q.scalar() or 0)

    requests = (
        db.query(PayoutRequest)
        .filter(PayoutRequest.user_id == user.id)
        .order_by(PayoutRequest.id.desc())
        .all()
    )
    return {
        "balance_pending": total("pending"),
        "in_review": total("requested"),
        "total_paid": total("paid"),
        "total_earned": total(),
        "saved_details": user.payout_details or {},
        "requests": [
            {
                "id": r.id,
                "number": r.number,
                "amount": float(r.amount or 0),
                "status": r.status,
                "created_at": r.created_at.isoformat(),
                "paid_at": r.paid_at.isoformat() if r.paid_at else None,
            }
            for r in requests
        ],
    }


@router.get("/ledger")
def my_ledger(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    entries = (
        db.query(Commission)
        .filter(Commission.user_id == user.id)
        .order_by(Commission.id.desc())
        .limit(200)
        .all()
    )
    products = {p.id: p.name for p in db.query(Product).all()}
    return [
        {
            "id": c.id,
            "event_type": c.event_type,
            "amount": float(c.amount),
            "product": products.get(c.product_id, "?"),
            "period": c.period,
            "status": c.status,
            "is_direct": c.source_user_id == c.user_id,
            "created_at": c.created_at.isoformat(),
        }
        for c in entries
    ]


@router.post("/request")
def request_payout(
    body: PayoutRequestIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user.role == "admin":
        raise HTTPException(403, "Admins do not receive commissions")
    details = {k: v for k, v in body.model_dump().items() if v}
    try:
        req = create_payout_request(db, user, details)
    except LookupError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(422, str(e))
    return {
        "id": req.id,
        "number": req.number,
        "amount": float(req.amount),
        "status": req.status,
    }
