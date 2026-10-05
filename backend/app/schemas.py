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
    network_commission_pct: float = 20


class ProductUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    url: str | None = None
    price: float | None = None
    network_commission_pct: float | None = None
    event_templates: dict | None = None
    is_active: bool | None = None


class RuleIn(BaseModel):
    event: str  # visited | signed_up | trial | subscribed
    type: str = "flat"  # flat | commission
    value: float = 0
    field: str | None = None  # dot path for commission type, e.g. params.subscription


class RulesIn(BaseModel):
    rules: list[RuleIn]


class UserCreateIn(BaseModel):
    email: str
    name: str
    password: str


class InviteIn(BaseModel):
    email: str


class PayoutRequestIn(BaseModel):
    upi: str | None = None
    bank_account: str | None = None
    ifsc: str | None = None
    account_name: str | None = None


class ProductEvent(BaseModel):
    """Inbound webhook message: {channel, event, params}."""

    channel: str
    event: str
    params: dict = {}
    user_id: str | None = None  # optional stable end-user id; params.email is the fallback
