import os
from sqlalchemy import create_engine,Column,Integer,BigInteger,String,Boolean,Numeric
from sqlalchemy.orm import declarative_base,sessionmaker

Base=declarative_base()

DATABASE_URL=os.getenv("DATABASE_URL").replace("postgres://","postgresql://",1)
engine=create_engine(DATABASE_URL)
SessionLocal=sessionmaker(bind=engine)

class User(Base):
    __tablename__="users"
    id=Column(Integer,primary_key=True)
    tg_user_id=Column(BigInteger,unique=True)
    is_active=Column(Boolean,default=False)
    usd_rate=Column(Numeric,default=0)

class Person(Base):
    __tablename__="people"
    id=Column(Integer,primary_key=True)
    owner_user_id=Column(BigInteger)
    name=Column(String)

class Debt(Base):
    __tablename__="debts"
    id=Column(Integer,primary_key=True)
    owner_user_id=Column(BigInteger)
    person_id=Column(Integer)
    amount=Column(Numeric)
    currency=Column(String)

def init_db():
    Base.metadata.create_all(engine)
