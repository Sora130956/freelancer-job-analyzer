# 实现计划 — Freelancer 任务分析器

**版本：** 1.0  
**日期：** 2026-08-19  
**状态：** 第 4 步 — 准备实现

---

## 1. 架构概览

### 技术栈

**后端：**
- FastAPI 0.115+（异步支持，OpenAPI 自动文档）
- httpx（异步 HTTP 客户端，调用 Freelancer.com API）
- pandas + openpyxl（Excel 生成）
- Pydantic v2（请求/响应验证）

**前端：**
- React 18 + Vite（组件化，现代构建工具）
- Tailwind CSS + shadcn/ui（专业 UI 组件）
- react-chartjs-2（Chart.js 的 React 封装，用于可视化）

**部署：**
- Render 免费套餐（Web Service）
- 单个 FastAPI 应用同时服务 API 和静态文件
- Python 3.11+

### 架构图

```
┌─────────────────────────────────────────────┐
│  浏览器（前端 — React SPA）                 │
│  ┌─────────────────────────────────────┐   │
│  │ React 18 + Vite（构建 → dist/）      │   │
│  │ ├─ FilterPanel（技能多选）           │   │
│  │ ├─ ResultsTable（客户端分页）        │   │
│  │ ├─ Charts（react-chartjs-2）         │   │
│  │ └─ ExportButton（下载 Excel）        │   │
│  └─────────────────────────────────────┘   │
└──────────────┬──────────────────────────────┘
               │ AJAX
               ▼
┌─────────────────────────────────────────────┐
│  FastAPI 后端                               │
│  ┌─────────────────────────────────────┐   │
│  │ API 路由                             │   │
│  │ ├─ GET /api/jobs（缓存的标签）       │   │
│  │ ├─ GET /api/search（项目查询）       │   │
│  │ └─ GET /api/export（Excel 下载）     │   │
│  └──────────┬──────────────────────────┘   │
│             │                                │
│  ┌──────────▼──────────────────────────┐   │
│  │ 服务层                               │   │
│  │ ├─ FreelancerAPIClient（httpx）     │   │
│  │ ├─ DataProcessor（USD 换算）        │   │
│  │ └─ ExcelGenerator（pandas/openpyxl）│   │
│  └─────────────────────────────────────┘   │
└──────────────┬──────────────────────────────┘
               │ HTTP
               ▼
┌─────────────────────────────────────────────┐
│  Freelancer.com 公开 API                    │
│  ├─ GET /projects/0.1/projects/active/     │
│  ├─ GET /projects/0.1/jobs/                 │
│  └─ GET /projects/0.1/currencies/           │
└─────────────────────────────────────────────┘
```

---

## 2. 模块拆分

### 模块 1：后端基础（`backend/`）

**文件：**
- `main.py` — FastAPI 应用入口
- `config.py` — 配置项（API 基础 URL、限流、CORS）
- `models.py` — Pydantic 模型（Project、Job、SearchRequest、SearchResponse）

**职责：**
- 初始化 FastAPI 应用 + CORS 中间件
- 挂载静态文件服务（`/` → `frontend/`）
- 健康检查端点（`GET /health`）

**验证：**
```bash
uvicorn backend.main:app --reload
curl http://localhost:8000/health
# 预期：{"status": "ok"}
```

---

### 模块 2：Freelancer API 客户端（`backend/services/api_client.py`）

**职责：**
- 使用 `httpx.AsyncClient` 的异步 HTTP 客户端
- 限流装饰器（50 次/分钟，1000 次/小时）
- 方法：
  - `fetch_projects(keywords, jobs, budget_min, budget_max, project_type, offset, limit)`
  - `fetch_jobs()` — 缓存 1 小时（内存）
  - `fetch_currencies()` — 缓存 24 小时

**验证：**
```bash
pytest tests/test_api_client.py -v
# 测试：成功获取、限流处理、USD 换算
```

**依赖：** 无（可最先开发）

---

### 模块 3：数据处理器（`backend/services/data_processor.py`）

**职责：**
- USD 换算：`budget_usd = budget.minimum * currency.exchange_rate`
- 技能频次统计（展开所有 `jobs[]`，计数）
- 预算区间分组：`<$50`, `$50-$150`, `$150-$500`, `$500-$1000`, `$1000+`
- Top 10 技能提取

**验证：**
```python
pytest tests/test_data_processor.py -v
# 测试：USD 换算准确性、技能频次正确性、预算分组
```

**依赖：** 模块 2（需要原始 API 响应结构）

---

