# Integrating a product (Meridian's Product Intelligence Engine)

> The Admin console generates a complete, product-specific version of this
> document: **Admin → product → ⚡ Integration prompt**. It embeds the real
> webhook URL, signing secret, current message templates and rules — paste it
> into the product's codebase or hand it to an AI coding agent.

The portal and the product talk in both directions:

1. **Attribution:** referral links carry `?channel=<affiliate-id>`. The
   product cookies that value (90 days, first-touch) and stamps it onto the
   user record at signup as `referrer_id`.
2. **Events (product → portal):** the product POSTs lifecycle messages to
   the product's webhook URL.
3. **Callbacks (portal → admin systems):** optionally, the portal forwards
   processed events to admin-configured endpoints (JSON or form, signed).

## 1. Affiliate identity and referral links

Every affiliate's channel id is a **hex hash of their email** (e.g.
`das232edads`) — one id across all products. Links:

| Link | Example |
|---|---|
| Referral link | `https://getmeridian.tech?channel=94825aa6b280` |
| Tracked hop (optional, counts the visit portal-side) | `https://<portal>/r/<product_id>/94825aa6b280` |

The product must add a `referrer_id` column to its user table: copy the
`channel` cookie into it at signup, then send it as `channel` on **every**
subsequent event that user generates.

## 2. Inbound webhook (product → portal)

```
POST {PORTAL_BASE_URL}/api/webhooks/meridian/{product_id}
Content-Type: application/json
X-Meridian-Signature: hex(HMAC_SHA256(webhook_secret, raw_body))
```

Message format — `{channel, event, params}`:

```json
{
  "channel": "das232edads",
  "event": "subscribed",
  "params": {
    "email": "shubho@getmeridian.tech",
    "name": "Shubhojyoti Ganguly",
    "plan": "Founder-Starter",
    "subscription": "2000",
    "frequency": "monthly"
  }
}
```

Default params per event (admin-editable templates under **Event messages**):

| `event` | `params` | Pays |
|---|---|---|
| `visited` | `user_info` (browser locale), `location`, `device_type` | per rule |
| `signed_up` | `email`, `name`, `job_role`, `industry` | once per user |
| `trial` | `name`, `email`, `credits_granted`, `trial_duration` | once per user |
| `subscribed` | `email`, `name`, `plan`, `subscription`, `frequency` | once per user (first charge) |
| `renewal` | same as `subscribed` + `renewal_count` | once per user **per month** — the recurring income stream |

Aliases are accepted (`signed up`, `trial_started`, `renewed`,
`subscription_renewed`, `cancelled`). Send `subscribed` on the first
successful charge and `renewal` on every later charge (hook your payment
provider's invoice-paid webhook); stop when the subscription is cancelled
(optionally send `cancelled`). One-time events never pay twice, so retries
are always safe.

## 3. Incentive rules (configured portal-side, no product code involved)

Per event the admin sets one rule:

```
event: subscribed · type: flat | commission · value: 300 or 20
field: params.subscription   (dot path into the message, commission type only)
```

The payable is computed from the rule, then distributed down the network.

## 4. Network distribution (admin-rooted, cost-constant)

- The **admin is the network root and earns nothing**.
- The payable walks the branch **top-down from the admin's direct child to
  the converting affiliate**: each intermediate level takes the product's
  *network commission %* (default 20%) of the running pool; the converter
  keeps the remainder.
- Total paid always equals the computed payable.

Example — `A(admin) → B → C → D`, user signs up via D's link, flat ₹300,
20% network commission:

| Member | Share |
|---|---|
| B (admin's direct child) | 20% × 300 = **₹60** |
| C | 20% × 240 = **₹48** |
| D (converter) | remainder = **₹192** |

If B's own link converts, B keeps the full ₹300.

## 5. Ledger and payouts

Every share lands in the earner's ledger as `pending`. Affiliates request a
payout (UPI or bank details) which freezes the balance into a payout
request; the admin approves, pays manually, and marks it paid — the
affiliate is notified by email.

## Example (curl)

```bash
BODY='{"channel":"das232edads","event":"signed_up","params":{"email":"u@x.in","name":"U","job_role":"Founder","industry":"SaaS"}}'
SIG=$(printf '%s' "$BODY" | openssl dgst -sha256 -hmac "$WEBHOOK_SECRET" | awk '{print $2}')
curl -X POST "$PORTAL/api/webhooks/meridian/1" \
  -H "Content-Type: application/json" \
  -H "X-Meridian-Signature: $SIG" \
  -d "$BODY"
```
