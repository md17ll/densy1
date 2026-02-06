import os
from datetime import datetime
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    BigInteger,
    String,
    Boolean,
    DateTime,
    Numeric,
    ForeignKey,
    Text,
    text,
)
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is missing")

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


# ---------------- USERS ----------------
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    tg_user_id = Column(BigInteger, unique=True, index=True)
    is_active = Column(Boolean, default=False)
    is_blocked = Column(Boolean, default=False)
    usd_rate = Column(Numeric(18, 2), default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


# ---------------- PEOPLE ----------------
class Person(Base):
    __tablename__ = "people"

    id = Column(Integer, primary_key=True)
    owner_user_id = Column(BigInteger, index=True)
    name = Column(String(255))


# ---------------- DEBTS ----------------
class Debt(Base):
    __tablename__ = "debts"

    id = Column(Integer, primary_key=True)
    owner_user_id = Column(BigInteger, index=True)
    person_id = Column(Integer, ForeignKey("people.id"))
    amount = Column(Numeric(18, 2))
    currency = Column(String(3))  # USD / SYP
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


def _ensure_schema():
    """
    ترقيات بسيطة للجداول الموجودة (بدون حذف بيانات)
    لأن create_all لا يضيف أعمدة جديدة للجداول القديمة.
    """
    with engine.begin() as conn:
        # users
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT FALSE"))
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_blocked BOOLEAN DEFAULT FALSE"))
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS usd_rate NUMERIC(18,2) DEFAULT 0"))
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NOW()"))

        # debts
        conn.execute(text("ALTER TABLE debts ADD COLUMN IF NOT EXISTS currency VARCHAR(3)"))
        conn.execute(text("ALTER TABLE debts ADD COLUMN IF NOT EXISTS note TEXT"))
        conn.execute(text("ALTER TABLE debts ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NOW()"))


def init_db():
    Base.metadata.create_all(bind=engine)
    _ensure_schema()
