# Implementation Plan — Freelancer Job Analyzer

**Version:** 1.0  
**Date:** 2026-08-19  
**Status:** Step 4 — Ready for implementation

---

## 1. Architecture Overview

### Tech Stack

**Backend:**
- FastAPI 0.115+ (async support, OpenAPI auto-docs)
- httpx (async HTTP client for Freelancer.com API)
- pandas + openpyxl (Excel generation)
- Pydantic v2 (request/response validation)

**Frontend:**
- React 18 + Vite (component-based, modern build tooling)
- Tailwind CSS + shadcn/ui (professional UI components)
- react-chartjs-2 (Chart.js React wrapper for visualizations)

**Deployment:**
- Render free tier (Web Service)
- Single FastAPI app serving both API and static files
- Python 3.11+

### Architecture Diagram

```
┌─────────────────────────────────────────────┐
│  Browser (Frontend — React SPA)             │
│  ┌─────────────────────────────────────┐   │
│  │ React 18 + Vite (build → dist/)      │   │
│  │ ├─ FilterPanel (skills multi-select) │   │
│  │ ├─ ResultsTable (client pagination)  │   │
│  │ ├─ Charts (react-chartjs-2)          │   │
│  │ └─ ExportButton                      │   │
│  └─────────────────────────────────────┘   │
└──────────────┬──────────────────────────────┘
               │ AJAX
               ▼
┌─────────────────────────────────────────────┐
│  FastAPI Backend                            │
│  ┌─────────────────────────────────────┐   │
│  │ API Routes                           │   │
│  │ ├─ GET /api/jobs (cached tags)      │   │
│  │ ├─ GET /api/search (projects query) │   │
│  │ └─ GET /api/export (Excel download) │   │
│  └──────────┬──────────────────────────┘   │
│             │                                │
│  ┌──────────▼──────────────────────────┐   │
│  │ Services Layer                       │   │
│  │ ├─ FreelancerAPIClient (httpx)      │   │
│  │ ├─ DataProcessor (USD conversion)   │   │
│  │ └─ ExcelGenerator (pandas/openpyxl) │   │
│  └─────────────────────────────────────┘   │
└──────────────┬──────────────────────────────┘
               │ HTTP
               ▼
┌─────────────────────────────────────────────┐
│  Freelancer.com Public API                  │
│  ├─ GET /projects/0.1/projects/active/     │
│  ├─ GET /projects/0.1/jobs/                 │
│  └─ GET /projects/0.1/currencies/           │
└─────────────────────────────────────────────┘
```

---

## 2. Module Breakdown

### Module 1: Backend Foundation (`backend/`)

**Files:**
- `main.py` — FastAPI app entry point
- `config.py` — Settings (API base URL, rate limits, CORS)
- `models.py` — Pydantic schemas (Project, Job, SearchRequest, SearchResponse)

**Responsibilities:**
- Initialize FastAPI app with CORS middleware
- Mount static file serving (`/` → `frontend/`)
- Health check endpoint (`GET /health`)

**Verification:**
```bash
uvicorn backend.main:app --reload
curl http://localhost:8000/health
# Expected: {"status": "ok"}
```

---

### Module 2: Freelancer API Client (`backend/services/api_client.py`)

**Responsibilities:**
- Async HTTP client using `httpx.AsyncClient`
- Rate limiting decorator (50 req/min, 1000 req/hour)
- Methods:
  - `fetch_projects(keywords, jobs, budget_min, budget_max, project_type, offset, limit)`
  - `fetch_jobs()` — cached for 1 hour (in-memory)
  - `fetch_currencies()` — cached for 24 hours

**Verification:**
```bash
pytest tests/test_api_client.py -v
# Test: successful fetch, rate limit handling, USD conversion
```

**Dependencies:** None (can be developed first)

---

### Module 3: Data Processor (`backend/services/data_processor.py`)

**Responsibilities:**
- USD conversion: `budget_usd = budget.minimum * currency.exchange_rate`
- Skill frequency counter (flatten all `jobs[]`, count occurrences)
- Budget distribution bins: `<$50`, `$50-$150`, `$150-$500`, `$500-$1000`, `$1000+`
- Top 10 skills extractor

**Verification:**
```python
pytest tests/test_data_processor.py -v
# Test: correct USD conversion, skill frequency accuracy, budget binning
```

