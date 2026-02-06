import os
from datetime import datetime, date
from sqlalchemy import (
    create_engine, Column, Integer, BigInteger, String, Boolean,
    DateTime, Date, Numeric, ForeignKey, Index, UniqueConstraint, Text
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

Base = declarative_base()

def _normalize_db_url(url: str) -> str:
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql://", 1)
    return url

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is missing.")

DATABASE_URL = _normalize_db_url(DATABASE_URL)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    connect_args={"sslmode": "require"},
)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    tg_user_id = Column(BigInteger, unique=True, nullable=False, index=True)
    is_blocked = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=False, nullable=False)
    sub_expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

class Person(Base):
    __tablename__ = "people"
    id = Column(Integer, primary_key=True)
    owner_user_id = Column(BigInteger, nullable=False, index=True)
    name = Column(String(120), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("owner_user_id", "name", name="uq_people_owner_name"),
    )

class Debt(Base):
    __tablename__ = "debts"
    id = Column(Integer, primary_key=True)
    owner_user_id = Column(BigInteger, nullable=False, index=True)
    person_id = Column(Integer, nullable=False, index=True)
    amount = Column(Numeric(18, 2), nullable=False)
    currency = Column(String(3), nullable=False)  # USD / SYP
    due_date = Column(Date, nullable=True)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

def init_db():
    Base.metadata.create_all(bind=engine)
