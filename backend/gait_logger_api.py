"""
gait_logger.py 의 log_step()과 동일한 시그니처를 갖는 API 버전 어댑터.

기존 파이프라인(gait_realtime.py / 앙상블 코드)에서는

    from gait_logger import log_step

한 줄만 아래처럼 바꾸면 CSV 대신 With-Stride 백엔드로 전송된다.

    from gait_logger_api import log_step

세션은 모듈 최초 호출 시 자동으로 하나 생성되고, 이후 호출은 같은 세션에 걸음을 계속 追加한다.
새 세션을 시작하려면 reset_log()를 호출하면 된다 (gait_logger.py와 동일한 이름/동작).
"""
import numpy as np
import requests

API_BASE = "http://127.0.0.1:8000"

_session_id = None


def _ensure_session():
    global _session_id
    if _session_id is None:
        resp = requests.post(f"{API_BASE}/api/sessions", json={"dog_name": "우리 강아지"})
        resp.raise_for_status()
        _session_id = resp.json()["id"]
        print(f"[gait_logger_api] 새 세션 시작: session_id={_session_id}")
    return _session_id


def _as_16x10_list(matrix, name):
    if matrix is None:
        return None
    arr = np.asarray(matrix, dtype=float)
    if arr.shape == (10, 16):
        raise ValueError(
            f"{name} 의 모양이 (10, 16)입니다 — 행/열이 뒤집힌 것 같아요. "
            f"log_step(..., {name}={name}.T) 처럼 전치해서 넣으세요."
        )
    if arr.shape != (16, 10):
        raise ValueError(f"{name} 의 모양이 {arr.shape} 입니다. 16x10(16행 10열)이어야 해요.")
    return arr.tolist()


def log_step(ensemble_score, left_matrix=None, right_matrix=None):
    """
    한 걸음의 결과를 With-Stride 백엔드로 전송한다.
    gait_logger.log_step()과 동일한 인자를 받는다.
    반환: 저장된 걸음의 global_step 번호
    """
    session_id = _ensure_session()
    payload = {
        "ensemble_score": float(ensemble_score),
        "left_matrix": _as_16x10_list(left_matrix, "left_matrix"),
        "right_matrix": _as_16x10_list(right_matrix, "right_matrix"),
    }
    resp = requests.post(f"{API_BASE}/api/sessions/{session_id}/steps", json=payload)
    resp.raise_for_status()
    data = resp.json()
    print(f"[gait_logger_api] {data['global_step']}걸음 전송 완료 (score={ensemble_score:.3f})")
    return data["global_step"]


def reset_log():
    """새 세션을 시작한다 (다음 log_step부터 1걸음째로 기록됨)."""
    global _session_id
    _session_id = None
    print("[gait_logger_api] 세션 초기화. 다음 log_step 은 새 세션의 1걸음부터 시작합니다.")


if __name__ == "__main__":
    # gait_logger.py와 동일한 데모: 백엔드가 http://127.0.0.1:8000 에서 실행 중이어야 함
    reset_log()
    rng = np.random.default_rng(0)
    demo_scores = [0.67, 0.62, 0.55, 0.48, 0.42, 0.10]
    for s in demo_scores:
        rows, cols = np.mgrid[0:16, 0:10]
        left = np.exp(-(((rows - 9) ** 2) / 20 + ((cols - 4.5) ** 2) / 12))
        right = 0.5 * np.exp(-(((rows - 8) ** 2) / 12 + ((cols - 5.5) ** 2) / 6))
        log_step(ensemble_score=s, left_matrix=left, right_matrix=right)
    print("\n시연 완료 - 백엔드 /api/sessions 에서 확인해보세요.")
