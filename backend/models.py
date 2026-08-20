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
    """Project budget information."""
    minimum: float
    maximum: float
    currency: Currency


class BidStats(BaseModel):
    """Bidding statistics."""
    bid_count: int
    bid_avg: Optional[float] = None


class Project(BaseModel):
    """Freelancer project."""
    id: int
    title: str
    seo_url: str
    budget: Budget
    jobs: List[Job] = Field(default_factory=list)
    bid_stats: BidStats
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
