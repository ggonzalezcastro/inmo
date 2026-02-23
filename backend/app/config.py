# Backward compatibility: re-export from core
from app.core.config import settings, Settings

__all__ = ["settings", "Settings"]
