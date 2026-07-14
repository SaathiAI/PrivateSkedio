"""
Rate Limiting and Quota Management
====================================

Prevents abuse and manages LLM API usage quotas.
"""

import time
import logging
from typing import Dict, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


@dataclass
class QuotaStatus:
    """Tracks API usage quotas."""
    daily_limit: int = 1000  # Max API calls per day
    monthly_limit: int = 25000  # Max API calls per month
    daily_used: int = 0
    monthly_used: int = 0
    daily_reset: datetime = field(default_factory=datetime.now)
    monthly_reset: datetime = field(default_factory=datetime.now)
    
    def can_use(self) -> bool:
        """Check if quota allows another API call."""
        now = datetime.now()
        
        # Reset daily counter if needed
        if now.date() > self.daily_reset.date():
            self.daily_used = 0
            self.daily_reset = now
        
        # Reset monthly counter if needed
        if now.month > self.monthly_reset.month or now.year > self.monthly_reset.year:
            self.monthly_used = 0
            self.monthly_reset = now
        
        return self.daily_used < self.daily_limit and self.monthly_used < self.monthly_limit
    
    def record_use(self, tokens_used: int = 1):
        """Record API usage."""
        self.daily_used += tokens_used
        self.monthly_used += tokens_used
    
    def get_remaining(self) -> dict:
        """Get remaining quota."""
        return {
            "daily_remaining": max(0, self.daily_limit - self.daily_used),
            "monthly_remaining": max(0, self.monthly_limit - self.monthly_used),
            "daily_used": self.daily_used,
            "monthly_used": self.monthly_used,
        }


class RateLimiter:
    """Simple token bucket rate limiter."""
    
    def __init__(self, rate: float = 10.0, max_tokens: int = 20):
        """
        Args:
            rate: Tokens added per second
            max_tokens: Maximum tokens in bucket
        """
        self.rate = rate
        self.max_tokens = max_tokens
        self.tokens = max_tokens
        self.last_refill = time.time()
    
    def _refill(self):
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_refill
        self.tokens = min(self.max_tokens, self.tokens + elapsed * self.rate)
        self.last_refill = now
    
    def acquire(self, tokens: int = 1) -> bool:
        """Try to acquire tokens. Returns True if successful."""
        self._refill()
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False
    
    def wait_time(self, tokens: int = 1) -> float:
        """Get estimated wait time for tokens."""
        self._refill()
        if self.tokens >= tokens:
            return 0.0
        return (tokens - self.tokens) / self.rate


class QuotaManager:
    """Manages rate limiting and quota for intake agent."""
    
    def __init__(self, rate_limit: float = 10.0, daily_limit: int = 1000, monthly_limit: int = 25000):
        self.rate_limiter = RateLimiter(rate=rate_limit)
        self.quota = QuotaStatus(daily_limit=daily_limit, monthly_limit=monthly_limit)
        self._blocked_until: Optional[float] = None
    
    def can_proceed(self) -> bool:
        """Check if request can proceed (rate limit + quota)."""
        # Check if we're in a blocked period
        if self._blocked_until and time.time() < self._blocked_until:
            return False
        
        # Check rate limit
        if not self.rate_limiter.acquire():
            logger.warning("[QUOTA] Rate limit exceeded")
            self._blocked_until = time.time() + 1.0  # Block for 1 second
            return False
        
        # Check quota
        if not self.quota.can_use():
            logger.error("[QUOTA] API quota exceeded")
            self._blocked_until = time.time() + 60.0  # Block for 1 minute
            return False
        
        return True
    
    def record_use(self, tokens_used: int = 1):
        """Record API usage."""
        self.quota.record_use(tokens_used)
    
    def get_status(self) -> dict:
        """Get current quota and rate limit status."""
        return {
            "rate_limiter": {
                "tokens": self.rate_limiter.tokens,
                "max_tokens": self.rate_limiter.max_tokens,
            },
            "quota": self.quota.get_remaining(),
            "blocked_until": self._blocked_until,
        }
    
    def reset(self):
        """Reset all limits (for testing)."""
        self.rate_limiter.tokens = self.rate_limiter.max_tokens
        self.quota.daily_used = 0
        self.quota.monthly_used = 0
        self._blocked_until = None


# Global instance
_quota_manager = QuotaManager()


def get_quota_manager() -> QuotaManager:
    """Get the global quota manager instance."""
    return _quota_manager
