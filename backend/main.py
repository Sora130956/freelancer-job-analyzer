"""Main FastAPI application."""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.config import settings
from backend.dependencies import set_api_client
from backend.models import HealthResponse
from backend.routes import export, jobs, search
from backend.services.api_client import FreelancerAPIClient

logger = logging.getLogger(__name__)

# 上游返回这些状态码时原样透出：客户端需要区别对待
# （404 查无此项、429 需退避重试），其余 5xx 统一归一为 502。
PASSTHROUGH_STATUS = {404, 429}
UPSTREAM_FAILURE_STATUS = 502

# 前端构建产物目录（frontend/npm run build 的输出）。
# 用相对本文件的路径而非 cwd，保证从任意目录启动 uvicorn 都能找到。
FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启停时管理 API 客户端单例。

    在这里创建而不是在模块顶层 import 时创建：httpx.AsyncClient 需要绑定
    运行中的事件循环，同时也保证进程退出前连接池被显式关掉、不泄漏。
    """
    client = FreelancerAPIClient()
    set_api_client(client)
    try:
        yield
    finally:
        set_api_client(None)
        await client.close()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(httpx.HTTPStatusError)
async def upstream_status_error_handler(
    request: Request, exc: httpx.HTTPStatusError
) -> JSONResponse:
    """把上游 API 的错误状态码翻译成本服务的响应。

    不让 httpx 异常直接冒泡成 500：那样前端只能看到「服务器错误」，
    无法区分「上游限流、稍后重试」和「本服务真的有 bug」。
    """
    upstream_status = exc.response.status_code
    status_code = (
        upstream_status
        if upstream_status in PASSTHROUGH_STATUS
        else UPSTREAM_FAILURE_STATUS
    )
    logger.warning(
        "upstream %s returned %s for %s (mapped to %s)",
        exc.request.url,
        upstream_status,
        exc.response.url,
        status_code,
    )
    return JSONResponse(
        status_code=status_code,
        content={"detail": f"Freelancer API error (upstream {upstream_status})"},
    )


@app.exception_handler(httpx.HTTPError)
async def upstream_transport_error_handler(
    request: Request, exc: httpx.HTTPError
) -> JSONResponse:
    """连不上上游 / 超时同样归一为 502，语义是「网关拿不到数据」。"""
    logger.warning("upstream transport error for %s: %s", exc.request.url, exc)
    return JSONResponse(
        status_code=UPSTREAM_FAILURE_STATUS,
        content={"detail": "Freelancer API unreachable"},
    )


app.include_router(jobs.router, prefix="/api", tags=["jobs"])
app.include_router(search.router, prefix="/api", tags=["search"])
app.include_router(export.router, prefix="/api", tags=["export"])


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="ok",
        version=settings.APP_VERSION
    )


# ---------------------------------------------------------------------------
# 前端静态资源（生产环境单端口部署）
#
# 必须写在所有 API 路由注册之后：Starlette 按注册顺序匹配，
# 挂在 "/" 上的 StaticFiles 会吃掉一切路径，先注册就会盖住 /api 和 /health。
#
# dist 不存在时（纯后端开发、CI 只跑 pytest）整段跳过，
# 否则 StaticFiles 会在 import 期直接抛 RuntimeError 让测试全红。
# ---------------------------------------------------------------------------
if FRONTEND_DIST.is_dir():
    # /assets 下是带 hash 的 js/css，交给 StaticFiles 处理（含 304 协商缓存）。
    app.mount(
        "/assets",
        StaticFiles(directory=FRONTEND_DIST / "assets"),
        name="assets",
    )

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        """把非 API 路径统一回 index.html，交给前端路由处理。

        命中真实文件（favicon、vite.svg 等）时直接返回该文件；
        否则回 index.html，这样刷新任意前端路径都不会 404。
        """
        # 未匹配的 /api 路径必须是 404 JSON，不能回 index.html：
        # 否则前端 fetch 拿到 HTML 再 .json() 会炸在解析上，
        # 真正的「路由写错了」被伪装成难查的前端报错。
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not Found")

        candidate = (FRONTEND_DIST / full_path).resolve()
        # 防目录穿越：candidate 必须仍在 dist 内，否则忽略、回落到 index.html。
        if (
            full_path
            and FRONTEND_DIST in candidate.parents
            and candidate.is_file()
        ):
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST / "index.html")
else:
    logger.warning(
        "frontend build not found at %s; serving API only "
        "(run `cd frontend && npm run build` to enable the SPA)",
        FRONTEND_DIST,
    )
