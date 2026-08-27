"""Tests for API routes (/api/jobs, /api/search, /api/export)."""
import logging
from io import BytesIO

import httpx
import openpyxl
import pytest
from fastapi.testclient import TestClient

from backend.dependencies import get_api_client
from backend.main import app
from backend.services.api_client import FreelancerAPIClient

JOBS_PATH = "/api/projects/0.1/jobs/"
CURRENCIES_PATH = "/api/projects/0.1/currencies/"
PROJECTS_PATH = "/api/projects/0.1/projects/active/"


def _project(project_id: int):
    """构造一条真实结构的项目数据（currency 与 budget 同级）。"""
    return {
        "id": project_id,
        "title": f"Python scraper {project_id}",
        "seo_url": f"projects/python/scraper-{project_id}",
        "type": "fixed",
        "time_submitted": 1700000000,
        "budget": {"minimum": 100.0, "maximum": 200.0},
        "currency": {"code": "EUR", "exchange_rate": 1.1},
        "jobs": [{"id": 3, "name": "Python"}, {"id": 7, "name": "Web Scraping"}],
        "bid_stats": {"bid_count": 12, "bid_avg": 150.0},
    }


def _jobs_payload(count: int = 2):
    return {"status": "success", "result": [
        {"id": i, "name": f"Skill {i}"} for i in range(1, count + 1)
    ]}


def _currencies_payload():
    return {"status": "success", "result": {"currencies": [
        {"code": "USD", "exchange_rate": 1.0},
        {"code": "EUR", "exchange_rate": 1.1},
    ]}}


def _client_for(handler):
    """用 MockTransport 造一个假的 API 客户端，供 dependency_overrides 注入。"""
    return FreelancerAPIClient(transport=httpx.MockTransport(handler))


def _test_client(handler):
    """返回注入了假客户端的 TestClient，测试结束需调用 clear_overrides。"""
    app.dependency_overrides[get_api_client] = lambda: _client_for(handler)
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


def test_jobs_endpoint_returns_skill_tags():
    """GET /api/jobs 返回技能标签数组。"""
    def handler(request):
        assert request.url.path == JOBS_PATH
        return httpx.Response(200, json=_jobs_payload(3))

    response = _test_client(handler).get("/api/jobs")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3
    assert data[0] == {"id": 1, "name": "Skill 1"}


def test_search_returns_projects_with_usd_and_stats():
    """GET /api/search 返回 USD 换算后的项目 + 技能频次 + 预算分布。"""
    def handler(request):
        if request.url.path == CURRENCIES_PATH:
            return httpx.Response(200, json=_currencies_payload())
        return httpx.Response(200, json={
            "status": "success",
            "result": {"projects": [_project(1), _project(2)]},
        })

    response = _test_client(handler).get("/api/search?keywords=python&limit=100")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["projects"]) == 2
    assert data["projects"][0]["budget_max_usd"] == 220.0
    assert data["skills_frequency"]["Python"] == 2
    assert data["budget_distribution"]["$150-$500"] == 2


def test_search_paginates_with_offset_until_limit():
    """limit > 100 时必须按 offset 循环拉取（每页 100）。"""
    offsets = []

    def handler(request):
        if request.url.path == CURRENCIES_PATH:
            return httpx.Response(200, json=_currencies_payload())
        offset = int(request.url.params["offset"])
        offsets.append(offset)
        return httpx.Response(200, json={
            "status": "success",
            "result": {"projects": [_project(offset + i) for i in range(100)]},
        })

    response = _test_client(handler).get("/api/search?limit=300")

    assert response.status_code == 200
    assert offsets == [0, 100, 200]
    assert response.json()["total"] == 300


def test_search_stops_early_when_page_not_full():
    """某页返回不足 100 条说明数据已取完，不再继续请求。"""
    offsets = []

    def handler(request):
        if request.url.path == CURRENCIES_PATH:
            return httpx.Response(200, json=_currencies_payload())
        offsets.append(int(request.url.params["offset"]))
        return httpx.Response(200, json={
            "status": "success",
            "result": {"projects": [_project(1), _project(2)]},
        })

    response = _test_client(handler).get("/api/search?limit=500")

    assert offsets == [0]
    assert response.json()["total"] == 2


def test_search_limit_above_500_is_rejected():
    """limit 上限 500（AC-001），超出应返回 422。"""
    def handler(request):
        return httpx.Response(200, json=_currencies_payload())

    response = _test_client(handler).get("/api/search?limit=600")

    assert response.status_code == 422


