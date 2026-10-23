"""HTTP binding for the private interview studio."""
from typing import Literal
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import current_user
from app.studio.service import StudioService
from app.studio.jobs import drain

router = APIRouter(prefix='/studio', tags=['studio'])
Category = Literal['RESUME', 'PORTFOLIO', 'COMPANY_INFO', 'JOB_DESCRIPTION']

class WorkspaceInput(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    company_name: str = Field(default='', max_length=200)
    target_role: str = Field(default='', max_length=100)

class SourceInput(BaseModel):
    category: Category
    title: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=1, max_length=100000)

class SessionInput(BaseModel):
    workspace_id: int
    source_ids: list[int] = Field(default_factory=list, max_length=50)
    interview_type: Literal['COMPREHENSIVE', 'TECHNICAL', 'BEHAVIORAL', 'RESUME', 'DOCUMENT_BASED'] = 'COMPREHENSIVE'
    difficulty: Literal['BEGINNER', 'INTERMEDIATE', 'ADVANCED'] = 'INTERMEDIATE'
    duration_minutes: int = Field(default=20, ge=5, le=60)
    feedback_mode: Literal['COACHING', 'SIMULATION'] = 'COACHING'
    input_mode: Literal['TEXT', 'AUDIO', 'VIDEO', 'AUDIO_VIDEO'] = 'TEXT'

class AnswerInput(BaseModel):
    text: str = Field(min_length=1, max_length=20000)
    client_submission_id: str = Field(min_length=1, max_length=100)

class ControlInput(BaseModel):
    expected_control_version: int = Field(ge=0)

class CaptureInput(BaseModel):
    turn_offset_ms: int = Field(default=0, ge=0, le=3_600_000)

class SealInput(BaseModel):
    last_seq: dict[Literal['audio', 'video'], int] = Field(min_length=1, max_length=2)
    is_final_for_turn: bool = True

class TranscriptInput(BaseModel):
    turn_index: int = Field(ge=0)
    text: str = Field(min_length=1, max_length=20000)


def dependencies(db: Session = Depends(get_db), user=Depends(current_user)):
    return StudioService(db, user)


def queued(background, ident, result, service):
    # FastAPI may close yield dependencies after background tasks. Release every
    # request transaction before the worker opens its independent connection.
    service.db.commit()
    background.add_task(drain, ident)
    return result

@router.get('/workspaces')
def workspaces(s=Depends(dependencies)):
    return s.workspace_list()

@router.post('/workspaces', status_code=201)
def create_workspace(payload: WorkspaceInput, s=Depends(dependencies)):
    return s.workspace_create(payload)

@router.get('/workspaces/{ident}/sources')
def sources(ident: int, s=Depends(dependencies)):
    return s.source_list(ident)

@router.post('/workspaces/{ident}/sources', status_code=201)
def create_source(ident: int, payload: SourceInput, s=Depends(dependencies)):
    return s.source_create(ident, payload)

@router.post('/workspaces/{ident}/sources/{source_id}/revisions', status_code=201)
def revise_source(ident: int, source_id: int, payload: SourceInput, s=Depends(dependencies)):
    return s.source_create(ident, payload, source_id)

@router.delete('/workspaces/{ident}/sources/{source_id}', status_code=204)
def delete_source(ident: int, source_id: int, s=Depends(dependencies)):
    s.source_delete(ident, source_id)

@router.post('/workspaces/{ident}/sources/upload', status_code=201)
async def upload_source(ident: int, category: Category = Form(...), title: str = Form(..., min_length=1, max_length=200), file: UploadFile = File(...), s=Depends(dependencies)):
    # Bound the stream before invoking document parsers.
    content = await file.read(10 * 1024 * 1024 + 1)
    return s.source_upload(ident, category, title, file.filename, content)

@router.post('/sessions', status_code=201)
def create_session(payload: SessionInput, s=Depends(dependencies)):
    return s.create(payload)

@router.get('/sessions')
def sessions(s=Depends(dependencies)):
    return s.session_list()

@router.get('/sessions/{ident}')
def session(ident: int, background: BackgroundTasks, s=Depends(dependencies)):
    result = s.detail(s.session(ident))
    return queued(background, ident, result, s)

@router.post('/sessions/{ident}/start')
def start(ident: int, payload: ControlInput, background: BackgroundTasks, idempotency_key: str = Header(..., min_length=1, max_length=100), s=Depends(dependencies)):
    return queued(background, ident, s.control(ident, 'start', payload.expected_control_version, idempotency_key), s)

@router.post('/sessions/{ident}/speaker-enrollment')
async def speaker_enrollment(ident: int, consent: bool = Form(...), file: UploadFile = File(...), s=Depends(dependencies)):
    content = await file.read(5 * 1024 * 1024 + 1)
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(413, '음성 등록은 5MB 이하여야 합니다.')
    return s.speaker_enrollment(ident, content, consent)

@router.post('/sessions/{ident}/pause')
def pause(ident: int, payload: ControlInput, background: BackgroundTasks, idempotency_key: str = Header(..., min_length=1, max_length=100), s=Depends(dependencies)):
    return queued(background, ident, s.control(ident, 'pause', payload.expected_control_version, idempotency_key), s)

@router.post('/sessions/{ident}/resume')
def resume(ident: int, payload: ControlInput, background: BackgroundTasks, idempotency_key: str = Header(..., min_length=1, max_length=100), s=Depends(dependencies)):
    return queued(background, ident, s.control(ident, 'resume', payload.expected_control_version, idempotency_key), s)

