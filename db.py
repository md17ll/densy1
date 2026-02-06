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

# Railway sometimes gives postgres://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


# =========================
# Models
# =========================

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    tg_user_id = Column(BigInteger, unique=True, index=True, nullable=False)

    # Premium / Access
    is_active = Column(Boolean, default=False, nullable=False)
    is_blocked = Column(Boolean, default=False, nullable=False)

    # USD rate
    usd_rate = Column(Numeric(18, 2), default=0, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Person(Base):
    __tablename__ = "people"

    id = Column(Integer, primary_key=True)
    owner_user_id = Column(BigInteger, index=True, nullable=False)  # Telegram ID (BIGINT)
    name = Column(String(255), nullable=False)


class Debt(Base):
    __tablename__ = "debts"

    id = Column(Integer, primary_key=True)
    owner_user_id = Column(BigInteger, index=True, nullable=False)  # Telegram ID (BIGINT)

    person_id = Column(Integer, ForeignKey("people.id"), nullable=False)

    amount = Column(Numeric(18, 2), nullable=False)
    currency = Column(String(3), nullable=False)  # USD / SYP
    note = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


# =========================
# Schema ensure / light migrations
# =========================

def _ensure_schema():
    """
    ترقيات بسيطة للجداول الموجودة بدون حذف بيانات:
    - إضافة الأعمدة الناقصة
    - تحويل أنواع Telegram IDs إلى BIGINT إذا كانت INT
    """
    with engine.begin() as conn:
        # ---- add missing columns (safe) ----
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT FALSE"))
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_blocked BOOLEAN DEFAULT FALSE"))
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS usd_rate NUMERIC(18,2) DEFAULT 0"))
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NOW()"))

        conn.execute(text("ALTER TABLE debts ADD COLUMN IF NOT EXISTS currency VARCHAR(3)"))
        conn.execute(text("ALTER TABLE debts ADD COLUMN IF NOT EXISTS note TEXT"))
        conn.execute(text("ALTER TABLE debts ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NOW()"))

        # ---- ensure BIGINT types for telegram ids ----
        # We use a DO block to check current types then alter safely.
        conn.execute(text("""
DO $$
BEGIN
  -- users.tg_user_id -> bigint
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name='users' AND column_name='tg_user_id' AND data_type IN ('integer', 'int4')
  ) THEN
    ALTER TABLE users
      ALTER COLUMN tg_user_id TYPE BIGINT USING tg_user_id::bigint;
  END IF;

  -- people.owner_user_id -> bigint
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name='people' AND column_name='owner_user_id' AND data_type IN ('integer', 'int4')
  ) THEN
    ALTER TABLE people
      ALTER COLUMN owner_user_id TYPE BIGINT USING owner_user_id::bigint;
  END IF;

  -- debts.owner_user_id -> bigint
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name='debts' AND column_name='owner_user_id' AND data_type IN ('integer', 'int4')
  ) THEN
    ALTER TABLE debts
      ALTER COLUMN owner_user_id TYPE BIGINT USING owner_user_id::bigint;
  END IF;
END $$;
        """))


def init_db():
    Base.metadata.create_all(bind=engine)
    _ensure_schema()
