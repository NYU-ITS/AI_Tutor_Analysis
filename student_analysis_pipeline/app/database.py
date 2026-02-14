import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

load_dotenv()

PIPELINE_DATABASE_URL = os.getenv("PIPELINE_DATABASE_URL")
if not PIPELINE_DATABASE_URL:
    raise RuntimeError("PIPELINE_DATABASE_URL not set in .env")

engine = create_engine(PIPELINE_DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
