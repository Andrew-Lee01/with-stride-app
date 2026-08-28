import { classify, STATE_COLORS, STATE_MESSAGE } from '../lib/gaitLogic'

interface Props {
  symmetry: number
  stepLabel: string
}

export default function StatusBanner({ symmetry, stepLabel }: Props) {
  const state = classify(symmetry)
  const { bg, fg, emoji } = STATE_COLORS[state]

  return (
    <div
      className="rounded-2xl flex items-center gap-5 my-2"
      style={{ background: bg, color: fg, padding: '18px 22px' }}
    >
      <div className="text-5xl leading-none">{emoji}</div>
      <div>
        <div className="text-sm opacity-85">측정 결과 ({stepLabel})</div>
        <div className="text-3xl font-bold my-0.5">
          {symmetry}% · {state}
        </div>
        <div className="text-sm opacity-85">{STATE_MESSAGE[state]}</div>
      </div>
    </div>
  )
}
