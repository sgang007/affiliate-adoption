import secrets
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
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
    # Hex hash of the email — this IS the ?channel= value in referral links.
    affiliate_id = Column(String(32), unique=True, index=True, nullable=False)
    parent_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    # Materialized path from the network root (an admin) to self, e.g. "1/4/9".
    path = Column(String(1024), default="", index=True)
    payout_details = Column(JSON, default=dict)  # {"upi": ..., "bank_account": ...}
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
    # Display/fallback monthly price (payouts come from incentive rules).
    price = Column(Numeric(12, 2), default=0)
    # % each ancestor (below the admin root) takes from the running pool.
    network_commission_pct = Column(Numeric(5, 2), default=20)
    # Admin-editable example message per event: {"visited": {...}, ...}
    event_templates = Column(JSON, default=dict)
    # Shared secret the product uses to sign inbound webhook payloads.
    webhook_secret = Column(String(64), default=gen_secret)
    is_active = Column(Boolean, default=True)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=utcnow)

    rules = relationship("IncentiveRule", backref="product", cascade="all, delete-orphan")


EVENT_KINDS = ["visited", "signed_up", "trial", "subscribed", "renewal"]


class IncentiveRule(Base):
    """Admin-defined payout rule for one event type of a product.

    type "flat"       → value is the payable amount in product currency.
    type "commission" → value is a %, applied to the payload field named in
                        `field` (dot path into the message, e.g.
                        "params.subscription").
    """

    __tablename__ = "incentive_rules"
    __table_args__ = (UniqueConstraint("product_id", "event", name="uq_rule_event"),)

    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    event = Column(String(20), nullable=False)  # visited | signed_up | trial | subscribed
    type = Column(String(20), default="flat")  # flat | commission
    value = Column(Numeric(12, 2), default=0)
    field = Column(String(255), nullable=True)  # payload dot-path for commission type
    is_active = Column(Boolean, default=True)
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
    """Per (product, user) tracking record. The channel is the owner's
    affiliate_id, so one channel identifies the affiliate on every product."""

    __tablename__ = "affiliate_links"
    __table_args__ = (
        UniqueConstraint("product_id", "user_id", name="uq_link"),
        Index("ix_link_channel", "product_id", "slug"),
    )

    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    slug = Column(String(64), index=True, nullable=False)  # == user.affiliate_id
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
    external_id = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True)
    status = Column(String(20), default="visited")
    subscription_amount = Column(Numeric(12, 2), nullable=True)
    meta = Column(JSON, default=dict)  # latest params: name, plan, device, …
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
    """Ledger entry. Every payable event appends immutable rows here; payout
    requests move them pending → requested → paid."""

    __tablename__ = "commissions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)  # earner
    # Affiliate whose channel converted; == user_id for the converter's own
    # share, different for network-override shares up the branch.
    source_user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    referred_user_id = Column(Integer, ForeignKey("referred_users.id"), nullable=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=True)
    event_type = Column(String(40), nullable=False)  # signed_up | trial | subscribed
    amount = Column(Numeric(12, 2), nullable=False)
    period = Column(String(7), index=True, nullable=False)  # YYYY-MM
    status = Column(String(20), default="pending")  # pending | requested | paid
    payout_request_id = Column(Integer, ForeignKey("payout_requests.id"), nullable=True)
    created_at = Column(DateTime, default=utcnow)

    user = relationship("User", foreign_keys=[user_id])
    source_user = relationship("User", foreign_keys=[source_user_id])
    product = relationship("Product")
    referred_user = relationship("ReferredUser")


class PayoutRequest(Base):
    __tablename__ = "payout_requests"

    id = Column(Integer, primary_key=True)
    number = Column(String(40), unique=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    bank_details = Column(JSON, default=dict)  # {"upi"| "bank_account","ifsc","account_name"}
    status = Column(String(20), default="requested")  # requested | approved | paid
    created_at = Column(DateTime, default=utcnow)
    approved_at = Column(DateTime, nullable=True)
    paid_at = Column(DateTime, nullable=True)

    user = relationship("User")


class WebhookEndpoint(Base):
    """Admin-configured outbound callback: forward processed funnel events to
    an external system (CRM, Slack bridge, data warehouse)."""

    __tablename__ = "webhook_endpoints"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)  # null = all
    event_type = Column(String(40), default="all")  # all | visited | signed_up | trial | subscribed
    url = Column(String(1024), nullable=False)
    format = Column(String(20), default="json")  # json | form
    secret = Column(String(64), default=gen_secret)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)

    user = relationship("User")
    product = relationship("Product")
