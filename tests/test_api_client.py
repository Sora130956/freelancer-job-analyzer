"""Tests for Freelancer API client."""
import time

import httpx
import pytest

from backend.services.api_client import FreelancerAPIClient, RateLimiter


def _projects_payload():
    return {
        "status": "success",
        "result": {
            "projects": [
                {
                    "id": 111,
                    "title": "Build a Python scraper",
                    "seo_url": "projects/python/build-scraper",
                    "type": "fixed",
                    "time_submitted": 1700000000,
                    "budget": {"minimum": 50.0, "maximum": 150.0},
                    "currency": {"code": "EUR", "exchange_rate": 1.1},
                    "jobs": [{"id": 3, "name": "Python"}],
                    "bid_stats": {"bid_count": 12, "bid_avg": 100.0},
                }
            ]
        },
    }


def _jobs_payload():
    return {
        "status": "success",
        "result": [
            {"id": 3, "name": "Python"},
            {"id": 7, "name": "Web Scraping"},
        ],
    }


def _currencies_payload():
    return {
        "status": "success",
        "result": {
            "currencies": [
                {"code": "USD", "exchange_rate": 1.0},
                {"code": "EUR", "exchange_rate": 1.1},
            ]
        },
    }


def _client_with(handler):
    transport = httpx.MockTransport(handler)
    return FreelancerAPIClient(transport=transport)


@pytest.mark.asyncio
async def test_fetch_projects_sends_required_params():
    """fetch_projects must request job_details/full_description/compact and paging params."""
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = request.url
        return httpx.Response(200, json=_projects_payload())

    client = _client_with(handler)
    projects = await client.fetch_projects(keywords="python", limit=100, offset=0)

    params = captured["url"].params
    assert captured["url"].path == "/api/projects/0.1/projects/active/"
    assert params["job_details"] == "true"
    assert params["full_description"] == "true"
    assert params["compact"] == "true"
    assert params["query"] == "python"
    assert params["limit"] == "100"
    assert params["offset"] == "0"

    assert len(projects) == 1
    assert projects[0]["id"] == 111


@pytest.mark.asyncio
async def test_fetch_projects_maps_filters_to_api_params():
    """Budget/type/time/jobs filters must map to Freelancer API parameter names."""
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = request.url
        return httpx.Response(200, json=_projects_payload())

    client = _client_with(handler)
    await client.fetch_projects(
        jobs=[3, 7],
        budget_min=100,
        budget_max=500,
        project_type="fixed",
        limit=50,
    )

    params = captured["url"].params
    assert params.get_list("jobs[]") == ["3", "7"]
    assert params["min_price"] == "100.0"
    assert params["max_price"] == "500.0"
    assert params["project_types[]"] == "fixed"


@pytest.mark.asyncio
async def test_fetch_projects_hourly_maps_to_hourly_rate_params():
    """Hourly projects must use min/max_hourly_rate instead of price params."""
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = request.url
        return httpx.Response(200, json=_projects_payload())

    client = _client_with(handler)
    await client.fetch_projects(budget_min=15, budget_max=25, project_type="hourly")

    params = captured["url"].params
    assert params["min_hourly_rate"] == "15.0"
    assert params["max_hourly_rate"] == "25.0"
    assert "min_price" not in params


@pytest.mark.asyncio
async def test_fetch_projects_raises_on_api_error():
    """Non-2xx responses must raise a clear error."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"status": "error"})

    client = _client_with(handler)
    with pytest.raises(httpx.HTTPStatusError):
        await client.fetch_projects()


@pytest.mark.asyncio
async def test_fetch_jobs_is_cached():
    """fetch_jobs must hit the network only once within the cache TTL."""
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return httpx.Response(200, json=_jobs_payload())

    client = _client_with(handler)
    first = await client.fetch_jobs()
    second = await client.fetch_jobs()

    assert len(calls) == 1
    assert calls[0] == "/api/projects/0.1/jobs/"
    assert first == second
    assert first[0]["name"] == "Python"


@pytest.mark.asyncio
async def test_fetch_jobs_refetches_after_cache_expiry():
    """Expired cache entries must trigger a new request."""
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return httpx.Response(200, json=_jobs_payload())

    client = _client_with(handler)
    await client.fetch_jobs()
    client._jobs_cache.expires_at = time.monotonic() - 1
    await client.fetch_jobs()

    assert len(calls) == 2


@pytest.mark.asyncio
async def test_fetch_currencies_returns_rate_map_and_caches():
    """fetch_currencies must return code -> exchange_rate and cache the result."""
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return httpx.Response(200, json=_currencies_payload())

    client = _client_with(handler)
    rates = await client.fetch_currencies()
    await client.fetch_currencies()

    assert len(calls) == 1
    assert rates["USD"] == 1.0
    assert rates["EUR"] == 1.1


def test_rate_limiter_allows_within_limit():
    """Requests under the limit must not wait."""
    limiter = RateLimiter(max_calls=3, period=60)

    assert limiter.time_until_available() == 0
    for _ in range(3):
        limiter.record()

    assert limiter.time_until_available() > 0


def test_rate_limiter_drops_expired_calls():
    """Calls older than the window must not count against the limit."""
    limiter = RateLimiter(max_calls=2, period=60)
    limiter.record()
    limiter.record()
    assert limiter.time_until_available() > 0

    limiter._calls = [t - 61 for t in limiter._calls]
    assert limiter.time_until_available() == 0


@pytest.mark.asyncio
async def test_client_waits_when_rate_limited(monkeypatch):
    """Client must sleep instead of exceeding the configured rate limit."""
    sleeps = []

    async def fake_sleep(seconds):
        sleeps.append(seconds)

    monkeypatch.setattr("backend.services.api_client.asyncio.sleep", fake_sleep)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_projects_payload())

    client = _client_with(handler)
    client.minute_limiter = RateLimiter(max_calls=1, period=60)

    await client.fetch_projects()
    await client.fetch_projects()

    assert len(sleeps) == 1
    assert sleeps[0] > 0
