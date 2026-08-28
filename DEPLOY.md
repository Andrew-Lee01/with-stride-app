# 배포 가이드 (Neon + Render, 완전 무료)

계정 생성이나 결제 정보 입력은 사용자 본인이 직접 해야 하는 부분이라 제가 대신 할 수 없습니다.
아래 순서대로만 따라 하면 됩니다. 코드/설정 파일은 이미 다 준비돼 있습니다
(`Dockerfile`, `render.yaml`, `backend/app/db.py`가 `DATABASE_URL` 환경변수를 자동으로 인식합니다).

## 1. Neon (무료 Postgres, 영구 저장)

1. https://neon.tech 접속 → 가입 (신용카드 불필요)
2. 프로젝트 생성 (이름 아무거나, 예: `with-stride`)
3. 생성 후 나오는 **Connection string**을 복사
   (`postgresql://...`로 시작하는 긴 문자열, `sslmode=require` 포함)

## 2. GitHub에 코드 올리기

이 폴더(`with-stride-app`)는 이미 git 저장소로 초기화되고 첫 커밋까지 끝났습니다.

1. https://github.com 에서 새 저장소 생성 (Public/Private 상관없음, README 등 추가 옵션은 체크하지 말 것 — 이미 로컬에 커밋이 있으므로)
2. 아래 명령을 이 폴더에서 실행 (본인이 직접 실행하거나, 실행해달라고 다시 말씀해주시면 제가 실행합니다)
   ```bash
   git remote add origin <새로 만든 저장소 URL>
   git branch -M main
   git push -u origin main
   ```

## 3. Render (무료 웹 호스팅)

1. https://render.com 접속 → 가입 (GitHub 계정으로 로그인하면 편함, 신용카드 불필요)
2. **New +** → **Blueprint** 선택 → 방금 만든 GitHub 저장소 연결
   (저장소 안의 `render.yaml`을 Render가 자동으로 읽어서 Docker 빌드로 설정합니다)
3. 배포 설정 화면에서 환경변수 `DATABASE_URL`에 **1번에서 복사한 Neon 연결 문자열**을 붙여넣기
4. Deploy 클릭 → 5~10분 정도 빌드 (Node로 프런트 빌드 + Python 이미지 생성)
5. 완료되면 `https://with-stride-XXXX.onrender.com` 같은 고정 주소가 생깁니다.
   이 주소를 아무 기기에서나 열면 됩니다 (휴대폰 포함).

## 참고 — 무료 호스팅의 특성

- **첫 접속이 느릴 수 있음**: 15분 동안 아무도 안 들어오면 서버가 잠들고, 다음 접속 시 깨어나는 데 약 1분 걸립니다.
  (재활 모니터링처럼 가끔 확인하는 용도라 큰 문제는 아닙니다)
- **데이터는 Neon에 영구 저장**되므로 Render가 잠들었다 깨어나도 기록은 그대로 남습니다.
- 실시간 갱신은 WebSocket 대신 **3초 간격 자동 새로고침**으로 동작하도록 이미 코드에 반영해뒀습니다
  (무료 호스팅은 WebSocket을 지원하지 않아서).

## 실제 측정 데이터를 배포된 주소로 보내기

로컬 PC(SnowForce3가 연결된 컴퓨터)에서 실행하는 파이프라인의 `gait_logger_api.py`에서
`API_BASE` 값을 로컬 주소 대신 배포된 주소로 바꾸면 됩니다.

```python
# backend/gait_logger_api.py
API_BASE = "https://with-stride-XXXX.onrender.com"   # ← Render에서 받은 실제 주소로 교체
```
