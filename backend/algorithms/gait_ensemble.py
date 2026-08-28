# -*- coding: utf-8 -*-
"""
gait_ensemble.py — ML + HMM + DTW 앙상블 보행 판별 모듈
═══════════════════════════════════════════════════════════════════
파이프라인:
  Snowforce3 데이터 수신 → 전처리 → 특징 추출
  → ML(0.4) + HMM(0.3) + DTW(0.3) 가중 앙상블 → 최종 판별

실행 방법:
  py gait_ensemble.py

필요 파일 (같은 폴더):
  gait_realtime.py       ← 전처리 / 특징 추출 / 수신 루프
  gait_ml.py             ← ML predict 함수
  gait_dtw.py            ← GaitDTW 클래스
  gait_ml_model.pkl      ← 학습된 ML 모델
  normal_gait_hmm.pkl    ← 학습된 HMM 모델

앙상블 가중치:
  ML  0.4 / HMM 0.3 / DTW 0.3
  최종 점수 > 0.5 → 비정상 (ABNORMAL)
═══════════════════════════════════════════════════════════════════
"""

import numpy as np
import pickle
import joblib
import threading
import time

# ── 로컬 모듈 ─────────────────────────────────────────────────────
from gait_realtime import (
    KLib2,
    GaitCycleBuffer,
    preprocess_cycle,
    extract_features_single_cycle,
    receive_loop,
    LF_HOST, LF_PORT,
    IMU_PITCH_DEG,
)
from gait_ml import predict as ml_predict
from gait_dtw import GaitDTW
from gait_logger import log_step, reset_log   # ← [연결] 결과 기록 도구 (강민 제공)

# ══════════════════════════════════════════════════════════════════
# 설정값
# ══════════════════════════════════════════════════════════════════
ML_WEIGHT  = 0.4
HMM_WEIGHT = 0.3
DTW_WEIGHT = 0.3

CONSECUTIVE_ABNORMAL_THRESHOLD = 2   # 연속 N회 이상 비정상 → 즉시 최종 비정상 판정

# HMM 정규화 기준값 (조원 문서 기준)
HMM_LOG_MAX = -40.0    # 완벽 정상 기준
HMM_LOG_MIN = -300.0   # 최악 파행 기준
HMM_SI_THRESHOLD = 15.0  # 수의학 표준 대칭 지수 임계값 (Voss 2007)

ML_MODEL_PATH  = 'gait_ml_model.pkl'
HMM_MODEL_PATH = 'normal_gait_hmm.pkl'
CSV_PATH       = 'gait_collected_data.csv'

# ══════════════════════════════════════════════════════════════════
# 1. DTW 보정 — gait_collected_data.csv 의 정상 데이터 사용
#    강아지 상태와 무관하게 항상 올바른 정상 기준 적용
# ══════════════════════════════════════════════════════════════════
def _dtw_calibrate_from_csv(dtw_model):
    import pandas as pd, ast, os

    if not os.path.exists(CSV_PATH):
        print(f"  ⚠️  DTW: {CSV_PATH} 없음 — DTW 보정 건너뜀")
        return

    df = pd.read_csv(CSV_PATH)
    normal_df = df[df['label'] == 0]

    if len(normal_df) < 2:
        print(f"  ⚠️  DTW: 정상 데이터 부족({len(normal_df)}개) — 최소 2개 필요")
        return

    healthy_cycles = [ast.literal_eval(r) for r in normal_df['LF_time_series']]
    info = dtw_model.calibrate_from_cycles(healthy_cycles)

    print(f"  ✅ DTW 보정 완료! 정상 {len(healthy_cycles)}주기 사용  "
          f"임계값={info['threshold']:.3f}  정상평균={info['normal_mean']:.3f}")


# ══════════════════════════════════════════════════════════════════
# 2. 모델 로드
# ══════════════════════════════════════════════════════════════════
def load_models():
    print("  모델 로드 중...")

    # ML 모델
    with open(ML_MODEL_PATH, 'rb') as f:
        ml_model = pickle.load(f)
    print(f"  ✅ ML 모델 로드 완료 ({type(ml_model).__name__})")

    # HMM 모델
    hmm_model = joblib.load(HMM_MODEL_PATH)
    print(f"  ✅ HMM 모델 로드 완료 ({type(hmm_model).__name__})")

    return ml_model, hmm_model


