import { useEffect, useRef } from 'react'
import type { Matrix } from '../api'
import { turbo } from '../lib/turbo'

interface Props {
  matrix: Matrix // 16행 x 10열, 0~1 정규화된 압력값
  label: string
  sublabel?: string
}

const ROWS = 16
const COLS = 10

export default function PawHeatmap({ matrix, label, sublabel }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const cellW = canvas.width / COLS
    const cellH = canvas.height / ROWS

    let max = 0
    for (const row of matrix) for (const v of row) if (v > max) max = v
    const norm = max > 0 ? max : 1

    for (let r = 0; r < ROWS; r++) {
      for (let c = 0; c < COLS; c++) {
        const v = matrix[r]?.[c] ?? 0
        ctx.fillStyle = turbo(v / norm)
        ctx.fillRect(c * cellW, r * cellH, cellW + 1, cellH + 1)
      }
    }
  }, [matrix])

  const total = matrix.reduce((sum, row) => sum + row.reduce((s, v) => s + v, 0), 0)

  return (
    <div className="flex flex-col items-center">
      <div className="text-sm font-semibold text-[#2c2c2a] mb-2">{label}</div>
      <canvas
        ref={canvasRef}
        width={140}
        height={224}
        className="rounded-md shadow-sm border border-black/5"
        style={{ imageRendering: 'pixelated' }}
      />
      <div className="text-sm font-medium text-[#444] mt-1.5">
        정규화 압력 : {total.toFixed(1)} [Pa]
      </div>
      {sublabel && <div className="text-xs text-[#5f5e5a]">{sublabel}</div>}
    </div>
  )
}
