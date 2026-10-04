"""Seed demo data: admin, a Meridian product, a 3-level affiliate network and
a realistic stream of funnel events so every dashboard has something to show.

Run from backend/:  python -m scripts.seed
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal, init_db  # noqa: E402
from app.models import AffiliateLink, Product, ProductAssignment, User  # noqa: E402
from app.security import hash_password  # noqa: E402
from app.services.commission import process_meridian_event  # noqa: E402
from app.services.slugs import make_slug  # noqa: E402

DEMO_PASSWORD = "demo123"


def get_or_create_user(db, email, name, parent=None):
    user = db.query(User).filter(User.email == email).first()
    if user:
        return user
    user = User(
        email=email,
        name=name,
        hashed_password=hash_password(DEMO_PASSWORD),
        role="affiliate",
        parent_id=parent.id if parent else None,
    )
    db.add(user)
    db.flush()
    user.path = f"{parent.path}/{user.id}" if parent else str(user.id)
    db.commit()
    return user


def assign(db, product, user):
    if not db.query(ProductAssignment).filter_by(product_id=product.id, user_id=user.id).first():
        db.add(ProductAssignment(product_id=product.id, user_id=user.id))
        db.commit()


def link_for(db, product, user):
    link = db.query(AffiliateLink).filter_by(product_id=product.id, user_id=user.id).first()
    if not link:
        link = AffiliateLink(product_id=product.id, user_id=user.id, slug=make_slug(user.path))
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
            url="https://meridian.example.com",
            price=1800,
            signup_commission=100,
            trial_commission=300,
            subscription_pct=20,
            created_by=admin.id,
        )
        db.add(product)
        db.commit()

    # 3-level network: Ananya → Rohan & Priya → Kabir (under Rohan)
    ananya = get_or_create_user(db, "ananya@demo.in", "Ananya Sharma")
    rohan = get_or_create_user(db, "rohan@demo.in", "Rohan Mehta", parent=ananya)
    priya = get_or_create_user(db, "priya@demo.in", "Priya Nair", parent=ananya)
    kabir = get_or_create_user(db, "kabir@demo.in", "Kabir Singh", parent=rohan)

    for u in (ananya, rohan, priya, kabir):
        assign(db, product, u)

    links = {u.id: link_for(db, product, u) for u in (ananya, rohan, priya, kabir)}

    def fire(user, event, ext_id, email=None, amount=None):
        process_meridian_event(
            db, product, event, links[user.id].slug, ext_id, email=email, amount=amount
        )

    # Only seed events once.
    if links[ananya.id].visits == 0:
        # Ananya's direct funnel
        for i in range(14):
            fire(ananya, "visited", f"a-visitor-{i}")
        for i in range(6):
            fire(ananya, "signed_up", f"a-visitor-{i}", email=f"founder{i}@startups.in")
        for i in range(3):
            fire(ananya, "trial_started", f"a-visitor-{i}")
        fire(ananya, "subscribed", "a-visitor-0", amount=1800)
        fire(ananya, "subscribed", "a-visitor-1", amount=1800)

        # Rohan's funnel (Ananya earns overrides)
        for i in range(9):
            fire(rohan, "visited", f"r-visitor-{i}")
        for i in range(4):
            fire(rohan, "signed_up", f"r-visitor-{i}", email=f"builder{i}@ideas.in")
        for i in range(2):
            fire(rohan, "trial_started", f"r-visitor-{i}")
        fire(rohan, "subscribed", "r-visitor-0", amount=1800)

        # Priya's funnel
        for i in range(7):
            fire(priya, "visited", f"p-visitor-{i}")
        for i in range(3):
            fire(priya, "signed_up", f"p-visitor-{i}", email=f"maker{i}@dreamers.in")
        fire(priya, "trial_started", "p-visitor-0")

        # Kabir's funnel (Rohan and Ananya both earn overrides)
        for i in range(5):
            fire(kabir, "visited", f"k-visitor-{i}")
        for i in range(2):
            fire(kabir, "signed_up", f"k-visitor-{i}", email=f"hustler{i}@garage.in")
        fire(kabir, "trial_started", "k-visitor-0")
        fire(kabir, "subscribed", "k-visitor-0", amount=1800)

    print("Seeded demo data.")
    print(f"  Admin     : {admin.email} / admin123")
    print(f"  Affiliates: ananya@demo.in, rohan@demo.in, priya@demo.in, kabir@demo.in / {DEMO_PASSWORD}")
    print(f"  Product   : {product.name} (id={product.id})")
    print(f"  Webhook   : POST /api/webhooks/meridian/{product.id}  secret={product.webhook_secret}")
    db.close()


if __name__ == "__main__":
    main()
