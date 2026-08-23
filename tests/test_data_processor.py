"""Tests for the data processor."""
import pytest

from backend.services.data_processor import (
    BUDGET_BINS,
    build_budget_distribution,
    build_skill_frequency,
    enrich_projects,
    top_skills,
)

RATES = {"USD": 1.0, "EUR": 1.1, "INR": 0.012}


def _project(
    project_id=1,
    minimum=50.0,
    maximum=150.0,
    code="USD",
    jobs=None,
    bid_avg=100.0,
    bid_count=12,
):
    return {
        "id": project_id,
        "title": f"Project {project_id}",
        "seo_url": f"projects/p{project_id}",
        "type": "fixed",
        "time_submitted": 1700000000,
        "budget": {"minimum": minimum, "maximum": maximum},
        "currency": {"code": code, "exchange_rate": RATES[code]},
        "jobs": jobs if jobs is not None else [{"id": 3, "name": "Python"}],
        "bid_stats": {"bid_count": bid_count, "bid_avg": bid_avg},
    }


def test_enrich_converts_budget_to_usd():
    """EUR amounts must be multiplied by the exchange rate."""
    projects = [_project(minimum=50.0, maximum=150.0, code="EUR")]

    enriched = enrich_projects(projects, RATES)

    assert enriched[0]["budget_min_usd"] == pytest.approx(55.0)
    assert enriched[0]["budget_max_usd"] == pytest.approx(165.0)


def test_enrich_converts_bid_avg_to_usd():
    """Average bid must be converted with the same rate."""
    projects = [_project(code="EUR", bid_avg=100.0)]

    enriched = enrich_projects(projects, RATES)

    assert enriched[0]["bid_avg_usd"] == pytest.approx(110.0)


def test_enrich_keeps_usd_amounts_unchanged():
    """USD projects must pass through with a rate of 1.0."""
    projects = [_project(minimum=200.0, maximum=800.0, code="USD")]

    enriched = enrich_projects(projects, RATES)

    assert enriched[0]["budget_min_usd"] == pytest.approx(200.0)
    assert enriched[0]["budget_max_usd"] == pytest.approx(800.0)


def test_enrich_falls_back_to_embedded_rate_when_missing_from_map():
    """Unknown currency codes must fall back to the rate inside the payload."""
    project = _project(code="EUR", minimum=100.0, maximum=200.0)
    project["currency"]["code"] = "XYZ"
    project["currency"]["exchange_rate"] = 2.0

    enriched = enrich_projects([project], RATES)

    assert enriched[0]["budget_min_usd"] == pytest.approx(200.0)
    assert enriched[0]["budget_max_usd"] == pytest.approx(400.0)


def test_enrich_handles_missing_bid_avg():
    """Projects without an average bid must yield None instead of raising."""
    project = _project(code="USD")
    project["bid_stats"]["bid_avg"] = None

    enriched = enrich_projects([project], RATES)

    assert enriched[0]["bid_avg_usd"] is None


def test_enrich_does_not_mutate_input():
    """Enrichment must return new dicts and leave the raw payload untouched."""
    projects = [_project(code="EUR")]

    enrich_projects(projects, RATES)

    assert "budget_min_usd" not in projects[0]


def test_skill_frequency_counts_across_projects():
    """Every jobs[] entry must be counted once per project."""
    projects = [
        _project(project_id=1, jobs=[{"id": 3, "name": "Python"}, {"id": 7, "name": "Scrapy"}]),
        _project(project_id=2, jobs=[{"id": 3, "name": "Python"}]),
        _project(project_id=3, jobs=[{"id": 9, "name": "React"}, {"id": 3, "name": "Python"}]),
    ]

    freq = build_skill_frequency(projects)

    assert freq["Python"] == 3
    assert freq["Scrapy"] == 1
    assert freq["React"] == 1


def test_skill_frequency_is_sorted_descending():
    """Result order must be highest count first."""
    projects = [
        _project(project_id=1, jobs=[{"id": 7, "name": "Scrapy"}]),
        _project(project_id=2, jobs=[{"id": 3, "name": "Python"}]),
        _project(project_id=3, jobs=[{"id": 3, "name": "Python"}]),
    ]

    freq = build_skill_frequency(projects)

    assert list(freq.keys())[0] == "Python"


def test_skill_frequency_handles_projects_without_jobs():
    """Missing jobs[] must not raise."""
    project = _project()
    del project["jobs"]

    assert build_skill_frequency([project]) == {}


def test_top_skills_returns_at_most_ten_entries():
    """Top 10 extraction must cap the list length."""
    projects = [
        _project(project_id=i, jobs=[{"id": i, "name": f"Skill{i}"}] * (15 - i))
        for i in range(1, 15)
    ]

    result = top_skills(build_skill_frequency(projects))

    assert len(result) == 10


def test_top_skills_respects_custom_limit():
    """The limit must be configurable."""
    projects = [
        _project(project_id=1, jobs=[{"id": 3, "name": "Python"}]),
        _project(project_id=2, jobs=[{"id": 7, "name": "Scrapy"}]),
        _project(project_id=3, jobs=[{"id": 9, "name": "React"}]),
    ]

    result = top_skills(build_skill_frequency(projects), limit=2)

    assert len(result) == 2


def test_budget_distribution_assigns_correct_bins():
    """Projects must land in the bin matching their USD maximum."""
    projects = [
        _project(project_id=1, maximum=30.0),
        _project(project_id=2, maximum=100.0),
        _project(project_id=3, maximum=300.0),
        _project(project_id=4, maximum=750.0),
        _project(project_id=5, maximum=5000.0),
    ]

    distribution = build_budget_distribution(enrich_projects(projects, RATES))

    assert distribution["<$50"] == 1
    assert distribution["$50-$150"] == 1
    assert distribution["$150-$500"] == 1
    assert distribution["$500-$1000"] == 1
    assert distribution["$1000+"] == 1


def test_budget_distribution_bin_boundaries_are_inclusive_lower():
    """A value equal to a bin's lower bound belongs to that bin."""
    projects = [
        _project(project_id=1, maximum=50.0),
        _project(project_id=2, maximum=150.0),
        _project(project_id=3, maximum=1000.0),
    ]

    distribution = build_budget_distribution(enrich_projects(projects, RATES))

    assert distribution["$50-$150"] == 1
    assert distribution["$150-$500"] == 1
    assert distribution["$1000+"] == 1


def test_budget_distribution_includes_all_bins_with_zero():
    """Empty bins must still be present so the chart keeps a stable axis."""
    distribution = build_budget_distribution([])

    assert list(distribution.keys()) == [label for label, _, _ in BUDGET_BINS]
    assert all(count == 0 for count in distribution.values())


def test_budget_distribution_skips_projects_without_usd_budget():
    """Projects lacking a converted budget must not be counted."""
    projects = enrich_projects([_project()], RATES)
    projects[0]["budget_max_usd"] = None

    distribution = build_budget_distribution(projects)

    assert sum(distribution.values()) == 0
