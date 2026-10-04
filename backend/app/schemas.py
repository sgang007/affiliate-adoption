from pydantic import BaseModel


class LoginIn(BaseModel):
    email: str
    password: str


class AcceptInviteIn(BaseModel):
    token: str
    name: str
    password: str


class ProductIn(BaseModel):
    name: str
    description: str = ""
    url: str
    currency: str = "INR"
    price: float = 0
    signup_commission: float = 100
    trial_commission: float = 300
    subscription_pct: float = 20


class ProductUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    url: str | None = None
    price: float | None = None
    signup_commission: float | None = None
    trial_commission: float | None = None
    subscription_pct: float | None = None
    is_active: bool | None = None


class UserCreateIn(BaseModel):
    email: str
    name: str
    password: str


class AssignIn(BaseModel):
    user_id: int


class InviteIn(BaseModel):
    email: str


class InvoiceGenerateIn(BaseModel):
    period: str | None = None  # YYYY-MM, defaults to current month


class WebhookSettingIn(BaseModel):
    url: str
    event_type: str = "all"  # all | visited | signed_up | trial | subscribed
    format: str = "json"  # json | form
    product_id: int | None = None


class WebhookSettingUpdate(BaseModel):
    url: str | None = None
    event_type: str | None = None
    format: str | None = None
    is_active: bool | None = None


class PayoutDetailsIn(BaseModel):
    upi: str | None = None
    bank_account: str | None = None
    ifsc: str | None = None
    account_name: str | None = None


class MeridianEvent(BaseModel):
    """Inbound payload from Meridian's product intelligence engine."""

    event: str  # visited | signed_up | trial_started | subscribed | subscription_renewed | subscription_cancelled
    channel: str  # the ?channel= slug from the referral link
    user_id: str = ""  # Meridian's id for the end user
    email: str | None = None
    amount: float | None = None  # subscription amount for subscribed/renewed
    timestamp: str | None = None
