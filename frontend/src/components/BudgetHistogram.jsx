import { useMemo } from 'react'
import {
  BarElement,
  CategoryScale,
  Chart as ChartJS,
  LinearScale,
  Tooltip,
} from 'chart.js'
import { Bar } from 'react-chartjs-2'

// 同 SkillsBarChart：chart.js v4 需显式注册用到的模块。
ChartJS.register(CategoryScale, LinearScale, BarElement, Tooltip)

/**
 * 预算分布直方图。
 *
 * 参数:
 *   distribution: 后端返回的 budget_distribution，形如 {"<$50": 3, "$50-$150": 8, ...}。
 *                 后端保证 5 个区间即使计数为 0 也保留（见 build_budget_distribution），
 *                 所以直接按对象顺序取 label，不在前端硬编码分桶，避免两边分桶定义漂移。
 *
 * 全部区间都是 0（即没有任何项目带预算上限）时返回 null，不画一张空图。
 */
export default function BudgetHistogram({ distribution }) {
  const data = useMemo(() => {
    const entries = Object.entries(distribution ?? {})
    return {
      labels: entries.map(([label]) => label),
      datasets: [
        {
          label: 'Projects',
          data: entries.map(([, count]) => count),
          backgroundColor: '#0d9488',
          borderRadius: 3,
        },
      ],
    }
  }, [distribution])

  const options = useMemo(
    () => ({
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        y: { beginAtZero: true, ticks: { precision: 0 } },
        // 直方图的分桶是连续区间，categoryPercentage 调大让相邻柱子挨紧，
        // 视觉上区别于上面那张离散的技能柱状图。
        x: { ticks: { autoSkip: false } },
      },
      datasets: { bar: { categoryPercentage: 0.95, barPercentage: 0.98 } },
    }),
    [],
  )

  const total = data.datasets[0].data.reduce((sum, n) => sum + n, 0)
  if (data.labels.length === 0 || total === 0) return null

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4">
      <h2 className="mb-3 text-sm font-semibold text-gray-700">
        Budget distribution (USD)
      </h2>
      <div className="h-64">
        <Bar data={data} options={options} />
      </div>
    </div>
  )
}
