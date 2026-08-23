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
    """Resolve the USD exchange rate, preferring the shared currency table."""
    currency = project.get("currency") or {}
    code = currency.get("code")
    if code in rates:
        return rates[code]
    return currency.get("exchange_rate", 1.0)


def _to_usd(amount: Optional[float], rate: float) -> Optional[float]:
    if amount is None:
        return None
    return round(amount * rate, 2)


def enrich_projects(projects: List[dict], rates: Dict[str, float]) -> List[dict]:
    """Return copies of the projects with USD amounts added."""
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
    """Count how many projects mention each skill, highest first."""
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
    """Return the highest ranked skills as (name, count) pairs."""
    return list(frequency.items())[:limit]


def build_budget_distribution(projects: List[dict]) -> Dict[str, int]:
    """Bucket projects by their USD maximum budget, keeping every bin present."""
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
