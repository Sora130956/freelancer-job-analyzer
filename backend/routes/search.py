"""Search route: fetch projects, convert to USD, and summarise them."""
from dataclasses import dataclass
from typing import List, Optional

from fastapi import APIRouter, Depends, Query

from backend.dependencies import get_api_client
from backend.models import SearchResponse
from backend.services.api_client import FreelancerAPIClient
from backend.services.data_processor import (
    build_budget_distribution,
    build_skill_frequency,
    enrich_projects,
)

router = APIRouter()

# Freelancer API 单次最多返回 100 条，更多结果只能靠 offset 递增多次请求。
PAGE_SIZE = 100
MAX_RESULTS = 500


@dataclass
class SearchFilters:
    """筛选面板的一组查询条件。

    search 和 export 两个端点接受完全相同的参数，抽成一个依赖对象，
    避免两处重复声明 7 个 Query 参数导致定义漂移。
    """

    keywords: Optional[str] = None
    jobs: Optional[List[int]] = None
    budget_min: Optional[float] = None
    budget_max: Optional[float] = None
    project_type: Optional[str] = None
    time_range: Optional[int] = None
    limit: int = PAGE_SIZE


def search_filters(
    keywords: Optional[str] = None,
    jobs: List[int] = Query(default=[], alias="jobs[]"),
    budget_min: Optional[float] = None,
    budget_max: Optional[float] = None,
    project_type: Optional[str] = Query(default=None, pattern="^(fixed|hourly)$"),
    time_range: Optional[int] = Query(default=None),
    limit: int = Query(default=PAGE_SIZE, ge=10, le=MAX_RESULTS),
) -> SearchFilters:
    """把 URL 查询参数解析成 SearchFilters。

    limit 用 ge/le 兜住 10..500（AC-001 上限 500），越界由 FastAPI 直接返回 422，
    不进业务代码；project_type 用正则限定，避免把非法值透传给上游 API。
    """
    return SearchFilters(
        keywords=keywords,
        jobs=jobs or None,
        budget_min=budget_min,
        budget_max=budget_max,
        project_type=project_type,
        time_range=time_range,
        limit=limit,
    )


async def collect_projects(
    client: FreelancerAPIClient, filters: SearchFilters
) -> List[dict]:
    """按 offset 循环拉取项目，直到取满 limit 或数据取完，并补上 USD 金额。

    为什么要循环：上游单次上限 100 条，而需求允许查最多 500 条，
    所以这一层负责翻页拼装。某页返回不足一页（PAGE_SIZE）说明后面没有数据了，
    此时立即停止，避免白跑请求浪费限流额度。

    参数:
        client: API 客户端单例。
        filters: 已解析的筛选条件。
    返回:
        enrich_projects 处理过的项目列表（含 budget_min_usd 等字段），长度不超过 limit。
    """
    rates = await client.fetch_currencies()

    collected: List[dict] = []
    offset = 0
    while len(collected) < filters.limit:
        page_size = min(PAGE_SIZE, filters.limit - len(collected))
        page = await client.fetch_projects(
            keywords=filters.keywords,
            jobs=filters.jobs,
            budget_min=filters.budget_min,
            budget_max=filters.budget_max,
            project_type=filters.project_type,
            time_range=filters.time_range,
            offset=offset,
            limit=page_size,
        )
        collected.extend(page)
        if len(page) < page_size:
            break
        offset += page_size

    return enrich_projects(collected[: filters.limit], rates)


@router.get("/search", response_model=SearchResponse)
async def search_projects(
    filters: SearchFilters = Depends(search_filters),
    client: FreelancerAPIClient = Depends(get_api_client),
) -> SearchResponse:
    """搜索项目并返回列表 + 技能频次 + 预算分布。

    技能频次和预算分布在后端算好一起返回，前端图表直接用，
    省得前端为了画图再遍历一遍全量数据。
    """
    projects = await collect_projects(client, filters)
    return SearchResponse(
        projects=projects,
        total=len(projects),
        skills_frequency=build_skill_frequency(projects),
        budget_distribution=build_budget_distribution(projects),
    )
