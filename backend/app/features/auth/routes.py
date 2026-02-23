# Auth feature routes - re-export from app.routes for feature-based structure
from app.routes import auth

router = auth.router

__all__ = ["router"]
