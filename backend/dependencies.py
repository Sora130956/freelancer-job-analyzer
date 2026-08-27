"""Shared FastAPI dependencies (API client singleton access)."""
from typing import Optional

from fastapi import HTTPException

from backend.services.api_client import FreelancerAPIClient

# 进程内唯一的 API 客户端实例，由 main.py 的 lifespan 在启动时装入、关闭时清空。
# 做成单例是为了让 RateLimiter 的滑动窗口和 jobs/currencies 缓存在所有请求间共享，
# 否则每个请求各自计数，限流形同虚设、缓存也永远打不中。
_api_client: Optional[FreelancerAPIClient] = None


def set_api_client(client: Optional[FreelancerAPIClient]) -> None:
    """由 lifespan 调用，装入或清空单例。"""
    global _api_client
    _api_client = client


def get_api_client() -> FreelancerAPIClient:
    """FastAPI 依赖：取出 API 客户端单例。

    测试里用 app.dependency_overrides[get_api_client] 替换成
    带 MockTransport 的假客户端，从而不发真实网络请求。
    返回:
        进程内共享的 FreelancerAPIClient。
    异常:
        HTTPException 503：单例未初始化（正常启动流程下不会发生）。
    """
    if _api_client is None:
        raise HTTPException(status_code=503, detail="API client not initialised")
    return _api_client
