import { useMemo, useState } from 'react'

const PAGE_SIZE_CHOICES = [10, 20, 50]

/** 把 USD 金额格式化成 "$120" 这样的短文本；缺值显示 "—"。 */
function money(value) {
  if (value == null) return '—'
  return `$${Math.round(value).toLocaleString('en-US')}`
}

/** 预算区间：只有下限或只有上限时也要能读，故分别兜底。 */
function budgetRange(project) {
  const { budget_min_usd: min, budget_max_usd: max, type } = project
  const suffix = type === 'hourly' ? '/hr' : ''
  if (min == null && max == null) return '—'
  if (max == null) return `${money(min)}${suffix}+`
  if (min == null) return `≤ ${money(max)}${suffix}`
  return `${money(min)} – ${money(max)}${suffix}`
}

/** Unix 秒级时间戳 → 相对时间文案（"2h ago"）。 */
function relativeTime(unixSeconds) {
  const diffMs = Date.now() - unixSeconds * 1000
  const minutes = Math.floor(diffMs / 60000)
  if (minutes < 60) return `${Math.max(minutes, 0)}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  return `${Math.floor(hours / 24)}d ago`
}

/**
 * 结果表格 + 客户端分页。
 *
 * 客户端分页含义：projects 是一次搜索取回的全量数据（最多 500 条），
 * 切页只是对这个数组做 slice，不再发网络请求（AC-003 要求）。
 * page / pageSize 属于「纯展示状态」，所以放在本组件内部而不是提到 App。
 */
export default function ResultsTable({ projects }) {
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)

  const totalPages = Math.max(1, Math.ceil(projects.length / pageSize))
  // 数据或每页条数变化后，当前页可能越界（比如原来在第 11 页，改成 50 条/页后只剩 5 页）。
  const safePage = Math.min(page, totalPages)

  // useMemo：只有 projects / safePage / pageSize 变化时才重新切片，
  // 避免每次父组件重渲染都白算一遍（数据量到 500 条时有意义）。
  const pageRows = useMemo(() => {
    const start = (safePage - 1) * pageSize
    return projects.slice(start, start + pageSize)
  }, [projects, safePage, pageSize])

  if (projects.length === 0) {
    return (
      <p className="rounded-lg border border-dashed border-gray-300 p-8 text-center text-sm text-gray-500">
        No results yet. Set your filters above and hit Search.
      </p>
    )
  }

  return (
    <section className="space-y-3">
      {/* 摘要栏 + 每页条数 */}
      <div className="flex flex-wrap items-center justify-between gap-3 text-sm">
        <span>
          <strong>{projects.length}</strong> projects found — page {safePage} of {totalPages}
        </span>
        <label className="flex items-center gap-2">
          Per page
          <select
            value={pageSize}
            onChange={(e) => {
              setPageSize(Number(e.target.value))
              setPage(1)
            }}
            className="rounded border border-gray-300 px-2 py-1"
          >
            {PAGE_SIZE_CHOICES.map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
        </label>
      </div>

      {/* 表格 */}
      <div className="overflow-x-auto rounded-lg border border-gray-200">
        <table className="min-w-full divide-y divide-gray-200 text-sm">
          <thead className="bg-gray-50 text-left text-xs uppercase text-gray-500">
            <tr>
              <th className="px-3 py-2">Title</th>
              <th className="px-3 py-2">Skills</th>
              <th className="px-3 py-2">Budget (USD)</th>
              <th className="px-3 py-2">Avg bid</th>
              <th className="px-3 py-2">Bids</th>
              <th className="px-3 py-2">Type</th>
              <th className="px-3 py-2">Posted</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 bg-white">
            {pageRows.map((p) => (
              <tr key={p.id} className="hover:bg-gray-50">
                <td className="max-w-xs px-3 py-2">
                  <a
                    href={`https://www.freelancer.com/projects/${p.seo_url ?? ''}`}
                    target="_blank"
                    rel="noreferrer"
                    className="text-blue-600 hover:underline"
                  >
                    {p.title}
                  </a>
                </td>
                <td className="px-3 py-2">
                  <div className="flex flex-wrap gap-1">
                    {p.jobs.slice(0, 4).map((j) => (
                      <span
                        key={j.id}
                        className="rounded bg-gray-100 px-1.5 py-0.5 text-xs text-gray-700"
                      >
                        {j.name}
                      </span>
                    ))}
                  </div>
                </td>
                <td className="whitespace-nowrap px-3 py-2">{budgetRange(p)}</td>
                <td className="whitespace-nowrap px-3 py-2">{money(p.bid_avg_usd)}</td>
                <td className="px-3 py-2">{p.bid_stats?.bid_count ?? '—'}</td>
                <td className="px-3 py-2">
                  <span className="rounded bg-gray-100 px-2 py-0.5 text-xs">
                    {p.type === 'hourly' ? 'Hourly' : 'Fixed'}
                  </span>
                </td>
                <td className="whitespace-nowrap px-3 py-2 text-gray-500">
                  {relativeTime(p.time_submitted)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* 分页控件 */}
      <div className="flex items-center justify-center gap-1 text-sm">
        <button
          type="button"
          onClick={() => setPage(safePage - 1)}
          disabled={safePage === 1}
          className="rounded border border-gray-300 px-2 py-1 disabled:opacity-40"
        >
          &lt;
        </button>
        {Array.from({ length: totalPages }, (_, i) => i + 1)
          // 页数多时只显示当前页附近的页码，避免 26 个按钮铺满一行。
          .filter((n) => n === 1 || n === totalPages || Math.abs(n - safePage) <= 2)
          .map((n, idx, arr) => (
            <span key={n} className="flex items-center gap-1">
              {idx > 0 && n - arr[idx - 1] > 1 && <span className="px-1">…</span>}
              <button
                type="button"
                onClick={() => setPage(n)}
                className={`rounded border px-2.5 py-1 ${
                  n === safePage
                    ? 'border-blue-600 bg-blue-600 text-white'
                    : 'border-gray-300 hover:bg-gray-100'
                }`}
              >
                {n}
              </button>
            </span>
          ))}
        <button
          type="button"
          onClick={() => setPage(safePage + 1)}
          disabled={safePage === totalPages}
          className="rounded border border-gray-300 px-2 py-1 disabled:opacity-40"
        >
          &gt;
        </button>
      </div>
    </section>
  )
}
