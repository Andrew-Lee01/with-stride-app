"""
gait_dashboard.py(Streamlit)의 판정/집계 로직을 그대로 옮겨온 모듈.
임계값·공식을 절대 바꾸지 말 것 — 기존 대시보드와 같은 기준으로 판정되어야 한다.
"""
from typing import Literal

STEPS_PER_SET = 20
NORMAL_MIN = 80
WARN_MIN = 60

StateName = Literal["정상", "경고", "위험"]


def symmetry_from_score(ensemble_score: float) -> int:
    return round((1 - ensemble_score) * 100)


def classify(symmetry: int) -> StateName:
    if symmetry >= NORMAL_MIN:
        return "정상"
    if symmetry >= WARN_MIN:
        return "경고"
    return "위험"


def set_and_step_in_set(global_step: int) -> tuple[int, int]:
    """세션 내 global_step(1부터)으로부터 (set_no, step_in_set)을 계산."""
    set_no = (global_step - 1) // STEPS_PER_SET + 1
    step_in_set = (global_step - 1) % STEPS_PER_SET + 1
    return set_no, step_in_set
