import os
from functools import lru_cache

from sqlmodel import Session, create_engine


@lru_cache
def get_engine():
    DATABASE_URL = os.getenv("DATABASE_URL")
    engine = create_engine(DATABASE_URL, echo=False, pool_pre_ping=True)
    return engine


def get_session():
    engine = get_engine()
    with Session(engine) as session:
        yield session