# ══════════════════════════════════════════════════════════════════
# 2. HMM 스코어 계산
#    입력: lf_series(100,), rf_series(100,)
#    출력: 0~1 비정상 점수
# ══════════════════════════════════════════════════════════════════
def hmm_score(hmm_model, lf_series, rf_series):
    """
    HMM 비정상 점수 계산 (0=정상, 1=비정상)

    지표① P_evasion   : log_likelihood → Min-Max 역정규화
    지표② P_temporal  : 은닉 상태 디코딩 → 대칭 지수(SI) → 확률
    최종  = (P_evasion + P_temporal) / 2
    """
    # 초기 20프레임 슬라이싱 (100포인트 중 앞 20%)
    x_strike = np.column_stack([
        lf_series[:20],   # 왼쪽 다리 하중
        rf_series[:20]    # 오른쪽 다리 하중
    ])  # shape: (20, 2)

    # ── 지표① P_evasion ──────────────────────────────────────────
    log_likelihood = hmm_model.score(x_strike)
    log_likelihood = float(np.clip(log_likelihood, HMM_LOG_MIN, HMM_LOG_MAX))

    p_evasion = 1.0 - (
        (log_likelihood - HMM_LOG_MIN) /
        (HMM_LOG_MAX   - HMM_LOG_MIN)
    )
    p_evasion = float(np.clip(p_evasion, 0.0, 1.0))

    # ── 지표② P_temporal_asymmetry ───────────────────────────────
    hidden_states = hmm_model.predict(x_strike)

    # 은닉 상태별 프레임 수 → 입각기 시간 비율로 환산
    lf_stance_frames = float(np.sum(hidden_states == 0))
    rf_stance_frames = float(np.sum(hidden_states != 0))

    denom = 0.5 * (lf_stance_frames + rf_stance_frames)
    if denom > 0:
        si = abs(lf_stance_frames - rf_stance_frames) / denom * 100.0
    else:
        si = 0.0

    p_temporal = float(np.clip(si / HMM_SI_THRESHOLD, 0.0, 1.0))

    # ── 최종 HMM 점수 ─────────────────────────────────────────────
    final_hmm = (p_evasion + p_temporal) / 2.0

    return final_hmm, {
        'log_likelihood' : round(log_likelihood, 3),
        'p_evasion'      : round(p_evasion, 4),
        'SI(%)'          : round(si, 2),
        'p_temporal'     : round(p_temporal, 4),
        'hmm_score'      : round(final_hmm, 4),
    }


# ══════════════════════════════════════════════════════════════════
# 3. 앙상블 판별
# ══════════════════════════════════════════════════════════════════
def ensemble_predict(ml_model, hmm_model, dtw_model,
                     lf_features, rf_features,
                     lf_series, rf_series):
    """
    세 모델의 비정상 점수를 가중 평균하여 최종 판별

    반환:
        verdict      : 'NORMAL' or 'ABNORMAL'
        final_score  : 0~1 최종 앙상블 점수
        detail       : 각 알고리즘 점수 상세
    """
    # ── ML 점수 ───────────────────────────────────────────────────
    _, p_norm, p_abnorm, _ = ml_predict(ml_model, lf_features, rf_features)
    ml_s = float(p_abnorm)

    # ── HMM 점수 ──────────────────────────────────────────────────
    hmm_s, hmm_detail = hmm_score(hmm_model, lf_series, rf_series)

    # ── DTW 점수 ──────────────────────────────────────────────────
    # DTW는 LF/RF 각각 점수를 내어 평균
    if dtw_model.calibrated:
        dtw_lf = dtw_model.score(lf_series)
        dtw_rf = dtw_model.score(rf_series)
        dtw_s  = float((dtw_lf + dtw_rf) / 2.0)
    else:
        # DTW 보정 미완료 시 ML/HMM 결과만 사용
        dtw_s  = ml_s
        dtw_lf = dtw_rf = ml_s

    # ── 가중 앙상블 ───────────────────────────────────────────────
    final_score = (
        ML_WEIGHT  * ml_s  +
        HMM_WEIGHT * hmm_s +
        DTW_WEIGHT * dtw_s
    )
    verdict = 'ABNORMAL' if final_score > 0.5 else 'NORMAL'

    detail = {
        'ML_score'  : round(ml_s,         4),
        'HMM_score' : round(hmm_s,        4),
        'DTW_LF'    : round(dtw_lf,       4),
        'DTW_RF'    : round(dtw_rf,       4),
        'DTW_score' : round(dtw_s,        4),
        'final'     : round(final_score,  4),
        **{f'HMM_{k}': v for k, v in hmm_detail.items()},
    }
    return verdict, final_score, detail


