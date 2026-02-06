import os
from datetime import datetime

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


def _now():
    return datetime.utcnow()


class User(Base):
    __tablename__ = "users"

    # Telegram ID كبير -> لازم BigInteger
    tg_user_id = Column(BigInteger, primary_key=True, index=True)

    is_active = Column(Boolean, default=False, nullable=False)
    is_blocked = Column(Boolean, default=False, nullable=False)

    usd_rate = Column(Float, nullable=True)

    # انتهاء الاشتراك (اختياري)
    sub_expires_at = Column(DateTime(timezone=False), nullable=True)

    created_at = Column(DateTime(timezone=False), default=_now, nullable=False)
    updated_at = Column(DateTime(timezone=False), default=_now, nullable=False)

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

    created_at = Column(DateTime(timezone=False), default=_now, nullable=False)
    updated_at = Column(DateTime(timezone=False), default=_now, nullable=False)

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

    # مهم جداً: بعض قواعدك القديمة فيها status NOT NULL
    status = Column(String(20), default="open", nullable=False)  # open / paid / partial ...

    created_at = Column(DateTime(timezone=False), default=_now, nullable=False)
    updated_at = Column(DateTime(timezone=False), default=_now, nullable=False)

    owner = relationship("User", back_populates="debts")
    person = relationship("Person", back_populates="debts")


def init_db():
    Base.metadata.create_all(bind=engine)
