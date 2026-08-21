"""Freelancer.com API client with rate limiting and in-memory caching."""
import asyncio
import time
from typing import Any, List, Optional

import httpx

from backend.config import settings

PROJECTS_ENDPOINT = "/api/projects/0.1/projects/active/"
JOBS_ENDPOINT = "/api/projects/0.1/jobs/"
CURRENCIES_ENDPOINT = "/api/projects/0.1/currencies/"

JOBS_CACHE_TTL = 60 * 60  # 1 hour
CURRENCIES_CACHE_TTL = 24 * 60 * 60  # 24 hours


class RateLimiter:
    """Sliding-window rate limiter.

    Tracks call timestamps within a time window; when the window is full,
    reports how long the caller must wait before the next call is allowed.
    """

    def __init__(self, max_calls: int, period: float):
        self.max_calls = max_calls
        self.period = period
        self._calls: List[float] = []

    def _prune(self, now: float) -> None:
        """Drop timestamps older than the window."""
        cutoff = now - self.period
        self._calls = [t for t in self._calls if t > cutoff]

    def time_until_available(self) -> float:
        """Seconds to wait before the next call is allowed (0 = no wait)."""
        now = time.monotonic()
        self._prune(now)
        if len(self._calls) < self.max_calls:
            return 0
        oldest = self._calls[0]
        return max(0.0, oldest + self.period - now)

    def record(self) -> None:
        """Record a call at the current time."""
        self._calls.append(time.monotonic())


class CacheEntry:
    """A cached value with an absolute expiry time."""

    def __init__(self, value: Any, ttl: float):
        self.value = value
        self.expires_at = time.monotonic() + ttl

    @property
    def is_valid(self) -> bool:
        return time.monotonic() < self.expires_at


class FreelancerAPIClient:
    """Async client for the Freelancer.com public API."""

    def __init__(self, transport: Optional[httpx.AsyncBaseTransport] = None):
        self._client = httpx.AsyncClient(
            base_url=settings.FREELANCER_API_BASE_URL,
            timeout=30.0,
            transport=transport,
        )
        self.minute_limiter = RateLimiter(
            max_calls=settings.RATE_LIMIT_PER_MINUTE, period=60
        )
        self.hour_limiter = RateLimiter(
            max_calls=settings.RATE_LIMIT_PER_HOUR, period=3600
        )
        self._jobs_cache: Optional[CacheEntry] = None
        self._currencies_cache: Optional[CacheEntry] = None

    async def close(self) -> None:
        await self._client.aclose()

    async def _throttle(self) -> None:
        """Wait until both rate limit windows allow a new request."""
        for limiter in (self.minute_limiter, self.hour_limiter):
            wait = limiter.time_until_available()
            if wait > 0:
                await asyncio.sleep(wait)

    async def _get(self, path: str, params: Optional[dict] = None) -> dict:
        """Rate-limited GET returning parsed JSON; raises on HTTP errors."""
        await self._throttle()
        self.minute_limiter.record()
        self.hour_limiter.record()

        response = await self._client.get(path, params=params)
        response.raise_for_status()
        return response.json()

    async def fetch_projects(
        self,
        keywords: Optional[str] = None,
        jobs: Optional[List[int]] = None,
        budget_min: Optional[float] = None,
        budget_max: Optional[float] = None,
        project_type: Optional[str] = None,
        offset: int = 0,
        limit: int = 100,
    ) -> List[dict]:
        """Search active projects. Returns the raw project dicts."""
        params: List[tuple] = [
            ("job_details", "true"),
            ("full_description", "true"),
            ("compact", "true"),
            ("offset", str(offset)),
            ("limit", str(limit)),
        ]
        if keywords:
            params.append(("query", keywords))
        if jobs:
            for job_id in jobs:
                params.append(("jobs[]", str(job_id)))
        if project_type:
            params.append(("project_types[]", project_type))

        # Hourly projects use hourly-rate params; fixed (or unspecified) use price params
        if project_type == "hourly":
            if budget_min is not None:
                params.append(("min_hourly_rate", str(float(budget_min))))
            if budget_max is not None:
                params.append(("max_hourly_rate", str(float(budget_max))))
        else:
            if budget_min is not None:
                params.append(("min_price", str(float(budget_min))))
            if budget_max is not None:
                params.append(("max_price", str(float(budget_max))))

        data = await self._get(PROJECTS_ENDPOINT, params=params)
        return data.get("result", {}).get("projects", [])

    async def fetch_jobs(self) -> List[dict]:
        """Fetch all skill tags. Cached in memory for 1 hour."""
        if self._jobs_cache and self._jobs_cache.is_valid:
            return self._jobs_cache.value

        data = await self._get(JOBS_ENDPOINT)
        jobs = data.get("result", [])
        self._jobs_cache = CacheEntry(jobs, JOBS_CACHE_TTL)
        return jobs

    async def fetch_currencies(self) -> dict:
        """Fetch currencies as a {code: exchange_rate} map. Cached for 24 hours."""
        if self._currencies_cache and self._currencies_cache.is_valid:
            return self._currencies_cache.value

        data = await self._get(CURRENCIES_ENDPOINT)
        currencies = data.get("result", {}).get("currencies", [])
        rates = {c["code"]: c["exchange_rate"] for c in currencies}
        self._currencies_cache = CacheEntry(rates, CURRENCIES_CACHE_TTL)
        return rates
