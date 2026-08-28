import { useState } from 'react'

// PawDynamics 보드 4장의 광고 이름 (펌웨어_설계자료.md §7-4).
const BOARD_NAMES = ['PAW-LF', 'PAW-RF', 'PAW-LH', 'PAW-RH']

function hasWebBluetooth(): boolean {
  return typeof navigator !== 'undefined' && 'bluetooth' in navigator
}

export default function BleConnectPanel() {
  const [status, setStatus] = useState<string>('연결된 보드 없음')
  const supported = hasWebBluetooth()

  async function handleScan() {
    if (!supported) return
    try {
      // TODO: GATT 서비스/캐릭터리스틱 UUID가 확정되면(펌웨어 7단계 완료 후) 여기서
      // requestDevice({ filters: [{ namePrefix: 'PAW-' }], optionalServices: [SERVICE_UUID] })
      // 로 실제 연결 로직을 채운다.
      setStatus('기기 스캔 UI만 준비됨 — 펌웨어 BLE 전송 완료 후 실제 연결 가능')
      await navigator.bluetooth.requestDevice({
        acceptAllDevices: false,
        filters: [{ namePrefix: 'PAW-' }],
      })
    } catch (e) {
      setStatus(e instanceof Error ? `연결 취소/실패: ${e.message}` : '연결 취소됨')
    }
  }

  return (
    <div className="bg-white rounded-xl border border-black/5 p-5">
      <div className="text-sm font-semibold mb-2">펫슈즈 실시간 연결 (BLE)</div>

      {!supported && (
        <div className="text-sm text-[#e24b4a] bg-[#e24b4a]/10 rounded-lg p-3 mb-3">
          이 브라우저는 Web Bluetooth를 지원하지 않습니다. iOS Safari는 기술적으로 지원되지 않으니
          Android 또는 PC의 Chrome/Edge에서 이용해주세요.
        </div>
      )}

      <div className="flex flex-wrap gap-2 mb-3">
        {BOARD_NAMES.map((name) => (
          <span key={name} className="text-xs px-2 py-1 rounded-full bg-[#f3f1ea] text-[#5f5e5a]">
            {name}
          </span>
        ))}
      </div>

      <button
        onClick={handleScan}
        disabled={!supported}
        className="rounded-lg bg-[#1d9e75] text-white px-4 py-2 text-sm font-medium disabled:opacity-40 disabled:cursor-not-allowed"
      >
        기기 스캔 및 연결
      </button>

      <div className="text-xs text-[#5f5e5a] mt-3">{status}</div>
      <div className="text-xs text-[#9aa0a6] mt-1">
        현재는 펌웨어의 BLE 전송(개발 7단계)이 미완료 상태라 실제 데이터 연결은 준비 중입니다. 지금은
        유선(SnowForce3) 경로로 실시간 모니터링이 동작합니다.
      </div>
    </div>
  )
}
