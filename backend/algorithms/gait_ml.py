import numpy as np
import os
import pickle
import warnings
warnings.filterwarnings('ignore')

from sklearn.ensemble import RandomForestClassifier, VotingClassifier
from sklearn.svm import SVC
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import cross_val_score, StratifiedKFold
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.pipeline import Pipeline

# ============================================================
# MS9723 보행 정상/비정상 판별 — 머신러닝 모듈
# gait_realtime.py 에 이어서 사용
#
# 특징 벡터 구성 (총 25개)
#   LF 11개: Cycle_Duration, Stance_Duration, Swing_Duration,
#             Stance_Ratio, GRF_Peak, Loading_Rate,
#             Contact_Area, COP_Row_Range, COP_Col_Range,
#             Foot_Angle_est, Stride_Length_est
#   RF 11개: 동일
#   공통 3개: SI_GRF_Peak, SI_Stance_Duration, Force_Diff_peak
#
# 모델: RandomForest + SVM 소프트 투표(Soft Voting) 앙상블
# 라벨: 0 = 정상(Normal), 1 = 비정상(Abnormal)
# ============================================================

MODEL_SAVE_PATH = 'gait_ml_model.pkl'   # 학습된 모델 저장 경로

# 특징 컬럼 순서 (이 순서 그대로 벡터를 만들어야 함)
FEATURE_NAMES = [
    'LF_Cycle_Duration(s)',      'LF_Stance_Duration(s)',
    'LF_Swing_Duration(s)',      'LF_Stance_Ratio(%)',
    'LF_GRF_Peak(kgf)',          'LF_Loading_Rate(kgf/s)',
    'LF_Contact_Area(cm²)',      'LF_COP_Row_Range(mm)',
    'LF_COP_Col_Range(mm)',      'LF_Foot_Angle_est(deg)',
    'LF_Stride_Length_est(mm)',
    'RF_Cycle_Duration(s)',      'RF_Stance_Duration(s)',
    'RF_Swing_Duration(s)',      'RF_Stance_Ratio(%)',
    'RF_GRF_Peak(kgf)',          'RF_Loading_Rate(kgf/s)',
    'RF_Contact_Area(cm²)',      'RF_COP_Row_Range(mm)',
    'RF_COP_Col_Range(mm)',      'RF_Foot_Angle_est(deg)',
    'RF_Stride_Length_est(mm)',
    'SI_GRF_Peak(%)',            'SI_Stance_Duration(%)',
    'Force_Diff_peak(kgf)',
]


