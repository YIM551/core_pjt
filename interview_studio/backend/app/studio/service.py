"""Owner-scoped studio state machine and media lifecycle."""
import hashlib
import time
from copy import deepcopy
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException
from sqlalchemy import select, delete, func
from app.core.config import get_settings
from app.studio.analysis import evaluate, generate_question
from app.studio.retrieval import retrieve, ingest
from app.studio.models import StudioWorkspace, StudioSource, StudioSession, StudioCapture, StudioChunk, StudioSourceChunk, StudioJob


class StudioService:
    def __init__(self, db, user):
        self.db, self.user = db, user

    def owned(self, model, ident):
        row = self.db.scalar(select(model).where(model.id == ident).with_for_update())
        if not row or row.deleted_at or row.user_id != self.user.id:
            raise HTTPException(404, '자료를 찾을 수 없습니다.')
        return row

    def workspace(self, ident):
        return self.owned(StudioWorkspace, ident)

    def session(self, ident):
        row = self.owned(StudioSession, ident)
        if row.status == 'ACTIVE' and self.remaining(row) == 0:
            d = deepcopy(row.data)
            cutoff = d.get('active_since', time.time()) + max(0, d['settings']['duration_minutes'] * 60 - d.get('elapsed', 0))
            self.clock_stop(d, 'TIME_LIMIT', cutoff)
            row.status = 'FINALIZING'
            d.update(cutoff_at=cutoff, finalize_deadline=cutoff + 120, end_reason='time_limit')
            d['control_version'] += 1
            row.data = d
            job = self.new_job(row, 'FINALIZE')
            d['job_id'] = job.id
            row.data = deepcopy(d)
            self.db.commit()
        return row

    def save(self, row, data):
        row.data = deepcopy(data)
        self.db.commit()
        return self.detail(row)

    def remaining(self, row):
        d = row.data
        used = d.get('elapsed', 0)
        if row.status == 'ACTIVE' and d.get('active_since') is not None:
            used += max(0, time.time() - d['active_since'])
        return max(0, d['settings']['duration_minutes'] * 60 - int(used))

    def detail(self, row):
        data = {k: deepcopy(v) for k, v in row.data.items() if k != 'controls' and not k.startswith('_')}
        return dict(id=row.id, status=row.status, remaining_seconds=self.remaining(row), **data)

    def clock_stop(self, d, reason, cutoff=None):
        start = d.pop('active_since', None)
        if start is not None:
            end = min(time.time(), cutoff) if cutoff is not None else time.time()
            d['elapsed'] = d.get('elapsed', 0) + max(0, end - start)
            d.setdefault('timer_segments', []).append({'start': start, 'end': end, 'reason': reason})
        d['timer_phase'] = reason

    def create(self, payload):
        workspace = self.workspace(payload.workspace_id)
        sources = []
        for ident in dict.fromkeys(payload.source_ids):
            source = self.db.get(StudioSource, ident)
            if not source or source.deleted_at or source.workspace_id != workspace.id:
                raise HTTPException(404, '선택 자료를 찾을 수 없습니다.')
            sources.append(dict(id=source.id, category=source.category, title=source.title, content_hash=source.content_hash, revision=source.revision))
        settings = payload.model_dump()
        settings['target_role'] = workspace.target_role
        row = StudioSession(user_id=self.user.id, workspace_id=workspace.id, status='READY', data={
            'settings': settings, 'sources': sources, 'answers': [], 'elapsed': 0, 'question': None,
            'control_version': 0, 'source_epoch': 0, 'timer_segments': [], 'timer_phase': 'READY',
            'controls': {}, 'report_revision': 0, 'transcripts': [], 'turn_index': 0,
            'turn_epochs': {'0': 0}, 'invalidated_turns': [],
        })
        self.db.add(row)
        self.db.commit()
        return self.detail(row)

    def new_job(self, row, kind, payload=None):
        job = StudioJob(session_id=row.id, kind=kind, status='PENDING', data={
            **(payload or {}), 'source_epoch': row.data.get('source_epoch', 0), 'attempt': 1,
        })
        self.db.add(job)
        self.db.flush()
        return job

    def control(self, ident, action, expected=None, key=None):
        row = self.session(ident)
        d = deepcopy(row.data)
        fingerprint = f'{action}:{expected}'
        if action == 'finish' and row.status in ('FINALIZING', 'COMPLETED'):
            return self.detail(row)
        if key and key in d.get('controls', {}):
            previous = d['controls'][key]
            if previous['fingerprint'] != fingerprint:
                raise HTTPException(409, '동일 요청 키에 다른 요청입니다.')
            return previous['response']
        if expected is not None and expected != d['control_version']:
            raise HTTPException(409, '면접 상태가 변경되었습니다. 새로 조회해 주세요.')
        allowed = {'start': ['READY'], 'pause': ['ACTIVE'], 'resume': ['PAUSED'], 'finish': ['ACTIVE', 'PAUSED', 'READY']}
        if row.status not in allowed[action]:
            raise HTTPException(409, '현재 상태에서 실행할 수 없습니다.')
        expired = self.remaining(row) == 0
        if action == 'resume' and expired:
            raise HTTPException(409, '면접 시간이 종료되었습니다.')
        previous_phase = d.get('timer_phase', 'QUESTION')
        resume_phase = d.get('paused_timer_phase', previous_phase) if previous_phase == 'PAUSE' else previous_phase
        if action == 'pause':
            d['paused_timer_phase'] = previous_phase
        self.clock_stop(d, action.upper())
        if action in ('start', 'resume'):
            row.status = 'ACTIVE'
            pending_analysis = self.db.scalar(select(StudioJob.id).where(StudioJob.session_id == ident, StudioJob.kind.in_(['CONTENT', 'QUESTION', 'TRANSCRIBE']), StudioJob.status.in_(['PENDING', 'RUNNING'])).limit(1))
            if pending_analysis:
                d['timer_phase'] = 'ANALYZING'
            elif action == 'resume' and resume_phase == 'TRANSCRIPT_REVIEW':
                d['timer_phase'] = 'TRANSCRIPT_REVIEW'
            elif d['question']:
                d['active_since'] = time.time()
                d['timer_phase'] = 'QUESTION'
            else:
                job = self.new_job(row, 'QUESTION')
                d['job_id'] = job.id
                d['timer_phase'] = 'ANALYZING'
        elif action == 'pause':
            row.status = 'PAUSED'
            # Preserve sealed segments; resumption always creates a different capture.
            for capture in self.db.scalars(select(StudioCapture).where(StudioCapture.session_id == ident, StudioCapture.sealed.is_(False))):
                data = deepcopy(capture.data)
                data['cutoff_at'] = time.time()
                data['pause_pending'] = True
                capture.data = data
        else:
            row.status = 'FINALIZING'
            d['end_reason'] = 'time_limit' if expired else 'user_finish'
            d['cutoff_at'] = time.time()
            d['finalize_deadline'] = time.time() + 120
            job = self.new_job(row, 'FINALIZE')
            d['job_id'] = job.id
        d['control_version'] += 1
        row.data = deepcopy(d)
        response = self.detail(row)
        if key:
            controls = d.setdefault('controls', {})
            if len(controls) >= 100:
                del controls[next(iter(controls))]
            # Avoid recursive copies of previous control results.
            controls[key] = {'fingerprint': fingerprint, 'response': deepcopy(response)}
        return self.save(row, d)

    def answer(self, ident, payload):
        row = self.session(ident)
        d = deepcopy(row.data)
        for answer in d['answers']:
            if answer['client_submission_id'] == payload.client_submission_id:
                if answer['text'] != payload.text:
                    raise HTTPException(409, '동일 제출 키에 다른 답변입니다.')
                return self.detail(row)
        if row.status != 'ACTIVE' or self.remaining(row) <= 0 or not d.get('question'):
            raise HTTPException(409, '답변을 제출할 수 없는 상태입니다.')
        if d.get('timer_phase') == 'ANALYZING':
            raise HTTPException(409, '이전 답변을 분석하고 있습니다.')
        if d['settings']['input_mode'] != 'TEXT':
            raise HTTPException(409, '음성 면접은 턴 전사를 확정해 주세요. 텍스트 모드에서만 직접 제출할 수 있습니다.')
        self.clock_stop(d, 'ANALYZING')
        index = len(d['answers'])
        d['answers'].append(dict(text=payload.text, client_submission_id=payload.client_submission_id,
                                 question=d['question'], content_status='pending_analysis', turn_index=d['turn_index']))
        row.data = d
        job = self.new_job(row, 'CONTENT', {'answer_index': index, 'text_hash': hashlib.sha256(payload.text.encode()).hexdigest()})
        d['job_id'] = job.id
        return self.save(row, d)

    def workspace_list(self):
        return [self.workspace_json(w) for w in self.db.scalars(select(StudioWorkspace).where(StudioWorkspace.user_id == self.user.id, StudioWorkspace.deleted_at.is_(None)))]

    @staticmethod
    def workspace_json(w):
        return dict(id=w.id, name=w.name, company_name=w.company_name, target_role=w.target_role)

    def workspace_create(self, payload):
        row = StudioWorkspace(user_id=self.user.id, **payload.model_dump())
        self.db.add(row)
        self.db.commit()
        return self.workspace_json(row)

    def source_list(self, ident):
        self.workspace(ident)
        return [self.source_json(r) for r in self.db.scalars(select(StudioSource).where(StudioSource.workspace_id == ident, StudioSource.deleted_at.is_(None)))]

    @staticmethod
    def source_json(r):
        return dict(id=r.id, category=r.category, title=r.title, text=r.text, content_hash=r.content_hash,
                    revision=r.revision, parent_id=r.parent_id, status=(r.processing or {}).get('status', 'READY'), processing=r.processing)

    def source_create(self, ident, payload, parent=None):
        self.workspace(ident)
        if parent:
            old = self.db.get(StudioSource, parent)
            if not old or old.workspace_id != ident or old.deleted_at:
                raise HTTPException(404, '원본 자료를 찾을 수 없습니다.')
        else:
            old = None
        row = StudioSource(workspace_id=ident, content_hash=hashlib.sha256(payload.text.encode()).hexdigest(),
                           revision=old.revision + 1 if old else 1, parent_id=parent,
                           processing={'status': 'PROCESSING'}, **payload.model_dump())
        self.db.add(row)
        self.db.commit()
        # Network work runs without an ownership lock; deletion during ingestion is handled by final check.
        ingest(self.db, row)
        return self.source_json(row)

    def source_delete(self, workspace_id, ident):
        self.workspace(workspace_id)
        source = self.db.scalar(select(StudioSource).where(StudioSource.id == ident).with_for_update())
        if not source or source.workspace_id != workspace_id or source.deleted_at:
            raise HTTPException(404, '자료를 찾을 수 없습니다.')
        from app.shared.clients.file_storage import safe_delete
        if source.original_path:
            safe_delete(source.original_path)
            source.original_path = None
        source.original_filename = None
        source.deleted_at = datetime.now(timezone.utc)
        source.text = ''
        self.db.execute(delete(StudioSourceChunk).where(StudioSourceChunk.source_id == ident))
        for row in self.db.scalars(select(StudioSession).where(StudioSession.workspace_id == workspace_id).with_for_update()):
            d = deepcopy(row.data)
            if not any(r['id'] == ident for r in d.get('sources', [])):
                continue
            d['sources'] = [r for r in d['sources'] if r['id'] != ident]
            d['source_epoch'] = d.get('source_epoch', 0) + 1
            invalidated = set(d.get('invalidated_turns', []))
            invalidated.update(range(d['turn_index'] + 1))
            d['invalidated_turns'] = sorted(invalidated)
            for transcript in d.get('transcripts', []):
                transcript['invalidated'] = True
            # Retire open old-turn captures atomically; they may never block a fresh turn.
            for capture in self.db.scalars(select(StudioCapture).where(
                    StudioCapture.session_id == row.id, StudioCapture.sealed.is_(False)).with_for_update()):
                capture.sealed = True
                capture.deleted_at = datetime.now(timezone.utc)
                capture.data = {'generation': capture.data['generation'], 'turn_index': capture.data['turn_index'],
                    'cutoff_at': time.time(), 'discarded': True, 'reason': 'source_deleted', 'bytes': 0}
                self.db.execute(delete(StudioChunk).where(StudioChunk.capture_id == capture.id))
            d['question'] = None
            d['question_evidence'] = []
            d['turn_questions'] = {}
            d['turn_evidence'] = {}
            # Source erasure also redacts every archived report and acoustic reference.
            d.pop('report_archives', None)
            d.pop('audio_analyses', None)
            d['controls'] = {}
            for answer in d['answers']:
                answer['question'] = '[참고자료 삭제로 질문 근거를 폐기했습니다.]'
                answer.pop('assessment', None)
                answer['content_status'] = 'source_deleted'
            row.data = d
            for job in self.db.scalars(select(StudioJob).where(StudioJob.session_id == row.id)):
                job.status = 'INVALIDATED'
                job.data = {'reason': 'source_deleted'}
            if row.status == 'FINALIZING':
                final_job = self.new_job(row, 'FINALIZE')
                d['job_id'] = final_job.id
                row.data = deepcopy(d)
            elif row.status in ('ACTIVE', 'PAUSED'):
                # A replacement question gets a fresh turn; previous sealed captures stay immutable.
                d['turn_index'] += 1
                d.setdefault('turn_epochs', {})[str(d['turn_index'])] = d['source_epoch']
                d['transcript_status'] = 'source_deleted'
                self.clock_stop(d, 'ANALYZING')
                row.data = deepcopy(d)
                question_job = self.new_job(row, 'QUESTION')
                d['job_id'] = question_job.id
                row.data = deepcopy(d)
        self.db.commit()

    def session_list(self):
        return [self.detail(r) for r in self.db.scalars(select(StudioSession).where(StudioSession.user_id == self.user.id, StudioSession.deleted_at.is_(None)))]

    def owned_capture(self, ident):
        # Always lock parent before child to avoid pause/upload lock inversion.
        parent_id = self.db.scalar(select(StudioCapture.session_id).where(StudioCapture.id == ident))
        if parent_id is None:
            raise HTTPException(404, '수집 자료가 없습니다.')
        row = self.session(parent_id)
        capture = self.db.scalar(select(StudioCapture).where(StudioCapture.id == ident).with_for_update())
        if not capture or capture.deleted_at:
            raise HTTPException(404, '수집 자료가 없습니다.')
        return capture, row

    def capture_create(self, ident, payload):
        self.cleanup_media()
        row = self.session(ident)
        if row.status != 'ACTIVE' or self.remaining(row) <= 0 or not row.data.get('question') or row.data.get('timer_phase') == 'ANALYZING':
            raise HTTPException(409, '수집할 수 없는 상태입니다.')
        if row.data['settings']['input_mode'] == 'TEXT':
            raise HTTPException(409, '텍스트 면접에는 미디어를 수집하지 않습니다.')
        captures = list(self.db.scalars(select(StudioCapture).where(StudioCapture.session_id == ident)))
        if len(captures) >= 200:
            raise HTTPException(413, '면접당 수집 구간 수를 초과했습니다.')
        current_turn = row.data['turn_index']
        if any(c.data.get('turn_index') == current_turn and c.data.get('seal', {}).get('is_final_for_turn') for c in captures):
            raise HTTPException(409, '최종 봉인된 턴입니다.')
        if any(not c.sealed and not c.data.get('pause_pending') for c in captures):
            raise HTTPException(409, '열린 수집 구간을 먼저 봉인해 주세요.')
        generation = len(captures) + 1
        capture = StudioCapture(session_id=ident, sealed=False, data={'turn_offset_ms': payload.turn_offset_ms,
            'generation': generation, 'turn_index': current_turn, 'created_at': time.time(),
            'expires_at': time.time() + get_settings().studio_media_retention_hours * 3600, 'bytes': 0, 'tracks': {}})
        self.db.add(capture)
        self.db.commit()
        return dict(id=capture.id, **capture.data)

    def chunk_put(self, ident, track, seq, content, generation, start_ms, end_ms, mime):
        if seq < 0 or seq > 3600 or not 0 < len(content) <= 2 * 1024 * 1024:
            raise HTTPException(413, '청크 범위 또는 용량이 잘못되었습니다.')
        capture, row = self.owned_capture(ident)
        data = deepcopy(capture.data)
        if generation != data['generation']:
            raise HTTPException(409, '수집 버전이 다릅니다.')
        if start_ms < 0 or end_ms <= start_ms or end_ms - start_ms > 15000 or end_ms > 3_660_000:
            raise HTTPException(422, '미디어 시간 범위가 잘못되었습니다.')
        if mime not in ('audio/webm', 'audio/webm;codecs=opus', 'audio/ogg', 'audio/mp4', 'video/webm', 'video/webm;codecs=vp8,opus', 'video/mp4', 'application/octet-stream'):
            raise HTTPException(415, '지원하지 않는 미디어 형식입니다.')
        digest = hashlib.sha256(content).hexdigest()
        metadata = dict(start_ms=start_ms, end_ms=end_ms, mime=mime, hash=digest)
        track_data = data.setdefault('tracks', {}).setdefault(track, {})
        existing = self.db.scalar(select(StudioChunk).where(StudioChunk.capture_id == ident, StudioChunk.track == track, StudioChunk.seq == seq))
        if existing:
            if existing.content_hash != digest or track_data.get(str(seq)) != metadata:
                raise HTTPException(409, '기존 순번의 내용이나 시간이 다릅니다.')
            return dict(seq=seq, content_hash=digest)
        if capture.sealed or time.time() > data['expires_at']:
            raise HTTPException(409, '수집 구간이 종료되었습니다.')
        cutoff = min(v for v in (data.get('cutoff_at', float('inf')), row.data.get('cutoff_at', float('inf'))))
        if row.status == 'ACTIVE' and self.remaining(row) == 0:
            cutoff = min(cutoff, time.time())
        if cutoff != float('inf'):
            if time.time() > cutoff + 15 or data['created_at'] + end_ms / 1000 > cutoff + 1:
                raise HTTPException(409, '종료 이후 생성된 청크 또는 수신 유예시간을 넘었습니다.')
        elif row.status != 'ACTIVE':
            raise HTTPException(409, '현재 수집 상태가 아닙니다.')
        media_total = sum(c.data.get('bytes', 0) for c in self.db.scalars(select(StudioCapture).where(StudioCapture.session_id == row.id)))
        if media_total + len(content) > get_settings().studio_max_media_mb * 1024 * 1024:
            raise HTTPException(413, '면접 전체 미디어 용량을 초과했습니다.')
        # Reject overlapping adjacent chunks, while permitting out-of-order transport.
        for number, item in track_data.items():
            if int(number) < seq and item['end_ms'] > start_ms or int(number) > seq and item['start_ms'] < end_ms:
                raise HTTPException(409, '청크 미디어 시간이 겹칩니다.')
        track_data[str(seq)] = metadata
        data['bytes'] += len(content)
        capture.data = data
        self.db.add(StudioChunk(capture_id=ident, track=track, seq=seq, content_hash=digest, content=content))
        self.db.commit()
        return dict(seq=seq, content_hash=digest)

    def capture_detail(self, ident):
        capture, _ = self.owned_capture(ident)
        tracks = capture.data.get('tracks', {})
        return dict(id=ident, sealed=capture.sealed, generation=capture.data['generation'],
                    tracks={t: {'received': sorted(int(n) for n in values)} for t, values in tracks.items()})

    def capture_seal(self, ident, payload):
        capture, row = self.owned_capture(ident)
        data = deepcopy(capture.data)
        seal = payload.model_dump()
        if capture.sealed:
            if data.get('seal') != seal:
                raise HTTPException(409, '이미 다른 범위로 봉인했습니다.')
            return dict(id=ident, sealed=True, job_id=data.get('job_id'))
        now = time.time()
        if row.status not in ('ACTIVE', 'PAUSED', 'FINALIZING'):
            raise HTTPException(409, '최종화된 면접에는 새 수집 봉인을 만들 수 없습니다.')
        if now >= data.get('expires_at', 0) or now >= row.data.get('finalize_deadline', float('inf')):
            raise HTTPException(409, '미디어 보관 또는 최종화 기한이 종료되었습니다.')
        segments = list(self.db.scalars(select(StudioCapture).where(
            StudioCapture.session_id == row.id).order_by(StudioCapture.id).with_for_update()))
        turn_segments = sorted([c for c in segments if c.data.get('turn_index') == data['turn_index']],
                               key=lambda c: (c.data['turn_offset_ms'], c.id))
        if payload.is_final_for_turn:
            if any(not c.sealed for c in turn_segments if c.id != capture.id):
                raise HTTPException(409, '이전 수집 구간을 모두 봉인한 후 답변을 최종 봉인해 주세요.')
            if any(c.data.get('seal', {}).get('is_final_for_turn') for c in turn_segments if c.id != capture.id):
                raise HTTPException(409, '이미 최종 봉인한 턴입니다.')
        tracks = data.get('tracks', {})
        if not tracks or set(payload.last_seq) != set(tracks):
            raise HTTPException(422, '수신된 모든 트랙의 마지막 순번이 필요합니다.')
        missing = {}
        for track, last in payload.last_seq.items():
            if last < 0 or last > 3600:
                raise HTTPException(422, '청크 범위가 잘못되었습니다.')
            received = {int(n) for n in tracks[track]}
            if received and max(received) > last:
                raise HTTPException(409, '수신된 청크를 제외하고 봉인할 수 없습니다.')
            gaps = sorted(set(range(last + 1)) - received)
            if gaps:
                missing[track] = gaps
        if missing:
            raise HTTPException(409, detail={'missing': missing})
        capture.sealed = True
        data['seal'] = seal
        data['sealed_at'] = time.time()
        if payload.is_final_for_turn:
            d = deepcopy(row.data)
            self.clock_stop(d, 'TRANSCRIPT_REVIEW')
            row.data = d
            refs = [c.id for c in turn_segments]
            d.setdefault('turn_capture_refs', {})[str(data['turn_index'])] = refs
            row.data = deepcopy(d)
            job = self.new_job(row, 'TRANSCRIBE', {'capture_refs': refs, 'turn_index': data['turn_index']})
            data['job_id'] = job.id
        capture.data = data
        self.db.commit()
        return dict(id=ident, sealed=True, job_id=data.get('job_id'))

    def cleanup_media(self):
        enrollments = [r.id for r in self.db.scalars(select(StudioSession))
            if r.data.get('_speaker_enrollment_expires_at', float('inf')) < time.time()]
        self.db.commit()
        for ident in enrollments:
            row = self.db.scalar(select(StudioSession).where(StudioSession.id == ident).with_for_update())
            if row and row.data.get('_speaker_enrollment_expires_at', float('inf')) < time.time():
                self.delete_enrollment(row)
                d = deepcopy(row.data)
                d.pop('_speaker_enrollment_path', None)
                d.pop('_speaker_enrollment_expires_at', None)
                d['speaker_enrollment'] = {'status': 'expired'}
                row.data = d
            self.db.commit()
        # Use the same parent -> capture -> chunk order as collection and deletion.
        expired = [(c.id, c.session_id) for c in self.db.scalars(select(StudioCapture))
                   if c.data.get('expires_at', float('inf')) < time.time()]
        self.db.commit()
        for capture_id, session_id in expired:
            self.db.scalar(select(StudioSession).where(StudioSession.id == session_id).with_for_update())
            capture = self.db.scalar(select(StudioCapture).where(StudioCapture.id == capture_id).with_for_update())
            if capture and capture.data.get('expires_at', float('inf')) < time.time():
                self.db.execute(delete(StudioChunk).where(StudioChunk.capture_id == capture_id))
                data = deepcopy(capture.data)
                data['media_status'] = 'EXPIRED'
                data['bytes'] = 0
                capture.data = data
            self.db.commit()

    def transcript_create(self, ident, payload):
        row = self.session(ident)
        d = deepcopy(row.data)
        self.validate_transcript_turn(d, payload.turn_index)
        refs = d.get('turn_capture_refs', {}).get(str(payload.turn_index), [])
        final = any(c.data.get('seal', {}).get('is_final_for_turn') for c in self.db.scalars(select(StudioCapture).where(StudioCapture.id.in_(refs))))
        if not refs or not final:
            raise HTTPException(409, '답변을 최종 봉인한 후 전사를 수정해 주세요.')
        revisions = [t for t in d['transcripts'] if t['turn_index'] == payload.turn_index]
        revision = len(revisions) + 1
        d['transcripts'].append({'turn_index': payload.turn_index, 'revision': revision, 'text': payload.text,
            'capture_refs': refs, 'origin': 'USER', 'confirmed': False, 'created_at': time.time()})
        result = self.save(row, d)
        result['revision'] = revision
        return result

    def transcript_confirm(self, ident, turn_index, revision):
        row = self.session(ident)
        d = deepcopy(row.data)
        self.validate_transcript_turn(d, turn_index)
        candidates = [t for t in d['transcripts'] if t['turn_index'] == turn_index and t['revision'] == revision]
        if not candidates:
            raise HTTPException(404, '전사가 없습니다.')
        target = candidates[0]
        if target.get('confirmed'):
            return self.detail(row)
        target['confirmed'] = True
        index = len(d['answers'])
        d['answers'].append({'text': target['text'], 'question': d['turn_questions'][str(turn_index)], 'turn_index': turn_index,
            'transcript_revision': revision, 'client_submission_id': f'transcript:{turn_index}:{revision}', 'content_status': 'pending_analysis'})
        if turn_index == d['turn_index']:
            self.clock_stop(d, 'ANALYZING')
        row.data = d
        job = self.new_job(row, 'CONTENT', {'answer_index': index, 'text_hash': hashlib.sha256(target['text'].encode()).hexdigest()})
        self.new_job(row, 'ACOUSTIC', {'capture_refs': target.get('capture_refs', []),
            'turn_index': turn_index, 'transcript_revision': revision, 'reference_text': target['text']})
        d['job_id'] = job.id
        return self.save(row, d)

    def report(self, ident):
        row = self.session(ident)
        latest = {}
        for answer in row.data['answers']:
            latest[answer.get('turn_index', 0)] = answer
        answers = list(latest.values())
        assessments = [a.get('assessment', {}) for a in answers]
        captures = list(self.db.scalars(select(StudioCapture).where(StudioCapture.session_id == ident)))
        text_mode = row.data['settings']['input_mode'] == 'TEXT'
        has_audio = any(c.data.get('tracks', {}).get('audio') for c in captures)
        modalities = {}
        for key in ('pronunciation', 'speech_rate', 'gaze', 'gesture'):
            if text_mode:
                code, reason = 'text_mode', '텍스트 면접에서는 마이크·카메라 분석을 수집하지 않습니다.'
            elif key in ('gaze', 'gesture'):
                code, reason = 'no_visual_samples', '보정된 카메라 관측 표본이 없어 영상 지표를 측정하지 못했습니다.'
            elif not has_audio:
                code, reason = 'no_audio', '수집된 음성 구간이 없어 음성 지표를 측정하지 못했습니다.'
            else:
                code, reason = 'provider_unavailable', '해당 음성 분석 결과를 얻지 못했습니다. 로컬 분석 엔진 및 모델 상태를 확인해 주세요.'
            modalities[key] = {'status': 'unavailable', 'reason_code': code, 'reason': reason}

        complete = bool(assessments) and all(a.get('status') == 'complete' for a in assessments)
        modalities['content'] = {'status': 'complete' if complete else 'partial' if answers else 'unavailable',
                                 'reason': '확정한 답변의 근거 기반 내용 평가' if complete else '미확정 전사 또는 처리하지 못한 답변이 있습니다.'}
        report = {'session_id': row.id, 'status': 'partial', 'revision': row.data.get('report_revision', 0),
                'session_status': row.status, 'content': answers, 'modalities': modalities,
                'strengths': [v for a in assessments for v in a.get('strengths', [])],
                'improvements': [v for a in assessments for v in a.get('improvements', [])],
                'measurement_coverage': {'content_answers': sum(a.get('status') == 'complete' for a in assessments), 'total_answers': len(answers)},
                'notice': '미측정 항목은 감점하지 않습니다. 카메라 방향은 시선/집중도와 다릅니다.'}
        if not text_mode:
            self.visual_report(row, report)
            self.speech_report(row, report)
            analyses = list(row.data.get('audio_analyses', {}).values())
            if analyses:
                report['modalities']['pronunciation'] = {
                    'status': 'partial' if any(a.get('status') == 'complete' for a in analyses) else 'unavailable',
                    'reason_code': 'uncalibrated_acoustic_diagnostic', 'score': None,
                    'summary': '확정 전사와 음성의 로컬 음향 정렬 관찰', 'turns': analyses,
                    'reason': '음향 정렬은 검증된 발음 등급이 아닙니다. 기술 용어·전사 오류·화자 구분 불확실성을 함께 확인하세요.'}
            speaker = [output.get('speaker_analysis', {}) for t in row.data.get('transcripts', [])
                if t.get('origin') == 'ASR' for output in t.get('segments', [])]
            report['modalities']['speaker_separation'] = {
                'status': 'partial' if any(a.get('status') == 'complete' for a in speaker) else 'unavailable',
                'analyses': speaker, 'summary': '등록 목소리에 따른 두 화자 분리·불확실 구간 제외',
                'reason': '미등록 또는 모델 실패 시 배경 화자가 제거되었다고 보장하지 않습니다.'}
        report['pipeline_versions'] = {'report': 'studio-v0.3-audio-v2', 'stt': 'faster-whisper-small',
            'pronunciation': 'local-ctc-alignment-v1', 'speaker': 'two-source-enrollment-v1',
            'speaker_thresholds': {'cosine_min': .65, 'margin_min': .15, 'calibrated': False},
            'loaded_model_identity_verified': False,
            'expected_model_revisions': {'ecapa': '0f99f2d0ebe89ac095bcc5903c4dd8f72b367286',
                'sepformer': '9950fd8055b38679d2af5bef2366b5dba600ec66',
                'korean_ctc': '629c9a3501c10ba128bf3fa1eebb12af3be03f61'}}
        if row.status == 'COMPLETED':
            d = deepcopy(row.data)
            archives = d.setdefault('report_archives', {})
            revision = str(report['revision'])
            if revision not in archives:
                archives[revision] = deepcopy(report)
                row.data = d
                self.db.commit()
            else:
                report = deepcopy(archives[revision])
        return report

    def report_revision(self, ident, revision):
        row = self.session(ident)
        archive = row.data.get('report_archives', {}).get(str(revision))
        if archive is None:
            raise HTTPException(404, '보관된 리포트가 없습니다.')
        return deepcopy(archive)

    def media(self, ident, track):
        self.cleanup_media()
        capture, row = self.owned_capture(ident)
        if not capture.sealed or time.time() >= capture.data.get('expires_at', 0):
            raise HTTPException(410, '미디어가 만료되었거나 아직 봉인되지 않았습니다.')
        chunks = list(self.db.scalars(select(StudioChunk).where(StudioChunk.capture_id == ident,
            StudioChunk.track == track).order_by(StudioChunk.seq)))
        if not chunks:
            raise HTTPException(404, '미디어가 없습니다.')
        mime = capture.data.get('tracks', {}).get(track, {}).get('0', {}).get('mime', 'application/octet-stream')
        return b''.join(c.content for c in chunks), mime

    def session_delete(self, ident):
        row = self.session(ident)
        self.delete_enrollment(row)
        refs = list(self.db.scalars(select(StudioCapture.id).where(StudioCapture.session_id == ident)))
        self.db.execute(delete(StudioChunk).where(StudioChunk.capture_id.in_(refs)))
        self.db.execute(delete(StudioCapture).where(StudioCapture.session_id == ident))
        self.db.execute(delete(StudioJob).where(StudioJob.session_id == ident))
        self.db.delete(row)
        self.db.commit()

    @staticmethod
    def delete_enrollment(row):
        from app.shared.clients.file_storage import resolve_upload_path
        path = row.data.get('_speaker_enrollment_path')
        if path:
            resolve_upload_path(get_settings().upload_dir, path).unlink(missing_ok=True)

    def speaker_enrollment(self, ident, content, consent):
        from app.studio.local_audio import decode_audio
        from app.shared.clients.file_storage import write_upload
        row = self.session(ident)
        if not consent:
            raise HTTPException(422, '화자 구분을 위한 음성 등록에 동의해 주세요.')
        if row.status != 'READY':
            raise HTTPException(409, '면접 시작 전에만 화자를 등록할 수 있습니다.')
        try:
            audio = decode_audio(content)
            import numpy as np
            if not 5 <= len(audio) / 16000 <= 30 or float(np.sqrt(np.mean(audio ** 2))) < .003:
                raise ValueError('invalid enrollment')
        except Exception:
            raise HTTPException(422, '조용한 환경에서 본인 목소리로 5~30초 녹음해 주세요.')
        self.delete_enrollment(row)
        stored = write_upload(get_settings().upload_dir / 'studio-enrollment' / str(self.user.id), 'enrollment.webm', content)
        d = deepcopy(row.data)
        d['_speaker_enrollment_path'] = stored.path
        d['_speaker_enrollment_expires_at'] = time.time() + get_settings().studio_media_retention_hours * 3600
        d['speaker_enrollment'] = {'status': 'enrolled', 'duration_seconds': round(len(audio) / 16000, 2),
            'consent': True, 'expires_at': d['_speaker_enrollment_expires_at']}
        self.save(row, d)
        return d['speaker_enrollment']

    def source_upload(self, ident, category, title, filename, content):
        from pathlib import Path
        from app.document.services.ingestion import ALLOWED_SUFFIXES, extract_text
        from app.shared.clients.file_storage import describe_upload, UnsafeUploadName
        from app.studio.controller import SourceInput
        self.workspace(ident)
        if len(content) > 10 * 1024 * 1024:
            raise HTTPException(413, '문서는 10MB 이하여야 합니다.')
        try:
            name, suffix = describe_upload(filename or '')
        except UnsafeUploadName:
            raise HTTPException(422, '파일 이름이 잘못되었습니다.')
        if suffix not in ALLOWED_SUFFIXES:
            raise HTTPException(415, '지원하지 않는 문서 형식입니다.')
        try:
            text = extract_text(content, suffix).strip()
        except Exception:
            raise HTTPException(422, '문서에서 텍스트를 추출하지 못했습니다.')
        if not text or len(text) > 100000:
            raise HTTPException(422, '추출한 텍스트는 1~100000자여야 합니다.')
        from app.shared.clients.file_storage import write_upload, safe_delete
        root = get_settings().upload_dir / 'studio' / str(self.user.id) / str(ident)
        stored = write_upload(root, name, content)
        try:
            result = self.source_create(ident, SourceInput(category=category, title=title, text=text))
            row = self.db.scalar(select(StudioSource).where(StudioSource.id == result['id']).with_for_update())
            if row.deleted_at:
                safe_delete(stored.path)
                raise HTTPException(409, '업로드 중 자료가 삭제되었습니다.')
            row.original_path = stored.path
            row.original_filename = stored.original_filename
            self.db.commit()
            return result
        except Exception:
            safe_delete(stored.path)
            raise

    def job_get(self, ident):
        job = self.db.get(StudioJob, ident)
        if not job:
            raise HTTPException(404, '작업이 없습니다.')
        self.session(job.session_id)
        return {'id': job.id, 'session_id': job.session_id, 'kind': job.kind, 'status': job.status,
                'reason': job.data.get('reason'), 'attempt': job.data.get('attempt', 1)}

    def job_retry(self, ident):
        job = self.db.get(StudioJob, ident)
        if not job:
            raise HTTPException(404, '작업이 없습니다.')
        row = self.session(job.session_id)
        job = self.db.scalar(select(StudioJob).where(StudioJob.id == ident).with_for_update())
        if job.status not in ('FAILED', 'UNAVAILABLE') or job.data.get('source_epoch') != row.data.get('source_epoch', 0):
            raise HTTPException(409, '이 작업은 다시 실행할 수 없습니다.')
        if job.data.get('attempt', 1) >= 5:
            raise HTTPException(409, '재시도 횟수를 초과했습니다.')
        job.status = 'PENDING'
        job.data = {**job.data, 'attempt': job.data.get('attempt', 1) + 1}
        self.db.commit()
        return self.job_get(ident)

    def features(self, ident, payload):
        import json
        capture, row = self.owned_capture(ident)
        d = deepcopy(capture.data)
        if payload.generation != d['generation']:
            raise HTTPException(409, '수집 버전이 다릅니다.')
        content = payload.model_dump()
        digest = hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()
        batches = d.setdefault('feature_batches', {})
        if payload.batch_id in batches:
            if batches[payload.batch_id] != digest:
                raise HTTPException(409, '동일 지표 키에 다른 데이터입니다.')
            return {'id': ident, 'accepted': len(payload.samples)}
        if capture.sealed or time.time() > d['expires_at']:
            raise HTTPException(409, '수집 구간이 종료되었습니다.')
        values = d.setdefault('feature_samples', [])
        if len(values) + len(payload.samples) > 20000 or len(batches) >= 100:
            raise HTTPException(413, '지표 수집 한도를 초과했습니다.')
        existing = {v['t_ms'] for v in values}
        incoming = [v.t_ms for v in payload.samples]
        if len(set(incoming)) != len(incoming) or existing.intersection(incoming):
            raise HTTPException(409, '같은 시각의 지표가 중복되었습니다.')
        cutoff = min(d.get('cutoff_at', float('inf')), row.data.get('cutoff_at', float('inf')))
        if row.status not in ('ACTIVE', 'PAUSED', 'FINALIZING') or time.time() > cutoff + 15:
            raise HTTPException(409, '지표 수신이 종료되었습니다.')
        if incoming and d['created_at'] + max(incoming) / 1000 > min(time.time() + 1, cutoff + 1):
            raise HTTPException(422, '지표 시간이 수집 범위를 벗어났습니다.')
        values.extend(v.model_dump() for v in payload.samples)
        d['feature_schema'] = payload.schema_version
        d['calibration'] = payload.calibration.model_dump()
        batches[payload.batch_id] = digest
        capture.data = d
        self.db.commit()
        return {'id': ident, 'accepted': len(payload.samples)}

    def question_ready(self, ident):
        row = self.session(ident)
        if row.status != 'ACTIVE' or not row.data.get('question'):
            raise HTTPException(409, '진행 중인 질문이 없습니다.')
        d = deepcopy(row.data)
        d.setdefault('question_ready_at', {}).setdefault(str(d['turn_index']), time.time())
        return self.save(row, d)


    def visual_report(self, row, report):
        import statistics
        captures = list(self.db.scalars(select(StudioCapture).where(StudioCapture.session_id == row.id)))
        samples = [sample for c in captures for sample in c.data.get('feature_samples', []) if c.data.get('calibration', {}).get('calibrated')]
        if not samples:
            return
        face = [v['camera_direction_deviation'] for v in samples if v['face_valid'] and v['camera_direction_deviation'] is not None]
        pose = [v['normalized_wrist_movement'] for v in samples if v['pose_valid'] and v['normalized_wrist_movement'] is not None]
        for key, values, unit in [('gaze', face, 'interocular_distance'), ('gesture', pose, 'shoulder_width_per_frame')]:
            coverage = len(values) / len(samples)
            precise = key == 'gaze' and any(c.data.get('feature_schema') == 'iris-calibrated-v2' for c in captures)
            if precise:
                unit = 'calibrated_screen_distance'
                calibrated_captures = [c for c in captures if c.data.get('feature_schema') == 'iris-calibrated-v2'
                    and c.data.get('calibration', {}).get('point_count', 0) >= 5
                    and c.data.get('calibration', {}).get('validation_error') is not None
                    and c.data['calibration']['validation_error'] <= .25]
                precise_samples = [v for c in calibrated_captures for v in c.data.get('feature_samples', [])]
                values = [v['camera_direction_deviation'] for v in precise_samples
                    if v['face_valid'] and v.get('gaze_x') is not None and v.get('gaze_y') is not None
                    and v['camera_direction_deviation'] is not None]
                coverage = len(values) / max(1, len(samples))
            report['modalities'][key] = {'status': 'complete' if len(values) >= 10 and coverage >= .5 else 'insufficient_data',
                'reason_code': 'measured' if len(values) >= 10 and coverage >= .5 else 'insufficient_data',
                'valid_samples': len(values), 'total_samples': len(samples), 'coverage': coverage,
                'median': statistics.median(values) if values else None, 'unit': unit,
                'summary': ('눈동자·머리 자세 기반 보정 시선 방향 추정' if precise else '보정된 카메라 방향 편차') if key == 'gaze' else '가시 구간의 손목 이동량',
                'reason': '관측 가능한 구간의 기술 통계이며, 태도·성격·주의력 점수가 아닙니다.'}


    def speech_report(self, row, report):
        # Only original ASR timing participates; edited transcript text never changes rate.
        original = {}
        for transcript in row.data.get('transcripts', []):
            if transcript.get('origin') == 'ASR' and transcript['turn_index'] not in original:
                original[transcript['turn_index']] = transcript
        words = 0
        span = 0.0
        speech_seconds = 0.0
        excluded_seconds = 0.0
        pauses = []
        fillers = 0
        background_unresolved = False
        latencies = []
        for transcript in original.values():
            for output in transcript.get('segments', []):
                if output.get('status') != 'complete':
                    continue
                if output.get('response_latency_seconds') is not None:
                    latencies.append(output['response_latency_seconds'])
                segments = output.get('segments', [])
                if not segments:
                    continue
                speaker = output.get('speaker_analysis', {})
                background_unresolved |= speaker.get('status') != 'complete'
                intervals = speaker.get('intervals', [])
                excluded = [(v['start'], v['end']) for v in intervals if v.get('status') != 'candidate']
                # A segment crossing an excluded window is excluded as a whole;
                # its words and duration are removed together.
                dropped = [(v['start'], v['end']) for v in segments
                    if any(v['start'] < end and v['end'] > start for start, end in excluded)]
                merged = []
                for start, end in sorted(excluded + dropped):
                    if merged and start <= merged[-1][1]:
                        merged[-1] = (merged[-1][0], max(merged[-1][1], end))
                    else:
                        merged.append((start, end))
                excluded = merged
                excluded_seconds += sum(end - start for start, end in excluded)
                segments = [v for v in segments if not any(v['start'] < end and v['end'] > start for start, end in excluded)]
                if not segments:
                    continue
                duration = max(s['end'] for s in segments) - min(s['start'] for s in segments)
                duration -= sum(max(0, min(end, max(s['end'] for s in segments)) - max(start, min(s['start'] for s in segments))) for start, end in excluded)
                if duration > 0:
                    span += duration
                    words += sum(len(s.get('text', '').split()) for s in segments)
                    speech_seconds += sum(s['end'] - s['start'] for s in segments)
                    ordered = sorted(segments, key=lambda v: v['start'])
                    pauses.extend(b['start'] - a['end'] for a, b in zip(ordered, ordered[1:])
                        if b['start'] - a['end'] >= .5 and not any(a['end'] < end and b['start'] > start for start, end in excluded))
                    fillers += sum(token.strip(',.!?') in ('음', '어', '그', '저기', '그러니까')
                        for s in segments for token in s.get('text', '').split())
        if span >= 3 and words:
            report['modalities']['speech_rate'] = {'status': 'complete', 'reason_code': 'measured', 'eojeol_per_minute': round(words * 60 / span, 1),
                'measured_seconds': span, 'eojeol_count': words,
                'speech_seconds': speech_seconds, 'excluded_seconds': excluded_seconds,
                'pause_count': len(pauses), 'pause_seconds': round(sum(pauses), 2),
                'filler_count': fillers, 'background_speaker_unresolved': background_unresolved,
                'response_latency_seconds': latencies,
                'summary': '원음성 ASR 구간 기준 분당 어절 수(구간 안 쉼 포함)',
                'reason': '전사 수정은 속도를 변경하지 않습니다. 속도 적정성 점수와 발음 점수는 제공하지 않습니다.'}


    def retry_answer(self, ident):
        row = self.session(ident)
        d = deepcopy(row.data)
        if row.status not in ('ACTIVE', 'PAUSED') or d.get('transcript_status') not in ('no_speech', 'provider_unavailable', 'unavailable'):
            raise HTTPException(409, '미측정 음성 답변만 다시 녹음할 수 있습니다.')
        old_turn = str(d['turn_index'])
        d['turn_index'] += 1
        new_turn = str(d['turn_index'])
        d.setdefault('turn_epochs', {})[new_turn] = d.get('source_epoch', 0)
        d.setdefault('turn_questions', {})[new_turn] = d['turn_questions'].get(old_turn, d.get('question'))
        d.setdefault('turn_evidence', {})[new_turn] = deepcopy(d['turn_evidence'].get(old_turn, []))
        d['transcript_status'] = 'retry_recording'
        d['timer_phase'] = 'QUESTION'
        if row.status == 'ACTIVE':
            d['active_since'] = time.time()
        else:
            d['paused_timer_phase'] = 'QUESTION'
        d['control_version'] += 1
        return self.save(row, d)


    @staticmethod
    def validate_transcript_turn(data, turn_index):
        key = str(turn_index)
        if (turn_index in data.get('invalidated_turns', []) or
                data.get('turn_epochs', {}).get(key) != data.get('source_epoch', 0) or
                not data.get('turn_questions', {}).get(key)):
            raise HTTPException(409, '자료 삭제로 폐기된 답변의 전사는 수정하거나 평가할 수 없습니다.')
