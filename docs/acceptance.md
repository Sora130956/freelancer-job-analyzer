# Acceptance Criteria — Freelancer Job Analyzer

**Version:** 1.0  
**Date:** 2026-08-19  
**Status:** Ready for implementation (Step 3)

---

## Overview

This document defines the acceptance criteria for the Freelancer Job Analyzer web application. Each criterion is quantifiable and verifiable through automated or manual checks.

---

## AC-001: API Integration and Data Fetching

**Given** the user submits a search request with filters  
**When** the backend calls Freelancer.com API (`GET /projects/0.1/projects/active/`)  
**Then** the system must:

- Successfully fetch project data with `job_details=true`, `full_description=true`, `compact=true`
- Support pagination via `offset` parameter (100 results per request, max 500 total)
- Handle rate limits gracefully (50 requests/minute, 1000 requests/hour)
- Convert all budget values to USD using `currency.exchange_rate`
- Return structured JSON including: `id`, `title`, `seo_url`, `budget`, `jobs[]`, `bid_stats`, `type`, `time_submitted`

**Verification:**
```bash
# Test API endpoint with sample filters
curl "http://localhost:8000/api/search?keywords=python&limit=100" | jq '.projects | length'
# Expected: 100 (or fewer if fewer results exist)

# Verify USD conversion
curl "http://localhost:8000/api/search?limit=10" | jq '.projects[0].budget_usd'
# Expected: numeric value in USD, not original currency
```

---

## AC-002: Skill Tag Selector with Fuzzy Search

**Given** the user opens the web page  
**When** the page loads  
**Then** the system must:

- Fetch all skill tags from `GET /projects/0.1/jobs/` and cache them locally (session storage)
- Render a searchable multi-select dropdown
- Support fuzzy filtering: typing "py" shows "Python", "PyQt", "PySpark"
- Display selected tags as removable chips above the input
- Send selected tag IDs to the backend as `jobs[]` array

**Verification:**
```bash
# Check /api/jobs endpoint returns full tag list
curl "http://localhost:8000/api/jobs" | jq 'length'
# Expected: > 500 tags

# Manual browser test:
# 1. Open page → dropdown shows all tags
# 2. Type "scra" → sees "Web Scraping", "Scrapy"
# 3. Select both → chips appear above input
# 4. Click search → network tab shows `jobs[]=3&jobs=17` in request
```

---

## AC-003: Client-Side Pagination and Result Display

**Given** the user receives search results (e.g., 211 projects)  
**When** the results are rendered  
**Then** the system must:

- Cache all fetched results in memory (no re-fetch on page switch)
- Default to 20 results per page
- Allow user to switch per-page count (10 / 20 / 50)
- Display pagination controls: `[< 1 2 3 … 11 >]`
- Show summary: "Found 211 results, page 1 of 11"
- Render table with clickable title links → `https://www.freelancer.com/projects/{seo_url}`

**Verification:**
```bash
# Functional test in browser:
# 1. Search "python scraping" → sees "Found X results"
# 2. Default shows 20 rows
# 3. Click page 2 → shows next 20 rows (no network request)
# 4. Change to 50 per page → pagination updates, still no new fetch
# 5. Click title link → opens Freelancer project page in new tab
```

---

## AC-004: Chart.js Visualizations (Top 10 Skills + Budget Distribution)

**Given** search results are displayed  
**When** the user scrolls to the visualization section  
**Then** the system must:

- Render a **bar chart** showing Top 10 skills by frequency (e.g., Python: 85, Selenium: 42, …)
- Render a **histogram** showing budget distribution in bins: <$50, $50-$150, $150-$500, $500-$1000, $1000+
- Use Chart.js library for rendering
- Charts reflect only the **current filtered results**, not all-time data

**Verification:**
```bash
# Manual browser test:
# 1. Search "python" → bar chart shows Python-related skills at top
# 2. Inspect chart data via browser console:
#    document.querySelector('canvas').chart.data.datasets[0].data
#    → Expected: array of 10 numbers (frequencies)
# 3. Histogram shows budget bins with correct counts
```

---

## AC-005: Excel Export with Three Sheets

**Given** the user clicks "Download Excel" button  
**When** the export is triggered  
**Then** the system must:

- Generate an `.xlsx` file using `pandas` + `openpyxl`
- **Sheet 1 "Projects"**: All fetched results with columns: Title, Skills, Budget (USD), Avg Bid, Bid Count, Type, Posted, URL
- **Sheet 2 "Skills Frequency"**: Complete skill frequency table (not just Top 10), sorted descending
- **Sheet 3 "Budget Distribution"**: Budget bins with project counts

**Verification:**
```bash
# Download Excel file via browser, then:
python -c "
import openpyxl
wb = openpyxl.load_workbook('freelancer_projects.xlsx')
print(wb.sheetnames)  # Expected: ['Projects', 'Skills Frequency', 'Budget Distribution']
print(len(wb['Projects']['A']))  # Expected: row count = fetched results + 1 (header)
print(wb['Skills Frequency']['A2'].value)  # Expected: top skill name
"
```

---

## AC-006: Deployment to Render (Free Tier)

**Given** the application is ready for production  
**When** deployed to Render free tier  
**Then** the system must:

- Be accessible via public HTTPS URL (e.g., `https://freelancer-analyzer.onrender.com`)
- Serve the frontend and API from a single FastAPI app
- Load within 15 seconds on cold start (Render free tier limitation)
- Display correctly on desktop browsers (Chrome, Firefox, Safari)

**Verification:**
```bash
# Check deployment health
curl -I https://freelancer-analyzer.onrender.com/
# Expected: HTTP/2 200

# Load test (manual):
# 1. Open URL in incognito → page loads within 15s
# 2. Submit search → results appear
# 3. Download Excel → file downloads successfully
```

---

## Completion Checklist

Before marking the project as "done", verify all criteria:

- [ ] AC-001: API integration works, USD conversion correct
- [ ] AC-002: Skill tag selector with fuzzy search functional
- [ ] AC-003: Client-side pagination works, no unnecessary API calls
- [ ] AC-004: Charts render correctly and reflect filtered data
- [ ] AC-005: Excel export contains 3 sheets with correct data
- [ ] AC-006: Deployed to Render, publicly accessible

---

## Out of Scope (Explicitly NOT Required)

- User authentication / login system
- Saving search history or favorites
- Real-time notifications for new projects
- Mobile-responsive design (desktop-first for portfolio demo)
- Multi-language UI support (English only)
- Database persistence (all data is session-based)
