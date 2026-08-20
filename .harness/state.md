# 项目状态（单一进度源）

> 本文件是项目进度的唯一来源。每次会话结束前必须更新本文件。换会话、换模型都靠它接上进度。

## 当前阶段

第 3 步（验收标准）—— 已完成验收标准文档（`docs/acceptance.md`），包含 6 条可量化可脚本验证的标准，待进入第 4 步可行性分析

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

（第 4 步拆分后填写）

## 需求文档

- 中文版：`docs/requirements.zh.md`
- 英文版：`docs/requirements.en.md`

## 验收标准

- 验收标准文档：`docs/acceptance.md`
- 包含 6 条可量化标准：AC-001 API集成、AC-002 技能标签选择器、AC-003 客户端分页、AC-004 可视化、AC-005 Excel导出、AC-006 Render部署

## 下一步动作

1. 进入第 4 步：可行性分析与技术栈选型。
2. 输出实现计划 `docs/plan.md`，拆解模块清单。

## 决策摘要

- D-001：数据源选 Freelancer.com 官方 API，排除 Upwork/Guru/WWR；产出物从 CLI 升级为 Web 应用。详见 `.harness/decisions.md`。
