import os
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

def database_url():
    url=os.getenv("CLOUDOPS_DATABASE_URL","")
    if not url: raise RuntimeError("CLOUDOPS_DATABASE_URL is required for the platform database")
    if url.startswith("postgres://"): return "postgresql+psycopg://"+url.removeprefix("postgres://")
    if url.startswith("postgresql://"): return "postgresql+psycopg://"+url.removeprefix("postgresql://")
    return url

def make_engine(url=None):
    return create_engine(url or database_url(),pool_pre_ping=True,future=True)

def make_session_factory(engine=None):
    return sessionmaker(bind=engine or make_engine(),autoflush=False,expire_on_commit=False,class_=Session)
