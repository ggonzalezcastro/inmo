from datetime import datetime
from sqlalchemy import Column, Integer, DateTime, func
from sqlalchemy.orm import declarative_base
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.sql.functions import now

Base = declarative_base()

class TimestampMixin:
    """Mixin that adds created_at and updated_at timestamps"""
    
    @declared_attr
    def created_at(cls):
        return Column(
            DateTime(timezone=True),
            server_default=now(),
            nullable=False
        )
    
    @declared_attr
    def updated_at(cls):
        return Column(
            DateTime(timezone=True),
            server_default=now(),
            onupdate=now(),
            nullable=False
        )


class IdMixin:
    """Mixin that adds an id primary key"""
    
    @declared_attr
    def id(cls):
        return Column(Integer, primary_key=True, index=True)