# ============================================================
# 1. 학습 데이터 생성
#    실제 데이터가 없는 초기 단계에서 정상/비정상 범위를
#    기반으로 가상 데이터를 생성하여 모델을 초기 학습시킴
#    실제 데이터 수집 후 retrain() 함수로 재학습 가능
# ============================================================
def generate_training_data(n_per_class=200, seed=42):
    """
    정상/비정상 가상 학습 데이터 생성
    반환: X (샘플 x 25특징), y (0=정상, 1=비정상)

    정상 보행 기준 (4족 로봇 앞발 트롯 보행):
      - 보행 주기: 0.45~0.55초
      - 입각기 비율: 55~65%
      - GRF 피크: 8~13 kgf
      - 대칭성 지수(SI): 0~8%

    비정상 보행 기준 (이상 케이스):
      - 보행 주기 불규칙: 0.3~0.7초
      - 입각기 비율 감소: 35~50%
      - GRF 피크 저하: 4~8 kgf
      - 대칭성 지수 증가: 12~40%
    """
    np.random.seed(seed)

    # ── 정상 보행 특징 범위 ─────────────────────────
    normal_ranges = [
        (0.45, 0.55),   # Cycle_Duration(s)
        (0.26, 0.33),   # Stance_Duration(s)
        (0.16, 0.22),   # Swing_Duration(s)
        (55.0, 65.0),   # Stance_Ratio(%)
        (8.0,  13.0),   # GRF_Peak(kgf)
        (40.0, 80.0),   # Loading_Rate(kgf/s)
        (1.2,  1.8),    # Contact_Area(cm²)
        (8.0,  15.0),   # COP_Row_Range(mm)
        (0.5,  2.0),    # COP_Col_Range(mm)
        (3.0,  12.0),   # Foot_Angle_est(deg)
        (5.0,  20.0),   # Stride_Length_est(mm)
    ]

    # ── 비정상 보행 특징 범위 ───────────────────────
    # 다리 고장, 지형 이상, 하중 불균형 등을 반영
    abnormal_ranges = [
        (0.30, 0.70),   # 주기 불규칙
        (0.12, 0.25),   # 입각기 짧음
        (0.18, 0.45),   # 유각기 길어짐
        (30.0, 50.0),   # 입각기 비율 감소
        (2.0,  7.0),    # GRF 피크 저하
        (5.0,  35.0),   # 충격률 감소
        (0.3,  0.9),    # 접촉 면적 감소
        (1.0,  6.0),    # COP 이동 범위 감소
        (2.5,  7.0),    # 좌우 COP 편향 증가
        (18.0, 40.0),   # 발 각도 증가 (틀어짐)
        (0.0,  4.0),    # 보폭 감소
    ]

    def make_samples(ranges_per_foot, n):
        samples = []
        for _ in range(n):
            lf = [np.random.uniform(lo, hi) for lo, hi in ranges_per_foot]
            # RF는 LF 기준 ±10% 노이즈 (정상은 좌우 대칭)
            rf = [v * np.random.uniform(0.90, 1.10) for v in lf]
            # 대칭성 지수 계산 (자동)
            si_grf     = abs(lf[4] - rf[4]) / ((lf[4] + rf[4]) / 2 + 1e-9) * 100
            si_stance  = abs(lf[1] - rf[1]) / ((lf[1] + rf[1]) / 2 + 1e-9) * 100
            force_diff = abs(lf[4] - rf[4])
            samples.append(lf + rf + [si_grf, si_stance, force_diff])
        return np.array(samples)

    def make_abnormal_samples(ranges_per_foot, n):
        samples = []
        for _ in range(n):
            lf = [np.random.uniform(lo, hi) for lo, hi in ranges_per_foot]
            # 비정상은 좌우 비대칭 심화 (±20~40%)
            asym = np.random.uniform(0.6, 0.8)
            rf   = [v * asym for v in lf]
            si_grf     = abs(lf[4] - rf[4]) / ((lf[4] + rf[4]) / 2 + 1e-9) * 100
            si_stance  = abs(lf[1] - rf[1]) / ((lf[1] + rf[1]) / 2 + 1e-9) * 100
            force_diff = abs(lf[4] - rf[4])
            samples.append(lf + rf + [si_grf, si_stance, force_diff])
        return np.array(samples)

    X_normal   = make_samples(normal_ranges, n_per_class)
    X_abnormal = make_abnormal_samples(abnormal_ranges, n_per_class)

    X = np.vstack([X_normal, X_abnormal])
    y = np.array([0] * n_per_class + [1] * n_per_class)

    print(f"  ✅ 학습 데이터 생성: 정상 {n_per_class}개, 비정상 {n_per_class}개")
    print(f"     특징 벡터 크기: {X.shape[1]}개")
    return X, y


