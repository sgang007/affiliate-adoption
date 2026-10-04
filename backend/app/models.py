import secrets
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from .database import Base


def utcnow():
    return datetime.utcnow()


def gen_secret():
    return secrets.token_hex(16)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(20), default="affiliate", nullable=False)  # admin | affiliate
    parent_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    # Materialized path from root to self, e.g. "3/7/12". Encodes the full
    # ancestor chain used for commission cascades and referral slugs.
    path = Column(String(1024), default="", index=True)
    payout_details = Column(JSON, default=dict)  # {"upi": ..., "bank": ...}
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)

    parent = relationship("User", remote_side=[id], backref="children")

    @property
    def path_ids(self) -> list[int]:
        return [int(p) for p in self.path.split("/") if p]

    @property
    def depth(self) -> int:
        return max(len(self.path_ids) - 1, 0)


class Invite(Base):
    __tablename__ = "invites"

    id = Column(Integer, primary_key=True)
    email = Column(String(255), nullable=False)
    token = Column(String(64), unique=True, index=True, default=gen_secret)
    inviter_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    accepted = Column(Boolean, default=False)
    created_at = Column(DateTime, default=utcnow)

    inviter = relationship("User")


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, default="")
    url = Column(String(1024), nullable=False)
    currency = Column(String(8), default="INR")
    # Monthly subscription price (fallback when a webhook omits the amount).
    price = Column(Numeric(12, 2), default=0)
    signup_commission = Column(Numeric(12, 2), default=100)
    trial_commission = Column(Numeric(12, 2), default=300)
    subscription_pct = Column(Numeric(5, 2), default=20)
    # Shared secret Meridian uses to sign inbound webhook payloads.
    webhook_secret = Column(String(64), default=gen_secret)
    is_active = Column(Boolean, default=True)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=utcnow)


class ProductAssignment(Base):
    __tablename__ = "product_assignments"
    __table_args__ = (UniqueConstraint("product_id", "user_id", name="uq_assignment"),)

    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=utcnow)

    product = relationship("Product")
    user = relationship("User")


class AffiliateLink(Base):
    __tablename__ = "affiliate_links"
    __table_args__ = (UniqueConstraint("product_id", "user_id", name="uq_link"),)

    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    # channel slug: base36-encoded ancestor chain + random suffix,
    # e.g. "1-4-9~k3f7" → encodes the affiliate and all parents.
    slug = Column(String(255), unique=True, index=True, nullable=False)
    visits = Column(Integer, default=0)
    created_at = Column(DateTime, default=utcnow)

    product = relationship("Product")
    user = relationship("User")


REFERRAL_STATUS_ORDER = {"visited": 0, "signed_up": 1, "trial": 2, "subscribed": 3, "churned": 4}


class ReferredUser(Base):
    __tablename__ = "referred_users"
    __table_args__ = (UniqueConstraint("link_id", "external_id", name="uq_referred"),)

    id = Column(Integer, primary_key=True)
    link_id = Column(Integer, ForeignKey("affiliate_links.id"), nullable=False)
    external_id = Column(String(255), nullable=False)  # Meridian user id
    email = Column(String(255), nullable=True)
    status = Column(String(20), default="visited")
    subscription_amount = Column(Numeric(12, 2), nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    link = relationship("AffiliateLink")


class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True)
    link_id = Column(Integer, ForeignKey("affiliate_links.id"), nullable=False)
    referred_user_id = Column(Integer, ForeignKey("referred_users.id"), nullable=True)
    type = Column(String(40), nullable=False)
    payload = Column(JSON, default=dict)
    created_at = Column(DateTime, default=utcnow)


class Commission(Base):
    __tablename__ = "commissions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)  # earner
    # Affiliate whose link converted. When == user_id it's a direct
    # commission; otherwise it's a network override earned from a descendant.
    source_user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    referred_user_id = Column(Integer, ForeignKey("referred_users.id"), nullable=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=True)
    event_type = Column(String(40), nullable=False)  # signup | trial | subscription | subscription_renewal
    amount = Column(Numeric(12, 2), nullable=False)
    period = Column(String(7), index=True, nullable=False)  # YYYY-MM
    status = Column(String(20), default="pending")  # pending | invoiced | paid
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=True)
    created_at = Column(DateTime, default=utcnow)

    user = relationship("User", foreign_keys=[user_id])
    source_user = relationship("User", foreign_keys=[source_user_id])
    product = relationship("Product")
    referred_user = relationship("ReferredUser")


class Invoice(Base):
    __tablename__ = "invoices"
    __table_args__ = (UniqueConstraint("user_id", "period", name="uq_invoice_period"),)

    id = Column(Integer, primary_key=True)
    number = Column(String(40), unique=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    period = Column(String(7), nullable=False)
    total_amount = Column(Numeric(12, 2), default=0)
    status = Column(String(20), default="draft")  # draft | submitted | paid
    created_at = Column(DateTime, default=utcnow)
    submitted_at = Column(DateTime, nullable=True)
    paid_at = Column(DateTime, nullable=True)

    user = relationship("User")


class WebhookEndpoint(Base):
    """Outbound callback an affiliate (or admin, per product) configures to
    receive visited / signed_up / trial / subscribed events."""

    __tablename__ = "webhook_endpoints"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)  # null = all products
    event_type = Column(String(40), default="all")  # all | visited | signed_up | trial | subscribed
    url = Column(String(1024), nullable=False)
    format = Column(String(20), default="json")  # json | form
    secret = Column(String(64), default=gen_secret)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)

    user = relationship("User")
    product = relationship("Product")
