"""
Rate Limiting
=============
Rate limiting middleware to prevent API abuse.

Author: VidyuthLabs
Date: May 1, 2026
"""

import time
import logging
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """Rate limit configuration."""
    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    requests_per_day: int = 10000
    burst_size: int = 10  # Allow burst of requests


class RateLimiter:
    """
    Token bucket rate limiter.
    
    Features:
    - Per-user rate limiting
    - Per-IP rate limiting
    - Multiple time windows (minute, hour, day)
    - Burst support
    - Redis-backed (for distributed systems)
    
    Algorithm: Token Bucket
    - Each user/IP has a bucket of tokens
    - Tokens are added at a fixed rate
    - Each request consumes 1 token
    - If no tokens available, request is rejected
    """
    
    def __init__(self, config: Optional[RateLimitConfig] = None):
        """
        Initialize rate limiter.
        
        Args:
            config: Rate limit configuration
        """
        self.config = config or RateLimitConfig()
        
        # In-memory storage (use Redis in production)
        self.buckets: Dict[str, Dict[str, any]] = {}
        
        logger.info(
            f"Rate limiter initialized: "
            f"{self.config.requests_per_minute} req/min, "
            f"{self.config.requests_per_hour} req/hour, "
            f"{self.config.requests_per_day} req/day"
        )
    
    def check_rate_limit(
        self,
        identifier: str,
        cost: int = 1
    ) -> Tuple[bool, Optional[int]]:
        """
        Check if request is within rate limit.
        
        Args:
            identifier: User ID or IP address
            cost: Request cost (default: 1)
        
        Returns:
            (allowed, retry_after_seconds)
        """
        now = time.time()
        
        # Get or create bucket
        if identifier not in self.buckets:
            self.buckets[identifier] = {
                "minute": {
                    "tokens": self.config.requests_per_minute,
                    "last_update": now
                },
                "hour": {
                    "tokens": self.config.requests_per_hour,
                    "last_update": now
                },
                "day": {
                    "tokens": self.config.requests_per_day,
                    "last_update": now
                }
            }
        
        bucket = self.buckets[identifier]
        
        # Check each time window
        windows = [
            ("minute", 60, self.config.requests_per_minute),
            ("hour", 3600, self.config.requests_per_hour),
            ("day", 86400, self.config.requests_per_day)
        ]
        
        for window_name, window_seconds, max_tokens in windows:
            window = bucket[window_name]
            
            # Refill tokens based on time elapsed
            elapsed = now - window["last_update"]
            refill_rate = max_tokens / window_seconds
            tokens_to_add = elapsed * refill_rate
            
            window["tokens"] = min(
                max_tokens,
                window["tokens"] + tokens_to_add
            )
            window["last_update"] = now
            
            # Check if enough tokens
            if window["tokens"] < cost:
                # Rate limit exceeded
                retry_after = int((cost - window["tokens"]) / refill_rate)
                
                logger.warning(
                    f"Rate limit exceeded for {identifier} - "
                    f"Window: {window_name}, Retry after: {retry_after}s"
                )
                
                return False, retry_after
            
            # Consume tokens
            window["tokens"] -= cost
        
        return True, None
    
    def get_remaining(self, identifier: str) -> Dict[str, int]:
        """
        Get remaining requests for identifier.
        
        Args:
            identifier: User ID or IP address
        
        Returns:
            Remaining requests per window
        """
        if identifier not in self.buckets:
            return {
                "minute": self.config.requests_per_minute,
                "hour": self.config.requests_per_hour,
                "day": self.config.requests_per_day
            }
        
        bucket = self.buckets[identifier]
        
        return {
            "minute": int(bucket["minute"]["tokens"]),
            "hour": int(bucket["hour"]["tokens"]),
            "day": int(bucket["day"]["tokens"])
        }
    
    def reset(self, identifier: str):
        """Reset rate limit for identifier."""
        if identifier in self.buckets:
            del self.buckets[identifier]
            logger.info(f"Rate limit reset for {identifier}")


# Global rate limiter instance
_rate_limiter = None