# ============================================================
# 2. 모델 정의 및 학습
# ============================================================
def build_model():
    """
    RandomForest + SVM 소프트 투표 앙상블 모델 생성
    각 모델을 StandardScaler와 Pipeline으로 묶어 스케일링 자동화
    """
    # RandomForest: 결정 트리 100개 앙상블
    # - 소량 데이터에 강함
    # - 특징 중요도(feature importance) 제공
    # - 과적합에 강한 bagging 기반
    rf = Pipeline([
        ('scaler', StandardScaler()),
        ('clf',    RandomForestClassifier(
            n_estimators=100,    # 트리 100개
            max_depth=8,         # 과적합 방지를 위한 깊이 제한
            min_samples_leaf=3,  # 리프 노드 최소 샘플 수
            class_weight='balanced',  # 클래스 불균형 자동 보정
            random_state=42
        ))
    ])

    # SVM: 초평면으로 정상/비정상 경계 학습
    # - 고차원(25개 특징) 데이터에 효과적
    # - RBF 커널로 비선형 경계 학습
    # - probability=True: 확률값 출력 가능
    svm = Pipeline([
        ('scaler', StandardScaler()),
        ('clf',    SVC(
            kernel='rbf',
            C=10,              # 마진 vs 오분류 트레이드오프
            gamma='scale',     # 커널 폭 자동 설정
            probability=True,  # 확률값 출력
            class_weight='balanced',
            random_state=42
        ))
    ])

    # 소프트 투표 앙상블
    # - 각 모델의 확률값 평균으로 최종 판정
    # - RF 0.6 + SVM 0.4 가중치 (RF가 소량 데이터에 더 강함)
    ensemble = VotingClassifier(
        estimators=[('rf', rf), ('svm', svm)],
        voting='soft',
        weights=[0.6, 0.4]
    )
    return ensemble


def train_model(X, y, save=True):
    """
    모델 학습 + 교차검증 + 저장
    반환: 학습된 모델
    """
    print("\n🤖 [머신러닝] 모델 학습 시작...")

    model = build_model()

    # 5-Fold 교차검증 (Stratified: 클래스 비율 유지)
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    cv_scores = cross_val_score(model, X, y, cv=cv, scoring='accuracy')

    print(f"  교차검증 정확도: {cv_scores.mean()*100:.1f}% "
          f"(± {cv_scores.std()*100:.1f}%)")

    # 전체 데이터로 최종 학습
    model.fit(X, y)

    # 학습 데이터 기준 성능 리포트
    y_pred = model.predict(X)
    print("\n  📋 분류 성능 리포트 (학습 데이터 기준):")
    print(classification_report(y, y_pred,
          target_names=['정상(Normal)', '비정상(Abnormal)'],
          digits=3))

    # 혼동 행렬
    cm = confusion_matrix(y, y_pred)
    print(f"  혼동 행렬:")
    print(f"           예측 정상  예측 비정상")
    print(f"  실제 정상  {cm[0][0]:5d}      {cm[0][1]:5d}")
    print(f"  실제 비정상 {cm[1][0]:5d}      {cm[1][1]:5d}")

    # 모델 저장
    if save:
        with open(MODEL_SAVE_PATH, 'wb') as f:
            pickle.dump(model, f)
        print(f"\n  💾 모델 저장 완료: {MODEL_SAVE_PATH}")

    return model


def load_model():
    """저장된 모델 불러오기"""
    if os.path.exists(MODEL_SAVE_PATH):
        with open(MODEL_SAVE_PATH, 'rb') as f:
            model = pickle.load(f)
        print(f"  ✅ 저장된 모델 불러오기 완료: {MODEL_SAVE_PATH}")
        return model
    return None