**Dependencies:** Module 2 (needs raw API response structure)

---

### Module 4: Excel Generator (`backend/services/excel_generator.py`)

**Responsibilities:**
- Generate `.xlsx` with 3 sheets using pandas + openpyxl
- Sheet 1 "Projects": Title, Skills, Budget (USD), Avg Bid, Bid Count, Type, Posted, URL
- Sheet 2 "Skills Frequency": Skill name, Count (sorted desc)
- Sheet 3 "Budget Distribution": Bin, Count

**Verification:**
```bash
pytest tests/test_excel_generator.py -v
# Test: 3 sheets exist, correct columns, data integrity
```

**Dependencies:** Module 3 (needs processed data)

---

### Module 5: API Routes (`backend/routes/`)

**Files:**
- `jobs.py` — `GET /api/jobs` (returns cached job tags)
- `search.py` — `GET /api/search?keywords=...&jobs[]=...&budget_min=...`
- `export.py` — `GET /api/export?<same_params>` (returns Excel file)

**Responsibilities:**
- Parse query parameters
- Call API client → Data processor → Return JSON/file
- Handle errors (404, 429, 500)

**Verification:**
```bash
curl "http://localhost:8000/api/jobs" | jq 'length'
curl "http://localhost:8000/api/search?keywords=python&limit=10" | jq '.projects[0].title'
curl "http://localhost:8000/api/export?keywords=python" -o test.xlsx
python -c "import openpyxl; print(openpyxl.load_workbook('test.xlsx').sheetnames)"
```

**Dependencies:** Module 2, 3, 4 (full backend stack)

---

### Module 6: Frontend Structure (`frontend/`)

**Files:**
- `index.html` — Vite entry point
- `src/main.jsx` — React app bootstrap
- `src/App.jsx` — Root component (layout, state management)
- `src/components/FilterPanel.jsx` — Filter form with skill multi-select
- `src/components/ResultsTable.jsx` — Table with client-side pagination
- `src/components/ExportButton.jsx` — Excel download trigger
- `src/api.js` — API client (fetch wrappers for /api/jobs, /api/search, /api/export)
- `tailwind.config.js` + `vite.config.js` — Build config

**Responsibilities:**
- Skill tag multi-select with fuzzy search (shadcn/ui Combobox component)
- Results table with client-side pagination (20/page default, shadcn/ui Table + Pagination)
- Manage app state with React hooks (useState for results cache, filters, pagination)
- Download Excel button → triggers `/api/export` with current filters

**Verification:**
```bash
# Dev mode:
cd frontend && npm run dev
# Manual browser test:
# 1. Open http://localhost:5173/ → page loads
# 2. Type "scra" in skills combobox → sees "Web Scraping", "Scrapy"
# 3. Select both → chips appear
# 4. Click Search → table populates
# 5. Click page 2 → no network request (client-side pagination), table updates
# 6. Click Download Excel → file downloads
```

**Dependencies:** Module 5 (needs backend API)

---

### Module 7: Chart Integration (`frontend/src/components/Charts.jsx`)

**Responsibilities:**
- `SkillsBarChart.jsx` — Top 10 skills bar chart (react-chartjs-2 `<Bar>`)
- `BudgetHistogram.jsx` — Budget distribution histogram (react-chartjs-2 `<Bar>`)
- Charts re-render reactively when result data (props) changes

**Verification:**
```bash
# Manual browser test:
# 1. Search "python" → bar chart shows top 10 skills
# 2. React DevTools → inspect SkillsBarChart props.data → array of 10 numbers
# 3. Budget histogram shows 5 bins with correct counts
```

**Dependencies:** Module 6 (needs React component tree + result data)

---

### Module 8: Deployment Configuration

**Files:**
- `render.yaml` — Render service config (build command, start command)
- `requirements.txt` — Python dependencies
- `frontend/package.json` — Node dependencies (react, vite, tailwindcss, react-chartjs-2)
- `.gitignore` — Exclude `__pycache__`, `.pytest_cache`, `*.xlsx`, `node_modules`, `frontend/dist`
- `README.md` — Setup instructions, API docs, portfolio showcase

