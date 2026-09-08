"""
/api/analyze 엔드포인트가 쓰는 판별 로직.

★ 알려진 한계 (2026-08-31 기준, 하드웨어/데이터 준비되면 걷어낼 것) ★
- gait_realtime.py(원래 특징 추출 코드)가 프로젝트에 없어서, algorithms/gait_ml.py가
  기대하는 25개 특징 중 시간(걸음 주기)이 필요한 값들은 압력 매트릭스 한 장만으로는
  계산할 수 없다. 그래서 정상 범위 중간값으로 고정해두고, 실제로 매트릭스에서 뽑을 수
  있는 값(최고 압력, 접촉 면적, 압력 중심 퍼짐 정도)만 진짜로 계산한다.
- HMM은 20프레임 연속 시계열이 있어야 계산 가능한데 지금은 프레임 한 장뿐이라 제외.
  가중치는 원래 ML 0.4 / DTW 0.3 / HMM 0.3 이었던 것을, HMM 몫을 ML·DTW 비율대로
  나눠 ML 0.57 / DTW 0.43 으로 재조정했다.
- 압력 매트릭스 값(0~1)을 ML 분류기가 학습된 kgf 단위(정상 8~13kgf)에 맞춰 대략적인
  배율로 늘려서 넣는다. 실제 신발의 물리 단위가 정해지면 이 배율(PEAK_SCALE)을
  실측값 기준으로 다시 잡아야 한다.
- DTW의 "정상 걸음 템플릿"도 실측 정상 데이터가 없어서 합성 곡선으로 임시 보정했다.
  실제 정상 보행 데이터가 쌓이면 그걸로 다시 보정해야 한다.
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np

ALGORITHMS_DIR = Path(__file__).resolve().parent.parent / "algorithms"
if str(ALGORITHMS_DIR) not in sys.path:
    sys.path.insert(0, str(ALGORITHMS_DIR))

from gait_dtw import GaitDTW, resample_curve  # noqa: E402
from gait_ml import predict as ml_predict  # noqa: E402

PEAK_SCALE = 13.0
NODE_AREA_CM2 = 0.09
CONTACT_THRESHOLD = 0.1

ML_WEIGHT = 0.57
DTW_WEIGHT = 0.43

_ml_model = None
_dtw_model: GaitDTW | None = None


def _load_ml_model():
    global _ml_model
    if _ml_model is None:
        with open(ALGORITHMS_DIR / "gait_ml_model.pkl", "rb") as f:
            _ml_model = pickle.load(f)
    return _ml_model


def _row_profile(matrix: np.ndarray) -> np.ndarray:
    """16x10 매트릭스를 16개 길이의 '행별 압력 합' 곡선으로 압축 (DTW 입력용)."""
    return matrix.sum(axis=1)


def _synthetic_healthy_matrix(rng: np.random.Generator) -> np.ndarray:
    """실제 매트릭스와 같은 방식(가우시안 압력 분포)으로 '건강한 발' 매트릭스를 합성한다.
    DTW 템플릿과 실제 입력이 같은 통계(행 합 스케일)를 갖게 하기 위함 — 절대 각자 다른
    방식으로 만들면 안 됨(스케일이 어긋나 DTW 거리가 항상 최대로 튀는 버그가 났었음)."""
    rows, cols = 16, 10
    center_row = rows / 2 + rng.normal(0, 1)
    center_col = cols / 2 + rng.normal(0, 0.75)
    r_idx, c_idx = np.indices((rows, cols))
    dr = (r_idx - center_row) / 4.0
    dc = (c_idx - center_col) / 2.5
    peak = 0.85
    matrix = peak * np.exp(-(dr ** 2 + dc ** 2)) + rng.normal(0, 0.05, size=(rows, cols))
    return np.clip(matrix, 0, 1)


def _get_dtw_model() -> GaitDTW:
    """서버 시작 후 처음 호출될 때 한 번, 합성 '건강한 발' 매트릭스들로 DTW 템플릿을 보정한다.
    (진짜 정상 보행 데이터가 쌓이면 이 합성 데이터 대신 실측값으로 교체해야 함)"""
    global _dtw_model
    if _dtw_model is None:
        rng = np.random.default_rng(0)
        healthy_cycles = [
            _row_profile(_synthetic_healthy_matrix(rng)) * PEAK_SCALE for _ in range(10)
        ]
        dtw = GaitDTW()
        dtw.calibrate_from_cycles(healthy_cycles)
        _dtw_model = dtw
    return _dtw_model


def _approx_features(matrix: np.ndarray, prefix: str) -> dict:
    """압력 매트릭스 한 장에서 gait_ml.py가 기대하는 특징값들을 최대한 근사한다."""
    peak = float(matrix.max()) * PEAK_SCALE
    contact_cells = int((matrix > CONTACT_THRESHOLD).sum())
    contact_area = contact_cells * NODE_AREA_CM2

    rows_idx, cols_idx = np.indices(matrix.shape)
    total = float(matrix.sum())
    if total > 0:
        row_mean = float((matrix * rows_idx).sum() / total)
        col_mean = float((matrix * cols_idx).sum() / total)
        row_spread = float(np.sqrt(((rows_idx - row_mean) ** 2 * matrix).sum() / total))
        col_spread = float(np.sqrt(((cols_idx - col_mean) ** 2 * matrix).sum() / total))
    else:
        row_spread = col_spread = 0.0

    return {
        f"{prefix}_Cycle_Duration(s)": 0.5,
        f"{prefix}_Stance_Duration(s)": 0.3,
        f"{prefix}_Swing_Duration(s)": 0.2,
        f"{prefix}_Stance_Ratio(%)": 60.0,
        f"{prefix}_GRF_Peak(kgf)": peak,
        f"{prefix}_Loading_Rate(kgf/s)": 60.0,
        f"{prefix}_Contact_Area(cm²)": contact_area,
        f"{prefix}_COP_Row_Range(mm)": row_spread * 10,
        f"{prefix}_COP_Col_Range(mm)": col_spread * 10,
        f"{prefix}_Foot_Angle_est(deg)": 7.0,
        f"{prefix}_Stride_Length_est(mm)": 12.0,
    }


def analyze_pair(left_matrix, right_matrix) -> dict:
    """좌/우 한 쌍(예: 앞왼쪽/앞오른쪽)을 받아 ML+DTW 앙상블 점수를 계산한다.

    반환 dict: ensemble_score(0~1, 높을수록 비정상), verdict, ml_score, dtw_score
    """
    left = np.asarray(left_matrix, dtype=float)
    right = np.asarray(right_matrix, dtype=float)

    lf_features = _approx_features(left, "LF")
    rf_features = _approx_features(right, "RF")

    model = _load_ml_model()
    _, _p_normal, p_abnormal, _detail = ml_predict(model, lf_features, rf_features)
    ml_score = float(p_abnormal)

    dtw = _get_dtw_model()
    # 정상 템플릿(합성 곡선)은 PEAK_SCALE 단위로 만들어져 있으므로,
    # 매트릭스에서 뽑은 곡선도 같은 배율로 맞춰줘야 DTW 거리가 의미를 가진다.
    dtw_left = dtw.score(resample_curve(_row_profile(left) * PEAK_SCALE))
    dtw_right = dtw.score(resample_curve(_row_profile(right) * PEAK_SCALE))
    dtw_score = float((dtw_left + dtw_right) / 2.0)

    final_score = ML_WEIGHT * ml_score + DTW_WEIGHT * dtw_score
    verdict = "ABNORMAL" if final_score > 0.5 else "NORMAL"

    return {
        "ensemble_score": final_score,
        "verdict": verdict,
        "ml_score": ml_score,
        "dtw_score": dtw_score,
    }
