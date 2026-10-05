"""Seed demo data for the admin-rooted network:

  admin (root, earns nothing)
    └─ Ananya
         ├─ Rohan ── Kabir
         └─ Priya

plus a realistic event stream so every dashboard has data.

Run from backend/:  python -m scripts.seed
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal, init_db  # noqa: E402
from app.models import (  # noqa: E402
    AffiliateLink,
    IncentiveRule,
    Product,
    ProductAssignment,
    User,
)
from app.routers.admin import DEFAULT_RULES  # noqa: E402
from app.security import hash_password  # noqa: E402
from app.services.commission import process_product_event  # noqa: E402
from app.services.identity import assign_affiliate_id  # noqa: E402
from app.services.templates import default_event_templates  # noqa: E402

DEMO_PASSWORD = "demo123"


def get_or_create_user(db, email, name, parent):
    user = db.query(User).filter(User.email == email).first()
    if user:
        return user
    user = User(
        email=email,
        name=name,
        hashed_password=hash_password(DEMO_PASSWORD),
        role="affiliate",
        parent_id=parent.id,
        affiliate_id=assign_affiliate_id(db, email),
    )
    db.add(user)
    db.flush()
    user.path = f"{parent.path}/{user.id}"
    db.commit()
    return user


def assign(db, product, user):
    if not db.query(ProductAssignment).filter_by(product_id=product.id, user_id=user.id).first():
        db.add(ProductAssignment(product_id=product.id, user_id=user.id))
        db.commit()


def link_for(db, product, user):
    link = db.query(AffiliateLink).filter_by(product_id=product.id, user_id=user.id).first()
    if not link:
        link = AffiliateLink(product_id=product.id, user_id=user.id, slug=user.affiliate_id)
        db.add(link)
        db.commit()
    return link


def main():
    init_db()
    db = SessionLocal()

    admin = db.query(User).filter(User.role == "admin").first()

    product = db.query(Product).filter(Product.name == "Meridian").first()
    if not product:
        product = Product(
            name="Meridian",
            description="Product intelligence engine for aspiring and ideating entrepreneurs — "
            "validate ideas, find your market, and launch faster.",
            url="https://getmeridian.tech",
            price=2000,
            network_commission_pct=20,
            event_templates=default_event_templates(),
            created_by=admin.id,
        )
        db.add(product)
        db.flush()
        for r in DEFAULT_RULES:
            db.add(IncentiveRule(product_id=product.id, **r))
        db.commit()
    assign(db, product, admin)

    # Network: admin → Ananya → {Rohan → Kabir, Priya}
    ananya = get_or_create_user(db, "ananya@demo.in", "Ananya Sharma", parent=admin)
    rohan = get_or_create_user(db, "rohan@demo.in", "Rohan Mehta", parent=ananya)
    priya = get_or_create_user(db, "priya@demo.in", "Priya Nair", parent=ananya)
    kabir = get_or_create_user(db, "kabir@demo.in", "Kabir Singh", parent=rohan)

    affiliates = (ananya, rohan, priya, kabir)
    for u in affiliates:
        assign(db, product, u)
    links = {u.id: link_for(db, product, u) for u in affiliates}

    def fire(user, event, params, user_id=None):
        process_product_event(
            db,
            product,
            channel=links[user.id].slug,
            event_raw=event,
            payload={"channel": links[user.id].slug, "event": event,
                     "user_id": user_id, "params": params},
        )

    if links[ananya.id].visits == 0:
        def visit(user, uid):
            fire(user, "visited",
                 {"user_info": "en-IN", "location": "Bengaluru, IN", "device_type": "mobile"},
                 user_id=uid)

        def signup(user, uid, email, name):
            fire(user, "signed_up",
                 {"email": email, "name": name, "job_role": "Founder", "industry": "SaaS"},
                 user_id=uid)

        def trial(user, uid, email, name):
            fire(user, "trial",
                 {"email": email, "name": name, "credits_granted": 1000,
                  "trial_duration": "unlimited"},
                 user_id=uid)

        def subscribe(user, uid, email, name, amount="2000"):
            fire(user, "subscribed",
                 {"email": email, "name": name, "plan": "Founder-Starter",
                  "subscription": amount, "frequency": "monthly"},
                 user_id=uid)

        # Ananya (direct child of admin — keeps the remainder on her own sales)
        for i in range(14):
            visit(ananya, f"a-{i}")
        for i in range(6):
            signup(ananya, f"a-{i}", f"founder{i}@startups.in", f"Founder {i}")
        for i in range(3):
            trial(ananya, f"a-{i}", f"founder{i}@startups.in", f"Founder {i}")
        subscribe(ananya, "a-0", "founder0@startups.in", "Founder 0")
        subscribe(ananya, "a-1", "founder1@startups.in", "Founder 1")

        # Rohan (Ananya takes 20% network commission)
        for i in range(9):
            visit(rohan, f"r-{i}")
        for i in range(4):
            signup(rohan, f"r-{i}", f"builder{i}@ideas.in", f"Builder {i}")
        for i in range(2):
            trial(rohan, f"r-{i}", f"builder{i}@ideas.in", f"Builder {i}")
        subscribe(rohan, "r-0", "builder0@ideas.in", "Builder 0")

        # Priya
        for i in range(7):
            visit(priya, f"p-{i}")
        for i in range(3):
            signup(priya, f"p-{i}", f"maker{i}@dreamers.in", f"Maker {i}")
        trial(priya, "p-0", "maker0@dreamers.in", "Maker 0")

        # Kabir (Ananya and Rohan both take network commission above him)
        for i in range(5):
            visit(kabir, f"k-{i}")
        for i in range(2):
            signup(kabir, f"k-{i}", f"hustler{i}@garage.in", f"Hustler {i}")
        trial(kabir, "k-0", "hustler0@garage.in", "Hustler 0")
        subscribe(kabir, "k-0", "hustler0@garage.in", "Hustler 0")

    print("Seeded demo data.")
    print(f"  Admin     : {admin.email} / admin123  (network root, earns nothing)")
    print(f"  Affiliates: ananya@demo.in, rohan@demo.in, priya@demo.in, kabir@demo.in / {DEMO_PASSWORD}")
    for u in affiliates:
        print(f"    {u.name:<14} channel={u.affiliate_id}")
    print(f"  Product   : {product.name} (id={product.id})")
    print(f"  Webhook   : POST /api/webhooks/meridian/{product.id}  secret={product.webhook_secret}")
    db.close()


if __name__ == "__main__":
    main()