### 模块 4：Excel 生成器（`backend/services/excel_generator.py`）

**职责：**
- 使用 pandas + openpyxl 生成 3 个 Sheet 的 `.xlsx`
- Sheet 1 "Projects"：Title、Skills、Budget (USD)、Avg Bid、Bid Count、Type、Posted、URL
- Sheet 2 "Skills Frequency"：Skill name、Count（降序）
- Sheet 3 "Budget Distribution"：Bin、Count

**验证：**
```bash
pytest tests/test_excel_generator.py -v
# 测试：3 个 sheet 存在、列名正确、数据完整性
```

**依赖：** 模块 3（需要处理后的数据）

---

### 模块 5：API 路由（`backend/routes/`）

**文件：**
- `jobs.py` — `GET /api/jobs`（返回缓存的技能标签）
- `search.py` — `GET /api/search?keywords=...&jobs[]=...&budget_min=...`
- `export.py` — `GET /api/export?<相同参数>`（返回 Excel 文件）

**职责：**
- 解析查询参数
- 调用 API 客户端 → 数据处理器 → 返回 JSON/文件
- 处理错误（404、429、500）

**验证：**
```bash
curl "http://localhost:8000/api/jobs" | jq 'length'
curl "http://localhost:8000/api/search?keywords=python&limit=10" | jq '.projects[0].title'
curl "http://localhost:8000/api/export?keywords=python" -o test.xlsx
python -c "import openpyxl; print(openpyxl.load_workbook('test.xlsx').sheetnames)"
```

**依赖：** 模块 2、3、4（完整后端栈）

---

### 模块 6：前端结构（`frontend/`）

**文件：**
- `index.html` — Vite 入口
- `src/main.jsx` — React 应用引导
- `src/App.jsx` — 根组件（布局、状态管理）
- `src/components/FilterPanel.jsx` — 筛选表单 + 技能多选
- `src/components/ResultsTable.jsx` — 表格 + 客户端分页
- `src/components/ExportButton.jsx` — Excel 下载触发
- `src/api.js` — API 客户端（封装 /api/jobs、/api/search、/api/export 的 fetch）
- `tailwind.config.js` + `vite.config.js` — 构建配置

**职责：**
- 技能标签多选 + 模糊搜索（shadcn/ui Combobox 组件）
- 结果表格 + 客户端分页（默认 20 条/页，shadcn/ui Table + Pagination）
- 用 React hooks 管理应用状态（useState 缓存结果、筛选条件、分页）
- 下载 Excel 按钮 → 触发 `/api/export`（携带当前筛选条件）

**验证：**
```bash
# 开发模式：
cd frontend && npm run dev
# 浏览器手工测试：
# 1. 打开 http://localhost:5173/ → 页面加载
# 2. 在技能 combobox 输入 "scra" → 看到 "Web Scraping"、"Scrapy"
# 3. 选中两个 → 芯片出现
# 4. 点击搜索 → 表格填充
# 5. 点击第 2 页 → 无网络请求（客户端分页），表格更新
# 6. 点击下载 Excel → 文件下载
```

**依赖：** 模块 5（需要后端 API）

---

### 模块 7：图表集成（`frontend/src/components/Charts.jsx`）

**职责：**
- `SkillsBarChart.jsx` — Top 10 技能柱状图（react-chartjs-2 `<Bar>`）
- `BudgetHistogram.jsx` — 预算分布直方图（react-chartjs-2 `<Bar>`）
- 当结果数据（props）变化时，图表响应式重新渲染

**验证：**
```bash
# 浏览器手工测试：
# 1. 搜索 "python" → 柱状图显示 Top 10 技能
# 2. React DevTools → 查看 SkillsBarChart 的 props.data → 10 个数字的数组
# 3. 预算直方图显示 5 个分桶及正确计数
```

**依赖：** 模块 6（需要 React 组件树 + 结果数据）

---

### 模块 8：部署配置

**文件：**
- `render.yaml` — Render 服务配置（构建命令、启动命令）
- `requirements.txt` — Python 依赖
- `frontend/package.json` — Node 依赖（react、vite、tailwindcss、react-chartjs-2）
- `.gitignore` — 排除 `__pycache__`、`.pytest_cache`、`*.xlsx`、`node_modules`、`frontend/dist`
- `README.md` — 安装说明、API 文档、作品集展示

**职责：**
- 构建前端：`cd frontend && npm install && npm run build` → 输出 `frontend/dist/`
- FastAPI 挂载 `frontend/dist/` 作为静态文件（SPA fallback 到 `index.html`）
- 定义 Render 构建：`cd frontend && npm install && npm run build && cd .. && pip install -r requirements.txt`
- 定义启动：`uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
- 环境变量：`FREELANCER_API_BASE_URL=https://www.freelancer.com`

