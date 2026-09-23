from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, field_validator

Matrix16x10 = List[List[float]]


class SessionCreate(BaseModel):
    dog_name: str = "우리 강아지"


class SessionSummary(BaseModel):
    id: int
    dog_name: str
    started_at: datetime
    step_count: int
    latest_symmetry: Optional[int] = None


class StepCreate(BaseModel):
    ensemble_score: float
    left_matrix: Optional[Matrix16x10] = None
    right_matrix: Optional[Matrix16x10] = None

    @field_validator("ensemble_score")
    @classmethod
    def _score_range(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            hint = ""
            if 1.0 < v <= 100.0:
                hint = f" 0~100 범위(퍼센트)라면 {v}/100 으로 나눠서 보내세요."
            raise ValueError(f"ensemble_score는 0~1 사이여야 합니다. 받은 값: {v}.{hint}")
        return v

    @field_validator("left_matrix", "right_matrix")
    @classmethod
    def _shape(cls, v):
        if v is None:
            return v
        if len(v) != 16 or any(len(row) != 10 for row in v):
            shape = (len(v), len(v[0]) if v else 0)
            if shape == (10, 16):
                raise ValueError(
                    "행렬 모양이 (10, 16)입니다 — 행/열이 뒤집힌 것 같습니다. 전치(transpose)해서 보내세요."
                )
            raise ValueError(f"행렬 모양이 {shape}입니다. 16x10(16행 10열)이어야 합니다.")
        return v


class StepOut(BaseModel):
    id: int
    session_id: int
    global_step: int
    set_no: int
    step_in_set: int
    ensemble_score: float
    symmetry: int
    left_matrix: Matrix16x10
    right_matrix: Matrix16x10
    ts: datetime


class RoundSummary(BaseModel):
    set_no: int
    avg_symmetry: int
    state: str
    step_count: int


class SessionDetail(BaseModel):
    id: int
    dog_name: str
    started_at: datetime
    steps: List[StepOut]
    rounds: List[RoundSummary]


def _validate_16x10(v, name: str):
    if len(v) != 16 or any(len(row) != 10 for row in v):
        shape = (len(v), len(v[0]) if v else 0)
        if shape == (10, 16):
            raise ValueError(
                f"{name}의 모양이 (10, 16)입니다 — 행/열이 뒤집힌 것 같습니다. 전치(transpose)해서 보내세요."
            )
        raise ValueError(f"{name}의 모양이 {shape}입니다. 16x10(16행 10열)이어야 합니다.")
    return v


class AnalyzeRequest(BaseModel):
    # 하드웨어 사정으로 지금은 앞/뒤 중 한 축(2개)만 실제 센서가 있는 상태가 계속 바뀔 수
    # 있어서, 앞/뒤 전부 선택값으로 둔다 — 한 축(앞 둘 다 또는 뒤 둘 다)만 보내도 되고,
    # 둘 다 보내도 된다. 최소 한 축은 있어야 한다(둘 다 없으면 422).
    front_left: Optional[Matrix16x10] = None
    front_right: Optional[Matrix16x10] = None
    rear_left: Optional[Matrix16x10] = None
    rear_right: Optional[Matrix16x10] = None

    @field_validator("front_left", "front_right", "rear_left", "rear_right")
    @classmethod
    def _shape(cls, v, info):
        if v is None:
            return v
        return _validate_16x10(v, info.field_name)

    @field_validator("rear_right")
    @classmethod
    def _at_least_one_axle(cls, v, info):
        values = info.data
        has_front = values.get("front_left") is not None and values.get("front_right") is not None
        has_rear = values.get("rear_left") is not None and v is not None
        if not has_front and not has_rear:
            raise ValueError("front_left+front_right 또는 rear_left+rear_right 중 한 쌍은 반드시 있어야 합니다.")
        return v


class PairAnalysis(BaseModel):
    ensemble_score: float
    verdict: str
    ml_score: float
    dtw_score: float


class AnalyzeResponse(BaseModel):
    front: Optional[PairAnalysis] = None
    rear: Optional[PairAnalysis] = None
    overall_score: float
    overall_symmetry: int
    verdict: str
