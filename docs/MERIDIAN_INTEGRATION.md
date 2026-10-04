# Integrating Meridian's Product Intelligence Engine

The portal and Meridian talk in both directions:

1. **Attribution (Meridian → user's browser):** every referral link carries
   `?channel=<slug>`. Meridian must persist that value (cookie
   `channel`, 90 days) on first touch and attach it to every lifecycle event
   for that end user.
2. **Events (Meridian → portal):** Meridian POSTs funnel events to the
   product's webhook URL.
3. **Callbacks (portal → affiliates):** the portal fans events out to each
   affiliate's own configured endpoints, in their chosen format.

## 1. The referral link

Each affiliate gets, per product:

| Link | Example | Use |
|---|---|---|
| Referral link | `https://meridian.example.com?channel=1-4-9~x7kq` | direct share |
| Tracked link | `https://<portal>/r/1-4-9~x7kq` | counts the visit in the portal, sets the `channel` cookie, 302-redirects to the referral link |

The slug encodes the affiliate's id **and every parent** in their network
(base36 ids joined by `-`, plus a random suffix), e.g. `1-4-9~x7kq` means
user 9, recruited by 4, whose network root is 1.

## 2. Inbound webhook (Meridian → portal)

```
POST {PORTAL_BASE_URL}/api/webhooks/meridian/{product_id}
Content-Type: application/json
X-Meridian-Signature: hex(HMAC_SHA256(webhook_secret, raw_body))
```

The `webhook_secret` is shown in the Admin console per product (rotate with
`POST /api/admin/products/{id}/rotate-secret`).

Body:

```json
{
  "event": "signed_up",
  "channel": "1-4-9~x7kq",
  "user_id": "mrd_8f2k1",
  "email": "founder@startup.in",
  "amount": 1800,
  "timestamp": "2026-10-04T10:21:00Z"
}
```

| `event` | When | `amount` | Commission |
|---|---|---|---|
| `visited` | first attributed visit | — | ₹0 (tracked) |
| `signed_up` | account created | — | ₹100 (product-configurable) |
| `trial_started` | trial begins | — | ₹300 (product-configurable) |
| `subscribed` | first paid subscription | monthly price | 20% of amount |
| `subscription_renewed` | every monthly renewal | monthly price | 20% of amount (one payout per referred user per month) |
| `subscription_cancelled` | subscription ends | — | stops recurring income |

Signed-up / trial / first-subscription commissions are idempotent per
referred user — replaying an event never double-pays.

### Example (curl)

```bash
BODY='{"event":"subscribed","channel":"1-4-9~x7kq","user_id":"mrd_8f2k1","amount":1800}'
SIG=$(printf '%s' "$BODY" | openssl dgst -sha256 -hmac "$WEBHOOK_SECRET" | awk '{print $2}')
curl -X POST "$PORTAL/api/webhooks/meridian/1" \
  -H "Content-Type: application/json" \
  -H "X-Meridian-Signature: $SIG" \
  -d "$BODY"
```

## 3. Outbound callbacks (portal → affiliate endpoints)

Affiliates configure endpoints under **Webhooks** (URL + event filter +
format `json` or `form`). Each delivery is signed:
`X-Portal-Signature: hex(HMAC_SHA256(endpoint_secret, body))`.

JSON format:

```json
{
  "event": "subscribed",
  "product_id": 1,
  "channel": "1-4-9~x7kq",
  "referred_user": {"external_id": "mrd_8f2k1", "email": "founder@startup.in", "status": "subscribed"},
  "commissions_earned": [{"user_id": 9, "amount": 288.0, "type": "subscription"}],
  "is_direct": true
}
```

`is_direct: false` means the event came from a descendant's link and the
amounts are network overrides.

## Commission cascade (company cost is constant)

For every paid event the company owes exactly the base amount; the network
splits it:

- Converting affiliate keeps **80%**, passes 20% up.
- Each ancestor keeps **80% of what arrives**, passes 20% further up.
- The network root keeps the remainder.

| Converter | Base ₹100 split | Base ₹360 (20% of ₹1800 sub) |
|---|---|---|
| Root A | A: 100 | A: 360 |
| A → B | B: 80, A: 20 | B: 288, A: 72 |
| A → B → C | C: 80, B: 16, A: 4 | C: 288, B: 57.6, A: 14.4 |
