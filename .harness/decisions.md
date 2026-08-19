# 决策记录（ADR）

> 记录"为什么选 A 不选 B"。每做一个影响后续开发的技术/设计决策，追加一条。

## 格式

每条决策包含：编号、日期、状态、标题、背景、决策、影响、理由（为什么不选备选方案）。

## 决策列表

---

## D-001：数据源选 Freelancer.com 官方 API，产出物定为 CLI + Excel

- **日期**：2026-08-19
- **状态**：已接受
- **背景**：上一版项目用 RemoteOK 免费 API，存在三个致命问题——有薪资范围的数据太少、每次只能查 100 条、开发类岗位少，无法支撑技能行情分析。需换数据源。最初想爬 Upwork（个人最想接单的平台），但需评估风控与合规风险。
- **决策**：数据源选 **Freelancer.com 官方开发者 API**（`GET /projects/0.1/projects/active/`）；产出物定为 **CLI + Excel 报表**（岗位列表 + 技术栈需求统计 + 预算分布）。
- **理由**（为什么不选备选方案）：
  - **不选 Upwork**：ToS 明文禁自动化采集，账号封禁风险不可接受（正是要接单的平台）；官方 API 仅能访问自己账号数据，不能搜索市场岗位；第三方 Upwork 数据 API 均为付费。
  - **不选 Guru**：robots.txt 禁止 `/d/search/*`，搜索页不可爬，只能绕 sitemap，性价比低。
  - **不选 WeWorkRemotely**：全职远程岗，与 freelancer 接单场景不匹配，不满足 Who/Why。
  - **PeoplePerHour 延后**：robots.txt 允许岗位页，可作为后续迭代的第二数据源（HTML 爬虫），本期不做以控制范围。
  - **选 Freelancer.com**：官方免费 API，budget 必填（薪资数据全）、offset/limit 翻页（不限条数）、接单市场开发项目多、支持关键词/技能/预算过滤——逐条解决 RemoteOK 三痛点；且与 Upwork 同为接单市场，分析结论有迁移价值。
  - **产出物选 CLI + Excel 而非 Web 看板**：贴近 Upwork 爬虫单最常见交付形态，范围最小；图表/看板留作迭代。
- **影响**：项目从"HTML 反爬型爬虫"转为"API 集成 + 数据清洗 + Excel 交付"管道；需注册 Freelancer.com 开发者应用走 OAuth；作品集展示面偏数据管道能力，后续迭代 PeoplePerHour 可补 HTML 解析展示面。
