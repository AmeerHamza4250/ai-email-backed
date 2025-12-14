"""
Database base configuration and session management.
"""
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import DeclarativeBase

# Use DeclarativeBase for SQLAlchemy 2.0+
class Base(DeclarativeBase):
    """Base class for all database models."""
    pass

# For backward compatibility
BaseModel = Base

