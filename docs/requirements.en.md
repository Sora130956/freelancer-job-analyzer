# Freelancer Job Analyzer — Product Requirements Document

**Version:** 1.0 (Step 2.5 — Refined Requirements)
**Date:** 2026-08-19
**Status:** Awaiting acceptance criteria (Step 3)

---

## 1. Overview

### 1.1 One-liner

A web application that queries Freelancer.com's public API to help a Python scraping freelancer quickly identify which projects are worth bidding on, and demonstrates a full Python data-engineering skill chain to potential Upwork clients.

### 1.2 Who / What / Why

| Dimension | Detail |
|-----------|--------|
| **Primary user** | The developer themselves — scanning Freelancer.com for Python scraping projects worth bidding on |
| **Secondary user** | Potential Upwork clients — evaluating the developer's skills via a live, zero-friction portfolio demo |
| **What** | FastAPI backend + clean frontend; filter → fetch → display → export workflow |
| **Why (personal)** | Skip manual project-by-project evaluation; quantify tech-stack market fit |
| **Why (portfolio)** | Clients open a URL, use the tool instantly; see Python scraping + FastAPI + pandas/openpyxl + cloud deploy in one place |

---

## 2. Data Source

- **API:** Freelancer.com Developer API — `GET /projects/0.1/projects/active/`
- **Authentication:** Anonymous access confirmed working for public project search (no OAuth token required for read-only queries)
- **Rate limits:** 50 requests/min, 1 000 requests/hour
- **Key fields used:**

| Field | Purpose |
|-------|---------|
| `title`, `seo_url` | Display title + project link (`https://www.freelancer.com/projects/{seo_url}`) |
| `budget.minimum/maximum`, `currency.exchange_rate` | Budget → converted to USD |
| `hourly_project_info.min/max_hourly_rate` | Hourly rate (when `type = hourly`) |
| `bid_stats.bid_avg`, `bid_stats.bid_count` | Average bid price, competition count |
| `jobs[]` (with `job_details=true`) | Skill tags |
| `time_submitted` | Posted time |
| `type` | `fixed` or `hourly` |

---

## 3. Query / Filter Panel

### 3.1 Fields

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| Keywords | Text input | — | Maps to API `query` param |
| Skill tags | Multi-select with fuzzy search | — | See §3.2 |
| Budget min (USD) | Number | — | `min_price` (converted) |
| Budget max (USD) | Number | — | `max_price` (converted) |
| Project type | Radio: All / Fixed / Hourly | All | |
| Posted within | Select: 24h / 3d / 7d / 30d / Any | Any | |
| Result count | Number input | 100 | Max 500; step = 100 |

### 3.2 Skill Tag Selector

