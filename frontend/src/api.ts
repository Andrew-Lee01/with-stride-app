export type Matrix = number[][]

export interface SessionSummary {
  id: number
  dog_name: string
  started_at: string
  step_count: number
  latest_symmetry: number | null
}

export interface StepOut {
  id: number
  session_id: number
  global_step: number
  set_no: number
  step_in_set: number
  ensemble_score: number
  symmetry: number
  left_matrix: Matrix
  right_matrix: Matrix
  ts: string
}

export interface RoundSummary {
  set_no: number
  avg_symmetry: number
  state: '정상' | '경고' | '위험'
  step_count: number
}

export interface SessionDetail {
  id: number
  dog_name: string
  started_at: string
  steps: StepOut[]
  rounds: RoundSummary[]
}

const API_BASE = ''

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`API 오류 (${res.status}): ${text}`)
  }
  return res.json() as Promise<T>
}

export const api = {
  listSessions: () => fetch(`${API_BASE}/api/sessions`).then((r) => json<SessionSummary[]>(r)),
  getSession: (id: number) => fetch(`${API_BASE}/api/sessions/${id}`).then((r) => json<SessionDetail>(r)),
  createSession: (dog_name = '우리 강아지') =>
    fetch(`${API_BASE}/api/sessions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ dog_name }),
    }).then((r) => json<SessionSummary>(r)),
}

export function sessionWsUrl(sessionId: number): string {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${proto}//${window.location.host}/ws/sessions/${sessionId}`
}
