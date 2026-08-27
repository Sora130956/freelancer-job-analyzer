# 项目状态（单一进度源）

> 本文件是项目进度的唯一来源。每次会话结束前必须更新本文件。换会话、换模型都靠它接上进度。

## 当前阶段

第 5 步（生成 → validate → review）—— 后端模块 1-5 全量回归 59 passed；模块 6 前端已实现并通过浏览器 6 步手工验证，待进入模块 7

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
- [ ] 模块 7：图表集成（react-chartjs-2）
- [ ] 模块 8：部署配置（Render）

## 需求文档

- 中文版：`docs/requirements.zh.md`
- 英文版：`docs/requirements.en.md`

## 验收标准

- 验收标准文档：`docs/acceptance.md`
- 包含 6 条可量化标准：AC-001 API集成、AC-002 技能标签选择器、AC-003 客户端分页、AC-004 可视化、AC-005 Excel导出、AC-006 Render部署

## 下一步动作

模块 6 已实现完成（frontend/ 9 个文件），`npm run build` 通过（31 modules），浏览器 6 步手工验证全部通过：
页面加载填充 3422 个技能标签、"scra" 模糊匹配、选中出芯片、搜索返回 49 条 3 页每页 20、
切第 2 页无新网络请求（客户端分页成立）、`GET /api/export` 返回 200、刷新走 sessionStorage 缓存不重复请求。
后端未改动，59 passed 仍有效。待用户 commit 确认后进入模块 7：图表集成（react-chartjs-2）。

遗留：
- study/python/09-模块6-frontend.md 未写（用户明确表示暂不学习前端部分，跳过）。
- study/python/06-模块3-data-processor.md 缺 ★2/★3/★4 三节（已口头讲完未落盘）。
- code review 待记录到 docs/review.md（尚未创建，模块 5、6 均未记录）。
- 前端无自动化测试（未装 vitest），模块 6 靠浏览器手工验证；如需回归可在模块 8 前补。

## 决策摘要

- D-001：数据源选 Freelancer.com 官方 API，排除 Upwork/Guru/WWR；产出物从 CLI 升级为 Web 应用。详见 `.harness/decisions.md`。
- D-002（模块 5）：`SearchFilters` 用 dataclass 而非 Pydantic 模型，因为 search/export 需要共享同一组查询参数解析，避免两处声明 7 个 Query 参数导致定义漂移。
- D-003（模块 5）：`time_range` 由 api_client 换算成 `from_time = now - hours*3600` 传给上游；实测确认生效（24h→29、72h→80、168h→97、720h→97），故不采用后端按 `time_submitted` 过滤的备选方案。
- D-004（模块 5）：export 复用 `collect_projects` 而非接受前端回传数据，保证导出与页面一致、防篡改、省大 payload。
- D-005（模块 5）：API 客户端单例在 lifespan 中创建（非模块顶层），避免事件循环绑定问题，并保证进程退出前 `close()` 关闭连接池。
- D-006（模块 6）：不引入 shadcn/ui，技能多选与表格分页用原生 React 手写。理由：shadcn 需额外初始化（CLI、components.json、路径别名），对学习项目增加不必要的间接层；手写组件约 340 行、逻辑可直读。偏离 `docs/plan.zh.md` 模块 6 原定的 Combobox/Table/Pagination 方案。
- D-007（模块 6）：Vite 配置 `server.proxy` 把 `/api` 转发到 `http://localhost:8000`，`api.js` 里全部写相对路径。理由：开发期免 CORS 预检往返，且与生产（模块 8 让 FastAPI 挂载 `frontend/dist` 后同源）行为一致，无需切换 base URL。
