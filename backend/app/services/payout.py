"""Ledger and payout requests.

Commissions accumulate as pending ledger entries. An affiliate requests a
payout by submitting bank details; that freezes their pending balance into a
PayoutRequest (pending → requested). The admin approves it, pays manually,
and marks it paid — which emails the affiliate.
"""
from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from ..models import Commission, PayoutRequest, User


def pending_balance(db: Session, user: User) -> Decimal:
    from sqlalchemy import func

    total = (
        db.query(func.coalesce(func.sum(Commission.amount), 0))
        .filter(Commission.user_id == user.id, Commission.status == "pending")
        .scalar()
    )
    return Decimal(total or 0)


def create_payout_request(db: Session, user: User, bank_details: dict) -> PayoutRequest:
    pending = (
        db.query(Commission)
        .filter(Commission.user_id == user.id, Commission.status == "pending")
        .all()
    )
    amount = sum((Decimal(c.amount) for c in pending), Decimal(0))
    if amount <= 0:
        raise LookupError("No pending earnings to pay out")
    if not any(bank_details.get(k) for k in ("upi", "bank_account")):
        raise ValueError("Provide a UPI id or bank account for the payout")

    req = PayoutRequest(
        number=f"PAYOUT-{datetime.utcnow().strftime('%Y%m%d')}-{user.id:05d}-{len(pending):03d}",
        user_id=user.id,
        amount=amount,
        bank_details=bank_details,
    )
    db.add(req)
    db.flush()
    for c in pending:
        c.status = "requested"
        c.payout_request_id = req.id
    # Remember the details for next time.
    user.payout_details = bank_details
    db.commit()
    db.refresh(req)
    return req


def approve_payout(db: Session, request_id: int) -> PayoutRequest:
    req = db.get(PayoutRequest, request_id)
    if not req:
        raise LookupError("Payout request not found")
    if req.status != "requested":
        raise ValueError(f"Request is already {req.status}")
    req.status = "approved"
    req.approved_at = datetime.utcnow()
    db.commit()
    db.refresh(req)
    return req


def mark_payout_paid(db: Session, request_id: int) -> PayoutRequest:
    req = db.get(PayoutRequest, request_id)
    if not req:
        raise LookupError("Payout request not found")
    if req.status not in ("requested", "approved"):
        raise ValueError(f"Request is already {req.status}")
    req.status = "paid"
    req.paid_at = datetime.utcnow()
    db.query(Commission).filter(Commission.payout_request_id == req.id).update(
        {Commission.status: "paid"}
    )
    db.commit()
    db.refresh(req)
    return req
