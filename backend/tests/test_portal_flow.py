"""End-to-end flow with the admin-rooted network and the rules engine:
product setup → rules → invites → signed webhook messages → top-down
distribution → ledger → payout request → approve → paid."""
import hashlib
import hmac
import json

from tests.conftest import auth


def login(client, email, password):
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["token"]


def accept_invite(client, inviter_token, email, name):
    r = client.post("/api/team/invite", json={"email": email}, headers=auth(inviter_token))
    assert r.status_code == 200, r.text
    token = r.json()["invite_url"].rsplit("/", 1)[-1]
    r = client.post(
        "/api/auth/accept-invite", json={"token": token, "name": name, "password": "pass1234"}
    )
    assert r.status_code == 200, r.text
    return r.json()


def test_full_flow(client, admin_token):
    # Admin creates the product — admin is auto-assigned as the network root
    # and default incentive rules + event templates are attached.
    r = client.post(
        "/api/admin/products",
        json={
            "name": "Meridian",
            "description": "Product intelligence engine",
            "url": "https://getmeridian.tech",
            "price": 2000,
            "network_commission_pct": 20,
        },
        headers=auth(admin_token),
    )
    assert r.status_code == 200, r.text
    product = r.json()
    assert product["webhook_url"].endswith(f"/api/webhooks/meridian/{product['id']}")
    assert {x["event"] for x in product["rules"]} == {
        "visited", "signed_up", "trial", "subscribed", "renewal"
    }
    assert "renewal" in product["event_templates"]

    # Admin tunes the rules to the spec example: signed_up flat 300,
    # subscribed 20% of params.subscription.
    r = client.put(
        f"/api/admin/products/{product['id']}/rules",
        json={"rules": [{"event": "signed_up", "type": "flat", "value": 300}]},
        headers=auth(admin_token),
    )
    assert r.status_code == 200, r.text

    # Integration prompt contains the contract.
    r = client.get(
        f"/api/admin/products/{product['id']}/integration-prompt", headers=auth(admin_token)
    )
    prompt = r.json()["prompt"]
    assert "referrer_id" in prompt and "channel" in prompt
    # Endpoint, secret and signing instructions must be explicit.
    assert product["webhook_url"] in prompt
    assert product["webhook_secret"] in prompt
    assert "X-Meridian-Signature" in prompt and "HMAC" in prompt
    # Renewal is covered in the message formats.
    assert '"event": "renewal"' in prompt

    # Network: admin invites B; B invites C; C invites D.
    b = accept_invite(client, admin_token, "b@test.local", "B")
    b_token = b["token"]
    c = accept_invite(client, b_token, "c@test.local", "C")
    c_token = c["token"]
    d = accept_invite(client, c_token, "d@test.local", "D")
    d_token = d["token"]

    # Each affiliate's channel is the hex hash of their email.
    assert d["user"]["affiliate_id"] == hashlib.sha256(b"d@test.local").hexdigest()[:12]

    # D's referral link is auto-generated the moment the dashboard loads.
    r = client.get("/api/products", headers=auth(d_token))
    assert r.status_code == 200, r.text
    d_link = r.json()[0]["link"]
    assert d_link["referral_url"] == f"https://getmeridian.tech?channel={d['user']['affiliate_id']}"

    wh = f"/api/webhooks/meridian/{product['id']}"
    secret = product["webhook_secret"].encode()

    def fire(channel, event, params, expect=200):
        raw = json.dumps({"channel": channel, "event": event, "params": params}).encode()
        sig = hmac.new(secret, raw, hashlib.sha256).hexdigest()
        r = client.post(
            wh,
            content=raw,
            headers={"Content-Type": "application/json", "X-Meridian-Signature": sig},
        )
        assert r.status_code == expect, r.text
        return r.json()

    # Spec example: user signs up via D's link → flat 300 at 20% network
    # commission: B 60, C 48, D 192. Admin earns nothing.
    res = fire(
        d_link["slug"],
        "signed_up",
        {"email": "u1@x.in", "name": "U One", "job_role": "Founder", "industry": "SaaS"},
    )
    by_user = {x["user_id"]: x["amount"] for x in res["commissions"]}
    assert by_user == {
        b["user"]["id"]: 60.0,
        c["user"]["id"]: 48.0,
        d["user"]["id"]: 192.0,
    }

    # Replay is idempotent.
    res = fire(d_link["slug"], "signed_up", {"email": "u1@x.in"})
    assert res["commissions"] == []

    # Subscription: 20% of params.subscription (2000) = 400 → B 80, C 64, D 256.
    res = fire(
        d_link["slug"],
        "subscribed",
        {"email": "u1@x.in", "name": "U One", "plan": "Founder-Starter",
         "subscription": "2000", "frequency": "monthly"},
    )
    amounts = sorted((x["amount"] for x in res["commissions"]), reverse=True)
    assert amounts == [256.0, 80.0, 64.0]
    assert sum(amounts) == 400.0

    # subscribed is a one-time reward — replaying it never pays again.
    res = fire(d_link["slug"], "subscribed", {"email": "u1@x.in", "subscription": "2000"})
    assert res["commissions"] == []

    # renewal has its own rule (20% of params.subscription) and pays once per
    # user per month — the recurring income stream.
    res = fire(
        d_link["slug"],
        "renewal",
        {"email": "u1@x.in", "subscription": "2000", "frequency": "monthly", "renewal_count": 2},
    )
    amounts = sorted((x["amount"] for x in res["commissions"]), reverse=True)
    assert amounts == [256.0, 80.0, 64.0]
    # Same-month duplicate renewal is deduped; the payment-provider alias works too.
    res = fire(d_link["slug"], "subscription_renewed", {"email": "u1@x.in", "subscription": "2000"})
    assert res["commissions"] == []

    # Direct child of admin converts → keeps the full payable.
    b_link = client.post(f"/api/products/{product['id']}/link", headers=auth(b_token)).json()
    res = fire(b_link["slug"], "signed_up", {"email": "u2@x.in", "name": "U Two"})
    assert res["commissions"] == [
        {"user_id": b["user"]["id"], "amount": 300.0, "type": "signed_up"}
    ]

    # Dashboards: B earned 300 direct + 60 + 80 + 80 network overrides.
    r = client.get("/api/dashboard", headers=auth(b_token))
    dash = r.json()
    assert dash["earnings"]["direct"] == 300.0
    assert dash["earnings"]["network"] == 60.0 + 80.0 + 80.0

    # Ledger + payout request for D.
    r = client.get("/api/payouts", headers=auth(d_token))
    assert r.json()["balance_pending"] == 192.0 + 256.0 + 256.0
    r = client.post(
        "/api/payouts/request",
        json={"upi": "d@upi", "account_name": "D"},
        headers=auth(d_token),
    )
    assert r.status_code == 200, r.text
    req = r.json()
    assert req["amount"] == 704.0 and req["status"] == "requested"

    # Admin approves, then marks paid (which emails the affiliate).
    r = client.post(
        f"/api/admin/payout-requests/{req['id']}/approve", headers=auth(admin_token)
    )
    assert r.json()["status"] == "approved"
    r = client.post(
        f"/api/admin/payout-requests/{req['id']}/mark-paid", headers=auth(admin_token)
    )
    assert r.json()["status"] == "paid"

    r = client.get("/api/payouts", headers=auth(d_token))
    data = r.json()
    assert data["total_paid"] == 704.0 and data["balance_pending"] == 0.0

    # Admins never earn and cannot request payouts.
    r = client.post("/api/payouts/request", json={"upi": "a@upi"}, headers=auth(admin_token))
    assert r.status_code == 403


def test_webhook_rejects_bad_signature(client, admin_token):
    r = client.get("/api/admin/products", headers=auth(admin_token))
    product = r.json()[0]
    r = client.post(
        f"/api/webhooks/meridian/{product['id']}",
        json={"event": "visited", "channel": "nope", "params": {}},
        headers={"X-Meridian-Signature": "deadbeef"},
    )
    assert r.status_code == 401


def test_new_product_assigned_to_whole_network(client, admin_token):
    """A product created after affiliates joined is promoted by all of them."""
    r = client.post(
        "/api/admin/products",
        json={"name": "Second Launch", "url": "https://second.example.com"},
        headers=auth(admin_token),
    )
    assert r.status_code == 200, r.text
    b_token = login(client, "b@test.local", "pass1234")
    r = client.get("/api/products", headers=auth(b_token))
    names = {p["name"] for p in r.json()}
    assert "Second Launch" in names
    # And the link is already generated with B's channel.
    second = next(p for p in r.json() if p["name"] == "Second Launch")
    assert "channel=" in second["link"]["referral_url"]
