from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import get_settings

settings = get_settings()

connect_args = {}
if settings.database_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create tables and bootstrap the first admin account."""
    from . import models  # noqa: F401  (register mappings)
    from .security import hash_password

    Base.metadata.create_all(bind=engine)

    from .services.identity import assign_affiliate_id

    db = SessionLocal()
    try:
        admin = db.query(models.User).filter(models.User.role == "admin").first()
        if not admin:
            admin = models.User(
                email=settings.admin_email,
                name=settings.admin_name,
                hashed_password=hash_password(settings.admin_password),
                role="admin",
                affiliate_id=assign_affiliate_id(db, settings.admin_email),
            )
            db.add(admin)
            db.flush()
            admin.path = str(admin.id)
            db.commit()
    finally:
        db.close()
