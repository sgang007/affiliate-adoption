from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import Commission, Invoice, User
from ..schemas import InvoiceGenerateIn
from ..services.commission import current_period
from ..services.payout import generate_invoice, submit_invoice

router = APIRouter(prefix="/api/invoices", tags=["invoices"])


def invoice_out(i: Invoice) -> dict:
    return {
        "id": i.id,
        "number": i.number,
        "period": i.period,
        "total_amount": float(i.total_amount or 0),
        "status": i.status,
        "created_at": i.created_at.isoformat(),
        "submitted_at": i.submitted_at.isoformat() if i.submitted_at else None,
        "paid_at": i.paid_at.isoformat() if i.paid_at else None,
    }


@router.get("")
def my_invoices(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    invoices = (
        db.query(Invoice).filter(Invoice.user_id == user.id).order_by(Invoice.id.desc()).all()
    )
    return [invoice_out(i) for i in invoices]


@router.post("/generate")
def generate(
    body: InvoiceGenerateIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    period = body.period or current_period()
    try:
        invoice = generate_invoice(db, user, period)
    except LookupError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(409, str(e))
    return invoice_out(invoice)


@router.post("/{invoice_id}/submit")
def submit(
    invoice_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    try:
        invoice = submit_invoice(db, user, invoice_id)
    except LookupError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(409, str(e))
    return invoice_out(invoice)


@router.get("/{invoice_id}")
def invoice_detail(
    invoice_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    invoice = db.get(Invoice, invoice_id)
    if not invoice or (invoice.user_id != user.id and user.role != "admin"):
        raise HTTPException(404, "Invoice not found")
    lines = db.query(Commission).filter(Commission.invoice_id == invoice.id).all()
    out = invoice_out(invoice)
    out["lines"] = [
        {
            "id": c.id,
            "event_type": c.event_type,
            "amount": float(c.amount),
            "product_id": c.product_id,
            "is_direct": c.source_user_id == c.user_id,
            "created_at": c.created_at.isoformat(),
        }
        for c in lines
    ]
    return out
