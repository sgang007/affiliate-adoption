"""End-to-end flow: product setup → network building → Meridian events →
multi-level commission cascade → dashboards → monthly payout cycle."""
import hashlib
import hmac
import json

from tests.conftest import auth


def login(client, email, password):
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["token"]


def test_full_flow(client, admin_token):
    # Admin creates the Meridian product.
    r = client.post(
        "/api/admin/products",
        json={
            "name": "Meridian",
            "description": "Product intelligence engine",
            "url": "https://meridian.example.com",
            "price": 1800,
            "signup_commission": 100,
            "trial_commission": 300,
            "subscription_pct": 20,
        },
        headers=auth(admin_token),
    )
    assert r.status_code == 200, r.text
    product = r.json()
    assert product["webhook_url"].endswith(f"/api/webhooks/meridian/{product['id']}")

    # Admin creates the first (root) affiliate and assigns the product.
    r = client.post(
        "/api/admin/users",
        json={"email": "alpha@test.local", "name": "Alpha", "password": "pass1234"},
        headers=auth(admin_token),
    )
    assert r.status_code == 200, r.text
    alpha_id = r.json()["id"]
    r = client.post(
        f"/api/admin/products/{product['id']}/assign",
        json={"user_id": alpha_id},
        headers=auth(admin_token),
    )
    assert r.status_code == 200

    # Alpha logs in and generates a referral link.
    alpha_token = login(client, "alpha@test.local", "pass1234")
    r = client.post(f"/api/products/{product['id']}/link", headers=auth(alpha_token))
    assert r.status_code == 200
    alpha_link = r.json()
    assert "channel=" in alpha_link["referral_url"]

    # Tracking redirect sets the channel cookie and counts the visit.
    r = client.get(f"/r/{alpha_link['slug']}", follow_redirects=False)
    assert r.status_code == 302
    assert f"channel={alpha_link['slug']}" in r.headers["location"]
    assert "channel=" in r.headers.get("set-cookie", "")

    # Alpha invites Beta; Beta accepts and inherits product access.
    r = client.post(
        "/api/team/invite", json={"email": "beta@test.local"}, headers=auth(alpha_token)
    )
    assert r.status_code == 200
    invite_token = r.json()["invite_url"].rsplit("/", 1)[-1]
    r = client.post(
        "/api/auth/accept-invite",
        json={"token": invite_token, "name": "Beta", "password": "pass1234"},
    )
    assert r.status_code == 200
    beta_token = r.json()["token"]
    r = client.post(f"/api/products/{product['id']}/link", headers=auth(beta_token))
    assert r.status_code == 200
    beta_link = r.json()

    # Beta invites Gamma (level 3).
    r = client.post(
        "/api/team/invite", json={"email": "gamma@test.local"}, headers=auth(beta_token)
    )
    invite_token = r.json()["invite_url"].rsplit("/", 1)[-1]
    r = client.post(
        "/api/auth/accept-invite",
        json={"token": invite_token, "name": "Gamma", "password": "pass1234"},
    )
    gamma_token = r.json()["token"]
    gamma_link = client.post(
        f"/api/products/{product['id']}/link", headers=auth(gamma_token)
    ).json()

    wh = f"/api/webhooks/meridian/{product['id']}"
    secret = product["webhook_secret"].encode()

    def fire(channel, event, uid, amount=None):
        # Sign the raw body exactly like Meridian's engine would.
        raw = json.dumps(
            {"event": event, "channel": channel, "user_id": uid, "amount": amount}
        ).encode()
        signature = hmac.new(secret, raw, hashlib.sha256).hexdigest()
        r = client.post(
            wh,
            content=raw,
            headers={"Content-Type": "application/json", "X-Meridian-Signature": signature},
        )
        assert r.status_code == 200, r.text
        return r.json()

    # Direct conversion on Alpha's link → Alpha gets the full base amount.
    res = fire(alpha_link["slug"], "signed_up", "u1")
    assert res["commissions"] == [{"user_id": alpha_id, "amount": 100.0, "type": "signup"}]

    # Duplicate signup event must not double-pay.
    res = fire(alpha_link["slug"], "signed_up", "u1")
    assert res["commissions"] == []

    # Conversion on Beta's link → Beta 80, Alpha 20.
    res = fire(beta_link["slug"], "signed_up", "u2")
    amounts = {c["user_id"]: c["amount"] for c in res["commissions"]}
    assert sorted(amounts.values(), reverse=True) == [80.0, 20.0]

    # Trial on Gamma's link → Gamma 240, Beta 48, Alpha 12 (base 300).
    res = fire(gamma_link["slug"], "trial_started", "u3")
    amounts = sorted((c["amount"] for c in res["commissions"]), reverse=True)
    assert amounts == [240.0, 48.0, 12.0]
    assert sum(amounts) == 300.0  # company cost never exceeds the base

    # Subscription on Gamma's link: 20% of 1800 = 360 → 288 / 57.6 / 14.4.
    res = fire(gamma_link["slug"], "subscribed", "u3", amount=1800)
    amounts = sorted((c["amount"] for c in res["commissions"]), reverse=True)
    assert amounts == [288.0, 57.6, 14.4]

    # Monthly renewal keeps paying for the subscription's lifetime.
    res = fire(gamma_link["slug"], "subscription_renewed", "u3", amount=1800)
    assert res["commissions"] == []  # same period → deduped

    # Alpha's dashboard: direct + network earnings split.
    r = client.get("/api/dashboard", headers=auth(alpha_token))
    dash = r.json()
    assert dash["earnings"]["direct"] == 100.0
    assert dash["earnings"]["network"] == 20.0 + 12.0 + 14.4
    assert dash["network_size"] == 2

    # Network graph includes both descendants with their contribution to Alpha.
    r = client.get("/api/network", headers=auth(alpha_token))
    net = r.json()
    members = {m["name"]: m for m in net["members"]}
    assert members["Beta"]["earned_for_me"] == 20.0
    assert members["Gamma"]["earned_for_me"] == 12.0 + 14.4

    # Monthly payout: Gamma bills, submits, admin closes the cycle.
    r = client.post("/api/invoices/generate", json={}, headers=auth(gamma_token))
    assert r.status_code == 200
    inv = r.json()
    assert inv["total_amount"] == 240.0 + 288.0
    r = client.post(f"/api/invoices/{inv['id']}/submit", headers=auth(gamma_token))
    assert r.json()["status"] == "submitted"
    r = client.post("/api/admin/payouts/close-cycle", headers=auth(admin_token))
    assert r.json()["invoices_paid"] == 1
    r = client.get("/api/invoices", headers=auth(gamma_token))
    assert r.json()[0]["status"] == "paid"


def test_webhook_rejects_bad_signature(client, admin_token):
    r = client.get("/api/admin/products", headers=auth(admin_token))
    product = r.json()[0]
    # Secret is set on the product, so an unsigned request must be rejected.
    r = client.post(
        f"/api/webhooks/meridian/{product['id']}",
        json={"event": "visited", "channel": "nope", "user_id": "x"},
        headers={"X-Meridian-Signature": "deadbeef"},
    )
    assert r.status_code == 401
