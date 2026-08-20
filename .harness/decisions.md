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

---

## D-002：前端选 React（Vite + Tailwind + shadcn/ui + react-chartjs-2），而非原生 JS

- **日期**：2026-08-20
- **状态**：已接受
- **背景**：产出物从 CLI + Excel 升级为"Web 界面 + Excel 导出"。第 4 步整体设计时，最初在 plan 中推荐原生 JS（HTML/CSS/JS + Chart.js CDN），理由是加载快、直接展示 JS 功力、代码直观、无构建链。用户反馈提出三点诉求：以后想走全栈、之前公司前端用的就是 React 想借机会学、担心纯 JS+CSS 不够好看。
- **决策**：前端改用 **React 18 + Vite + Tailwind CSS + shadcn/ui + react-chartjs-2**。FastAPI 挂载 `frontend/dist/` 作为静态文件（SPA fallback），Render 构建链前置 `cd frontend && npm install && npm run build`。
- **理由**（为什么不选备选方案）：
  - **不选原生 JS**：虽然零构建、加载快，但不匹配用户"全栈转型 + 学 React"的职业诉求；纯 JS+CSS 手写现代 UI 成本高、观感难保证。
  - **选 React**：契合目标岗位技术栈（公司在用），作品集体现前后端集成能力；Vite 构建快、开发体验好；**shadcn/ui** 提供复制粘贴式、Tailwind 驱动的现代组件（Combobox/Table/Pagination），非 npm 黑盒依赖，快速搭出专业外观解决"好看"问题；react-chartjs-2 以声明式 props 驱动图表，随数据响应式重渲染。
- **影响**：引入 Node 构建步骤，Render 部署时间增加（需缓存 node_modules + 提交 lockfile）；打包体积影响冷启动（用 tree-shaking + 代码分割 + 图表懒加载缓解）；开发本地需 `npm run dev`（localhost:5173）与后端 `uvicorn`（localhost:8000）双端；模块 6/7/8 结构相应调整（见 plan 模块 6 React 组件清单、模块 7 react-chartjs-2、模块 8 Node 构建链）。
