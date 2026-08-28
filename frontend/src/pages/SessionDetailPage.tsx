import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, type SessionDetail } from '../api'
import PawHeatmap from '../components/PawHeatmap'
import RoundSummaryCards from '../components/RoundSummaryCards'
import SummaryStats from '../components/SummaryStats'
import SymmetryTrendChart from '../components/SymmetryTrendChart'

const EMPTY_MATRIX = Array.from({ length: 16 }, () => Array(10).fill(0))

export default function SessionDetailPage() {
  const { id } = useParams<{ id: string }>()
  const [detail, setDetail] = useState<SessionDetail | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!id) return
    api.getSession(Number(id)).then(setDetail).catch((e) => setError(String(e)))
  }, [id])

  if (error) return <div className="p-6 text-sm text-[#e24b4a]">불러오기 실패: {error}</div>
  if (!detail) return <div className="p-6 text-sm text-[#5f5e5a]">불러오는 중...</div>

  const lastStep = detail.steps[detail.steps.length - 1]
  const left = lastStep?.left_matrix ?? EMPTY_MATRIX
  const right = lastStep?.right_matrix ?? EMPTY_MATRIX

  return (
    <div className="max-w-[1100px] mx-auto px-4 py-4 flex flex-col gap-5">
      <Link to="/sessions" className="text-xs text-[#5f5e5a]">
        ← 세션 이력
      </Link>
      <h1 className="text-lg font-bold">
        {detail.dog_name} · {new Date(detail.started_at).toLocaleString('ko-KR')}
      </h1>

      <div className="bg-white rounded-xl border border-black/5 p-5">
        <div className="grid grid-cols-2 gap-6">
          <PawHeatmap matrix={left} label="왼발 (정상 발 · 기준)" sublabel="마지막 걸음 기준" />
          <PawHeatmap matrix={right} label="오른발 (검사 발)" sublabel="마지막 걸음 기준" />
        </div>
      </div>

      <div className="bg-white rounded-xl border border-black/5 p-5">
        <SymmetryTrendChart steps={detail.steps} />
      </div>

      <SummaryStats steps={detail.steps} />

      <div className="bg-white rounded-xl border border-black/5 p-5">
        <RoundSummaryCards rounds={detail.rounds} />
      </div>
    </div>
  )
}
