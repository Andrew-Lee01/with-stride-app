# -*- coding: utf-8 -*-
"""
gait_dtw.py  —  DTW 기반 보행 정상/비정상 판별 모듈  (담당: 강민)
═══════════════════════════════════════════════════════════════════════
앙상블(ML + HMM + DTW) 통합용 모듈입니다.
팀 합의(2번 방식): 각 알고리즘이 0~1 '비정상 점수'를 내고 가중평균
                  (ML 0.4 / DTW 0.3 / HMM 0.3) → 0.5 초과 시 비정상

[핵심 아이디어]
  앞발 중 한 발만 다친 경우를 대상으로 함.
  다친 발은 강아지가 힘을 덜 싣고 모양도 달라짐.
  → '건강한 발'의 평균 보행곡선을 정상 기준(템플릿)으로 삼고,
    비정상 임계값도 오직 건강한 발(정상 데이터)에서만 추출.
  → 검사 발의 한 걸음을 템플릿과 DTW 비교 → 거리가 크면 비정상.

[근거] 사람: DTW+압력센서로 비대칭 보행 통계적 구분(p<0.05).
       강아지/고양이: 압력판 좌우 대칭성지수로 편측 파행 판별,
       다친 다리의 최대수직힘(PVF)·충격량(VI)이 낮아짐이 신뢰 지표.

[의존성] numpy 만 사용. DTW는 외부 라이브러리 없이 직접 구현.
═══════════════════════════════════════════════════════════════════════

────────────────────────────────────────────────────────────────────
■ 팀장님(ML)께 — 통합 사용법 (3줄이면 끝납니다)
────────────────────────────────────────────────────────────────────

    from gait_dtw import GaitDTW

    dtw = GaitDTW()                 # 1) 객체 생성

    # 2) 보정: '정상 보행' 데이터를 한 번 학습시킴 (양발 %BW 프레임을 순서대로)
    #    - 실시간이면 calibrate_stream()에 프레임을 계속 push
    #    - 이미 모은 정상 사이클 배열이 있으면 calibrate_from_cycles() 사용
    dtw.calibrate_from_cycles(healthy_cycles)   # 아래 설명 참고

    # 3) 판정: 검사할 발의 한 걸음 곡선을 주면 0~1 점수 반환
    score = dtw.score(test_cycle)   # 0=완전정상, 1=확실한비정상
    # → 이 score를 ML*0.4 + DTW*0.3 + HMM*0.3 가중평균에 넣으면 됨

가중평균 예시 (팀장님 통합 코드에서):

    final = 0.4*ml_score + 0.3*dtw.score(cycle) + 0.3*hmm_score
    verdict = "비정상" if final > 0.5 else "정상"

────────────────────────────────────────────────────────────────────
■ 입력 형식 정의 (★ 팀 통일 필요 ★)
────────────────────────────────────────────────────────────────────
 - '한 걸음(stance) 곡선' = 발이 땅에 닿아있는 동안의 %BW 값들의 리스트.
   예) [2.1, 5.4, 7.8, 6.2, 3.1]  (길이는 걸음마다 달라도 됨)
 - %BW = 센서 ADC 합산값 × 노드면적(0.09cm²) ÷ 로봇무게(kg) × 100
 - 길이가 달라도 내부에서 100포인트로 정규화하므로 그대로 넣으면 됨.
 - 만약 ML이 raw ADC 합산값을 쓴다면 to_bw() 헬퍼로 변환 가능.
═══════════════════════════════════════════════════════════════════════
"""

import numpy as np


# ══════════════════════════════════════════════════════════════════
# 설정값 (실험 환경에 맞게 조정)
# ══════════════════════════════════════════════════════════════════
NODE_AREA_CM2   = 0.09     # MS9723 노드 면적 3mm × 3mm
ROBOT_WEIGHT_KG = 15.0     # 강아지 로봇 무게

STANCE_ON_BW    = 5.0      # 발이 닿았다고 볼 %BW (양손 테스트 땐 1.0)
STANCE_OFF_BW   = 3.0      # 발이 떨어졌다고 볼 %BW (양손 테스트 땐 0.5)
MIN_STANCE_FR   = 5        # 한 걸음으로 인정할 최소 프레임 수

RESAMPLE_N      = 100      # 모든 걸음 곡선을 이 길이로 정규화
DTW_WINDOW      = 15       # Sakoe-Chiba 밴드(±) — 과한 워핑 방지
CALIB_CYCLES    = 8        # 보정에 쓸 정상 걸음 수
K_SIGMA         = 2.5      # 임계값 = 정상거리 평균 + K_SIGMA × σ


