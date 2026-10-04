"""Monthly payout billing.

Affiliates generate a bill (invoice) for a month, submit it to the company,
and in each payout cycle the admin marks all submitted invoices as paid.
"""
from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from ..models import Commission, Invoice, User


def generate_invoice(db: Session, user: User, period: str) -> Invoice:
    invoice = (
        db.query(Invoice).filter(Invoice.user_id == user.id, Invoice.period == period).first()
    )
    if invoice and invoice.status != "draft":
        raise ValueError(f"Invoice for {period} is already {invoice.status}")

    pending = (
        db.query(Commission)
        .filter(
            Commission.user_id == user.id,
            Commission.period == period,
            Commission.status == "pending",
        )
        .all()
    )
    if not invoice and not pending:
        raise LookupError(f"No pending commissions for {period}")

    if not invoice:
        invoice = Invoice(
            number=f"INV-{period}-{user.id:05d}",
            user_id=user.id,
            period=period,
        )
        db.add(invoice)
        db.flush()

    for c in pending:
        c.status = "invoiced"
        c.invoice_id = invoice.id
    db.flush()

    total = (
        db.query(Commission)
        .filter(Commission.invoice_id == invoice.id)
        .with_entities(Commission.amount)
        .all()
    )
    invoice.total_amount = sum((t[0] for t in total), Decimal(0))
    db.commit()
    db.refresh(invoice)
    return invoice


def submit_invoice(db: Session, user: User, invoice_id: int) -> Invoice:
    invoice = db.get(Invoice, invoice_id)
    if not invoice or invoice.user_id != user.id:
        raise LookupError("Invoice not found")
    if invoice.status != "draft":
        raise ValueError(f"Invoice already {invoice.status}")
    invoice.status = "submitted"
    invoice.submitted_at = datetime.utcnow()
    db.commit()
    db.refresh(invoice)
    return invoice


def close_payout_cycle(db: Session) -> dict:
    """Admin action: pay out every submitted invoice in one cycle."""
    submitted = db.query(Invoice).filter(Invoice.status == "submitted").all()
    total = Decimal(0)
    for inv in submitted:
        inv.status = "paid"
        inv.paid_at = datetime.utcnow()
        total += Decimal(inv.total_amount or 0)
        db.query(Commission).filter(Commission.invoice_id == inv.id).update(
            {Commission.status: "paid"}
        )
    db.commit()
    return {"invoices_paid": len(submitted), "total_paid": float(total)}
