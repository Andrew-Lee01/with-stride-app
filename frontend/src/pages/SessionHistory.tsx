import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, type SessionSummary } from '../api'
import { classify, STATE_COLORS } from '../lib/gaitLogic'

export default function SessionHistory() {
  const [sessions, setSessions] = useState<SessionSummary[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.listSessions().then(setSessions).catch((e) => setError(String(e)))
  }, [])

  if (error) return <div className="p-6 text-sm text-[#e24b4a]">불러오기 실패: {error}</div>
  if (!sessions) return <div className="p-6 text-sm text-[#5f5e5a]">불러오는 중...</div>

  return (
    <div className="max-w-[1100px] mx-auto px-4 py-4">
      <h1 className="text-lg font-bold mb-4">세션 이력</h1>
      {sessions.length === 0 ? (
        <div className="text-sm text-[#5f5e5a]">기록된 세션이 없습니다.</div>
      ) : (
        <div className="flex flex-col gap-2">
          {sessions.map((s) => {
            const state = s.latest_symmetry !== null ? classify(s.latest_symmetry) : null
            const colors = state ? STATE_COLORS[state] : null
            return (
              <Link
                key={s.id}
                to={`/sessions/${s.id}`}
                className="bg-white rounded-xl border border-black/5 p-4 flex items-center justify-between hover:border-black/15"
              >
                <div>
                  <div className="font-medium">{s.dog_name}</div>
                  <div className="text-xs text-[#5f5e5a]">
                    {new Date(s.started_at).toLocaleString('ko-KR')} · {s.step_count}걸음
                  </div>
                </div>
                {colors && (
                  <span
                    className="text-xs px-2.5 py-1 rounded-full font-medium"
                    style={{ background: colors.bg, color: colors.fg }}
                  >
                    {s.latest_symmetry}% · {state}
                  </span>
                )}
              </Link>
            )
          })}
        </div>
      )}
    </div>
  )
}