# ══════════════════════════════════════════════════════════════════
# DTW 직접 구현 (외부 라이브러리 X) — 동적계획법
# ══════════════════════════════════════════════════════════════════
def dtw_distance(a, b, window=DTW_WINDOW):
    """두 1차원 시계열 a,b 의 DTW 거리. 작을수록 모양이 닮음."""
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    n, m = len(a), len(b)
    window = max(window, abs(n - m))

    INF = float("inf")
    D = np.full((n + 1, m + 1), INF)
    D[0, 0] = 0.0
    for i in range(1, n + 1):
        j0 = max(1, i - window)
        j1 = min(m, i + window)
        for j in range(j0, j1 + 1):
            cost = abs(a[i - 1] - b[j - 1])
            D[i, j] = cost + min(D[i - 1, j], D[i, j - 1], D[i - 1, j - 1])
    return D[n, m]


def resample_curve(curve, n=RESAMPLE_N):
    """걸음 곡선을 길이에 상관없이 n개 포인트로 선형 정규화 (시간 정규화)."""
    curve = np.asarray(curve, dtype=float)
    if len(curve) == n:
        return curve
    x_old = np.linspace(0.0, 1.0, len(curve))
    x_new = np.linspace(0.0, 1.0, n)
    return np.interp(x_new, x_old, curve)


def to_bw(adc_sum):
    """센서 ADC 합산값 → %BW 변환 헬퍼."""
    return adc_sum * NODE_AREA_CM2 / ROBOT_WEIGHT_KG * 100.0


# ══════════════════════════════════════════════════════════════════
# 실시간 스트림에서 한 걸음(stance)을 잘라내는 검출기
# ══════════════════════════════════════════════════════════════════
class StanceSegmenter:
    """%BW 값을 프레임마다 push → 한 걸음이 끝나면 그 곡선(list) 반환."""
    def __init__(self):
        self.in_stance = False
        self.buffer = []

    def push(self, value):
        if not self.in_stance:
            if value >= STANCE_ON_BW:
                self.in_stance = True
                self.buffer = [value]
            return None
        if value > STANCE_OFF_BW:
            self.buffer.append(value)
            return None
        # 발이 떨어짐 → 걸음 종료
        self.in_stance = False
        stance, self.buffer = self.buffer, []
        return stance if len(stance) >= MIN_STANCE_FR else None


# ══════════════════════════════════════════════════════════════════
# 메인 클래스 — 팀장님이 import 해서 쓰는 객체
# ══════════════════════════════════════════════════════════════════
class GaitDTW:
    """
    DTW 기반 보행 판별기.
    - calibrate_*()  : 건강한 발로 정상 템플릿 + 임계값 학습
    - score(cycle)   : 검사 발 한 걸음 → 0~1 비정상 점수  ★ 앙상블 입력 ★
    - is_abnormal()  : 0/1 이진 판정 (이진 투표 방식이 필요할 때)
    - push_frame()   : 실시간 양발 프레임 처리 (단독 검증용)
    """

    def __init__(self, injured_hint=None):
        """injured_hint: 'LF'/'RF' 로 다친 발을 미리 알면 지정, 모르면 None(자동)."""
        self.injured_hint = injured_hint
        self.template = None        # 건강한 발 평균 곡선
        self.threshold = None       # 비정상 판정 임계값(DTW 거리)
        self.calibrated = False

        # 실시간 단독 검증용
        self.seg = {"LF": StanceSegmenter(), "RF": StanceSegmenter()}
        self.calib_cycles = {"LF": [], "RF": []}
        self.healthy_foot = None
        self.test_foot = None
        self.results = []

    # ──────────────────────────────────────────────────────────────
    # [보정 A] 이미 모아둔 정상(건강한 발) 걸음 배열로 한 번에 학습
    #   healthy_cycles: 걸음 곡선들의 리스트. 예) [[2.1,5.4,...], [1.9,5.1,...], ...]
    # ──────────────────────────────────────────────────────────────
    def calibrate_from_cycles(self, healthy_cycles):
        if len(healthy_cycles) < 2:
            raise ValueError("정상 걸음이 2개 이상 필요합니다.")
        norm = [resample_curve(c) for c in healthy_cycles]
        self.template = np.mean(np.vstack(norm), axis=0)
        dists = np.array([dtw_distance(c, self.template) for c in norm])
        self.threshold = float(dists.mean() + K_SIGMA * dists.std())
        self.calibrated = True
        return {"template_len": len(self.template),
                "threshold": round(self.threshold, 3),
                "normal_mean": round(float(dists.mean()), 3),
                "normal_std": round(float(dists.std()), 3)}

    # ──────────────────────────────────────────────────────────────
    # [판정] 검사 발 한 걸음 → 0~1 비정상 점수  ★ 앙상블에 넣는 값 ★
    #   0 에 가까울수록 정상, 1 에 가까울수록 비정상.
    #   점수 정의: dtw_dist / (2 × threshold) 를 0~1로 클립
    #             → 임계값에서 정확히 0.5 가 되도록 설계.
    # ──────────────────────────────────────────────────────────────
    def score(self, cycle):
        if not self.calibrated:
            raise RuntimeError("먼저 calibrate_* 로 정상 데이터를 학습하세요.")
        c = resample_curve(cycle)
        d = dtw_distance(c, self.template)
        return float(min(d / (2.0 * self.threshold), 1.0))

    def is_abnormal(self, cycle):
        """이진 판정이 필요할 때: 점수>0.5 면 True(비정상)."""
        return self.score(cycle) > 0.5

    def raw_distance(self, cycle):
        """원시 DTW 거리가 필요할 때."""
        if not self.calibrated:
            raise RuntimeError("먼저 calibrate_* 로 정상 데이터를 학습하세요.")
        return float(dtw_distance(resample_curve(cycle), self.template))

    # ──────────────────────────────────────────────────────────────
    # [보정 B + 단독 검증] 실시간 양발 프레임 처리
    #   ML 통합 없이 DTW만 단독으로 돌려볼 때 사용.
    #   보정 단계: 양발 CALIB_CYCLES개씩 모아 자동 보정.
    #   감시 단계: 검사 발 걸음마다 판정 dict 반환.
    # ──────────────────────────────────────────────────────────────
    def push_frame(self, lf_bw, rf_bw):
        out = []
        for foot, val in (("LF", lf_bw), ("RF", rf_bw)):
            stance = self.seg[foot].push(val)
            if stance is None:
                continue
            curve = resample_curve(stance)
            if not self.calibrated:
                self.calib_cycles[foot].append(curve)
                if (len(self.calib_cycles["LF"]) >= CALIB_CYCLES and
                        len(self.calib_cycles["RF"]) >= CALIB_CYCLES):
                    self._auto_calibrate()
            elif foot == self.test_foot:
                s = self.score(curve)
                res = {"foot": foot,
                       "peak_%BW": round(float(curve.max()), 2),
                       "dtw_dist": round(self.raw_distance(curve), 2),
                       "threshold": round(self.threshold, 2),
                       "abnormal_score": round(s, 3),
                       "verdict": "ABNORMAL" if s > 0.5 else "NORMAL"}
                self.results.append(res)
                out.append(res)
        return out

    def _auto_calibrate(self):
        """양발 보정 데이터에서 건강한 발(피크 큰 쪽)을 골라 템플릿 생성."""
        peak = {f: np.mean([c.max() for c in self.calib_cycles[f]])
                for f in ("LF", "RF")}
        if self.injured_hint in ("LF", "RF"):
            self.test_foot = self.injured_hint
            self.healthy_foot = "RF" if self.injured_hint == "LF" else "LF"
        else:
            self.test_foot = min(peak, key=peak.get)
            self.healthy_foot = max(peak, key=peak.get)
        self.calibrate_from_cycles(self.calib_cycles[self.healthy_foot])

    def summary(self):
        if not self.results:
            return {"total": 0}
        ab = sum(1 for r in self.results if r["verdict"] == "ABNORMAL")
        total = len(self.results)
        return {"test_foot": self.test_foot,
                "total": total,
                "abnormal": ab,
                "abnormal_ratio": round(ab / total, 3),
                "verdict": "비정상" if ab / total >= 0.5 else "정상"}


