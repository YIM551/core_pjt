import json
from uuid import uuid4

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import current_user
from app.core.observability import reset_request_id, set_request_id
from app.interview.dto.models import InterviewCreateRequest, InterviewMessageRequest, InterviewDetailResponse, InterviewReportResponse, InterviewSessionResponse, InterviewTurnResponse
from app.interview.services.service import InterviewService

router = APIRouter(prefix="/interviews", tags=["interviews"])


@router.post("", status_code=status.HTTP_201_CREATED)
def create_interview(payload: InterviewCreateRequest, db: Session = Depends(get_db), user = Depends(current_user)):
    data = InterviewService(db, user).create(payload)
    return InterviewDetailResponse.model_validate(data)


@router.get("")
def list_interviews(db: Session = Depends(get_db), user = Depends(current_user)):
    return [InterviewSessionResponse.model_validate(item) for item in InterviewService(db, user).list()]


@router.get("/{session_id}")
def get_interview(session_id: int, db: Session = Depends(get_db), user = Depends(current_user)):
    return InterviewDetailResponse.model_validate(InterviewService(db, user).detail(session_id))


@router.post("/{session_id}/messages")
def create_message(session_id: int, payload: InterviewMessageRequest, db: Session = Depends(get_db), user = Depends(current_user)):
    return InterviewTurnResponse.model_validate(InterviewService(db, user).send(session_id, payload))


@router.post("/{session_id}/messages/stream")
async def stream_message(session_id: int, payload: InterviewMessageRequest, request: Request, db: Session = Depends(get_db), user = Depends(current_user)):
    service = InterviewService(db, user)
    prepared = service.prepare_message(session_id, payload)
    request_id = str(uuid4())

    async def events():
        token = set_request_id(request_id)
        try:
            yield f"event: status\ndata: {json.dumps({'step': 'generating'}, ensure_ascii=False)}\n\n"
            reply = prepared.result.interviewer_reply
            for offset in range(0, len(reply), 18):
                yield f"event: token\ndata: {json.dumps({'text': reply[offset:offset + 18]}, ensure_ascii=False)}\n\n"
            if await request.is_disconnected():
                service.rollback()
                return
            data = service.persist_message(prepared)
            yield f"event: complete\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"
        except Exception:
            service.rollback()
            yield 'event: error\ndata: {"code":"INTERNAL_ERROR"}\n\n'
        finally:
            reset_request_id(token)

    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/{session_id}/finish")
def finish_interview(session_id: int, db: Session = Depends(get_db), user = Depends(current_user)):
    return InterviewSessionResponse.model_validate(InterviewService(db, user).finish(session_id))


@router.get("/{session_id}/report")
def get_report(session_id: int, db: Session = Depends(get_db), user = Depends(current_user)):
    return InterviewReportResponse.model_validate(InterviewService(db, user).report(session_id))
