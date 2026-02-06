import os
from datetime import datetime, date
from sqlalchemy import (
    create_engine, Column, Integer, BigInteger, String, Boolean,
    DateTime, Date, Numeric, ForeignKey, Index, UniqueConstraint, Text
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

Base = declarative_base()


def _normalize_db_url(url: str) -> str:
    # Railway sometimes provides postgres://; SQLAlchemy prefers postgresql://
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql://", 1)
    return url


DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is missing. Add Postgres in Railway and ensure DATABASE_URL exists.")

DATABASE_URL = _normalize_db_url(DATABASE_URL)

# Railway Postgres requires SSL
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    connect_args={"sslmode": "require"},
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


# -----------------------
# Models
# -----------------------

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    tg_user_id = Column(BigInteger, unique=True, nullable=False, index=True)
    is_blocked = Column(Boolean, default=False, nullable=False)

    # subscription
    is_active = Column(Boolean, default=False, nullable=False)
    sub_expires_at = Column(DateTime, nullable=True)

    # security
    pin_hash = Column(String(255), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    people = relationship("Person", back_populates="owner", cascade="all, delete-orphan")
    debts = relationship("Debt", back_populates="owner", cascade="all, delete-orphan")
    rates = relationship("DailyRate", back_populates="owner", cascade="all, delete-orphan")


class Person(Base):
    __tablename__ = "people"

    id = Column(Integer, primary_key=True)
    owner_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(120), nullable=False)
    note = Column(String(255), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    owner = relationship("User", back_populates="people")
    debts = relationship("Debt", back_populates="person", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("owner_user_id", "name", name="uq_people_owner_name"),
        Index("ix_people_owner", "owner_user_id"),
    )


class Debt(Base):
    __tablename__ = "debts"

    id = Column(Integer, primary_key=True)
    owner_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    person_id = Column(Integer, ForeignKey("people.id", ondelete="CASCADE"), nullable=False)

    amount = Column(Numeric(18, 2), nullable=False)
    currency = Column(String(3), nullable=False)  # USD / SYP

    title = Column(String(160), nullable=True)
    note = Column(Text, nullable=True)
    due_date = Column(Date, nullable=True)
    status = Column(String(20), default="OPEN", nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    owner = relationship("User", back_populates="debts")
    person = relationship("Person", back_populates="debts")
    payments = relationship("Payment", back_populates="debt", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_debts_owner", "owner_user_id"),
        Index("ix_debts_person", "person_id"),
    )


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True)
    debt_id = Column(Integer, ForeignKey("debts.id", ondelete="CASCADE"), nullable=False)

    amount = Column(Numeric(18, 2), nullable=False)
    currency = Column(String(3), nullable=False)
    note = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    debt = relationship("Debt", back_populates="payments")


class DailyRate(Base):
    __tablename__ = "daily_rates"

    id = Column(Integer, primary_key=True)
    owner_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    rate_date = Column(Date, nullable=False, default=date.today)
    usd_to_syp = Column(Numeric(18, 2), nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    owner = relationship("User", back_populates="rates")

    __table_args__ = (
        UniqueConstraint("owner_user_id", "rate_date", name="uq_rate_owner_date"),
        Index("ix_rates_owner", "owner_user_id"),
    )


def init_db():
    Base.metadata.create_all(bind=engine)
