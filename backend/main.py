"""Main FastAPI application."""
import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

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
