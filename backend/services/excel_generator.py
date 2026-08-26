"""Render processed project data into a three-sheet Excel workbook."""
from datetime import datetime, timezone
from io import BytesIO
from typing import List, Optional

import pandas as pd

from backend.services.data_processor import (
    build_budget_distribution,
    build_skill_frequency,
)

PROJECTS_SHEET = "Projects"
SKILLS_SHEET = "Skills Frequency"
BUDGET_SHEET = "Budget Distribution"

PROJECT_COLUMNS = [
    "Title",
    "Skills",
    "Budget (USD)",
    "Avg Bid",
    "Bid Count",
    "Type",
    "Posted",
    "URL",
]

PROJECT_URL_PREFIX = "https://www.freelancer.com/projects/"


def _format_posted(timestamp: Optional[int]) -> Optional[str]:
    """把 API 的 time_submitted（Unix 秒）格式化成 UTC 文本。

    统一用 UTC 而不是本地时区：报表可能在任意机器上生成，
    固定时区才能让同一批数据产出同样的结果。
    写成字符串而非 datetime，避免 Excel 按本地区域设置重新解释日期。

    参数:
        timestamp: Unix 时间戳（秒），可能缺失。
    返回:
        "YYYY-MM-DD HH:MM" 文本；缺失时返回 None（单元格留空）。
    """
    if timestamp is None:
        return None
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime(
        "%Y-%m-%d %H:%M"
    )


def _format_skills(project: dict) -> str:
    """把项目的 jobs[] 压成一个逗号分隔的技能单元格。

    Excel 一格只能放一个值，所以这里做扁平化；无 name 的条目跳过，
    与 build_skill_frequency 的口径保持一致。
    """
    return ", ".join(
        job["name"] for job in project.get("jobs") or [] if job.get("name")
    )


def _project_url(project: dict) -> Optional[str]:
    """由 seo_url 拼出可点击的项目完整地址。

    API 只返回相对 slug（如 "python/build-a-scraper"），
    报表读者需要能直接点开，所以在这里补上站点前缀。
    """
    seo_url = project.get("seo_url")
    if not seo_url:
        return None
    return f"{PROJECT_URL_PREFIX}{seo_url}"


def _projects_frame(projects: List[dict]) -> pd.DataFrame:
    """构造 Sheet 1 的 DataFrame，一行一个项目。

    金额直接取上游 enrich_projects 写入的 *_usd 字段，本模块不再做换算，
    职责边界清晰；缺失值保持 None 以便 Excel 留空而不是写 0。
    显式传 columns，保证空结果时表头仍然存在（AC-005 空数据要求）。
    """
    rows = [
        {
            "Title": project.get("title"),
            "Skills": _format_skills(project),
            "Budget (USD)": project.get("budget_max_usd"),
            "Avg Bid": project.get("bid_avg_usd"),
            "Bid Count": (project.get("bid_stats") or {}).get("bid_count"),
            "Type": project.get("type"),
            "Posted": _format_posted(project.get("time_submitted")),
            "URL": _project_url(project),
        }
        for project in projects
    ]
    return pd.DataFrame(rows, columns=PROJECT_COLUMNS)


def _skills_frame(projects: List[dict]) -> pd.DataFrame:
    """构造 Sheet 2 的 DataFrame：全量技能频次，降序。

    这里刻意不调用 top_skills：Excel 是离线交付物，读者要能自己深挖长尾，
    Top 10 只服务于前端图表。顺序由 build_skill_frequency 保证。
    """
    frequency = build_skill_frequency(projects)
    return pd.DataFrame(
        list(frequency.items()), columns=["Skill name", "Count"]
    )


def _budget_frame(projects: List[dict]) -> pd.DataFrame:
    """构造 Sheet 3 的 DataFrame：预算分箱与计数。

    分箱逻辑完全复用 build_budget_distribution，包含计数为 0 的档位，
    使报表档位数量固定、可跨批次对比。
    """
    distribution = build_budget_distribution(projects)
    return pd.DataFrame(list(distribution.items()), columns=["Bin", "Count"])


def generate_excel(projects: List[dict]) -> bytes:
    """把已加工的项目列表渲染成 3 个 Sheet 的 xlsx 字节串。

    返回 bytes 而不是写磁盘文件：调用方是 HTTP 下载接口，
    内存缓冲既避免临时文件清理，也让本函数保持纯函数、易测试。

    参数:
        projects: 经 enrich_projects 处理过、带 *_usd 字段的项目列表。
    返回:
        xlsx 文件的原始字节。
    """
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        _projects_frame(projects).to_excel(
            writer, sheet_name=PROJECTS_SHEET, index=False
        )
        _skills_frame(projects).to_excel(
            writer, sheet_name=SKILLS_SHEET, index=False
        )
        _budget_frame(projects).to_excel(
            writer, sheet_name=BUDGET_SHEET, index=False
        )
    return buffer.getvalue()
