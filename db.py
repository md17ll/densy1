import os
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    BigInteger,
    String,
    Boolean,
    Float,
    DateTime,
    ForeignKey,
    func,
    text,
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship


def _get_database_url() -> str:
    url = os.getenv("DATABASE_URL", "")
    if not url:
        raise RuntimeError("DATABASE_URL is not set")

    # Railway أحياناً يعطي postgres:// لازم تتحول
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg2://", 1)
    elif url.startswith("postgresql://") and "psycopg2" not in url:
        url = url.replace("postgresql://", "postgresql+psycopg2://", 1)

    return url


DATABASE_URL = _get_database_url()

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    tg_user_id = Column(BigInteger, primary_key=True, index=True)

    is_active = Column(Boolean, default=False, nullable=False)
    is_blocked = Column(Boolean, default=False, nullable=False)

    usd_rate = Column(Float, nullable=True)
    sub_expires_at = Column(DateTime(timezone=False), nullable=True)

    created_at = Column(DateTime(timezone=False), server_default=func.now(), nullable=False)

    people = relationship("Person", back_populates="owner", cascade="all, delete-orphan")
    debts = relationship("Debt", back_populates="owner", cascade="all, delete-orphan")


class Person(Base):
    __tablename__ = "people"

    id = Column(Integer, primary_key=True, index=True)

    owner_user_id = Column(
        BigInteger,
        ForeignKey("users.tg_user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = Column(String(120), nullable=False)

    created_at = Column(DateTime(timezone=False), server_default=func.now(), nullable=False)

    owner = relationship("User", back_populates="people")
    debts = relationship("Debt", back_populates="person", cascade="all, delete-orphan")


class Debt(Base):
    __tablename__ = "debts"

    id = Column(Integer, primary_key=True, index=True)

    owner_user_id = Column(
        BigInteger,
        ForeignKey("users.tg_user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    person_id = Column(
        Integer,
        ForeignKey("people.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    amount = Column(Float, nullable=False)
    currency = Column(String(3), nullable=False)  # USD / SYP

    # ✅ هذا اللي ناقص عندك (حسب اللوج): عمود status NOT NULL
    # نعطيه default حتى ما يعود يفشل الإدخال
    status = Column(String(20), nullable=False, server_default=text("'open'"))

    created_at = Column(DateTime(timezone=False), server_default=func.now(), nullable=False)

    owner = relationship("User", back_populates="debts")
    person = relationship("Person", back_populates="debts")


def _patch_old_schema_for_postgres():
    """
    يرقّع الجداول القديمة إذا كانت موجودة (Postgres فقط).
    لأن create_all ما يعدّل الجداول الموجودة.
    """
    if "postgresql" not in DATABASE_URL:
        return

    patch_sql = r"""
    DO $$
    BEGIN
        -- people.created_at
        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name='people' AND column_name='created_at'
        ) THEN
            EXECUTE 'ALTER TABLE people ALTER COLUMN created_at SET DEFAULT now()';
            EXECUTE 'UPDATE people SET created_at = now() WHERE created_at IS NULL';
            EXECUTE 'ALTER TABLE people ALTER COLUMN created_at SET NOT NULL';
        END IF;

        -- debts.created_at
        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name='debts' AND column_name='created_at'
        ) THEN
            EXECUTE 'ALTER TABLE debts ALTER COLUMN created_at SET DEFAULT now()';
            EXECUTE 'UPDATE debts SET created_at = now() WHERE created_at IS NULL';
            EXECUTE 'ALTER TABLE debts ALTER COLUMN created_at SET NOT NULL';
        END IF;

        -- ✅ debts.status (إذا موجود بدون default/فيه NULL) أو إذا غير موجود نضيفه
        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name='debts' AND column_name='status'
        ) THEN
            EXECUTE 'ALTER TABLE debts ALTER COLUMN status SET DEFAULT ''open''';
            EXECUTE 'UPDATE debts SET status = ''open'' WHERE status IS NULL';
            EXECUTE 'ALTER TABLE debts ALTER COLUMN status SET NOT NULL';
        ELSE
            EXECUTE 'ALTER TABLE debts ADD COLUMN status varchar(20) NOT NULL DEFAULT ''open''';
        END IF;

        -- FK people.owner_user_id -> users(tg_user_id)
        EXECUTE (
          SELECT COALESCE(string_agg('ALTER TABLE people DROP CONSTRAINT '||quote_ident(c.conname)||';', ' '), '')
          FROM pg_constraint c
          JOIN pg_class t ON t.oid = c.conrelid
          JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY(c.conkey)
          WHERE t.relname='people' AND c.contype='f' AND a.attname='owner_user_id'
        );

        IF NOT EXISTS (
          SELECT 1
          FROM pg_constraint c
          JOIN pg_class t ON t.oid = c.conrelid
          WHERE t.relname='people' AND c.contype='f' AND c.conname='people_owner_user_id_fkey_tg'
        ) THEN
          EXECUTE 'ALTER TABLE people
                   ADD CONSTRAINT people_owner_user_id_fkey_tg
                   FOREIGN KEY (owner_user_id)
                   REFERENCES users(tg_user_id)
                   ON DELETE CASCADE';
        END IF;

        -- FK debts.owner_user_id -> users(tg_user_id)
        EXECUTE (
          SELECT COALESCE(string_agg('ALTER TABLE debts DROP CONSTRAINT '||quote_ident(c.conname)||';', ' '), '')
          FROM pg_constraint c
          JOIN pg_class t ON t.oid = c.conrelid
          JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY(c.conkey)
          WHERE t.relname='debts' AND c.contype='f' AND a.attname='owner_user_id'
        );

        IF NOT EXISTS (
          SELECT 1
          FROM pg_constraint c
          JOIN pg_class t ON t.oid = c.conrelid
          WHERE t.relname='debts' AND c.contype='f' AND c.conname='debts_owner_user_id_fkey_tg'
        ) THEN
          EXECUTE 'ALTER TABLE debts
                   ADD CONSTRAINT debts_owner_user_id_fkey_tg
                   FOREIGN KEY (owner_user_id)
                   REFERENCES users(tg_user_id)
                   ON DELETE CASCADE';
        END IF;

    EXCEPTION WHEN others THEN
        NULL;
    END $$;
    """
    with engine.begin() as conn:
        conn.execute(text(patch_sql))


def init_db():
    Base.metadata.create_all(bind=engine)
    _patch_old_schema_for_postgres()
