"""Tests for main FastAPI application."""
import pytest
from fastapi.testclient import TestClient

from backend.main import FRONTEND_DIST


def test_health_endpoint():
    """Test health check endpoint returns correct status."""
    from backend.main import app
    
    client = TestClient(app)
    response = client.get("/health")
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data
    assert data["version"] == "1.0.0"


def test_cors_middleware():
    """Test CORS middleware is configured."""
    from backend.main import app
    
    client = TestClient(app)
    response = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET"
        }
    )
    
    assert response.status_code == 200
    assert "access-control-allow-origin" in response.headers


# SPA 静态托管相关的测试依赖 frontend/dist 存在（未 build 时整段挂载被跳过），
# 所以统一挂一个 skipif，避免纯后端环境 / CI 未构建前端时报红。
requires_frontend_build = pytest.mark.skipif(
    not FRONTEND_DIST.is_dir(),
    reason="frontend/dist not built; run `cd frontend && npm run build`",
)


@requires_frontend_build
def test_unknown_api_path_returns_json_404():
    """未匹配的 /api 路径必须是 404 JSON，不能被 SPA catch-all 吞成 index.html。

    回落成 HTML 会让前端 fetch 在 .json() 上报解析错误，
    把「后端路由不存在」伪装成前端 bug。
    """
    from backend.main import app

    client = TestClient(app)
    response = client.get("/api/definitely-not-a-route")

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")
    assert response.json()["detail"] == "Not Found"


@requires_frontend_build
def test_spa_fallback_serves_index_for_deep_link():
    """任意前端深链接刷新都应拿到 index.html，由前端路由接管。"""
    from backend.main import app

    client = TestClient(app)
    response = client.get("/some/deep/route")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert '<div id="root"' in response.text
