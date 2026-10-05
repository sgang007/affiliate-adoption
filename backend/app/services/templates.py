"""Event message templates and the integration prompt generator.

Templates are admin-editable example messages per event — the contract the
product's engineering team (or an AI coding agent) implements. The prompt
generator renders everything an integrator needs into one copy-paste
document: the endpoint, signing code with the real secret, channel caching,
the referrer_id column, message formats and retry semantics.
"""
import json

from ..models import EVENT_KINDS, Product


def default_event_templates() -> dict:
    return {
        "visited": {
            "channel": "<affiliate-id from cookie/referrer>",
            "event": "visited",
            "params": {
                "user_info": "<browser locale, e.g. en-IN>",
                "location": "<city/country from IP>",
                "device_type": "<mobile | desktop | tablet>",
            },
        },
        "signed_up": {
            "channel": "<affiliate-id>",
            "event": "signed_up",
            "params": {
                "email": "shubho@getmeridian.tech",
                "name": "Shubhojyoti Ganguly",
                "job_role": "Founder",
                "industry": "SaaS",
            },
        },
        "trial": {
            "channel": "<affiliate-id>",
            "event": "trial",
            "params": {
                "name": "Shubhojyoti Ganguly",
                "email": "shubho@getmeridian.tech",
                "credits_granted": 1000,
                "trial_duration": "unlimited",
            },
        },
        "subscribed": {
            "channel": "<affiliate-id>",
            "event": "subscribed",
            "params": {
                "email": "shubho@getmeridian.tech",
                "name": "Shubhojyoti Ganguly",
                "plan": "Founder-Starter",
                "subscription": "2000",
                "frequency": "monthly",
            },
        },
        "renewal": {
            "channel": "<affiliate-id>",
            "event": "renewal",
            "params": {
                "email": "shubho@getmeridian.tech",
                "name": "Shubhojyoti Ganguly",
                "plan": "Founder-Starter",
                "subscription": "2000",
                "frequency": "monthly",
                "renewal_count": 2,
            },
        },
    }


def merged_templates(product: Product) -> dict:
    """Stored templates over defaults, so new event types always appear."""
    return {**default_event_templates(), **(product.event_templates or {})}


WHEN_TO_SEND = {
    "visited": "first attributed page view (a `channel` cookie or query param is present)",
    "signed_up": "account creation — pays once per user",
    "trial": "trial activation — pays once per user",
    "subscribed": "FIRST successful charge only — pays once per user",
    "renewal": "EVERY later successful charge (payment provider's invoice-paid webhook) — pays once per user per calendar month, the recurring income stream",
}


