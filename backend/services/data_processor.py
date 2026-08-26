"""Transform raw Freelancer API payloads into analysis-ready data."""
from collections import Counter
from typing import Dict, List, Optional, Tuple

# (label, lower bound inclusive, upper bound exclusive); None means unbounded.
BUDGET_BINS: List[Tuple[str, float, Optional[float]]] = [
    ("<$50", 0.0, 50.0),
    ("$50-$150", 50.0, 150.0),
    ("$150-$500", 150.0, 500.0),
    ("$500-$1000", 500.0, 1000.0),
    ("$1000+", 1000.0, None),
]

TOP_SKILLS_LIMIT = 10


def _exchange_rate(project: dict, rates: Dict[str, float]) -> float:
    """解析项目应使用的 USD 汇率。

    双层回退：优先用 /currencies/ 接口的共享汇率表（口径统一、每日更新），
    表里没有该币种时退回项目自带的 exchange_rate，两者都缺则用 1.0
    （视为已是 USD，宁可不换算也不丢弃项目）。

    参数:
        project: 单个原始项目 dict，币种信息在 project["currency"]。
        rates: 币种代码到 USD 汇率的映射。
    返回:
        用于金额换算的汇率。
    """
    currency = project.get("currency") or {}
    code = currency.get("code")
    if code in rates:
        return rates[code]
    return currency.get("exchange_rate", 1.0)


def _to_usd(amount: Optional[float], rate: float) -> Optional[float]:
    """把金额换算成 USD，保留 2 位小数。

    None 进 None 出：API 允许 budget/bid_avg 缺省，此时不能返回 0，
    否则会被预算分箱统计成「<$50」而污染图表。
    """
    if amount is None:
        return None
    return round(amount * rate, 2)


def enrich_projects(projects: List[dict], rates: Dict[str, float]) -> List[dict]:
    """为每个项目补充 USD 金额字段。

    返回浅拷贝而非原地修改入参，保证同一批原始数据可以被反复加工，
    调用方也不会因为共享引用而互相干扰。
    新增字段: budget_min_usd、budget_max_usd、bid_avg_usd。
    """
    enriched = []
    for project in projects:
        rate = _exchange_rate(project, rates)
        budget = project.get("budget") or {}
        bid_stats = project.get("bid_stats") or {}

        item = dict(project)
        item["budget_min_usd"] = _to_usd(budget.get("minimum"), rate)
        item["budget_max_usd"] = _to_usd(budget.get("maximum"), rate)
        item["bid_avg_usd"] = _to_usd(bid_stats.get("bid_avg"), rate)
        enriched.append(item)
    return enriched


def build_skill_frequency(projects: List[dict]) -> Dict[str, int]:
    """统计每个技能被多少个项目提及，按频次降序返回。

    同一项目内的重复技能按 API 约定不会出现，因此直接逐条累加。
    无 name 的技能条目跳过，避免出现空字符串键。
    """
    counter: Counter = Counter()
    for project in projects:
        for job in project.get("jobs") or []:
            name = job.get("name")
            if name:
                counter[name] += 1
    return dict(counter.most_common())


def top_skills(
    frequency: Dict[str, int], limit: int = TOP_SKILLS_LIMIT
) -> List[Tuple[str, int]]:
    """取排名最前的若干技能，返回 (技能名, 项目数) 列表。

    依赖 build_skill_frequency 已按降序排好，所以这里只切片不再排序。
    """
    return list(frequency.items())[:limit]


def build_budget_distribution(projects: List[dict]) -> Dict[str, int]:
    """按预算把项目归入 BUDGET_BINS 的 5 个区间并计数。

    用 budget_max_usd（客户愿付上限）分箱；缺该字段的项目跳过。
    区间左闭右开，边界值（如 150）归入更高一档。
    即使某区间为空也保留 0，避免前端图表 X 轴档位数量抖动。
    """
    distribution = {label: 0 for label, _, _ in BUDGET_BINS}
    for project in projects:
        amount = project.get("budget_max_usd")
        if amount is None:
            continue
        for label, lower, upper in BUDGET_BINS:
            if amount >= lower and (upper is None or amount < upper):
                distribution[label] += 1
                break
    return distribution
