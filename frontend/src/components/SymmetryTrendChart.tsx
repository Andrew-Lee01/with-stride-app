import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, XAxis, YAxis } from 'recharts'
import type { StepOut } from '../api'
import { NORMAL_MIN } from '../lib/gaitLogic'

interface Props {
  steps: StepOut[]
}

export default function SymmetryTrendChart({ steps }: Props) {
  const data = steps.map((s) => ({ step: s.global_step, symmetry: s.symmetry }))

  return (
    <div>
      <div className="text-sm font-semibold mb-2">걸음 횟수별 대칭성 추이</div>
      <ResponsiveContainer width="100%" height={220}>
        <LineChart data={data} margin={{ top: 8, right: 16, bottom: 4, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} opacity={0.25} />
          <XAxis
            dataKey="step"
            label={{ value: 'Step Count (#)', position: 'insideBottom', offset: -2, fontSize: 12 }}
            tick={{ fontSize: 11 }}
          />
          <YAxis
            domain={[0, 100]}
            label={{ value: 'Symmetry (%)', angle: -90, position: 'insideLeft', fontSize: 12 }}
            tick={{ fontSize: 11 }}
          />
          <ReferenceLine
            y={NORMAL_MIN}
            stroke="#9aa0a6"
            strokeDasharray="6 4"
            label={{ value: `Normal (${NORMAL_MIN}%)`, position: 'right', fontSize: 11, fill: '#9aa0a6' }}
          />
          <Line
            type="monotone"
            dataKey="symmetry"
            stroke="#1d9e75"
            strokeWidth={2}
            dot={{ r: 3 }}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
