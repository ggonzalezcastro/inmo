"""
Rate limiter middleware for FastAPI

Uses Redis to track request counts per IP/user and enforce rate limits.
Helps prevent API abuse and DDoS attacks.
"""
import time
import logging
from typing import Optional, Callable
from fastapi import Request, Response, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from redis import Redis
from app.config import settings

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Simple sliding window rate limiter using Redis.
    
    Tracks request counts per client IP and blocks requests 
    that exceed the configured limit.
    """
    
    def __init__(
        self,
        redis_url: str = None,
        requests_per_minute: int = 60,
        burst_limit: int = 10,
        enabled: bool = True
    ):
        """
        Initialize rate limiter.
        
        Args:
            redis_url: Redis connection URL
            requests_per_minute: Max requests allowed per minute
            burst_limit: Max requests allowed in a 5-second window (burst protection)
            enabled: Whether rate limiting is enabled
        """
        self.requests_per_minute = requests_per_minute
        self.burst_limit = burst_limit
        self.enabled = enabled
        self.redis: Optional[Redis] = None
        
        if enabled and redis_url:
            try:
                self.redis = Redis.from_url(redis_url, decode_responses=True)
                self.redis.ping()
                logger.info(f"Rate limiter connected to Redis. Limit: {requests_per_minute}/min")
            except Exception as e:
                logger.warning(f"Rate limiter could not connect to Redis: {e}. Disabled.")
                self.enabled = False
    
    def _get_client_key(self, request: Request, suffix: str = "") -> str:
        """Get unique identifier for the client"""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            client_ip = forwarded.split(",")[0].strip()
        else:
            client_ip = request.client.host if request.client else "unknown"
        base = f"rate_limit:{client_ip}"
        return f"{base}:{suffix}" if suffix else base

    def _get_path_limits(self, path: str) -> Optional[tuple[str, int, int]]:
        """
        Return (key_suffix, limit, window_seconds) for path-specific limits, or None for default.
        """
        if path.strip("/") == "auth/login":
            return ("auth_login", 5, 60)   # 5 attempts per minute
        if path.strip("/") == "auth/register":
            return ("auth_register", 3, 3600)  # 3 per hour
        return None

    def is_allowed(self, request: Request) -> tuple[bool, dict]:
        """
        Check if request is allowed under rate limit.
        
        Returns:
            Tuple of (is_allowed, info_dict with remaining/reset values)
        """
        if not self.enabled or not self.redis:
            return True, {"remaining": -1, "reset": 0}

        path_limits = self._get_path_limits(request.url.path)
        if path_limits:
            suffix, limit, window_seconds = path_limits
            key = self._get_client_key(request, suffix)
        else:
            key = self._get_client_key(request)
            limit = self.requests_per_minute
            window_seconds = 60

        now = int(time.time())
        window_start = now - window_seconds

        pipe = self.redis.pipeline()

        try:
            pipe.zadd(key, {str(now): now})
            pipe.zremrangebyscore(key, 0, window_start)
            pipe.zcard(key)
            pipe.expire(key, window_seconds + 60)

            results = pipe.execute()
            request_count = results[2]

            remaining = max(0, limit - request_count)
            reset = now + window_seconds

            info = {
                "remaining": remaining,
                "reset": reset,
                "limit": limit,
                "current": request_count
            }

            if request_count > limit:
                logger.warning("Rate limit exceeded for %s: %s/%s", key, request_count, limit)
                return False, info

            return True, info
            
        except Exception as e:
            logger.error(f"Rate limiter error: {e}")
            # Fail closed for auth endpoints (security); fail open for others (availability)
            path_limits = self._get_path_limits(request.url.path)
            if path_limits:
                return False, {"remaining": 0, "reset": 0, "error": "Rate limit unavailable"}
            return True, {"remaining": -1, "reset": 0, "error": str(e)}


class RateLimitMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware for rate limiting"""
    
    def __init__(
        self,
        app,
        rate_limiter: RateLimiter,
        exclude_paths: list[str] = None
    ):
        super().__init__(app)
        self.rate_limiter = rate_limiter
        self.exclude_paths = exclude_paths or ["/health", "/docs", "/redoc", "/openapi.json"]
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip rate limiting for excluded paths
        if any(request.url.path.startswith(path) for path in self.exclude_paths):
            return await call_next(request)
        
        # Check rate limit
        is_allowed, info = self.rate_limiter.is_allowed(request)
        
        if not is_allowed:
            return Response(
                content='{"detail": "Rate limit exceeded. Please try again later."}',
                status_code=429,
                media_type="application/json",
                headers={
                    "X-RateLimit-Limit": str(info.get("limit", 0)),
                    "X-RateLimit-Remaining": str(info.get("remaining", 0)),
                    "X-RateLimit-Reset": str(info.get("reset", 0)),
                    "Retry-After": "60"
                }
            )
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers to response
        if info.get("remaining", -1) >= 0:
            response.headers["X-RateLimit-Limit"] = str(info.get("limit", 0))
            response.headers["X-RateLimit-Remaining"] = str(info.get("remaining", 0))
            response.headers["X-RateLimit-Reset"] = str(info.get("reset", 0))
        
        return response


# Singleton rate limiter instance
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """Get or create the rate limiter singleton"""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter(
            redis_url=settings.REDIS_URL,
            requests_per_minute=60,  # 60 requests per minute
            burst_limit=10,
            enabled=settings.ENVIRONMENT == "production"  # Only in production
        )
    return _rate_limiter