# ============================================================
# 3. 특징 벡터 조합 함수
#    gait_realtime.py 의 extract_features_single_cycle()
#    결과 두 개(LF, RF)를 받아 25차원 벡터로 만듦
# ============================================================
def build_feature_vector(lf_features, rf_features):
    """
    LF/RF 특징 딕셔너리 → 25차원 numpy 벡터 변환

    입력:
        lf_features: extract_features_single_cycle(cycle, 'LF') 반환값
        rf_features: extract_features_single_cycle(cycle, 'RF') 반환값
    반환:
        numpy array shape=(1, 25)
    """
    lf_peak    = lf_features.get('LF_GRF_Peak(kgf)', 0)
    rf_peak    = rf_features.get('RF_GRF_Peak(kgf)', 0)
    lf_stance  = lf_features.get('LF_Stance_Duration(s)', 0)
    rf_stance  = rf_features.get('RF_Stance_Duration(s)', 0)

    denom_grf    = (lf_peak   + rf_peak)   / 2 + 1e-9
    denom_stance = (lf_stance + rf_stance) / 2 + 1e-9

    si_grf     = abs(lf_peak   - rf_peak)   / denom_grf    * 100
    si_stance  = abs(lf_stance - rf_stance) / denom_stance * 100
    force_diff = abs(lf_peak - rf_peak)

    vector = [
        lf_features.get('LF_Cycle_Duration(s)',      0),
        lf_features.get('LF_Stance_Duration(s)',     0),
        lf_features.get('LF_Swing_Duration(s)',      0),
        lf_features.get('LF_Stance_Ratio(%)',        0),
        lf_features.get('LF_GRF_Peak(kgf)',          0),
        lf_features.get('LF_Loading_Rate(kgf/s)',    0),
        lf_features.get('LF_Contact_Area(cm²)',      0),
        lf_features.get('LF_COP_Row_Range(mm)',      0),
        lf_features.get('LF_COP_Col_Range(mm)',      0),
        lf_features.get('LF_Foot_Angle_est(deg)',    0),
        lf_features.get('LF_Stride_Length_est(mm)',  0),
        rf_features.get('RF_Cycle_Duration(s)',      0),
        rf_features.get('RF_Stance_Duration(s)',     0),
        rf_features.get('RF_Swing_Duration(s)',      0),
        rf_features.get('RF_Stance_Ratio(%)',        0),
        rf_features.get('RF_GRF_Peak(kgf)',          0),
        rf_features.get('RF_Loading_Rate(kgf/s)',    0),
        rf_features.get('RF_Contact_Area(cm²)',      0),
        rf_features.get('RF_COP_Row_Range(mm)',      0),
        rf_features.get('RF_COP_Col_Range(mm)',      0),
        rf_features.get('RF_Foot_Angle_est(deg)',    0),
        rf_features.get('RF_Stride_Length_est(mm)',  0),
        si_grf,
        si_stance,
        force_diff,
    ]
    return np.array(vector).reshape(1, -1)


# ============================================================
# 4. 실시간 판별 함수
#    gait_realtime.py 의 메인 루프에서 호출
# ============================================================
def predict(model, lf_features, rf_features):
    """
    보행 주기 1개에 대한 정상/비정상 판별

    반환:
        result   : 'NORMAL' 또는 'ABNORMAL'
        prob_normal   : 정상 확률 (0.0~1.0)
        prob_abnormal : 비정상 확률 (0.0~1.0)
        detail   : 판별 근거 딕셔너리
    """
    X = build_feature_vector(lf_features, rf_features)

    # 확률값 예측
    proba  = model.predict_proba(X)[0]  # [정상 확률, 비정상 확률]
    label  = model.predict(X)[0]        # 0=정상, 1=비정상
    result = 'NORMAL' if label == 0 else 'ABNORMAL'

    # 판별 근거: 이상이 감지된 특징 항목 추출
    X_flat = X[0]
    detail = {}
    if X_flat[3] < 50:   # Stance_Ratio
        detail['입각기 비율 저하'] = f"{X_flat[3]:.1f}% (정상: 55~65%)"
    if X_flat[4] < 6:    # LF GRF Peak
        detail['LF 지면반력 저하'] = f"{X_flat[4]:.2f} kgf (정상: 8~13)"
    if X_flat[15] < 6:   # RF GRF Peak
        detail['RF 지면반력 저하'] = f"{X_flat[15]:.2f} kgf (정상: 8~13)"
    if X_flat[22] > 10:  # SI_GRF
        detail['좌우 하중 비대칭'] = f"SI = {X_flat[22]:.1f}% (정상: <10%)"
    if X_flat[9] > 15:   # LF Foot Angle
        detail['LF 발 각도 이상'] = f"{X_flat[9]:.1f}° (정상: 3~12°)"
    if X_flat[20] > 15:  # RF Foot Angle
        detail['RF 발 각도 이상'] = f"{X_flat[20]:.1f}° (정상: 3~12°)"

    return result, proba[0], proba[1], detail


