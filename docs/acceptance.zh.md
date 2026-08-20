# 验收标准 — Freelancer 任务分析器

**版本：** 1.0  
**日期：** 2026-08-19  
**状态：** 准备实现（第 3 步）

---

## 概述

本文档定义 Freelancer 任务分析器 Web 应用的验收标准。每条标准均可量化且可通过自动化或手工检查验证。

---

## AC-001: API 集成与数据获取

**前置条件** 用户提交带筛选条件的搜索请求  
**执行操作** 后端调用 Freelancer.com API (`GET /projects/0.1/projects/active/`)  
**预期结果** 系统必须：

- 成功获取项目数据，参数包含 `job_details=true`, `full_description=true`, `compact=true`
- 通过 `offset` 参数支持分页（每次请求 100 条结果，最多 500 条）
- 优雅处理限流（50 次/分钟，1000 次/小时）
- 使用 `currency.exchange_rate` 将所有预算金额换算为 USD
- 返回结构化 JSON，包含字段：`id`, `title`, `seo_url`, `budget`, `jobs[]`, `bid_stats`, `type`, `time_submitted`

**验证方法：**
```bash
# 测试 API 端点和筛选条件
curl "http://localhost:8000/api/search?keywords=python&limit=100" | jq '.projects | length'
# 预期：100（或更少，如果结果不足 100 条）

# 验证 USD 换算
curl "http://localhost:8000/api/search?limit=10" | jq '.projects[0].budget_usd'
# 预期：数值型 USD 金额，而非原始货币
```

---

## AC-002: 技能标签选择器（带模糊搜索）

**前置条件** 用户打开网页  
**执行操作** 页面加载  
**预期结果** 系统必须：

- 从 `GET /projects/0.1/jobs/` 获取全部技能标签并本地缓存（session storage）
- 渲染可搜索的多选下拉框
- 支持模糊过滤：输入 "py" 显示 "Python", "PyQt", "PySpark"
- 选中的标签显示为输入框上方的可移除芯片
- 向后端发送选中的标签 ID 数组 `jobs[]`

**验证方法：**
```bash
# 检查 /api/jobs 端点返回完整标签列表
curl "http://localhost:8000/api/jobs" | jq 'length'
# 预期：> 500 个标签

# 浏览器手工测试：
# 1. 打开页面 → 下拉框显示所有标签
# 2. 输入 "scra" → 看到 "Web Scraping", "Scrapy"
# 3. 选中两个 → 芯片出现在输入框上方
# 4. 点击搜索 → network 面板显示 `jobs[]=3&jobs=17`
```

---

## AC-003: 客户端分页与结果展示

**前置条件** 用户收到搜索结果（例如 211 个项目）  
**执行操作** 结果渲染  
**预期结果** 系统必须：

- 将所有获取的结果缓存在内存（切页时无重复请求）
- 默认每页 20 条
- 允许用户切换每页条数（10 / 20 / 50）
- 显示分页控件：`[< 1 2 3 … 11 >]`
- 显示摘要："Found 211 results, page 1 of 11"
- 渲染表格，标题可点击跳转 → `https://www.freelancer.com/projects/{seo_url}`

**验证方法：**
```bash
# 浏览器功能测试：
# 1. 搜索 "python scraping" → 看到 "Found X results"
# 2. 默认显示 20 行
# 3. 点击第 2 页 → 显示接下来 20 行（无新 network 请求）
# 4. 改为每页 50 条 → 分页控件更新，仍无新请求
# 5. 点击标题链接 → 新标签页打开 Freelancer 项目页面
```

---

## AC-004: Chart.js 可视化（Top 10 技能 + 预算分布）

**前置条件** 搜索结果已显示  
**执行操作** 用户滚动到可视化区域  
**预期结果** 系统必须：

- 渲染**柱状图**显示 Top 10 技能频次（例如 Python: 85, Selenium: 42, …）
- 渲染**直方图**显示预算分布区间：<$50, $50-$150, $150-$500, $500-$1000, $1000+
- 使用 Chart.js 库渲染
- 图表仅反映**当前筛选结果**，而非全量历史数据

**验证方法：**
```bash
# 浏览器手工测试：
# 1. 搜索 "python" → 柱状图顶部显示 Python 相关技能
# 2. 通过浏览器控制台检查图表数据：
#    document.querySelector('canvas').chart.data.datasets[0].data
#    → 预期：10 个数字组成的数组（频次）
# 3. 直方图显示预算区间与正确计数
```

---

## AC-005: Excel 导出（三个 Sheet）

**前置条件** 用户点击"Download Excel"按钮  
**执行操作** 触发导出  
**预期结果** 系统必须：

- 使用 `pandas` + `openpyxl` 生成 `.xlsx` 文件
- **Sheet 1 "Projects"**：全量结果列表，列名：Title, Skills, Budget (USD), Avg Bid, Bid Count, Type, Posted, URL
- **Sheet 2 "Skills Frequency"**：完整技能频次表（非仅 Top 10），降序排列
- **Sheet 3 "Budget Distribution"**：预算区间与项目计数

**验证方法：**
```bash
# 通过浏览器下载 Excel 文件，然后：
python -c "
import openpyxl
wb = openpyxl.load_workbook('freelancer_projects.xlsx')
print(wb.sheetnames)  # 预期：['Projects', 'Skills Frequency', 'Budget Distribution']
print(len(wb['Projects']['A']))  # 预期：行数 = 获取结果数 + 1（表头）
print(wb['Skills Frequency']['A2'].value)  # 预期：频次最高的技能名称
"
```

---

## AC-006: 部署到 Render（免费套餐）

**前置条件** 应用已准备好生产发布  
**执行操作** 部署到 Render 免费套餐  
**预期结果** 系统必须：

- 通过公开 HTTPS URL 可访问（例如 `https://freelancer-analyzer.onrender.com`）
- 从单个 FastAPI 应用同时提供前端和 API
- 冷启动时 15 秒内加载完成（Render 免费套餐限制）
- 在桌面浏览器（Chrome, Firefox, Safari）上正确显示

**验证方法：**
```bash
# 检查部署健康状态
curl -I https://freelancer-analyzer.onrender.com/
# 预期：HTTP/2 200

# 负载测试（手工）：
# 1. 无痕模式打开 URL → 15 秒内页面加载完成
# 2. 提交搜索 → 结果出现
# 3. 下载 Excel → 文件成功下载
```

---

## 完成检查清单

标记项目为"完成"之前，验证所有标准：

- [ ] AC-001: API 集成正常，USD 换算正确
- [ ] AC-002: 技能标签选择器带模糊搜索功能正常
- [ ] AC-003: 客户端分页正常，无不必要的 API 调用
- [ ] AC-004: 图表正确渲染且反映筛选数据
- [ ] AC-005: Excel 导出包含 3 个 Sheet，数据正确
- [ ] AC-006: 已部署到 Render，公开可访问

---

## 明确不包含的功能（Out of Scope）

- 用户认证 / 登录系统
- 保存搜索历史或收藏
- 新项目实时通知
- 移动端响应式设计（桌面优先，用于作品集展示）
- 多语言 UI 支持（仅英文）
- 数据库持久化（所有数据基于会话）
