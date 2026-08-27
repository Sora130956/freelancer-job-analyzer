import { useState } from 'react'

// 时间范围选项：value 对应后端 time_range（小时），label 是界面文案。
const TIME_RANGES = [
  { value: '', label: '不限' },
  { value: 24, label: '24 小时内' },
  { value: 72, label: '3 天内' },
  { value: 168, label: '7 天内' },
  { value: 720, label: '30 天内' },
]

// 结果条数选项：对应后端 limit，取值 10..500（这里只提供常用档位）。
const LIMIT_CHOICES = [100, 200, 300, 500]

/**
 * 筛选面板：收集关键词/技能/预算/类型/发布时间/条数，并触发搜索。
 *
 * filters 是 App 里集中管理的筛选状态对象（单一来源）。
 * 组件本身不持有状态，只负责把用户的每次输入写回 filters（通过 onChange），
 * 这样「筛选条件」与「结果」都由 App 统一管理，切页/导出都能复用同一份条件。
 */
export default function FilterPanel({ jobs, filters, onChange, onSearch, loading }) {
  // 技能输入框的当前文字（仅用于模糊过滤列表，不立即写入 filters）。
  const [skillQuery, setSkillQuery] = useState('')

  // 改单个筛选字段的小助手：复制一份 filters 再覆盖那一个 key，
  // 保持「不直接修改原对象」的 React 惯例（改原对象不会触发重渲染）。
  const set = (key, value) => onChange({ ...filters, [key]: value })

  // 根据输入文字模糊过滤技能标签（name 包含输入内容即可，忽略大小写）。
  const query = skillQuery.trim().toLowerCase()
  const matchedSkills = query
    ? jobs.filter((job) => job.name.toLowerCase().includes(query))
    : jobs

  // 只渲染前 50 条：3422 个标签全部塞进 DOM 会明显拖慢下拉框。
  const visibleSkills = matchedSkills.slice(0, 50)

  // 在已选集合里判断某个技能是否被选中（App 层用 jobs 存的 id 数组）。
  const isSelected = (id) => filters.jobs.includes(id)

  // 点击选项：把点击的技能 id 加入/移出 filters.jobs。
  // 已选中就 filter 掉，未选中就展开旧数组再追加 —— 两条路径都产出新数组，不改原数组。
  const toggleSkill = (id) => {
    const current = filters.jobs
    const next = current.includes(id)
      ? current.filter((x) => x !== id)
      : [...current, id]
    onChange({ ...filters, jobs: next })
  }

  // 把选中的技能 id 翻译成名称，用于展示芯片文字。
  const selectedSkills = filters.jobs
    .map((id) => jobs.find((j) => j.id === id))
    .filter(Boolean)

  return (
    <section className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        {/* 关键词 */}
        <label className="flex flex-col gap-1 text-sm">
          <span>关键词</span>
          <input
            type="text"
            value={filters.keywords}
            onChange={(e) => set('keywords', e.target.value)}
            placeholder="例如 python"
            className="rounded border border-gray-300 px-3 py-2"
          />
        </label>

        {/* 项目类型 */}
        <label className="flex flex-col gap-1 text-sm">
          <span>项目类型</span>
          <select
            value={filters.project_type}
            onChange={(e) => set('project_type', e.target.value)}
            className="rounded border border-gray-300 px-3 py-2"
          >
            <option value="">全部</option>
            <option value="fixed">固定价</option>
            <option value="hourly">时薪</option>
          </select>
        </label>

        {/* 发布时间 + 结果条数 */}
        <label className="flex flex-col gap-1 text-sm">
          <span>发布时间</span>
          <select
            value={filters.time_range ?? ''}
            onChange={(e) => set('time_range', Number(e.target.value) || null)}
            className="rounded border border-gray-300 px-3 py-2"
          >
            {TIME_RANGES.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </select>
        </label>

        {/* 预算区间 */}
        <label className="flex flex-col gap-1 text-sm">
          <span>预算下限 (USD)</span>
          <input
            type="number"
            value={filters.budget_min ?? ''}
            onChange={(e) =>
              set('budget_min', e.target.value === '' ? null : Number(e.target.value))
            }
            placeholder="0"
            className="rounded border border-gray-300 px-3 py-2"
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          <span>预算上限 (USD)</span>
          <input
            type="number"
            value={filters.budget_max ?? ''}
            onChange={(e) =>
              set('budget_max', e.target.value === '' ? null : Number(e.target.value))
            }
            placeholder="无上限"
            className="rounded border border-gray-300 px-3 py-2"
          />
        </label>

        {/* 结果条数 */}
        <label className="flex flex-col gap-1 text-sm">
          <span>结果条数</span>
          <select
            value={filters.limit}
            onChange={(e) => set('limit', Number(e.target.value))}
            className="rounded border border-gray-300 px-3 py-2"
          >
            {LIMIT_CHOICES.map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
        </label>
      </div>

      {/* 技能多选 */}
      <div className="mt-4 text-sm">
        <span>技能标签</span>

        {/* 已选芯片 */}
        {selectedSkills.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-2">
            {selectedSkills.map((job) => (
              <span
                key={job.id}
                className="inline-flex items-center gap-1 rounded-full bg-blue-100 px-3 py-1 text-xs text-blue-700"
              >
                {job.name}
                <button
                  type="button"
                  onClick={() => toggleSkill(job.id)}
                  aria-label={`移除 ${job.name}`}
                  className="text-blue-700 hover:text-blue-900"
                >
                  ×
                </button>
              </span>
            ))}
          </div>
        )}

        {/* 搜索输入 + 下拉列表 */}
        <input
          type="text"
          value={skillQuery}
          onChange={(e) => setSkillQuery(e.target.value)}
          placeholder="搜索标签… 例如 scra"
          className="mt-2 w-full rounded border border-gray-300 px-3 py-2"
        />
        {skillQuery && (
          <ul className="mt-1 max-h-40 overflow-y-auto rounded border border-gray-200 bg-white">
            {visibleSkills.length === 0 && (
              <li className="px-3 py-2 text-gray-400">无匹配标签</li>
            )}
            {visibleSkills.map((job) => (
              <li key={job.id}>
                <button
                  type="button"
                  onClick={() => toggleSkill(job.id)}
                  className={`flex w-full px-3 py-1.5 text-left hover:bg-gray-100 ${
                    isSelected(job.id) ? 'bg-blue-50 text-blue-700' : ''
                  }`}
                >
                  {job.name} {isSelected(job.id) ? '✓' : ''}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* 搜索按钮 */}
      <button
        type="button"
        onClick={onSearch}
        disabled={loading}
        className="mt-4 rounded bg-blue-600 px-5 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
      >
        {loading ? '搜索中…' : '搜索'}
      </button>
    </section>
  )
}
