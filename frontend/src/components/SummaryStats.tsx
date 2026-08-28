import type { StepOut } from '../api'
import { NORMAL_MIN, STEPS_PER_SET } from '../lib/gaitLogic'

interface Props {
  steps: StepOut[]
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-[#f3f1ea] rounded-[10px] p-3.5 text-center">
      <div className="text-xs text-[#5f5e5a]">{label}</div>
      <div className="text-lg font-semibold text-[#2c2c2a] mt-1">{value}</div>
    </div>
  )
}

export default function SummaryStats({ steps }: Props) {
  const normalSteps = steps.filter((s) => s.symmetry >= NORMAL_MIN).length
  const currentSet = steps.length > 0 ? steps[steps.length - 1].set_no : null
  const setDone = steps.length > 0 && steps[steps.length - 1].step_in_set >= STEPS_PER_SET
  const bestSym = steps.length > 0 ? Math.max(...steps.map((s) => s.symmetry)) : null
  const firstSym = steps.length > 0 ? steps[0].symmetry : null
  const improvement = bestSym !== null && firstSym !== null ? bestSym - firstSym : null

  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
      <Stat label="정상 판정 횟수" value={`${normalSteps}걸음`} />
      <Stat label="현재 회차" value={setDone && currentSet ? `${currentSet}회차` : '-'} />
      <Stat label="대칭성 최고 기록" value={setDone && bestSym !== null ? `${bestSym}%` : '-'} />
      <Stat label="총 개선폭" value={setDone && improvement !== null ? `${improvement >= 0 ? '+' : ''}${improvement}%` : '-'} />
    </div>
  )
}
