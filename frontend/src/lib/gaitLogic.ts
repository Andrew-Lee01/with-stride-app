// backend/app/gait_logic.py 와 동일한 임계값/공식. 절대 값을 바꾸지 말 것.
export const STEPS_PER_SET = 20
export const NORMAL_MIN = 80
export const WARN_MIN = 60

export type StateName = '정상' | '경고' | '위험'

export function classify(symmetry: number): StateName {
  if (symmetry >= NORMAL_MIN) return '정상'
  if (symmetry >= WARN_MIN) return '경고'
  return '위험'
}

export const STATE_COLORS: Record<StateName, { bg: string; fg: string; emoji: string }> = {
  정상: { bg: '#1d9e75', fg: '#ffffff', emoji: '🟢' },
  경고: { bg: '#ef9f27', fg: '#412402', emoji: '🟡' },
  위험: { bg: '#e24b4a', fg: '#ffffff', emoji: '🔴' },
}

export const STATE_MESSAGE: Record<StateName, string> = {
  정상: '두 발 균형 안정',
  경고: '오른발에 힘을 덜 실음 — 관찰 필요',
  위험: '명확한 비대칭 — 이상 의심',
}
