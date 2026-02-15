import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, Column, String, Text, BigInteger, Boolean, JSON
from sqlalchemy.orm import sessionmaker, declarative_base

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL not set in .env (OpenWebUI database)")

owui_engine = create_engine(DATABASE_URL, pool_pre_ping=True)
OwuiSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=owui_engine)

OwuiBase = declarative_base()


class OwuiUser(OwuiBase):
    __tablename__ = "user"
    id = Column(String, primary_key=True)
    name = Column(String)
    email = Column(String)
    role = Column(String)


class OwuiGroup(OwuiBase):
    __tablename__ = "group"
    id = Column(Text, primary_key=True)
    name = Column(Text)
    user_ids = Column(JSON)


class OwuiChat(OwuiBase):
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


def get_owui_db():
    db = OwuiSessionLocal()
    try:
        yield db
    finally:
        db.close()