@router.post('/sessions/{ident}/finish', status_code=202)
def finish(ident: int, payload: ControlInput, background: BackgroundTasks, idempotency_key: str = Header(..., min_length=1, max_length=100), s=Depends(dependencies)):
    return queued(background, ident, s.control(ident, 'finish', payload.expected_control_version, idempotency_key), s)

@router.post('/sessions/{ident}/answers', status_code=202)
def answer(ident: int, payload: AnswerInput, background: BackgroundTasks, s=Depends(dependencies)):
    return queued(background, ident, s.answer(ident, payload), s)

@router.post('/sessions/{ident}/question-ready')
def question_ready(ident: int, s=Depends(dependencies)):
    return s.question_ready(ident)

@router.get('/sessions/{ident}/report')
def report(ident: int, background: BackgroundTasks, s=Depends(dependencies)):
    return queued(background, ident, s.report(ident), s)

@router.get('/sessions/{ident}/reports/{revision}')
def archived_report(ident: int, revision: int, s=Depends(dependencies)):
    return s.report_revision(ident, revision)

@router.get('/captures/{ident}/media/{track}')
def capture_media(ident: int, track: Literal['audio', 'video'], s=Depends(dependencies)):
    content, mime = s.media(ident, track)
    return Response(content, media_type=mime, headers={'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})

@router.post('/sessions/{ident}/captures', status_code=201)
def capture_create(ident: int, payload: CaptureInput, s=Depends(dependencies)):
    return s.capture_create(ident, payload)

@router.get('/captures/{ident}')
def capture_detail(ident: int, s=Depends(dependencies)):
    return s.capture_detail(ident)

@router.put('/captures/{ident}/chunks/{track}/{seq}')
async def chunk_put(ident: int, track: Literal['audio', 'video'], seq: int, request: Request,
                    x_capture_generation: int = Header(...), x_media_start_ms: int = Header(...),
                    x_media_end_ms: int = Header(...), s=Depends(dependencies)):
    content = bytearray()
    async for part in request.stream():
        content.extend(part)
        if len(content) > 2 * 1024 * 1024:
            raise HTTPException(413, '청크 용량을 초과했습니다.')
    return s.chunk_put(ident, track, seq, bytes(content), x_capture_generation, x_media_start_ms,
                       x_media_end_ms, request.headers.get('content-type', 'application/octet-stream'))

@router.post('/captures/{ident}/seal', status_code=202)
def capture_seal(ident: int, payload: SealInput, background: BackgroundTasks, s=Depends(dependencies)):
    result = s.capture_seal(ident, payload)
    capture, row = s.owned_capture(ident)
    return queued(background, row.id, result, s)

@router.get('/sessions/{ident}/transcripts')
def transcript_list(ident: int, s=Depends(dependencies)):
    return s.session(ident).data['transcripts']

@router.post('/sessions/{ident}/transcripts', status_code=201)
def transcript_create(ident: int, payload: TranscriptInput, s=Depends(dependencies)):
    return s.transcript_create(ident, payload)

@router.post('/sessions/{ident}/transcripts/{turn_index}/{revision}/confirm', status_code=202)
def transcript_confirm(ident: int, turn_index: int, revision: int, background: BackgroundTasks, s=Depends(dependencies)):
    return queued(background, ident, s.transcript_confirm(ident, turn_index, revision), s)

@router.get('/jobs/{ident}')
def job_get(ident: int, s=Depends(dependencies)):
    return s.job_get(ident)

@router.post('/jobs/{ident}/retry', status_code=202)
def job_retry(ident: int, background: BackgroundTasks, s=Depends(dependencies)):
    result = s.job_retry(ident)
    return queued(background, result['session_id'], result, s)

@router.delete('/sessions/{ident}', status_code=204)
def delete_session(ident: int, s=Depends(dependencies)):
    s.session_delete(ident)

class FeatureSample(BaseModel):
    t_ms: int = Field(ge=0, le=3_660_000)
    face_valid: bool
    pose_valid: bool
    camera_direction_deviation: float | None = Field(default=None, ge=0, le=10, allow_inf_nan=False)
    normalized_wrist_movement: float | None = Field(default=None, ge=0, le=100, allow_inf_nan=False)
    gaze_x: float | None = Field(default=None, ge=-5, le=5, allow_inf_nan=False)
    gaze_y: float | None = Field(default=None, ge=-5, le=5, allow_inf_nan=False)
    gaze_region: Literal['camera', 'screen', 'away', 'unknown'] | None = None
    quality_reason: str | None = Field(default=None, max_length=100)

class CalibrationInput(BaseModel):
    method: Literal['nose_relative_eye_midpoint', 'binocular_iris_headpose_affine'] = 'nose_relative_eye_midpoint'
    unit: Literal['interocular_distance', 'calibrated_screen_distance'] = 'interocular_distance'
    calibrated: bool = False
    point_count: int = Field(default=0, ge=0, le=100)
    validation_error: float | None = Field(default=None, ge=0, le=10, allow_inf_nan=False)

class FeatureInput(BaseModel):
    schema_version: Literal['landmark-proxy-v1', 'iris-calibrated-v2']
    generation: int = Field(ge=1)
    batch_id: str = Field(min_length=1, max_length=100)
    samples: list[FeatureSample] = Field(min_length=1, max_length=6000)
    calibration: CalibrationInput = Field(default_factory=CalibrationInput)

@router.post('/captures/{ident}/features')
def features(ident: int, payload: FeatureInput, s=Depends(dependencies)):
    return s.features(ident, payload)


@router.post('/sessions/{ident}/retry-answer')
def retry_answer(ident: int, s=Depends(dependencies)):
    return s.retry_answer(ident)