def get_rate_limiter() -> RateLimiter:
    """Get or create global rate limiter instance."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter


# ===================================================================
#  FastAPI Middleware
# ===================================================================

class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware for FastAPI.
    
    Usage:
        app.add_middleware(RateLimitMiddleware)
    """
    
    def __init__(self, app, config: Optional[RateLimitConfig] = None):
        """
        Initialize middleware.
        
        Args:
            app: FastAPI application
            config: Rate limit configuration
        """
        super().__init__(app)
        self.rate_limiter = RateLimiter(config)
    
    async def dispatch(self, request: Request, call_next):
        """Process request with rate limiting."""
        # Skip rate limiting for health checks and docs
        if request.url.path in ["/health", "/docs", "/redoc", "/openapi.json"]:
            return await call_next(request)
        
        # Get identifier (user ID or IP)
        identifier = self._get_identifier(request)
        
        # Check rate limit
        allowed, retry_after = self.rate_limiter.check_rate_limit(identifier)
        
        if not allowed:
            # Rate limit exceeded
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Retry after {retry_after} seconds.",
                headers={"Retry-After": str(retry_after)}
            )
        
        # Add rate limit headers
        remaining = self.rate_limiter.get_remaining(identifier)
        
        response = await call_next(request)
        
        response.headers["X-RateLimit-Limit-Minute"] = str(self.rate_limiter.config.requests_per_minute)
        response.headers["X-RateLimit-Limit-Hour"] = str(self.rate_limiter.config.requests_per_hour)
        response.headers["X-RateLimit-Limit-Day"] = str(self.rate_limiter.config.requests_per_day)
        response.headers["X-RateLimit-Remaining-Minute"] = str(remaining["minute"])
        response.headers["X-RateLimit-Remaining-Hour"] = str(remaining["hour"])
        response.headers["X-RateLimit-Remaining-Day"] = str(remaining["day"])
        
        return response
    
    def _get_identifier(self, request: Request) -> str:
        """
        Get identifier for rate limiting.
        
        Priority:
        1. User ID (from JWT token)
        2. API key
        3. IP address
        
        Args:
            request: FastAPI request
        
        Returns:
            Identifier string
        """
        # Try to get user ID from JWT token
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]
            
            # Try to decode token
            try:
                from vanl.backend.core.auth import decode_access_token
                payload = decode_access_token(token)
                if payload and "user_id" in payload:
                    return f"user:{payload['user_id']}"
            except:
                pass
        
        # Fall back to IP address
        # Check for X-Forwarded-For header (proxy/load balancer)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Get first IP (client IP)
            ip = forwarded_for.split(",")[0].strip()
        else:
            ip = request.client.host if request.client else "unknown"
        
        return f"ip:{ip}"


# ===================================================================
#  Dependency for Manual Rate Limiting
# ===================================================================

async def check_rate_limit(request: Request):
    """
    Dependency for manual rate limiting in specific endpoints.
    
    Usage:
        @app.post("/expensive-operation", dependencies=[Depends(check_rate_limit)])
        async def expensive_operation():
            ...
    """
    rate_limiter = get_rate_limiter()
    
    # Get identifier
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:]
        try:
            from vanl.backend.core.auth import decode_access_token
            payload = decode_access_token(token)
            if payload and "user_id" in payload:
                identifier = f"user:{payload['user_id']}"
            else:
                identifier = f"ip:{request.client.host}"
        except:
            identifier = f"ip:{request.client.host}"
    else:
        identifier = f"ip:{request.client.host}"
    
    # Check rate limit with higher cost for expensive operations
    allowed, retry_after = rate_limiter.check_rate_limit(identifier, cost=5)
    
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Retry after {retry_after} seconds.",
            headers={"Retry-After": str(retry_after)}
        )


# ===================================================================
#  Redis-Backed Rate Limiter (Production)
# ===================================================================

class RedisRateLimiter:
    """
    Redis-backed rate limiter for distributed systems.
    
    Use this in production for multi-instance deployments.
    """
    
    def __init__(self, redis_client, config: Optional[RateLimitConfig] = None):
        """
        Initialize Redis rate limiter.
        
        Args:
            redis_client: Redis client instance
            config: Rate limit configuration
        """
        self.redis = redis_client
        self.config = config or RateLimitConfig()
        logger.info("Redis rate limiter initialized")
    
    def check_rate_limit(
        self,
        identifier: str,
        cost: int = 1
    ) -> Tuple[bool, Optional[int]]:
        """
        Check rate limit using Redis.
        
        Args:
            identifier: User ID or IP address
            cost: Request cost
        
        Returns:
            (allowed, retry_after_seconds)
        """
        now = int(time.time())
        
        # Check each time window
        windows = [
            ("minute", 60, self.config.requests_per_minute),
            ("hour", 3600, self.config.requests_per_hour),
            ("day", 86400, self.config.requests_per_day)
        ]
        
        for window_name, window_seconds, max_requests in windows:
            key = f"ratelimit:{identifier}:{window_name}"
            
            # Use Redis sorted set with timestamps
            # Remove old entries
            self.redis.zremrangebyscore(key, 0, now - window_seconds)
            
            # Count requests in window
            count = self.redis.zcard(key)
            
            if count >= max_requests:
                # Rate limit exceeded
                # Get oldest entry to calculate retry_after
                oldest = self.redis.zrange(key, 0, 0, withscores=True)
                if oldest:
                    oldest_time = int(oldest[0][1])
                    retry_after = window_seconds - (now - oldest_time)
                else:
                    retry_after = window_seconds
                
                return False, retry_after
            
            # Add current request
            self.redis.zadd(key, {f"{now}:{id(identifier)}": now})
            
            # Set expiration
            self.redis.expire(key, window_seconds)
        
        return True, None
