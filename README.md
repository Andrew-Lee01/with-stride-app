# With-Stride 재활 모니터링 PWA

PAW DYNAMICS(With-Stride) 팀의 스마트 펫슈즈 데이터를 보호자가 홈 화면에 설치해 쓰는 모니터링 앱으로 만든 것.
기존 `gait_dashboard.py`(Streamlit)를 대체하며, 알고리즘(`gait_ensemble.py` 등)은 그대로 재사용한다.

## 구성

```
backend/    FastAPI + SQLite. 세션/걸음 저장, REST API, 실시간 WebSocket
  algorithms/   gait_ensemble.py 등 1학기 알고리즘 코드 원본 그대로
  app/          API 서버
  gait_logger_api.py   기존 gait_logger.log_step()과 같은 시그니처의 API 어댑터
frontend/   React + Vite PWA. 대시보드 · 세션 이력 · BLE 연결(뼈대)
```

## 실행 방법

### 1. 백엔드

```bash
cd backend
venv/Scripts/python.exe -m uvicorn app.main:app --port 8000
```

첫 실행 시 `gait.db`(SQLite)가 자동 생성된다.

### 2. 프런트엔드

```bash
cd frontend
npm run dev
```

`http://localhost:5173` 접속. `/api`, `/ws` 요청은 자동으로 8000번 백엔드로 프록시된다.

### 3. 실제 측정 데이터 연결하기

기존 앙상블/실시간 코드(`gait_realtime.py` 등)에서

```python
from gait_logger import log_step
```

이 부분을

```python
from gait_logger_api import log_step
```

로 바꾸면, 한 걸음이 끝날 때마다 CSV 대신 이 앱의 백엔드로 데이터가 전송되어 대시보드에 실시간으로 뜬다.
(`gait_logger_api.py`를 실행 스크립트와 같은 폴더에 두거나 `sys.path`에 추가할 것)

### 4. 홈 화면에 설치 (PWA)

```bash
cd frontend
npm run build
npm run preview
```

Android/PC Chrome에서 접속 후 "홈 화면에 추가"로 설치. iOS Safari도 설치 자체는 되지만, BLE 실시간 연결은
iOS에서 기술적으로 불가능하므로(Web Bluetooth 미지원) 실시간 연동은 Android/PC 기준으로 우선 구현했다.

## 아직 안 된 것

- **BLE 실시간 연동**: 펌웨어의 BLE 전송(개발 10단계 중 7단계)이 아직 미완료라 `BleConnectPanel`은 스캔 UI만
  준비된 상태. GATT 서비스/캐릭터리스틱 UUID가 확정되면 `frontend/src/components/BleConnectPanel.tsx`의
  TODO 부분을 채우면 된다.
- 로그인/여러 강아지 지원, 추가 시각화는 필요할 때 붙이기로 함.
