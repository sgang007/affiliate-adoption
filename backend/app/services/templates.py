"""Event message templates and the integration prompt generator.

Templates are admin-editable example messages per event — the contract the
product's engineering team (or an AI coding agent) implements. The prompt
generator renders everything an integrator needs into one copy-paste
document: channel caching, the referrer_id column, message formats, signing
and retry semantics.
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


def integration_prompt(product: Product, webhook_url: str) -> str:
    templates = product.event_templates or default_event_templates()
    rules_md = "\n".join(
        f"| `{r.event}` | {'flat ' + format(float(r.value), 'g') + ' ' + product.currency if r.type == 'flat' else format(float(r.value), 'g') + '% of `' + (r.field or 'params.subscription') + '`'} |"
        for r in sorted(product.rules, key=lambda r: EVENT_KINDS.index(r.event) if r.event in EVENT_KINDS else 99)
        if r.is_active
    ) or "| — | no rules configured yet |"

    templates_md = "\n\n".join(
        f"**`{event}`**\n```json\n{json.dumps(templates.get(event, {}), indent=2)}\n```"
        for event in EVENT_KINDS
    )

    return f"""# Affiliate tracking integration — {product.name}

You are integrating **{product.url}** with our affiliate adoption portal so
that every visitor, signup, trial and subscription brought by an affiliate
referral link is attributed and rewarded. Implement the following exactly.

## 1. Capture the referral channel

Affiliate links look like `{product.url}?channel=<affiliate-id>` (the
affiliate id is a hex hash, e.g. `das232edads`).

- On every landing, read the `channel` query parameter. If present and no
  `channel` cookie exists yet, store it in a cookie for 90 days
  (first-touch attribution — never overwrite an existing value):

```js
const channel = new URLSearchParams(location.search).get("channel");
if (channel && !document.cookie.includes("channel=")) {{
  document.cookie = `channel=${{channel}}; max-age=${{90 * 24 * 3600}}; path=/; samesite=lax`;
}}
```

## 2. Add a `referrer_id` column to your user table

When an account is created, copy the `channel` cookie value into a
`referrer_id` field on the user record. From then on, **every** event that
user generates (signed_up, trial, subscribed, renewals) must send that
stored `referrer_id` as the `channel` in the message — the cookie is only
the bridge until signup.

## 3. Send webhook messages on these lifecycle events

```
POST {webhook_url}
Content-Type: application/json
X-Meridian-Signature: hex(HMAC_SHA256(secret, raw_request_body))
```

Signing secret: `{product.webhook_secret}` (keep it server-side only).

Message format per event — send exactly these shapes, with real values:

{templates_md}

Send `visited` on the first attributed page view (channel cookie present),
`signed_up` on account creation, `trial` on trial activation, `subscribed`
on the **first** successful charge, and `renewal` on **every later**
successful charge (hook your payment provider's invoice-paid webhook).
Renewal payouts happen at most once per user per month, so sending
`renewal` on each billing cycle is what keeps the affiliate's recurring
income flowing; stop when the subscription is cancelled (optionally send
`{{"event": "cancelled", ...}}`).

## 4. Delivery semantics

- Retries are safe: ingestion is idempotent (one-time events never pay
  twice; `subscribed` pays at most once per user per calendar month).
- A `200` response means accepted; `401` means your signature is wrong;
  `404` means the channel is unknown (user was organic — you may skip
  sending events for users with no `referrer_id`).

## 5. Current incentive rules (for reference)

| Event | Payout |
{rules_md}

Network commission: {float(product.network_commission_pct or 0):g}% per
network level. These are configured portal-side — changing them requires no
code change on your side.
"""
