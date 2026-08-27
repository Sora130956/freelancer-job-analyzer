import { exportExcel } from '../api'

/**
 * Excel 下载按钮。
 *
 * 不用 fetch 拿 blob，而是直接让浏览器打开 /api/export?<筛选条件>：
 * 后端已设 Content-Disposition: attachment，浏览器会当附件保存，
 * 省掉「读进内存 → createObjectURL → 手动释放」这一整套。
 * disabled：还没有搜索结果时禁用，避免导出一个空表。
 */
export default function ExportButton({ filters, disabled }) {
  return (
    <button
      type="button"
      onClick={() => exportExcel(filters)}
      disabled={disabled}
      className="rounded border border-green-600 px-4 py-2 text-sm font-medium text-green-700 hover:bg-green-50 disabled:opacity-40"
    >
      下载 Excel
    </button>
  )
}
