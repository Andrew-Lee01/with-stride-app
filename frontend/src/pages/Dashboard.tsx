import { useCallback, useEffect, useRef, useState } from 'react'
import { api, sessionWsUrl, type SessionDetail, type StepOut } from '../api'
import PawHeatmap from '../components/PawHeatmap'
import RoundSummaryCards from '../components/RoundSummaryCards'
import StatusBanner from '../components/StatusBanner'
import SummaryStats from '../components/SummaryStats'
import SymmetryTrendChart from '../components/SymmetryTrendChart'
import BleConnectPanel from '../components/BleConnectPanel'

const EMPTY_MATRIX = Array.from({ length: 16 }, () => Array(10).fill(0))

export default function Dashboard() {
  const [detail, setDetail] = useState<SessionDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const wsRef = useRef<WebSocket | null>(null)

  const loadLatestSession = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const sessions = await api.listSessions()
      if (sessions.length === 0) {
        setDetail(null)
        return
      }
      const latest = await api.getSession(sessions[0].id)
      setDetail(latest)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadLatestSession()
  }, [loadLatestSession])

  const applyStep = useCallback((step: StepOut) => {
    setDetail((prev) => {
      if (!prev || prev.id !== step.session_id) return prev
      if (prev.steps.some((s) => s.id === step.id)) return prev
      const steps = [...prev.steps, step]
      const bySet = new Map<number, StepOut[]>()
      for (const s of steps) {
        const arr = bySet.get(s.set_no) ?? []
        arr.push(s)
        bySet.set(s.set_no, arr)
      }
      const rounds = [...bySet.entries()]
        .sort((a, b) => a[0] - b[0])
        .map(([set_no, group]) => {
          const avg = Math.round(group.reduce((sum, g) => sum + g.symmetry, 0) / group.length)
          const state = avg >= 80 ? '정상' : avg >= 60 ? '경고' : '위험'
          return { set_no, avg_symmetry: avg, state, step_count: group.length } as const
        })
      return { ...prev, steps, rounds }
    })
  }, [])

  // WebSocket이 되는 환경(로컬 개발 등)에서는 즉시 반영 — 지원 안 되면 그냥 연결 실패로 끝남
  useEffect(() => {
    if (!detail) return
    let ws: WebSocket | null = null
    try {
      ws = new WebSocket(sessionWsUrl(detail.id))
      wsRef.current = ws
      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data)
          if (msg.type === 'step') applyStep(msg.data as StepOut)
        } catch {
          // ignore malformed messages
        }
      }
    } catch {
      // WebSocket 미지원 환경 — 아래 폴링이 담당
    }
    return () => ws?.close()
  }, [detail?.id, applyStep])

  // 무료 호스팅(WebSocket 미지원) 환경에서도 실시간처럼 보이도록 짧은 주기로 폴링
  useEffect(() => {
    if (!detail) return
    const id = detail.id
    const timer = setInterval(async () => {
      try {
        const fresh = await api.getSession(id)
        setDetail((prev) => (prev && prev.id === id ? fresh : prev))
      } catch {
        // 다음 주기에 재시도
      }
    }, 3000)
    return () => clearInterval(timer)
  }, [detail?.id])

  async function handleNewSession() {
    const s = await api.createSession()
    const fresh = await api.getSession(s.id)
    setDetail(fresh)
  }

  if (loading) return <div className="p-6 text-sm text-[#5f5e5a]">불러오는 중...</div>
  if (error)
    return (
      <div className="p-6 text-sm text-[#e24b4a]">
        데이터를 불러오지 못했습니다: {error}
        <div className="text-xs text-[#9aa0a6] mt-1">백엔드(http://127.0.0.1:8000)가 실행 중인지 확인하세요.</div>
      </div>
    )

  if (!detail) {
    return (
      <div className="p-6 flex flex-col items-center gap-3">
        <div className="text-sm text-[#5f5e5a]">아직 측정 세션이 없습니다.</div>
        <button
          onClick={handleNewSession}
          className="rounded-lg bg-[#1d9e75] text-white px-4 py-2 text-sm font-medium"
        >
          새 세션 시작
        </button>
      </div>
    )
  }

  const steps = detail.steps
  const lastStep = steps[steps.length - 1]
  const currentRound = lastStep?.set_no
  const roundSteps = steps.filter((s) => s.set_no === currentRound)
  const curSym = roundSteps.length > 0
    ? Math.round(roundSteps.reduce((s, r) => s + r.symmetry, 0) / roundSteps.length)
    : 0
  const stepLabel = lastStep ? `${lastStep.step_in_set}/20걸음 진행 중 (${currentRound}회차)` : '측정 대기 중'

  const left = lastStep?.left_matrix ?? EMPTY_MATRIX
  const right = lastStep?.right_matrix ?? EMPTY_MATRIX

  return (
    <div className="max-w-[1100px] mx-auto px-4 py-4 flex flex-col gap-5">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-bold">보행 판별 모니터링 · {detail.dog_name}</h1>
        <button
          onClick={handleNewSession}
          className="text-xs rounded-lg border border-black/10 px-3 py-1.5 text-[#5f5e5a]"
        >
          + 새 세션
        </button>
      </div>

      <StatusBanner symmetry={curSym} stepLabel={stepLabel} />

      <div className="bg-white rounded-xl border border-black/5 p-5">
        <div className="grid grid-cols-2 gap-6">
          <PawHeatmap matrix={left} label="왼발 (정상 발 · 기준)" />
          <PawHeatmap matrix={right} label="오른발 (검사 발)" />
        </div>
      </div>

      <div className="bg-white rounded-xl border border-black/5 p-5">
        <SymmetryTrendChart steps={steps} />
      </div>

      <SummaryStats steps={roundSteps} />

      <div className="bg-white rounded-xl border border-black/5 p-5">
        <RoundSummaryCards rounds={detail.rounds} />
      </div>

      <BleConnectPanel />
    </div>
  )
}