# ══════════════════════════════════════════════════════════════════
# 4. 결과 출력
# ══════════════════════════════════════════════════════════════════
def print_result(cycle_no, verdict, final_score, detail):
    icon = '🟢' if verdict == 'NORMAL' else '🔴'
    bar_len = int(final_score * 20)
    bar = '█' * bar_len + '░' * (20 - bar_len)

    print(f"\n  {'─'*55}")
    print(f"  [{cycle_no:>3}주기] {icon} {verdict}   "
          f"앙상블 점수: {final_score:.3f}  [{bar}]")
    print(f"        ML({ML_WEIGHT})={detail['ML_score']:.3f}  "
          f"HMM({HMM_WEIGHT})={detail['HMM_score']:.3f}  "
          f"DTW({DTW_WEIGHT})={detail['DTW_score']:.3f}")
    print(f"        HMM 로그우도={detail['HMM_log_likelihood']:.1f}  "
          f"대칭지수={detail['HMM_SI(%)']:.1f}%")


# ══════════════════════════════════════════════════════════════════
# [연결] 대시보드용: 한 걸음의 대표 압력 프레임을 골라
#        왼발/오른발 16x10 으로 나누고 0~1 로 정규화
#   · 센서 한 장 16x10 짜리 2개 → 한 프레임이 16x20 으로 읽힘
#   · 왼쪽 10열 = 왼발, 오른쪽 10열 = 오른발 (좌우 바뀌면 아래 :10 / 10: 교체)
#   · 센서 값(0~7 kgf/cm²)을 7로 나눠 0~1 로 변환 (대시보드 히트맵 기준)
# ══════════════════════════════════════════════════════════════════
def _split_paws_for_dashboard(cycle):
    frames = cycle.get('frames', [])
    if not frames:
        return None, None
    # 압력 총합이 가장 큰 프레임 1장을 대표로 선택
    _, peak = max(frames, key=lambda tm: float(np.asarray(tm[1]).sum()))
    peak = np.asarray(peak, dtype=float)
    if peak.ndim != 2 or peak.shape[1] < 20:
        # 예상(16x20)과 다르면 히트맵은 건너뛰고 점수만 기록되게 함
        return None, None
    left  = np.clip(peak[:, :10] / 7.0, 0, 1)   # 왼발
    right = np.clip(peak[:, 10:20] / 7.0, 0, 1)  # 오른발
    return left, right


