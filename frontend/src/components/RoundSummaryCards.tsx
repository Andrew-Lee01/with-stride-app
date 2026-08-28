import type { RoundSummary } from '../api'
import { STATE_COLORS } from '../lib/gaitLogic'

interface Props {
  rounds: RoundSummary[]
}

export default function RoundSummaryCards({ rounds }: Props) {
  return (
    <div>
      <div className="text-sm font-semibold mb-2">회차별 회복 추세 (회차별 20걸음 평균)</div>
      {rounds.length === 0 ? (
        <div className="text-xs text-[#5f5e5a]">20걸음이 완료되면 회차 결과가 여기에 표시됩니다.</div>
      ) : (
        <div className="grid gap-2" style={{ gridTemplateColumns: `repeat(${Math.min(rounds.length, 6)}, 1fr)` }}>
          {rounds.map((r) => {
            const { bg, fg } = STATE_COLORS[r.state]
            return (
              <div
                key={r.set_no}
                className="rounded-lg text-center"
                style={{ background: bg, color: fg, padding: '10px 6px' }}
              >
                <div className="text-xs opacity-85">{r.set_no}회차 ({r.step_count}걸음 평균)</div>
                <div className="text-xl font-bold">{r.avg_symmetry}%</div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