**Responsibilities:**
- Build frontend: `cd frontend && npm install && npm run build` → outputs `frontend/dist/`
- FastAPI mounts `frontend/dist/` as static files (SPA fallback to `index.html`)
- Define Render build: `cd frontend && npm install && npm run build && cd .. && pip install -r requirements.txt`
- Define start: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
- Environment variables: `FREELANCER_API_BASE_URL=https://www.freelancer.com`

**Verification:**
```bash
# Local test:
cd frontend && npm run build && cd ..
PORT=8000 uvicorn backend.main:app --host 0.0.0.0 --port $PORT
# Open http://localhost:8000/ → serves built React app
# Then deploy to Render, check public URL
```

**Dependencies:** Module 1-7 (full app)

---

## 3. Implementation Order

### Phase 1: Backend Core (Day 1-2)
1. ✅ Module 1: Backend Foundation — FastAPI skeleton + health check
2. ✅ Module 2: Freelancer API Client — fetch projects/jobs/currencies, rate limiting
3. ✅ Module 3: Data Processor — USD conversion, skill/budget stats

**Milestone:** Backend can fetch and process data, verified via unit tests.

---

### Phase 2: API & Excel (Day 3)
4. ✅ Module 4: Excel Generator — 3-sheet XLSX output
5. ✅ Module 5: API Routes — `/api/jobs`, `/api/search`, `/api/export`

**Milestone:** Backend API fully functional, testable via curl.

---

### Phase 3: Frontend (Day 4-5)
6. ✅ Module 6: Frontend Structure — React + Vite + shadcn/ui, skill selector, table, pagination
7. ✅ Module 7: Chart Integration — react-chartjs-2 visualizations

**Milestone:** Full-stack app working locally.

---

### Phase 4: Deployment (Day 6)
8. ✅ Module 8: Deployment Configuration — Render deployment, README

**Milestone:** Live public URL, all 6 acceptance criteria verified.

---

## 4. Testing Strategy

### Unit Tests (pytest)
- `tests/test_api_client.py` — Mock httpx responses, test rate limiting
- `tests/test_data_processor.py` — Test USD conversion, skill frequency, budget bins
- `tests/test_excel_generator.py` — Verify 3 sheets, columns, data integrity

### Integration Tests
- `tests/test_routes.py` — FastAPI TestClient, test all endpoints

### Manual Tests
- Browser functional tests (see AC-002, AC-003, AC-004)
- Deployment smoke test (AC-006)

---

## 5. Dependency Graph

```
Module 1 (FastAPI skeleton)
    ↓
Module 2 (API Client) ───┐
    ↓                    │
Module 3 (Data Processor)│
    ↓                    │
Module 4 (Excel Gen) ────┤
    ↓                    │
Module 5 (API Routes) ───┘
    ↓
Module 6 (Frontend) ──────→ Module 7 (Charts)
    ↓
Module 8 (Deployment)
```

**Critical Path:** 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8

---

## 6. Risks & Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| Freelancer API rate limit hit during dev | High | Use cached responses in tests, implement exponential backoff |
| React bundle size affects Render cold start | Medium | Vite production build with tree-shaking + code splitting; lazy-load charts |
| Node build step increases Render deploy time | Medium | Cache node_modules; commit lockfile for reproducible builds |
| Excel generation slow for 500+ results | Low | Use streaming response if >200 results |
| CORS issues on deployed Render URL | Medium | Configure CORS middleware in FastAPI to allow all origins |

---

## 7. Definition of Done (DoD)

For each module:
- [ ] Code written + type hints
- [ ] Unit tests pass (>80% coverage)
- [ ] Manual verification command executed successfully
- [ ] Code reviewed (Step 5.5)

For the project:
- [ ] All 6 acceptance criteria verified (AC-001 ~ AC-006)
- [ ] Deployed to Render with public HTTPS URL
- [ ] README includes screenshots + portfolio-ready description
- [ ] Git history clean (meaningful commits, no secrets)

---

## 8. Next Steps

After user approval of this plan:
1. Create project structure: `backend/`, `frontend/`, `tests/`
2. Start with Module 1 (FastAPI skeleton) in TDD mode
3. After each module, run verification commands before moving to next
4. At Phase 2 milestone, do a mid-project review (Step 5.5)
5. Final deployment + full acceptance test (AC-001 ~ AC-006)