# ══════════════════════════════════════════════════════════════════
# 5. 메인 실행
# ══════════════════════════════════════════════════════════════════
def main():
    print("=" * 60)
    print("  MS9723 보행 앙상블 판별 시스템")
    print(f"  가중치: ML={ML_WEIGHT} / HMM={HMM_WEIGHT} / DTW={DTW_WEIGHT}")
    print("=" * 60)

    # ── 모델 로드 ─────────────────────────────────────────────────
    ml_model, hmm_model = load_models()

    # ── DTW 초기화 (수집된 정상 데이터로 즉시 보정) ──────────────
    dtw_model = GaitDTW()
    _dtw_calibrate_from_csv(dtw_model)

    # ── Snowforce3 연결 ───────────────────────────────────────────
    print(f"\n  Snowforce3 연결 중... ({LF_HOST}:{LF_PORT})")
    lf_klib = KLib2(LF_HOST, LF_PORT)

    try:
        lf_klib.start()
        lf_klib.init()
    except ConnectionRefusedError:
        print("  ❌ 연결 실패: Snowforce3 실행 및 Send Data TCP 체크 확인")
        return

    lf_buffer  = GaitCycleBuffer('LF')
    rf_buffer  = GaitCycleBuffer('RF')
    stop_event = threading.Event()

    lf_thread = threading.Thread(
        target=receive_loop, args=(lf_klib, lf_buffer, stop_event))
    rf_thread = threading.Thread(
        target=receive_loop, args=(lf_klib, rf_buffer, stop_event))

    lf_thread.start()
    rf_thread.start()

    print("  ✅ 수신 시작 — 보행 주기 감지 대기 중...")
    if not dtw_model.calibrated:
        print(f"  ⏳ DTW 보정 중: 정상 보행을 먼저 걸어주세요.")
    print("  (종료: Ctrl+C)\n")

    lf_processed       = 0
    rf_processed       = 0
    cycle_no           = 0
    results            = []
    consecutive_abnormal = 0   # 현재 연속 비정상 횟수
    forced_abnormal    = False # 연속 조건으로 비정상 확정됐는지

    try:
        while True:
            time.sleep(0.05)

            if (lf_buffer.cycle_count > lf_processed and
                    rf_buffer.cycle_count > rf_processed):

                lf_cycle = lf_buffer.cycles[lf_processed]
                rf_cycle = rf_buffer.cycles[rf_processed]
                lf_processed += 1
                rf_processed += 1
                cycle_no     += 1

                # 전처리
                lf_series = preprocess_cycle(lf_cycle, IMU_PITCH_DEG)
                rf_series = preprocess_cycle(rf_cycle, IMU_PITCH_DEG)

                # 특징 추출
                lf_features = extract_features_single_cycle(lf_cycle, 'LF')
                rf_features = extract_features_single_cycle(rf_cycle, 'RF')

                # DTW 미보정 시 스킵 (정상 CSV 없을 때 대비)
                if not dtw_model.calibrated:
                    print("  ⚠️  DTW 미보정 — gait_collected_data.csv 확인 필요")
                    continue

                # 앙상블 판별
                verdict, final_score, detail = ensemble_predict(
                    ml_model, hmm_model, dtw_model,
                    lf_features, rf_features,
                    lf_series, rf_series
                )

                # 연속 비정상 카운터 갱신
                if verdict == 'ABNORMAL':
                    consecutive_abnormal += 1
                else:
                    consecutive_abnormal = 0   # 정상이 나오면 연속 카운터 초기화

                # 연속 N회 이상 비정상 → 즉시 확정
                if consecutive_abnormal >= CONSECUTIVE_ABNORMAL_THRESHOLD and not forced_abnormal:
                    forced_abnormal = True
                    print(f"\n  ⚠️  연속 {consecutive_abnormal}회 비정상 감지 → 최종 판정: 비정상 확정!")

                print_result(cycle_no, verdict, final_score, detail)
                results.append({
                    'cycle': cycle_no,
                    'verdict': verdict,
                    'score': final_score,
                    **detail
                })

                # ── [연결] 대시보드용 기록: 점수(0~1) + 양발 히트맵(16x10) ──
                left_paw, right_paw = _split_paws_for_dashboard(lf_cycle)
                log_step(
                    ensemble_score=final_score,   # 0~1 최종 점수 (그대로)
                    left_matrix=left_paw,         # 16x10, 0~1 (없으면 None)
                    right_matrix=right_paw         # 16x10, 0~1 (없으면 None)
                )

    except KeyboardInterrupt:
        print("\n\n  종료 요청")

    finally:
        stop_event.set()
        lf_klib.stop()
        lf_thread.join(timeout=2)
        rf_thread.join(timeout=2)

    # ── 세션 요약 ─────────────────────────────────────────────────
    if results:
        total    = len(results)
        abnormal = sum(1 for r in results if r['verdict'] == 'ABNORMAL')
        print(f"\n{'='*60}")
        print(f"  세션 요약: 총 {total}주기 판별")
        print(f"  정상: {total-abnormal}회 / 비정상: {abnormal}회")
        print(f"  평균 앙상블 점수: "
              f"{np.mean([r['score'] for r in results]):.3f}")

        # 최종 판정 — 연속 N회 비정상이면 무조건 비정상
        if forced_abnormal:
            final_verdict = '🔴 비정상 (연속 비정상 감지)'
        elif abnormal >= (total - abnormal):
            final_verdict = '🔴 비정상'
        else:
            final_verdict = '🟢 정상'

        print(f"  최종 판정: {final_verdict}")
        print(f"{'='*60}")


if __name__ == '__main__':
    main()
