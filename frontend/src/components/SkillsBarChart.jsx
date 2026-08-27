import { useMemo } from 'react'
import {
  BarElement,
  CategoryScale,
  Chart as ChartJS,
  LinearScale,
  Tooltip,
} from 'chart.js'
import { Bar } from 'react-chartjs-2'

// chart.js v4 是 tree-shaking 的：用到的 scale / element / plugin 必须显式注册，
// 否则运行时报 "not a registered scale"。这里只注册柱状图需要的四个，不用 Legend
// （单数据集图例没信息量）。register 幂等，两个图表组件各注册一次不冲突。
ChartJS.register(CategoryScale, LinearScale, BarElement, Tooltip)

const TOP_N = 10

/**
 * Top 10 技能柱状图。
 *
 * 参数:
 *   frequency: 后端 /api/search 返回的 skills_frequency，形如 {技能名: 项目数}，
 *              已按频次降序（见 data_processor.build_skill_frequency），所以这里
 *              只切前 10 个，不再重复排序。
 *
 * 空数据（undefined 或空对象）时返回 null，由父组件决定整块图表区是否出现。
 */
export default function SkillsBarChart({ frequency }) {
  // useMemo：Object.entries + slice 只在 frequency 变化时重算。
  // 父组件每次重渲染都新建 data 对象会让 chart.js 误判数据已变而重画整张图。
  const data = useMemo(() => {
    const entries = Object.entries(frequency ?? {}).slice(0, TOP_N)
    return {
      labels: entries.map(([name]) => name),
      datasets: [
        {
          label: 'Projects',
          data: entries.map(([, count]) => count),
          backgroundColor: '#2563eb',
          borderRadius: 3,
        },
      ],
    }
  }, [frequency])

  const options = useMemo(
    () => ({
      // maintainAspectRatio: false + 外层固定高度 = 图表跟着容器宽度自适应，
      // 否则 canvas 会按默认 2:1 比例把高度撑得很大。
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        // 频次是整数计数，ticks.precision: 0 避免 Y 轴出现 2.5 这种刻度。
        y: { beginAtZero: true, ticks: { precision: 0 } },
        x: { ticks: { autoSkip: false, maxRotation: 45, minRotation: 0 } },
      },
    }),
    [],
  )

  if (data.labels.length === 0) return null

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4">
      <h2 className="mb-3 text-sm font-semibold text-gray-700">
        Top {TOP_N} skills
      </h2>
      <div className="h-64">
        <Bar data={data} options={options} />
      </div>
    </div>
  )
}
