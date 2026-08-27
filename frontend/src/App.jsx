import { useEffect, useState } from 'react'
import FilterPanel from './components/FilterPanel'
import ResultsTable from './components/ResultsTable'
import ExportButton from './components/ExportButton'
import { fetchJobs, searchJobs, DEFAULT_LIMIT } from './api'

// 筛选条件的初始值。空串/null 在 api.js 里会被过滤掉，不会发给后端。
const INITIAL_FILTERS = {
  keywords: '',
  jobs: [],
  budget_min: null,
  budget_max: null,
  project_type: '',
  time_range: null,
  limit: DEFAULT_LIMIT,
}

// 技能标签缓存在 sessionStorage：3422 条数据极少变动，
// 刷新页面时直接读缓存，省一次 /api/jobs 往返（需求 §3.2 的会话级缓存）。
const SKILLS_CACHE_KEY = 'freelancer-analyzer:jobs'

/**
 * 根组件：持有全局状态（技能列表、筛选条件、搜索结果、加载/错误），
 * 并把它们分发给三个子组件。
 *
 * 状态放在这里而不是各子组件内部，是因为它们要被跨组件共享：
 * filters 既被 FilterPanel 编辑，也被 ExportButton 用来拼导出 URL；
 * result 既喂给 ResultsTable，也决定导出按钮是否可用。
 */
export default function App() {
  const [jobs, setJobs] = useState([])
  const [filters, setFilters] = useState(INITIAL_FILTERS)
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  // useEffect(..., []) = 组件首次挂载后执行一次，用于加载技能标签。
  // 空依赖数组是关键：不写它会每次渲染都重新请求。
  useEffect(() => {
    const cached = sessionStorage.getItem(SKILLS_CACHE_KEY)
    if (cached) {
      setJobs(JSON.parse(cached))
      return
    }
    fetchJobs()
      .then((data) => {
        setJobs(data)
        sessionStorage.setItem(SKILLS_CACHE_KEY, JSON.stringify(data))
      })
      .catch((err) => setError(err.message))
  }, [])

  /** 点击搜索：调 /api/search 并把整份结果存进 state（供客户端分页切片用）。 */
  const handleSearch = async () => {
    setLoading(true)
    setError('')
    try {
      const data = await searchJobs(filters)
      setResult(data)
    } catch (err) {
      setError(err.message)
      setResult(null)
    } finally {
      setLoading(false)
    }
  }

  const projects = result?.projects ?? []

  return (
    <div className="min-h-screen bg-gray-50 px-4 py-6">
      <div className="mx-auto max-w-6xl space-y-5">
        <header className="flex items-end justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-gray-900">
              Freelancer Job Analyzer
            </h1>
            <p className="mt-1 text-sm text-gray-500">
              按预算、技能与竞争度筛选 Freelancer.com 上的可投项目
            </p>
          </div>
          <ExportButton filters={filters} disabled={projects.length === 0} />
        </header>

        <FilterPanel
          jobs={jobs}
          filters={filters}
          onChange={setFilters}
          onSearch={handleSearch}
          loading={loading}
        />

        {error && (
          <p className="rounded border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-700">
            {error}
          </p>
        )}

        <ResultsTable projects={projects} />
      </div>
    </div>
  )
}