- On page load, fetch all available skill tags from `GET /projects/0.1/jobs/` and cache locally (session).
- Render as a searchable multi-select: user types to fuzzy-filter the cached tag list, then clicks to select.
- Selected tags appear as removable chips above the input.
- Keyword search and tag selection are **additive** (AND logic with the API's `jobs[]` filter).

---

## 3.3 Page Layout (Wireframe)

```
┌─────────────────────────────────────────────────────────────────┐
│  Freelancer Job Analyzer                                        │
├─────────────────────────────────────────────────────────────────┤
│  ┌─── Filter Panel ───────────────────────────────────────────┐  │
│  │  Keywords  [________________________]                      │  │
│  │                                                            │  │
│  │  Skill Tags  [Search tags...  ▼]                           │  │
│  │  Selected: [Python ×] [Web Scraping ×] [Scrapy ×]         │  │
│  │                                                            │  │
│  │  Budget (USD)  Min [______]  Max [______]                  │  │
│  │                                                            │  │
│  │  Project Type  ● All  ○ Fixed  ○ Hourly                   │  │
│  │                                                            │  │
│  │  Posted Within  [Any  ▼]        Result Count [100]        │  │
│  │                                                            │  │
│  │                          [  🔍 Search  ]                   │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                 │
│  Found 211 results, page 1 of 11  Per page [20 ▼]              │
│  [< 1 2 3 … 11 >]                          [⬇ Download Excel]  │
│                                                                 │
│  ┌──────────────┬──────────────┬──────────┬────────┬────────┐  │
│  │ Title        │ Skills       │Budget    │Avg Bid │Compet. │… │
│  ├──────────────┼──────────────┼──────────┼────────┼────────┤  │
│  │ 🔗 Project   │[Python][Scr] │$50–$150  │ $80    │  12    │… │
│  │ 🔗 Project   │[Selenium]    │$200–$500 │ $320   │   8    │… │
│  │ …            │ …            │ …        │  …     │  …     │… │
│  └──────────────┴──────────────┴──────────┴────────┴────────┘  │
│  (Table also shows: Type badge | Posted | 🔗 link icon)        │
│                                                                 │
│  ┌─── Top 10 Skills Bar Chart ───┐  ┌─── Budget Distribution ─┐ │
│  │  30 ┤█                       │  │  40 ┤██                  │ │
│  │  20 ┤██ █                    │  │  25 ┤██ ██               │ │
│  │  10 ┤██ ██ █ █ █ █ █ █ █    │  │  10 ┤██ ██ ██ █ █        │ │
│  │     └─────────────────────   │  │     └──────────────────  │ │
│  │  Py  Sel Bea Scr …           │  │  <50 50- 150- 500- 1k+   │ │
│  └───────────────────────────── ┘  └────────────────────────  ┘ │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. Results Display

### 4.1 Summary Bar

```
Found 211 results — showing page 1 of 11  [< 1 2 3 … 11 >]   [Download Excel]
```

### 4.2 Results Table

| Column | Source field | Notes |
|--------|-------------|-------|
| Title | `title` + `seo_url` | Clickable link → `https://www.freelancer.com/projects/{seo_url}` (bid page) |
| Skills | `jobs[].name` | Comma-separated chips |
| Budget (USD) | `budget.*` × `exchange_rate` | Format: `$50 – $150` (fixed) or `$15/hr – $25/hr` (hourly) |
| Avg Bid (USD) | `bid_stats.bid_avg` × rate | |
| Competitors | `bid_stats.bid_count` | |
| Type | `type` | Badge: Fixed / Hourly |
| Posted | `time_submitted` | Relative: "2 hours ago" |
| Link | `seo_url` | Icon button → project bid page |

### 4.3 Pagination

- Default: **20 rows per page** (fills one screen without scrolling on a typical laptop)
- User can change page size: 10 / 20 / 50 options
- Data for all fetched results is cached in-memory; pagination is client-side (no re-fetching)
- Page size selector sits in the summary bar

### 4.4 Empty / Error States

| Scenario | Display |
|----------|---------|
| No results | Centered message: "No projects found. Try broader keywords or filters." |
| API error | Toast notification with HTTP status; results area shows previous data if available |
| Partial results (API returns < requested) | Note in summary bar: "API returned 87 of 100 requested results" |

---

## 5. Data Visualizations (Page)

Rendered below the results table using **Chart.js**.

### 5.1 Top 10 Skills Bar Chart

- X-axis: skill name
- Y-axis: frequency count
- Shows only the top 10 skills from the current result set
- Title: "Top 10 Skills in Results"

### 5.2 Budget Distribution Histogram

- X-axis: USD budget buckets (e.g., $0–50, $50–150, $150–500, $500–1k, $1k+)
- Y-axis: project count
- Fixed and hourly projects use different colors (stacked or grouped)
- Title: "Budget Distribution (USD)"

Both charts update whenever a new search is run.

---

## 6. Excel Export

Triggered by the "Download Excel" button. Generated server-side with **openpyxl** via FastAPI endpoint.

### Sheet 1 — Jobs List

All fetched results (up to the requested count, e.g. 500), not just the current page.

| Column | Type | Notes |
|--------|------|-------|
| Title | string | |
| URL | string (hyperlink) | `https://www.freelancer.com/projects/{seo_url}` |
| Skills | string | comma-separated |
| Budget Min (USD) | float | 2 decimal places |
| Budget Max (USD) | float | |
| Avg Bid (USD) | float | |
| Competitors | integer | |
| Type | string | Fixed / Hourly |
| Currency (original) | string | e.g. INR, CAD |
| Posted At | datetime | ISO 8601 |

Sorted by: Budget Max (USD) descending.

### Sheet 2 — Skills Frequency

Full skill frequency table (all skills, not just top 10).

| Column | Type |
|--------|------|
| Skill | string |
| Count | integer |
| % of Results | float (1 decimal) |

Sorted by: Count descending.

### Sheet 3 — Budget Distribution

| Column | Type |
|--------|------|
| Budget Range (USD) | string |
| Fixed Count | integer |
| Hourly Count | integer |
| Total | integer |

Buckets: `<$50`, `$50–150`, `$150–500`, `$500–1k`, `$1k–5k`, `>$5k`.

---

## 7. Backend API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/search` | Query Freelancer API; returns JSON results |
| `GET` | `/api/tags` | Fetch & cache all skill tags |
| `POST` | `/api/export` | Accept result JSON; return `.xlsx` file |
| `GET` | `/` | Serve frontend HTML |

---

## 8. Tech Stack (Portfolio-Intentional)

| Layer | Choice | Portfolio signal |
|-------|--------|-----------------|
| Backend | **FastAPI** | Modern async Python API framework |
| Data processing | **pandas** | Data cleaning, aggregation, budget conversion |
| Excel export | **openpyxl** | Multi-sheet Excel generation |
| HTTP client | **requests** (or `httpx`) | API integration |
| Frontend | Vanilla JS + **Chart.js** | Lightweight, no-framework visualization |
| Deployment | **Render** free tier | Live demo link for portfolio |

---

## 9. Non-Goals (Out of Scope for v1)

- User authentication / saved searches
- PeoplePerHour as second data source (noted for v2)
- Email alerts / scheduled scraping
- Mobile-optimized layout (desktop-first is sufficient for portfolio)

---

## 10. Constraints

- Must stay within Freelancer API rate limits (50 req/min): fetching 500 results = 5 requests, well within limits
- Render free tier: app may cold-start (~30s delay); acceptable for portfolio use
- No database required: all data is ephemeral per search session
