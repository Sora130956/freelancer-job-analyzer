# 项目状态（单一进度源）

> 本文件是项目进度的唯一来源。每次会话结束前必须更新本文件。换会话、换模型都靠它接上进度。

## 当前阶段

第 5 步（生成 → validate → review）—— 后端模块 1-5 全量回归 59 passed；模块 6 前端结构、模块 7 图表集成均已实现并通过浏览器验证，待进入模块 8（Render 部署）

## 需求一句话（Who / What / Why）

> v1（原始版，第 1 步）：CLI 工具，输出 Excel 报表。

### v2（打磨版，第 2.5 步）

- **Who（为谁）**：
  - 主用户：我自己，筛选 Freelancer.com 上 Python 爬虫方向的可投单子。
  - 次用户（作品集受众）：Upwork 潜在客户，零摩擦体验这个工具，判断我的技术能力。
- **What（做什么）**：一个 **Web 应用**（FastAPI 后端 + 简洁前端），用户在页面上填写查询条件（关键词 / 技能标签 / 预算区间 / 项目类型 / 发布时间），点击搜索后：
  - 页面直接展示结果列表（标题可点击→投标页、技能标签、USD 换算后预算、竞标均价、竞争人数、发布时间、链接图标）
  - 客户端分页，默认每页 20 条，可切换 10/20/50
  - 技能标签选择器：页面加载时拉取全量标签缓存本地，支持模糊搜索多选
  - 默认查询 100 条，最多 500 条；查询数可在筛选面板调整
  - 结果下方展示 Chart.js 可视化：Top 10 技能柱状图 + 预算分布直方图
  - 一键下载 Excel（Sheet1 全量列表 + Sheet2 完整技能频次 + Sheet3 预算分布）
  - 预算统一换算为 USD（用 `currency.exchange_rate` 实时换算，区分固定价/时薪）
  - 部署到 Render 免费套餐，客户打开链接即可使用
- **Why（达到什么价值）**：
  - 个人价值：不用手动逐条判断，按真实 USD 预算和竞争度快速过滤值得投的单子；量化验证技术栈与市场需求的匹配度。
  - 作品集价值：客户零摩擦体验真实可用的工具；展示 Python 数据采集 + FastAPI + 前后端集成 + 云部署的完整技能链。

## 可行性 / 技术选型

- **数据源**：Freelancer.com 官方开发者 API（`GET /projects/0.1/projects/active/`），免费 + OAuth。
  - 支持：关键词搜索、`min_price`/`max_price`/`min_hourly_rate`/`max_hourly_rate` 预算过滤、`jobs[]` 技能过滤、`full_description`、`offset/limit` 翻页。
  - 解决 RemoteOK 三痛点：budget 必填（薪资数据全）、可翻页（不限 100 条）、接单市场（开发类项目多）。
- **已排除**：
  - Upwork：ToS 禁爬 + 官方 API 不能搜索市场岗位，且账号封禁风险不可接受（正是要接单的平台）。
  - Guru：robots.txt 禁 `/d/search/*`，搜索页不可爬。
  - WeWorkRemotely：全职远程岗，与 freelancer 接单场景不匹配。
- **迭代方向（不在本期范围）**：后续可加 PeoplePerHour HTML 爬虫作为第二数据源（robots.txt 允许岗位页）。
- **待补**：OAuth 注册流程验证、API 限流实测、字段结构确认（拿真实响应看 budget/skills 字段形态）。

## 验收标准

（第 3 步填写后引用 `docs/acceptance.md`）

- [ ] <可量化、可脚本检查的标准 1>
- [ ] <标准 2>
- [ ] <标准 3>

## 实现计划

（第 4 步填写后引用 `docs/plan.md`）

## 模块清单

- [x] 模块 1：后端基础（FastAPI 骨架 + /health）— 2 测试通过
- [x] 模块 2：Freelancer API 客户端（`backend/services/api_client.py`）— 10 测试通过，commit b3480e7
- [x] 模块 3：数据处理器（`backend/services/data_processor.py`）— 15 测试通过，commit 8b171e9
- [x] 模块 4：Excel 生成器（`backend/services/excel_generator.py`）— 11 测试通过，commit 8b171e9
- [x] 模块 5：API 路由（`backend/routes/`）— 12 测试通过（test_routes.py），全量 59 passed
- [x] 模块 6：前端结构（React + Vite）— 9 个文件，npm run build 通过，浏览器 6 步手工验证通过
- [x] 模块 7：图表集成（react-chartjs-2）— npm run build 通过（37 modules），浏览器确认两图渲染且随结果响应式变化
- [x] 模块 8：部署配置（Render）— render.yaml / README.md / 静态托管 SPA fallback，61 passed，8010 单端口浏览器验证通过

## 需求文档

- 中文版：`docs/requirements.zh.md`
- 英文版：`docs/requirements.en.md`

## 验收标准

- 验收标准文档：`docs/acceptance.md`
- 包含 6 条可量化标准：AC-001 API集成、AC-002 技能标签选择器、AC-003 客户端分页、AC-004 可视化、AC-005 Excel导出、AC-006 Render部署

## 下一步动作

