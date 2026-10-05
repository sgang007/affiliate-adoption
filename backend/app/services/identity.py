"""Affiliate identity.

Every user gets a stable hexadecimal affiliate id derived from their email
(e.g. vijetha@x.in → "das232edads"-style hash). It is the ?channel= value on
every referral link they share, across all products.
"""
import hashlib

from sqlalchemy.orm import Session


def affiliate_id_for_email(email: str, length: int = 12) -> str:
    return hashlib.sha256(email.lower().strip().encode()).hexdigest()[:length]


def assign_affiliate_id(db: Session, email: str) -> str:
    """Hash of the email, extended on the (astronomically rare) collision."""
    from ..models import User

    for length in (12, 16, 24, 32):
        candidate = affiliate_id_for_email(email, length)
        if not db.query(User).filter(User.affiliate_id == candidate).first():
            return candidate
    return hashlib.sha256(email.lower().encode()).hexdigest()[:32]