**验证：**
```bash
# 本地测试：
cd frontend && npm run build && cd ..
PORT=8000 uvicorn backend.main:app --host 0.0.0.0 --port $PORT
# 打开 http://localhost:8000/ → 提供构建后的 React 应用
# 然后部署到 Render，检查公开 URL
```

**依赖：** 模块 1-7（完整应用）

---

## 3. 实现顺序

### 阶段 1：后端核心（第 1-2 天）
1. ✅ 模块 1：后端基础 — FastAPI 骨架 + 健康检查
2. ✅ 模块 2：Freelancer API 客户端 — 获取 projects/jobs/currencies、限流
3. ✅ 模块 3：数据处理器 — USD 换算、技能/预算统计

**里程碑：** 后端可获取并处理数据，通过单元测试验证。

---

### 阶段 2：API 与 Excel（第 3 天）
4. ✅ 模块 4：Excel 生成器 — 3 个 Sheet 的 XLSX 输出
5. ✅ 模块 5：API 路由 — `/api/jobs`、`/api/search`、`/api/export`

**里程碑：** 后端 API 完全可用，可通过 curl 测试。

---

### 阶段 3：前端（第 4-5 天）
6. ✅ 模块 6：前端结构 — React + Vite + shadcn/ui、技能选择器、表格、分页
7. ✅ 模块 7：图表集成 — react-chartjs-2 可视化

**里程碑：** 全栈应用本地运行正常。

---

### 阶段 4：部署（第 6 天）
8. ✅ 模块 8：部署配置 — Render 部署、README

**里程碑：** 公开 URL 上线，全部 6 条验收标准验证通过。

---

## 4. 测试策略

### 单元测试（pytest）
- `tests/test_api_client.py` — Mock httpx 响应，测试限流
- `tests/test_data_processor.py` — 测试 USD 换算、技能频次、预算分组
- `tests/test_excel_generator.py` — 验证 3 个 sheet、列名、数据完整性

### 集成测试
- `tests/test_routes.py` — FastAPI TestClient，测试所有端点

### 手工测试
- 浏览器功能测试（见 AC-002、AC-003、AC-004）
- 部署冒烟测试（AC-006）

---

## 5. 依赖关系图

```
模块 1（FastAPI 骨架）
    ↓
模块 2（API 客户端）───┐
    ↓                  │
模块 3（数据处理器）   │
    ↓                  │
模块 4（Excel 生成）───┤
    ↓                  │
模块 5（API 路由）─────┘
    ↓
模块 6（前端）─────────→ 模块 7（图表）
    ↓
模块 8（部署）
```

**关键路径：** 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8

---

## 6. 风险与应对

| 风险 | 影响 | 应对措施 |
|------|------|---------|
| 开发过程中触发 Freelancer API 限流 | 高 | 测试使用缓存响应，实现指数退避 |
| React 打包体积影响 Render 冷启动 | 中 | Vite 生产构建配合 tree-shaking + 代码分割；图表懒加载 |
| Node 构建步骤增加 Render 部署时间 | 中 | 缓存 node_modules；提交 lockfile 保证可复现构建 |
| 500+ 结果时 Excel 生成慢 | 低 | 超过 200 条使用流式响应 |
| 部署到 Render 后 CORS 问题 | 中 | FastAPI CORS 中间件配置允许所有来源 |

---

## 7. 完成标准（DoD）

每个模块：
- [ ] 代码编写 + 类型提示
- [ ] 单元测试通过（覆盖率 >80%）
- [ ] 手工验证命令成功执行
- [ ] 代码审查完成（第 5.5 步）

整个项目：
- [ ] 全部 6 条验收标准验证通过（AC-001 ~ AC-006）
- [ ] 部署到 Render，公开 HTTPS URL 可访问
- [ ] README 包含截图 + 作品集级别的描述
- [ ] Git 提交历史清晰（有意义的 commit message，无敏感信息）

---

## 8. 下一步

用户确认此计划后：
1. 创建项目结构：`backend/`、`frontend/`、`tests/`
2. 从模块 1（FastAPI 骨架）开始，TDD 模式
3. 每个模块完成后，运行验证命令再进入下一个
4. 阶段 2 里程碑后，做中期项目审查（第 5.5 步）
5. 最终部署 + 完整验收测试（AC-001 ~ AC-006）
