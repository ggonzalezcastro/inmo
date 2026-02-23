# Backward compatibility: re-export from core
from app.core.database import (
    engine,
    AsyncSessionLocal,
    get_db,
    init_db,
    close_db,
)
from app.models.base import Base

__all__ = [
    "Base",
    "engine",
    "AsyncSessionLocal",
    "get_db",
    "init_db",
    "close_db",
]