def test_search_forwards_filters_to_api():
    """筛选面板字段必须原样传给 API 客户端。"""
    captured = {}

    def handler(request):
        if request.url.path == CURRENCIES_PATH:
            return httpx.Response(200, json=_currencies_payload())
        captured["params"] = request.url.params
        return httpx.Response(200, json={"status": "success", "result": {"projects": []}})

    response = _test_client(handler).get(
        "/api/search?keywords=scraper&jobs[]=3&jobs[]=7"
        "&budget_min=100&budget_max=500&project_type=fixed&time_range=24"
    )

    assert response.status_code == 200
    params = captured["params"]
    assert params["query"] == "scraper"
    assert params.get_list("jobs[]") == ["3", "7"]
    assert params["min_price"] == "100.0"
    assert params["max_price"] == "500.0"
    assert params["project_types[]"] == "fixed"
    assert "from_time" in params


def test_search_empty_result_returns_zero_stats():
    """无结果时返回空列表和全 0 分布，而不是报错。"""
    def handler(request):
        if request.url.path == CURRENCIES_PATH:
            return httpx.Response(200, json=_currencies_payload())
        return httpx.Response(200, json={"status": "success", "result": {"projects": []}})

    data = _test_client(handler).get("/api/search").json()

    assert data["total"] == 0
    assert data["projects"] == []
    assert data["skills_frequency"] == {}
    assert set(data["budget_distribution"].values()) == {0}


def test_export_returns_xlsx_with_three_sheets():
    """GET /api/export 返回三 Sheet 的 xlsx 文件流。"""
    def handler(request):
        if request.url.path == CURRENCIES_PATH:
            return httpx.Response(200, json=_currencies_payload())
        return httpx.Response(200, json={
            "status": "success",
            "result": {"projects": [_project(1)]},
        })

    response = _test_client(handler).get("/api/export?keywords=python")

    assert response.status_code == 200
    assert response.headers["content-type"] == (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert "attachment" in response.headers["content-disposition"]
    workbook = openpyxl.load_workbook(BytesIO(response.content))
    assert workbook.sheetnames == [
        "Projects", "Skills Frequency", "Budget Distribution"
    ]


def test_upstream_429_returns_429():
    """上游限流必须原样透出 429，让前端知道要退避重试。"""
    def handler(request):
        return httpx.Response(429, json={"status": "error"})

    response = _test_client(handler).get("/api/jobs")

    assert response.status_code == 429
    assert "detail" in response.json()


def test_upstream_404_returns_404():
    """上游 404 透出 404。"""
    def handler(request):
        return httpx.Response(404, json={"status": "error"})

    response = _test_client(handler).get("/api/jobs")

    assert response.status_code == 404


def test_upstream_500_returns_502():
    """上游 5xx 归一为 502：错不在本服务，但请求确实失败了。"""
    def handler(request):
        return httpx.Response(500, json={"status": "error"})

    response = _test_client(handler).get("/api/jobs")

    assert response.status_code == 502


def test_network_error_returns_502():
    """网络异常（超时/连不上）同样归一为 502。"""
    def handler(request):
        raise httpx.ConnectTimeout("timeout")

    response = _test_client(handler).get("/api/jobs")

    assert response.status_code == 502


def test_status_error_handler_logs_warning():
    """上游 4xx/5xx 必须留下日志，便于服务端排查上游故障。"""
    records = []
    handler = logging.Handler()
    handler.emit = records.append

    logger = logging.getLogger("backend.main")
    logger.addHandler(handler)
    try:
        def upstream_handler(request):
            return httpx.Response(503, json={"status": "error"})

        _test_client(upstream_handler).get("/api/jobs")
    finally:
        logger.removeHandler(handler)

    assert any(record.levelno == logging.WARNING for record in records)


def test_transport_error_handler_logs_warning():
    """连不上上游同样要留日志。"""
    records = []
    handler = logging.Handler()
    handler.emit = records.append

    logger = logging.getLogger("backend.main")
    logger.addHandler(handler)
    try:
        def network_handler(request):
            raise httpx.ConnectTimeout("timeout")

        _test_client(network_handler).get("/api/jobs")
    finally:
        logger.removeHandler(handler)

    assert any(record.levelno == logging.WARNING for record in records)
