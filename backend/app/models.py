from datetime import datetime
from typing import Optional

from sqlmodel import SQLModel, Field


class GaitSession(SQLModel, table=True):
    """한 번의 측정 세션 (보행 로봇/강아지 1회 착용 ~ 탈착까지)."""

    id: Optional[int] = Field(default=None, primary_key=True)
    dog_name: str = Field(default="우리 강아지")
    started_at: datetime = Field(default_factory=datetime.utcnow)


class GaitStep(SQLModel, table=True):
    """걸음 1개의 측정 결과. gait_logger.log_step()과 동일한 정보를 담는다."""

    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: int = Field(foreign_key="gaitsession.id", index=True)

    global_step: int  # 세션 내 누적 걸음 번호 (1부터)
    set_no: int  # 회차 번호 (20걸음 = 1회차)
    step_in_set: int  # 회차 내 걸음 번호 (1~20)

    ensemble_score: float  # 0~1, 높을수록 비대칭(비정상)
    symmetry: int  # round((1 - ensemble_score) * 100)

    left_matrix: str  # 16x10 압력 행렬, JSON 문자열로 저장
    right_matrix: str

    ts: datetime = Field(default_factory=datetime.utcnow)