def integration_prompt(product: Product, webhook_url: str) -> str:
    templates = merged_templates(product)
    secret = product.webhook_secret or ""

    rules_md = "\n".join(
        f"| `{r.event}` | {'flat ' + format(float(r.value), 'g') + ' ' + product.currency if r.type == 'flat' else format(float(r.value), 'g') + '% of `' + (r.field or 'params.subscription') + '`'} |"
        for r in sorted(
            product.rules,
            key=lambda r: EVENT_KINDS.index(r.event) if r.event in EVENT_KINDS else 99,
        )
        if r.is_active
    ) or "| — | no rules configured yet |"

    templates_md = "\n\n".join(
        f"**`{event}`** — send on {WHEN_TO_SEND[event]}:\n"
        f"```json\n{json.dumps(templates.get(event, {}), indent=2)}\n```"
        for event in EVENT_KINDS
    )

    return f"""# Affiliate tracking integration — {product.name}

You are integrating **{product.url}** with our affiliate adoption portal so
that every visitor, signup, trial, subscription and renewal brought by an
affiliate referral link is attributed and rewarded. Implement the following
exactly.

## 1. The webhook endpoint and how to call it

Send every event as an HTTP POST, server-side (never from the browser — the
secret must not be exposed):

```
URL:    {webhook_url}
Method: POST
Header: Content-Type: application/json
Header: X-Meridian-Signature: <hex HMAC-SHA256 of the EXACT raw request body, keyed with the secret>
Secret: {secret}
```

Store the URL and secret in environment variables, e.g.
`AFFILIATE_WEBHOOK_URL` and `AFFILIATE_WEBHOOK_SECRET`. Copy-paste helper —
sign the exact bytes you send:

Python:
```python
import hashlib, hmac, json, os
import httpx  # or requests

WEBHOOK_URL = os.environ["AFFILIATE_WEBHOOK_URL"]      # {webhook_url}
WEBHOOK_SECRET = os.environ["AFFILIATE_WEBHOOK_SECRET"]  # {secret}

def send_affiliate_event(channel: str, event: str, params: dict) -> None:
    if not channel:
        return  # organic user — nothing to report
    body = json.dumps({{"channel": channel, "event": event, "params": params}})
    signature = hmac.new(WEBHOOK_SECRET.encode(), body.encode(), hashlib.sha256).hexdigest()
    httpx.post(
        WEBHOOK_URL,
        content=body,
        headers={{"Content-Type": "application/json", "X-Meridian-Signature": signature}},
        timeout=5,
    )
```

Node.js:
```js
const crypto = require("crypto");

const WEBHOOK_URL = process.env.AFFILIATE_WEBHOOK_URL;      // {webhook_url}
const WEBHOOK_SECRET = process.env.AFFILIATE_WEBHOOK_SECRET; // {secret}

async function sendAffiliateEvent(channel, event, params) {{
  if (!channel) return; // organic user — nothing to report
  const body = JSON.stringify({{ channel, event, params }});
  const signature = crypto.createHmac("sha256", WEBHOOK_SECRET).update(body).digest("hex");
  await fetch(WEBHOOK_URL, {{
    method: "POST",
    headers: {{ "Content-Type": "application/json", "X-Meridian-Signature": signature }},
    body,
  }});
}}
```

Responses: `200` accepted · `401` wrong signature (you signed different
bytes than you sent) · `404` unknown channel (organic user — safe to skip).

## 2. Capture the referral channel

Affiliate links look like `{product.url}?channel=<affiliate-id>` (the
affiliate id is a hex hash, e.g. `das232edads`).

On every landing, read the `channel` query parameter. If present and no
`channel` cookie exists yet, store it in a cookie for 90 days (first-touch
attribution — never overwrite an existing value):

```js
const channel = new URLSearchParams(location.search).get("channel");
if (channel && !document.cookie.includes("channel=")) {{
  document.cookie = `channel=${{channel}}; max-age=${{90 * 24 * 3600}}; path=/; samesite=lax`;
}}
```

## 3. Add a `referrer_id` column to your user table

When an account is created, copy the `channel` cookie value into a
`referrer_id` field on the user record. From then on, **every** event that
user generates — signed_up, trial, subscribed and each monthly renewal —
must pass that stored `referrer_id` as the `channel` argument of
`send_affiliate_event`. The cookie is only the bridge until signup.

## 4. Message formats — when to send what

{templates_md}

If a subscription is cancelled, stop sending `renewal` (optionally send
`{{"channel": "...", "event": "cancelled", "params": {{"email": "..."}}}}`
to mark the user churned).

## 5. Delivery semantics

- Retries are safe: ingestion is idempotent. `signed_up`, `trial` and
  `subscribed` never pay twice per user; `renewal` pays at most once per
  user per calendar month.
- Fire events asynchronously (queue/background job) so the portal being
  unreachable never blocks your signup or billing flows; retry failures
  with backoff.

## 6. Current incentive rules (for reference — configured portal-side)

| Event | Payout |
{rules_md}

Network commission: {float(product.network_commission_pct or 0):g}% per
network level. Rules can change in the portal at any time with no code
change on your side.
"""