# ============================================================
# 5. 재학습 함수
#    실제 데이터가 쌓이면 호출하여 모델 업데이트
# ============================================================
def retrain(new_X, new_y, existing_model=None):
    """
    실제 측정 데이터로 모델 재학습

    사용 방법:
        # 실제 데이터 수집 후
        X_real = np.array([...])   # shape: (샘플수, 25)
        y_real = np.array([...])   # 0=정상, 1=비정상
        model  = retrain(X_real, y_real)

    기존 가상 데이터와 실제 데이터를 합쳐서 학습 (데이터 부족 보완)
    """
    print("\n🔄 [재학습] 실제 데이터로 모델 업데이트...")

    # 기존 가상 데이터와 합산
    X_virtual, y_virtual = generate_training_data(n_per_class=100)
    X_combined = np.vstack([X_virtual, new_X])
    y_combined = np.concatenate([y_virtual, new_y])

    print(f"  학습 데이터: 가상 {len(X_virtual)}개 + 실제 {len(new_X)}개 "
          f"= 총 {len(X_combined)}개")

    model = train_model(X_combined, y_combined, save=True)
    return model


# ============================================================
# 6. 특징 중요도 출력 함수 (RandomForest 기반)
# ============================================================
def print_feature_importance(model, top_n=10):
    """
    어떤 특징이 판별에 가장 중요한지 출력
    모델 해석과 이상 원인 분석에 활용
    """
    try:
        # VotingClassifier 내부 RF 추출
        rf_pipeline = model.estimators_[0]
        rf_clf      = rf_pipeline.named_steps['clf']
        importances = rf_clf.feature_importances_

        idx_sorted  = np.argsort(importances)[::-1]
        print(f"\n  📊 특징 중요도 Top {top_n}:")
        print(f"  {'순위':>4}  {'특징명':<35}  {'중요도':>8}")
        print("  " + "─" * 52)
        for rank, idx in enumerate(idx_sorted[:top_n], 1):
            print(f"  {rank:>4}  {FEATURE_NAMES[idx]:<35}  "
                  f"{importances[idx]*100:>7.2f}%")
    except Exception as e:
        print(f"  ⚠️  특징 중요도 출력 불가: {e}")


# ============================================================
# 7. 메인 (실제 수집 데이터로만 학습)
# ============================================================
if __name__ == '__main__':
    from gait_data_collector import load_collected_data

    print("=" * 65)
    print("  MS9723 보행 판별 — 머신러닝 모듈 (실측 데이터 학습)")
    print("=" * 65)

    # ── 실제 수집 데이터 로드 ─────────────────────────
    print("\n📦 [1단계] 실측 데이터 로드 (gait_collected_data.csv)")
    X, y, lf_s, rf_s = load_collected_data()

    if X is None or len(X) == 0:
        print("\n  ❌ 수집된 데이터가 없습니다.")
        print("     gait_data_collector.py를 먼저 실행하여 데이터를 수집하세요.")
        exit()

    normal_cnt   = (y == 0).sum()
    abnormal_cnt = (y == 1).sum()

    if normal_cnt == 0 or abnormal_cnt == 0:
        print(f"\n  ❌ 정상({normal_cnt}개) / 비정상({abnormal_cnt}개)")
        print("     정상과 비정상 데이터가 모두 있어야 학습할 수 있습니다.")
        exit()

    print(f"\n  정상: {normal_cnt}개 / 비정상: {abnormal_cnt}개 로드 완료")

    # ── 모델 학습 ─────────────────────────────────────
    print("\n🤖 [2단계] 모델 학습")
    model = train_model(X, y, save=True)   # gait_ml_model.pkl 저장

    # ── 특징 중요도 출력 ──────────────────────────────
    print_feature_importance(model, top_n=10)

    print("\n" + "─" * 65)
    print("✅ 학습 완료! gait_ml_model.pkl 이 저장되었습니다.")
    print("   이제 gait_realtime.py 를 실행하면 실시간 판별이 가능합니다.")
    print("─" * 65)
