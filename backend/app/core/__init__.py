# Core: config, database, cache
# Import config only here to avoid circular imports; use app.core.database / app.core.cache as needed
from app.core.config import settings, Settings

__all__ = ["settings", "Settings"]
