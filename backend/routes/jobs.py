"""Jobs route: expose the cached skill-tag list to the frontend."""
from typing import List

from fastapi import APIRouter, Depends

from backend.dependencies import get_api_client
from backend.models import Job
from backend.services.api_client import FreelancerAPIClient

router = APIRouter()


@router.get("/jobs", response_model=List[Job])
async def list_jobs(
    client: FreelancerAPIClient = Depends(get_api_client),
) -> List[dict]:
    """返回全量技能标签（1000+ 条），供前端做模糊搜索多选。

    数据量大但极少变动，所以由客户端层做 1 小时内存缓存，
    这里只负责透出；前端再缓存到 session storage，两级缓存都不打上游。
    返回:
        [{"id": ..., "name": ...}, ...]
    """
    return await client.fetch_jobs()
