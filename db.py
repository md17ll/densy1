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

# SQLAlchemy + psycopg2 يحتاج postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    tg_user_id = Column(BigInteger, unique=True, index=True, nullable=False)

    is_active = Column(Boolean, default=False, nullable=False)
    is_blocked = Column(Boolean, default=False, nullable=False)

    usd_rate = Column(Numeric(18, 2), default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Person(Base):
    __tablename__ = "people"

    id = Column(Integer, primary_key=True)
    owner_user_id = Column(BigInteger, index=True, nullable=False)
    name = Column(String(255), nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Debt(Base):
    __tablename__ = "debts"

    id = Column(Integer, primary_key=True)

    owner_user_id = Column(BigInteger, index=True, nullable=False)
    person_id = Column(Integer, ForeignKey("people.id"), nullable=False)

    amount = Column(Numeric(18, 2), nullable=False)
    currency = Column(String(3), nullable=False)  # USD / SYP

    note = Column(Text, nullable=True)
    due_date = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


def _ensure_schema():
    """
    ترقيات آمنة بدون حذف بيانات:
    - إضافة أعمدة ناقصة
    - تحويل Telegram IDs إلى BIGINT
    - ضمان created_at NOT NULL
    - ضمان amount NUMERIC
    - ضمان currency NOT NULL (لو كان موجود عمود بس فيه null)
    """
    with engine.begin() as conn:
        # users
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT FALSE"))
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_blocked BOOLEAN DEFAULT FALSE"))
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS usd_rate NUMERIC(18,2) DEFAULT 0"))
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NOW()"))

        # people
        conn.execute(text("ALTER TABLE people ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NOW()"))

        # debts
        conn.execute(text("ALTER TABLE debts ADD COLUMN IF NOT EXISTS currency VARCHAR(3)"))
        conn.execute(text("ALTER TABLE debts ADD COLUMN IF NOT EXISTS note TEXT"))
        conn.execute(text("ALTER TABLE debts ADD COLUMN IF NOT EXISTS due_date TIMESTAMP"))
        conn.execute(text("ALTER TABLE debts ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NOW()"))

        # ترقيات أنواع + إصلاح NULLs
        conn.execute(text("""
DO $$
BEGIN
  -- users.tg_user_id -> bigint
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name='users' AND column_name='tg_user_id' AND data_type IN ('integer','int4')
  ) THEN
    ALTER TABLE users ALTER COLUMN tg_user_id TYPE BIGINT USING tg_user_id::bigint;
  END IF;

  -- people.owner_user_id -> bigint
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name='people' AND column_name='owner_user_id' AND data_type IN ('integer','int4')
  ) THEN
    ALTER TABLE people ALTER COLUMN owner_user_id TYPE BIGINT USING owner_user_id::bigint;
  END IF;

  -- debts.owner_user_id -> bigint
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name='debts' AND column_name='owner_user_id' AND data_type IN ('integer','int4')
  ) THEN
    ALTER TABLE debts ALTER COLUMN owner_user_id TYPE BIGINT USING owner_user_id::bigint;
  END IF;

  -- debts.amount -> numeric(18,2)
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name='debts' AND column_name='amount' AND data_type <> 'numeric'
  ) THEN
    ALTER TABLE debts ALTER COLUMN amount TYPE NUMERIC(18,2) USING amount::numeric;
  END IF;

  -- people.created_at: تعبئة null ثم NOT NULL
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name='people' AND column_name='created_at'
  ) THEN
    UPDATE people SET created_at = NOW() WHERE created_at IS NULL;
    BEGIN
      ALTER TABLE people ALTER COLUMN created_at SET NOT NULL;
    EXCEPTION WHEN others THEN
      NULL;
    END;
  END IF;

  -- debts.created_at: تعبئة null ثم NOT NULL
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name='debts' AND column_name='created_at'
  ) THEN
    UPDATE debts SET created_at = NOW() WHERE created_at IS NULL;
    BEGIN
      ALTER TABLE debts ALTER COLUMN created_at SET NOT NULL;
    EXCEPTION WHEN others THEN
      NULL;
    END;
  END IF;

  -- debts.currency: إذا العمود موجود وفيه NULL، عبّيه USD ثم حاول NOT NULL
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name='debts' AND column_name='currency'
  ) THEN
    UPDATE debts SET currency='USD' WHERE currency IS NULL;
    BEGIN
      ALTER TABLE debts ALTER COLUMN currency SET NOT NULL;
    EXCEPTION WHEN others THEN
      NULL;
    END;
  END IF;
END $$;
        """))


def init_db():
    Base.metadata.create_all(bind=engine)
    _ensure_schema()
