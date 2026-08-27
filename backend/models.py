"""Pydantic models for request/response validation."""
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class Job(BaseModel):
    """Skill/job tag."""
    id: int
    name: str


class Currency(BaseModel):
    """Currency information."""
    code: str
    exchange_rate: float


class Budget(BaseModel):
    """项目预算区间。

    真实 API 里 minimum/maximum 都可能缺一个（例如只给下限的固定价项目），
    所以两个字段都是 Optional；币种不在这里，见 Project.currency。
    """
    minimum: Optional[float] = None
    maximum: Optional[float] = None


class BidStats(BaseModel):
    """竞标统计。尚无人竞标时 bid_avg 缺失。"""
    bid_count: int
    bid_avg: Optional[float] = None


class Project(BaseModel):
    """Freelancer 项目。

    字段形态以 `compact=true` 的真实响应为准：
    - currency 与 budget 同级（不是 Budget 的子字段），换算汇率从这里取；
    - seo_url / budget / bid_stats / currency 都可能缺失，缺失不应让整批数据校验失败，
      因此设为 Optional，由下游 data_processor 做兜底（缺汇率按 1.0、缺金额留 None）。
    """
    id: int
    title: str
    seo_url: Optional[str] = None
    budget: Optional[Budget] = None
    currency: Optional[Currency] = None
    jobs: List[Job] = Field(default_factory=list)
    bid_stats: Optional[BidStats] = None
    type: str  # "fixed" or "hourly"
    time_submitted: int  # Unix timestamp

    # Computed fields
    budget_min_usd: Optional[float] = None
    budget_max_usd: Optional[float] = None
    bid_avg_usd: Optional[float] = None


class SearchRequest(BaseModel):
    """Search request parameters."""
    keywords: Optional[str] = None
    jobs: List[int] = Field(default_factory=list)
    budget_min: Optional[float] = None
    budget_max: Optional[float] = None
    project_type: Optional[str] = None  # "fixed", "hourly", or None for all
    time_range: Optional[int] = None  # Hours (24, 72, 168, 720, or None)
    limit: int = Field(default=100, ge=10, le=500)


class SearchResponse(BaseModel):
    """Search response."""
    projects: List[Project]
    total: int
    skills_frequency: dict  # {skill_name: count}
    budget_distribution: dict  # {range: count}


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str
