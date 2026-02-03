
from sqlalchemy import Column, String, Text, BigInteger, Boolean, JSON
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class User(Base):
    __tablename__ = "user"
    id = Column(String, primary_key=True)
    name = Column(String)
    email = Column(String)
    role = Column(String)

class Group(Base):
    __tablename__ = "group"
    id = Column(Text, primary_key=True)
    name = Column(Text)
    user_ids = Column(JSON) 

class Chat(Base):
    __tablename__ = "chat"
    id = Column(String, primary_key=True)
    user_id = Column(String)
    title = Column(Text)
    chat = Column(JSON)
    meta = Column(JSON)
    created_at = Column(BigInteger)
    updated_at = Column(BigInteger)
    share_id = Column(String, nullable=True)
    archived = Column(Boolean, default=False)
    pinned = Column(Boolean, default=False)
