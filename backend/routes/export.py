"""Export route: stream the search result as an Excel workbook."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Response

from backend.dependencies import get_api_client
from backend.routes.search import SearchFilters, collect_projects, search_filters
from backend.services.api_client import FreelancerAPIClient
from backend.services.excel_generator import generate_excel

router = APIRouter()

XLSX_MEDIA_TYPE = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)


def _filename() -> str:
    """生成带 UTC 时间戳的文件名，避免多次导出互相覆盖。"""
    stamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"freelancer-projects-{stamp}.xlsx"


@router.get("/export")
async def export_projects(
    filters: SearchFilters = Depends(search_filters),
    client: FreelancerAPIClient = Depends(get_api_client),
) -> Response:
    """用与 /api/search 相同的筛选条件导出 xlsx 文件流。

    刻意复用 collect_projects，保证导出的数据和页面上看到的完全一致；
    不接受前端回传数据，避免被篡改、也省去大 payload 上传。
    用 Response 直接回字节串（Excel 已在内存里，无需 StreamingResponse），
    Content-Disposition 设 attachment 让浏览器直接下载而不是内联打开。
    """
    projects = await collect_projects(client, filters)
    content = generate_excel(projects)
    return Response(
        content=content,
        media_type=XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{_filename()}"'},
    )
