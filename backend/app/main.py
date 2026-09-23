import json
import pathlib
from collections import defaultdict
from typing import List

from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session, select

from . import analyze as analyze_module
from . import gait_logic
from .db import get_session, init_db
from .models import GaitSession, GaitStep
from .schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    PairAnalysis,
    RoundSummary,
    SessionCreate,
    SessionDetail,
    SessionSummary,
    StepCreate,
    StepOut,
)
from .ws_manager import manager

app = FastAPI(title="With-Stride API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    init_db()


def _step_to_out(step: GaitStep) -> StepOut:
    return StepOut(
        id=step.id,
        session_id=step.session_id,
        global_step=step.global_step,
        set_no=step.set_no,
        step_in_set=step.step_in_set,
        ensemble_score=step.ensemble_score,
        symmetry=step.symmetry,
        left_matrix=json.loads(step.left_matrix),
        right_matrix=json.loads(step.right_matrix),
        ts=step.ts,
    )


def _rounds_from_steps(steps: List[GaitStep]) -> List[RoundSummary]:
    by_set: dict[int, list[GaitStep]] = defaultdict(list)
    for s in steps:
        by_set[s.set_no].append(s)
    rounds = []
    for set_no in sorted(by_set):
        group = by_set[set_no]
        avg_sym = round(sum(s.symmetry for s in group) / len(group))
        rounds.append(
            RoundSummary(
                set_no=set_no,
                avg_symmetry=avg_sym,
                state=gait_logic.classify(avg_sym),
                step_count=len(group),
            )
        )
    return rounds


@app.post("/api/sessions", response_model=SessionSummary)
def create_session(body: SessionCreate, db: Session = Depends(get_session)):
    session = GaitSession(dog_name=body.dog_name)
    db.add(session)
    db.commit()
    db.refresh(session)
    return SessionSummary(
        id=session.id,
        dog_name=session.dog_name,
        started_at=session.started_at,
        step_count=0,
        latest_symmetry=None,
    )


@app.get("/api/sessions", response_model=List[SessionSummary])
def list_sessions(db: Session = Depends(get_session)):
    sessions = db.exec(
        select(GaitSession).order_by(GaitSession.started_at.desc())
    ).all()
    out = []
    for s in sessions:
        steps = db.exec(
            select(GaitStep)
            .where(GaitStep.session_id == s.id)
            .order_by(GaitStep.global_step.desc())
        ).all()
        out.append(
            SessionSummary(
                id=s.id,
                dog_name=s.dog_name,
                started_at=s.started_at,
                step_count=len(steps),
                latest_symmetry=steps[0].symmetry if steps else None,
            )
        )
    return out


@app.get("/api/sessions/{session_id}", response_model=SessionDetail)
def get_session_detail(session_id: int, db: Session = Depends(get_session)):
    session = db.get(GaitSession, session_id)
    if not session:
        raise HTTPException(404, "세션을 찾을 수 없습니다.")
    steps = db.exec(
        select(GaitStep)
        .where(GaitStep.session_id == session_id)
        .order_by(GaitStep.global_step)
    ).all()
    return SessionDetail(
        id=session.id,
        dog_name=session.dog_name,
        started_at=session.started_at,
        steps=[_step_to_out(s) for s in steps],
        rounds=_rounds_from_steps(steps),
    )


@app.post("/api/sessions/{session_id}/steps", response_model=StepOut)
async def log_step(
    session_id: int, body: StepCreate, db: Session = Depends(get_session)
):
    session = db.get(GaitSession, session_id)
    if not session:
        raise HTTPException(404, "세션을 찾을 수 없습니다.")

    prev_count = len(
        db.exec(select(GaitStep).where(GaitStep.session_id == session_id)).all()
    )
    global_step = prev_count + 1
    set_no, step_in_set = gait_logic.set_and_step_in_set(global_step)
    symmetry = gait_logic.symmetry_from_score(body.ensemble_score)

    zeros = [[0.0] * 10 for _ in range(16)]
    step = GaitStep(
        session_id=session_id,
        global_step=global_step,
        set_no=set_no,
        step_in_set=step_in_set,
        ensemble_score=body.ensemble_score,
        symmetry=symmetry,
        left_matrix=json.dumps(body.left_matrix or zeros),
        right_matrix=json.dumps(body.right_matrix or zeros),
    )
    db.add(step)
    db.commit()
    db.refresh(step)

    out = _step_to_out(step)
    await manager.broadcast(session_id, {"type": "step", "data": out.model_dump(mode="json")})
    return out


@app.post("/api/analyze", response_model=AnalyzeResponse)
def analyze(body: AnalyzeRequest):
    """
    뒷발(rear_left/rear_right) 압력 매트릭스를 받아 ML+DTW 앙상블로 정상/비정상
    점수를 계산해서 돌려준다. 앞발(front_left/front_right)은 하드웨어가 갖춰지면
    다시 켤 수 있도록 선택값으로 남겨뒀고, 오면 같이 계산해서 함께 보여준다.
    (HMM 제외 및 특징 근사 등 현재 한계는 app/analyze.py 상단 주석 참고)
    """
    rear = analyze_module.analyze_pair(body.rear_left, body.rear_right)

    front = None
    if body.front_left is not None and body.front_right is not None:
        front = analyze_module.analyze_pair(body.front_left, body.front_right)

    overall_score = (
        (front["ensemble_score"] + rear["ensemble_score"]) / 2.0 if front else rear["ensemble_score"]
    )
    overall_symmetry = gait_logic.symmetry_from_score(overall_score)
    verdict = "ABNORMAL" if overall_score > 0.5 else "NORMAL"

    return AnalyzeResponse(
        front=PairAnalysis(**front) if front else None,
        rear=PairAnalysis(**rear),
        overall_score=overall_score,
        overall_symmetry=overall_symmetry,
        verdict=verdict,
    )


@app.websocket("/ws/sessions/{session_id}")
async def session_ws(websocket: WebSocket, session_id: int):
    await manager.connect(session_id, websocket)
    try:
        while True:
            await websocket.receive_text()  # 클라이언트로부터는 heartbeat만 기대
    except WebSocketDisconnect:
        manager.disconnect(session_id, websocket)


# ── 프런트엔드 정적 파일 서빙 (배포용, 한 서비스로 프런트+백엔드 같이 뜨도록) ──
# 반드시 API/WS 라우트 전부를 등록한 "뒤"에 와야 한다. 그래야 /api/*, /ws/* 요청이
# 아래 catch-all에 먼저 잡히지 않는다.
_FRONTEND_DIST = pathlib.Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"

if _FRONTEND_DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=_FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}")
    def spa_fallback(full_path: str):
        candidate = _FRONTEND_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_FRONTEND_DIST / "index.html")
