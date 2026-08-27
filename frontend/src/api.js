// api.js —— 唯一负责和 FastAPI 后端通信的地方。
// 其他组件只 import 这里的函数，不直接写 fetch。
// 好处：base URL、错误处理、URL 拼装都集中在一处，改后端地址只改这里。

// 后端 search 端点接受 7 个查询参数，这里用 buildParams 统一拼装。
// null / undefined / 空串会被过滤掉，避免发一个没意义的占位参数。
const DEFAULT_LIMIT = 100

function buildParams(filters) {
  const params = new URLSearchParams()
  const { keywords, jobs, budget_min, budget_max, project_type, time_range, limit } = filters

  if (keywords) params.append('keywords', keywords)
  // FREELANCER_API 用 jobs[] 作为数组参数名（重复键），这里逐个 append 即可。
  if (jobs && jobs.length) jobs.forEach((id) => params.append('jobs[]', id))
  if (budget_min != null) params.append('budget_min', budget_min)
  if (budget_max != null) params.append('budget_max', budget_max)
  if (project_type) params.append('project_type', project_type)
  if (time_range != null) params.append('time_range', time_range)
  if (limit != null) params.append('limit', limit)

  return params.toString()
}

/** 拉取全量技能标签列表（GET /api/jobs）。返回 [{id, name}, ...]。 */
export async function fetchJobs() {
  const res = await fetch('/api/jobs')
  if (!res.ok) throw new Error(`加载技能标签失败：HTTP ${res.status}`)
  return res.json()
}

/** 按筛选条件搜索（GET /api/search）。返回 SearchResponse。 */
export async function searchJobs(filters) {
  const qs = buildParams(filters)
  const res = await fetch(`/api/search?${qs}`)
  if (!res.ok) throw new Error(`搜索失败：HTTP ${res.status}`)
  return res.json()
}

/** 按当前筛选条件导出 Excel（GET /api/export）。该方法直接触发浏览器下载。 */
export function exportExcel(filters) {
  const qs = buildParams(filters)
  // 方案：动态创建一个 <a>，href 指向 /api/export?<qs>，点击后靠 Content-Disposition
  // 附件头让浏览器直接保存文件。全程无需把 xlsx 读进内存。
  const a = document.createElement('a')
  a.href = `/api/export?${qs}`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
}

export { DEFAULT_LIMIT }
