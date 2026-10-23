"""Durable database jobs; provider work happens outside row locks."""
import hashlib
import time
from copy import deepcopy
from types import SimpleNamespace
from sqlalchemy import select
from app.studio.models import StudioSession, StudioJob, StudioSource, StudioCapture, StudioChunk
from app.studio.service import StudioService
from app.studio.analysis import evaluate, generate_question, generate_followup, transcribe
from app.studio.retrieval import retrieve
from app.core.config import get_settings


def enrollment_bytes(snapshot):
    from app.shared.clients.file_storage import read_bytes
    path = snapshot.get('_speaker_enrollment_path')
    if not path or time.time() >= snapshot.get('_speaker_enrollment_expires_at', 0):
        return None
    try:
        return read_bytes(get_settings().upload_dir, path)
    except OSError:
        return None


def filtered_audio(content, snapshot):
    from app.studio.local_audio import separate_speakers
    import io
    import wave
    import numpy as np
    settings = get_settings()
    separation = separate_speakers(content, enrollment_bytes(snapshot), settings.studio_speaker_model_path,
                                   settings.studio_separation_model_path)
    candidate = separation.pop('candidate_audio', None)
    if candidate is None:
        return content, separation
    output = io.BytesIO()
    with wave.open(output, 'wb') as wav:
        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(16000)
        wav.writeframes((np.clip(candidate, -1, 1) * 32767).astype('<i2').tobytes())
    return output.getvalue(), separation


