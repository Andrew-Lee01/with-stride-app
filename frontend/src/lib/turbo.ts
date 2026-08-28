// matplotlib "turbo" 컬러맵의 단순화된 근사치 (제어점 보간).
// gait_dashboard.py의 ax.imshow(m, cmap="turbo", vmin=0, vmax=1)와 시각적으로 맞추기 위함.
const STOPS: [number, number, number][] = [
  [48, 18, 59],
  [70, 107, 227],
  [40, 187, 224],
  [65, 231, 133],
  [176, 240, 60],
  [246, 199, 41],
  [237, 106, 38],
  [164, 30, 22],
]

export function turbo(t: number): string {
  const x = Math.min(1, Math.max(0, t)) * (STOPS.length - 1)
  const i = Math.floor(x)
  const frac = x - i
  const a = STOPS[i]
  const b = STOPS[Math.min(i + 1, STOPS.length - 1)]
  const r = Math.round(a[0] + (b[0] - a[0]) * frac)
  const g = Math.round(a[1] + (b[1] - a[1]) * frac)
  const bl = Math.round(a[2] + (b[2] - a[2]) * frac)
  return `rgb(${r},${g},${bl})`
}