模块 8 已实现完成并验证。证据：
- `npm run build` 通过（37 modules，dist/index.html 0.47 kB + assets/index-BS31nbux.js 299.62 kB）。
- 后端新增静态托管：`backend/main.py` 挂载 `frontend/dist/assets`（StaticFiles，带 304 协商缓存）+ SPA catch-all fallback（`/{full_path:path}` 回 index.html，带目录穿越防护），dist 未 build 时降级为纯 API 模式并打 warning。
- 全量 `pytest -q`：61 passed（新增 2 条 SPA 托管回归测试）。
- 8010 单端口（模拟 Render 生产行为）浏览器验证：`/` 返回构建后 SPA、`/api/jobs` 3422 条、搜 "python" 返回 99 条 + 两张 canvas（各 668×320，非透明像素 47623 / 98928）完整渲染；截图可见 Top 10 技能柱状图与预算分布直方图。
- 修了一个真实 bug：SPA catch-all 会把未知 `/api` 路径也回成 index.html（200 + HTML），导致前端 `fetch().json()` 解析报错——已加守卫让未匹配 `/api` 返回 404 JSON，并补测试锁定。
- README.md 重写：安装说明 + 三接口 API 文档 + Render 部署要点 + 项目结构。

已就绪可 deploy：`render.yaml`（Blueprint，单 web service、先 pip 后 npm build、`$PORT`、`/health` 健康检查、`PYTHON_VERSION`/`NODE_VERSION`/`FREELANCER_API_BASE_URL` 环境变量）、`requirements.txt`、`.gitignore`（含 `.venv/`）。

待用户 commit 确认后：推 GitHub → Render Dashboard New Blueprint → 选定本仓库 → 自动构建启动。

遗留：
- study/python/09-模块6-frontend.md 未写（用户明确表示暂不学习前端部分，跳过）。
- study/python/06-模块3-data-processor.md 缺 ★2/★3/★4 三节（已口头讲完未落盘）。
- code review 待记录到 docs/review.md（尚未创建，模块 5、6 均未记录）。
- 前端无自动化测试（未装 vitest），模块 7、8 靠浏览器手工验证。

## 决策摘要

- D-001：数据源选 Freelancer.com 官方 API，排除 Upwork/Guru/WWR；产出物从 CLI 升级为 Web 应用。详见 `.harness/decisions.md`。
- D-002（模块 5）：`SearchFilters` 用 dataclass 而非 Pydantic 模型，因为 search/export 需要共享同一组查询参数解析，避免两处声明 7 个 Query 参数导致定义漂移。
- D-003（模块 5）：`time_range` 由 api_client 换算成 `from_time = now - hours*3600` 传给上游；实测确认生效（24h→29、72h→80、168h→97、720h→97），故不采用后端按 `time_submitted` 过滤的备选方案。
- D-004（模块 5）：export 复用 `collect_projects` 而非接受前端回传数据，保证导出与页面一致、防篡改、省大 payload。
- D-005（模块 5）：API 客户端单例在 lifespan 中创建（非模块顶层），避免事件循环绑定问题，并保证进程退出前 `close()` 关闭连接池。
- D-006（模块 6）：不引入 shadcn/ui，技能多选与表格分页用原生 React 手写。理由：shadcn 需额外初始化（CLI、components.json、路径别名），对学习项目增加不必要的间接层；手写组件约 340 行、逻辑可直读。偏离 `docs/plan.zh.md` 模块 6 原定的 Combobox/Table/Pagination 方案。
- D-007（模块 6）：Vite 配置 `server.proxy` 把 `/api` 转发到 `http://localhost:8000`，`api.js` 里全部写相对路径。理由：开发期免 CORS 预检往返，且与生产（模块 8 让 FastAPI 挂载 `frontend/dist` 后同源）行为一致，无需切换 base URL。
- D-008（模块 7）：走 npm 安装 `react-chartjs-2@5.2.0` + `chart.js@4.4.7`（npmmirror 源规避 npmjs.org ECONNRESET）；图表组件里显式 `ChartJS.register(CategoryScale, LinearScale, BarElement, Tooltip)`——chart.js v4 是 tree-shaking 的，未注册的 scale/element 会在运行时抛 "not a registered scale"。Top 10 切片在前端做（`Object.entries(...).slice(0,10)`），后端 `skills_frequency` 已降序返回；预算直方图不硬编码分桶、直接取后端 `budget_distribution` 的 label 顺序，避免两边分桶定义漂移（该 dict 由 `build_budget_distribution` 保证恒有 5 个区间）。空态口径与 ResultsTable 一致：无结果时整块图表区不渲染。
- D-009（模块 8）：生产用单个 Render Web Service 同端口托管前后端，不拆 Static Site + Web Service。理由：backend/main.py 已挂载 `frontend/dist`，同源免生产 CORS 配置，免费套餐也只需一个服务额度。构建命令先 `pip install` 再 `cd frontend && npm ci && npm run build`（顺序有依赖——dist 必须先产出，否则启动时 FRONTEND_DIST 不存在而降级成纯 API 模式）。静态托管必须写在所有 API 路由注册之后（Starlette 按注册顺序匹配，先挂 `/{full_path:path}` 会盖住 /api 与 /health）。SPA catch-all 对未匹配的 `/api` 路径返回 404 JSON 而非回 index.html，避免前端 fetch 拿到 HTML 后 `.json()` 报解析错误。静态相关测试统一挂 `skipif(not FRONTEND_DIST.is_dir())`，保证 CI/纯后端环境未 build 前端时不报红。