# ══════════════════════════════════════════════════════════════════
# 자체 테스트 — python gait_dtw.py 로 실행하면 동작 검증 (합성 데이터)
# ══════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    rng = np.random.default_rng(0)

    # 정상(건강한 발) 걸음 곡선 10개 생성: 이중봉 형태, 피크 ~70%BW
    t = np.linspace(0, np.pi, 60)
    base = (np.sin(t) + 0.45 * np.sin(2 * t)).clip(min=0)
    base = base / base.max()
    healthy = [(base * 70 + rng.normal(0, 1.5, 60)).clip(min=0)
               for _ in range(10)]

    dtw = GaitDTW()
    info = dtw.calibrate_from_cycles(healthy)
    print("[보정 완료]", info)

    # 정상 걸음 판정 → 점수 낮아야 함
    normal_cycle = (base * 70 + rng.normal(0, 1.5, 60)).clip(min=0)
    print(f"\n정상 걸음 점수 : {dtw.score(normal_cycle):.3f}  "
          f"(낮을수록 정상)  → {'비정상' if dtw.is_abnormal(normal_cycle) else '정상'}")

    # 다친 발 걸음 판정 → 점수 높아야 함 (피크 ~32%BW)
    injured_cycle = (base * 32 + rng.normal(0, 1.5, 60)).clip(min=0)
    print(f"다친 발 점수   : {dtw.score(injured_cycle):.3f}  "
          f"(높을수록 비정상) → {'비정상' if dtw.is_abnormal(injured_cycle) else '정상'}")

    # 앙상블 가중평균 예시
    ml_score, hmm_score = 0.8, 0.7   # (팀원 점수 예시)
    dtw_score = dtw.score(injured_cycle)
    final = 0.4 * ml_score + 0.3 * dtw_score + 0.3 * hmm_score
    print(f"\n[앙상블 예시] 0.4×{ml_score} + 0.3×{dtw_score:.2f} + 0.3×{hmm_score}"
          f" = {final:.3f} → {'비정상' if final > 0.5 else '정상'}")