def run_job(db, ident):
    # Match every session mutation: parent session, then child job.
    session_id = db.scalar(select(StudioJob.session_id).where(StudioJob.id == ident))
    if session_id is None:
        db.rollback()
        return
    row = db.scalar(select(StudioSession).where(StudioSession.id == session_id).with_for_update())
    job = db.scalar(select(StudioJob).where(StudioJob.id == ident).with_for_update())
    if not job or job.status != 'PENDING':
        db.rollback()
        return
    if not row or row.deleted_at or row.data.get('source_epoch', 0) != job.data.get('source_epoch'):
        job.status = 'INVALIDATED'
        db.commit()
        return
    session_id = row.id
    user_id = row.user_id
    payload = deepcopy(job.data)
    snapshot = deepcopy(row.data)
    kind = job.kind
    job.status = 'RUNNING'
    job.data = {**payload, 'started_at': time.time()}
    db.commit()
    service = StudioService(db, SimpleNamespace(id=user_id))
    try:
        if kind == 'QUESTION':
            query = f"{snapshot['settings']['target_role']} {snapshot['settings']['interview_type']} {snapshot['settings']['difficulty']}"
            evidence = retrieve(db, [s['id'] for s in snapshot['sources']], query)
            db.commit()
            previous = next((a for a in reversed(snapshot.get('answers', [])) if a.get('turn_index') == snapshot['turn_index'] - 1), None)
            parents = snapshot.get('followup_parents', {})
            followup = previous is not None and str(previous['turn_index']) not in parents and previous['turn_index'] not in parents.values()
            if followup:
                question, mode = generate_followup(previous['question'], previous['text'], snapshot['settings'])
                evidence = snapshot.get('turn_evidence', {}).get(str(previous['turn_index']), [])
            else:
                question, mode = generate_question(snapshot['settings'], evidence, snapshot['turn_index'])
            result = {'question': question, 'mode': mode, 'evidence': evidence,
                'parent_turn_index': previous['turn_index'] if followup else None}
        elif kind == 'CONTENT':
            answer = snapshot['answers'][payload['answer_index']]
            if hashlib.sha256(answer['text'].encode()).hexdigest() != payload['text_hash']:
                raise ValueError('changed input')
            context = '\n'.join(e['text'] for e in snapshot.get('turn_evidence', {}).get(str(answer['turn_index']), []))
            result = evaluate(answer['question'], answer['text'], context)
            result['evidence_refs'] = [{'source_id': e.get('source_id'), 'chunk_id': e.get('chunk_id')}
                for e in snapshot.get('turn_evidence', {}).get(str(answer['turn_index']), [])]
        elif kind == 'TRANSCRIBE':
            captures = list(db.scalars(select(StudioCapture).where(StudioCapture.id.in_(payload['capture_refs']))))
            outputs = []
            for capture in sorted(captures, key=lambda c: c.data['turn_offset_ms']):
                chunks = list(db.scalars(select(StudioChunk).where(StudioChunk.capture_id == capture.id, StudioChunk.track == 'audio').order_by(StudioChunk.seq)))
                if not chunks:
                    outputs.append({'status': 'unavailable', 'reason': '음성 자료가 없습니다.'})
                    continue
                mime = capture.data['tracks']['audio']['0']['mime']
                audio, separation = filtered_audio(b''.join(c.content for c in chunks), snapshot)
                output = transcribe(audio, mime)
                output['speaker_analysis'] = separation
                output['capture_id'] = capture.id
                output['turn_offset_ms'] = capture.data['turn_offset_ms']
                first = min((v['start'] for v in output.get('segments', [])), default=None)
                ready_at = snapshot.get('question_ready_at', {}).get(str(payload['turn_index']))
                output['response_latency_seconds'] = max(0, capture.data['created_at'] + first - ready_at) if first is not None and ready_at is not None else None
                outputs.append(output)
            result = {'status': 'complete' if outputs and all(o['status'] == 'complete' for o in outputs) else 'unavailable',
                      'text': ' '.join(o.get('text', '') for o in outputs), 'segments': outputs,
                      'reason_code': 'no_speech' if outputs and all(o.get('reason_code') == 'no_speech' for o in outputs) else 'provider_unavailable'}
            db.commit()
        elif kind == 'ACOUSTIC':
            from app.studio.local_audio import assess_pronunciation
            captures = list(db.scalars(select(StudioCapture).where(StudioCapture.id.in_(payload['capture_refs']))))
            audio_parts = []
            import io
            import wave
            import numpy as np
            from app.studio.local_audio import decode_audio
            separation_results = []
            for capture in sorted(captures, key=lambda c: c.data['turn_offset_ms']):
                chunks = list(db.scalars(select(StudioChunk).where(StudioChunk.capture_id == capture.id,
                    StudioChunk.track == 'audio').order_by(StudioChunk.seq)))
                if not chunks:
                    continue
                content, separation = filtered_audio(b''.join(c.content for c in chunks), snapshot)
                audio_parts.append(decode_audio(content))
                separation_results.append(separation)
            db.commit()
            if audio_parts:
                buf = io.BytesIO()
                with wave.open(buf, 'wb') as wav:
                    wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(16000)
                    wav.writeframes((np.clip(np.concatenate(audio_parts), -1, 1) * 32767).astype('<i2').tobytes())
                result = assess_pronunciation(buf.getvalue(), payload['reference_text'], get_settings().studio_pronunciation_model_path)
            else:
                result = {'status': 'unavailable', 'reason_code': 'audio_expired'}
            result['speaker_analyses'] = separation_results
        elif kind == 'FINALIZE':
            result = {}
        else:
            raise ValueError('unknown job')
        row = service.session(session_id)
        job = db.scalar(select(StudioJob).where(StudioJob.id == ident).with_for_update())
        if not job or job.status != 'RUNNING' or row.data.get('source_epoch', 0) != payload['source_epoch']:
            db.rollback()
            return
        d = deepcopy(row.data)
        if kind == 'QUESTION':
            d['question'] = result['question']
            d.setdefault('turn_questions', {})[str(d['turn_index'])] = result['question']
            d.setdefault('turn_epochs', {})[str(d['turn_index'])] = d.get('source_epoch', 0)
            d['question_evidence'] = result['evidence']
            d.setdefault('turn_evidence', {})[str(d['turn_index'])] = deepcopy(result['evidence'])
            d['question_generation'] = result['mode']
            if result.get('parent_turn_index') is not None:
                d.setdefault('followup_parents', {})[str(d['turn_index'])] = result['parent_turn_index']
            if row.status == 'ACTIVE':
                d['active_since'] = time.time()
                d['timer_phase'] = 'QUESTION'
            elif row.status == 'PAUSED':
                d['timer_phase'] = 'PAUSE'
                d['paused_timer_phase'] = 'QUESTION'
        elif kind == 'CONTENT':
            answer = d['answers'][payload['answer_index']]
            answer['assessment'] = result
            answer['content_status'] = result['status']
            if row.status in ('ACTIVE', 'PAUSED') and d['turn_index'] == answer['turn_index'] and not answer.get('advance_done'):
                answer['advance_done'] = True
                d['turn_index'] += 1
                d['question'] = None
                row.data = d
                next_job = service.new_job(row, 'QUESTION')
                d['job_id'] = next_job.id
                d['timer_phase'] = 'ANALYZING'
            else:
                d['report_revision'] = d.get('report_revision', 0) + 1
        elif kind == 'TRANSCRIBE':
            if result['status'] == 'complete':
                revision = len([t for t in d['transcripts'] if t['turn_index'] == payload['turn_index']]) + 1
                d['transcripts'].append({'turn_index': payload['turn_index'], 'revision': revision,
                    'text': result['text'], 'segments': result['segments'], 'origin': 'ASR',
                    'capture_refs': payload['capture_refs'], 'confirmed': False, 'created_at': time.time()})
                d['transcript_status'] = 'awaiting_confirmation'
                if d['settings']['feedback_mode'] == 'SIMULATION':
                    index = len(d['answers'])
                    d['answers'].append({'text': result['text'], 'question': d.get('turn_questions', {}).get(str(payload['turn_index']), d.get('question') or ''),
                        'turn_index': payload['turn_index'], 'transcript_revision': revision, 'transcript_provisional': True,
                        'client_submission_id': f"asr:{payload['turn_index']}:{revision}", 'content_status': 'pending_analysis'})
                    row.data = d
                    content_job = service.new_job(row, 'CONTENT', {'answer_index': index, 'text_hash': hashlib.sha256(result['text'].encode()).hexdigest()})
                    d['job_id'] = content_job.id
                    d['timer_phase'] = 'ANALYZING'
            else:
                d['transcript_status'] = result.get('reason_code', 'unavailable')
            if not (result['status'] == 'complete' and d['settings']['feedback_mode'] == 'SIMULATION'):
                d['timer_phase'] = 'TRANSCRIPT_REVIEW'
        elif kind == 'ACOUSTIC':
            confirmed = [t for t in d.get('transcripts', [])
                if t['turn_index'] == payload['turn_index'] and t.get('confirmed') and not t.get('invalidated')]
            latest = max(confirmed, key=lambda t: t['revision'], default=None)
            if (latest is None or latest['revision'] != payload['transcript_revision']
                    or latest['text'] != payload['reference_text']):
                job.status = 'INVALIDATED'
                job.data = {**payload, 'reason': '새 확정 전사로 대체된 음향 분석입니다.'}
                db.commit()
                return
            result['transcript_revision'] = payload['transcript_revision']
            result['turn_index'] = payload['turn_index']
            d.setdefault('audio_analyses', {})[str(payload['turn_index'])] = result
            d['report_revision'] = d.get('report_revision', 0) + 1
        elif kind == 'FINALIZE':
            other_jobs = list(db.scalars(select(StudioJob).where(StudioJob.session_id == session_id, StudioJob.id != ident, StudioJob.status.in_(['PENDING', 'RUNNING']))))
            open_captures = list(db.scalars(select(StudioCapture).where(StudioCapture.session_id == session_id, StudioCapture.sealed.is_(False))))
            now = time.time()
            if (other_jobs or open_captures) and now < d['finalize_deadline']:
                job.status = 'PENDING'
                db.commit()
                return
            row.status = 'COMPLETED'
            d['report_revision'] = d.get('report_revision', 0) + 1
            d['finalized_at'] = now
            d['report_status'] = 'partial'
        row.data = d
        job.status = 'COMPLETED' if result.get('status', 'complete') != 'unavailable' else 'UNAVAILABLE'
        job.data = {**payload, 'completed_at': time.time()}
        db.commit()
        if row.status == 'COMPLETED':
            service.report(session_id)
    except Exception:
        db.rollback()
        db.scalar(select(StudioSession).where(StudioSession.id == session_id).with_for_update())
        job = db.scalar(select(StudioJob).where(StudioJob.id == ident).with_for_update())
        if job and job.status == 'RUNNING':
            job.status = 'FAILED'
            job.data = {**payload, 'reason': '분석 작업을 완료하지 못했습니다.'}
            db.commit()
        else:
            db.rollback()


def drain(session_id):
    from app.core.database import SessionLocal
    with SessionLocal() as db:
        # Bounded passes handle CONTENT->QUESTION without an unbounded worker loop.
        for _ in range(3):
            ids = list(db.scalars(select(StudioJob.id).where(StudioJob.session_id == session_id, StudioJob.status == 'PENDING')))
            if not ids:
                break
            for ident in ids:
                run_job(db, ident)
            db.expire_all()
