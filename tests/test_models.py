"""Tests for Pydantic models matching the real Freelancer API payload shape."""
import pytest

from backend.models import Project


def _real_project_payload():
    """真实 API 返回的项目结构（compact=true）：currency 与 budget 同级。"""
    return {
        "id": 111,
        "title": "Build a Python scraper",
        "seo_url": "projects/python/build-scraper",
        "type": "fixed",
        "time_submitted": 1700000000,
        "budget": {"minimum": 50.0, "maximum": 150.0},
        "currency": {"code": "EUR", "exchange_rate": 1.1},
        "jobs": [{"id": 3, "name": "Python"}],
        "bid_stats": {"bid_count": 12, "bid_avg": 100.0},
    }


def test_project_accepts_currency_at_top_level():
    """currency 是 Project 的同级字段，不在 Budget 内部。"""
    project = Project(**_real_project_payload())

    assert project.currency is not None
    assert project.currency.code == "EUR"
    assert project.currency.exchange_rate == 1.1


def test_budget_does_not_require_currency():
    """Budget 只有 minimum/maximum，不再要求 currency 子对象。"""
    project = Project(**_real_project_payload())

    assert project.budget.minimum == 50.0
    assert project.budget.maximum == 150.0


def test_project_allows_missing_optional_fields():
    """seo_url / budget / bid_stats 在真实数据里可能缺失，缺失时不应报错。"""
    payload = _real_project_payload()
    del payload["seo_url"]
    del payload["budget"]
    del payload["bid_stats"]

    project = Project(**payload)

    assert project.seo_url is None
    assert project.budget is None
    assert project.bid_stats is None


def test_project_allows_missing_currency():
    """currency 缺失时退化为 None，由数据处理层按 1.0 汇率兜底。"""
    payload = _real_project_payload()
    del payload["currency"]

    project = Project(**payload)

    assert project.currency is None


def test_project_budget_bounds_are_optional():
    """固定价项目可能只有 minimum 没有 maximum。"""
    payload = _real_project_payload()
    payload["budget"] = {"minimum": 250.0}

    project = Project(**payload)

    assert project.budget.minimum == 250.0
    assert project.budget.maximum is None
