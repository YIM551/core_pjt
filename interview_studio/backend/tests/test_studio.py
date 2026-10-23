from types import SimpleNamespace
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
import pytest
from fastapi import HTTPException
from app.core.database import Base
from app.core import entity_registry
from app.studio.models import StudioWorkspace, StudioSource, StudioSession, StudioJob, StudioCapture, StudioChunk
from app.studio.service import StudioService
from app.studio.controller import SessionInput, AnswerInput, SourceInput, CaptureInput, SealInput, TranscriptInput, FeatureInput
from app.studio.jobs import run_job

@pytest.fixture
def service(monkeypatch):
    from app.shared.clients.embedding import EmbeddingServiceError
    def unavailable(*a, **kw): raise EmbeddingServiceError('test')
    monkeypatch.setattr('app.studio.retrieval.embed_documents',unavailable)
    monkeypatch.setattr('app.studio.jobs.generate_question',lambda *a: ('경험과 기여를 설명해주세요.','FALLBACK'))
    monkeypatch.setattr('app.studio.jobs.generate_followup',lambda *a: ('그 행동의 결과를 구체적으로 설명해주세요.','FALLBACK_FOLLOWUP'))
    monkeypatch.setattr('app.studio.jobs.evaluate',lambda *a: {'status':'complete','strengths':['근거를 제시했습니다.'],'improvements':[],'feedback':'구체적 경험입니다.'})
    engine=create_engine('sqlite://')
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        s=StudioService(db,SimpleNamespace(id=1))
        w=StudioWorkspace(user_id=1,name='test',company_name='A',target_role='backend')
        db.add(w);db.commit()
        yield s,w

def drain(s):
    for _ in range(3):
        ids=list(s.db.scalars(select(StudioJob.id).where(StudioJob.status=='PENDING')))
        for ident in ids:run_job(s.db,ident)

def active(s,w,mode='TEXT'):
    result=s.create(SessionInput(workspace_id=w.id,input_mode=mode))
    s.control(result['id'],'start',0,'start-key');drain(s)
    return result['id']

def test_private_sources_and_snapshot(service):
    s,w=service
    source=s.source_create(w.id,SourceInput(category='RESUME',title='R',text='original'))
    result=s.create(SessionInput(workspace_id=w.id,source_ids=[source['id']]))
    revised=s.source_create(w.id,SourceInput(category='RESUME',title='R',text='changed'),source['id'])
    assert s.session(result['id']).data['sources'][0]['content_hash']==source['content_hash']
    assert revised['revision']==2
    s.user=SimpleNamespace(id=2)
    with pytest.raises(HTTPException) as exc:s.session(result['id'])
    assert exc.value.status_code==404

def test_answer_survives_analysis_failure_and_duplicate(service,monkeypatch):
    s,w=service;ident=active(s,w)
    monkeypatch.setattr('app.studio.jobs.evaluate',lambda *a:{'status':'unavailable'})
    answer=AnswerInput(text='my answer',client_submission_id='key')
    s.answer(ident,answer);s.answer(ident,answer)
    assert len(s.session(ident).data['answers'])==1
    with pytest.raises(HTTPException):s.answer(ident,AnswerInput(text='different',client_submission_id='key'))
    drain(s)
    assert s.session(ident).data['answers'][0]['text']=='my answer'
    assert s.session(ident).data['answers'][0]['assessment']['status']=='unavailable'

def test_controls_are_versioned_and_idempotent(service):
    s,w=service;ident=s.create(SessionInput(workspace_id=w.id))['id']
    first=s.control(ident,'start',0,'request')
    second=s.control(ident,'start',0,'request')
    assert first['control_version']==second['control_version']==1
    with pytest.raises(HTTPException):s.control(ident,'pause',0,'new')
    with pytest.raises(HTTPException):s.control(ident,'pause',1,'request')

def test_analysis_time_excluded_and_pause_ledger(service,monkeypatch):
    s,w=service;clock=[100.0]
    monkeypatch.setattr('app.studio.service.time.time',lambda:clock[0])
    ident=active(s,w)
    clock[0]=110
    s.answer(ident,AnswerInput(text='answer',client_submission_id='1'))
    clock[0]=200
    assert s.remaining(s.session(ident))==1190
    drain(s)
    clock[0]=205
    s.control(ident,'pause')
    clock[0]=500
    assert s.remaining(s.session(ident))==1185
    assert len(s.session(ident).data['timer_segments'])==2

def test_source_delete_redacts_and_invalidates_jobs(service):
    s,w=service
    source=s.source_create(w.id,SourceInput(category='RESUME',title='R',text='private evidence'))
    ident=s.create(SessionInput(workspace_id=w.id,source_ids=[source['id']]))['id']
    s.control(ident,'start')
    s.source_delete(w.id,source['id'])
    assert s.session(ident).data['sources']==[]
    assert all(j.status=='INVALIDATED' for j in s.db.scalars(select(StudioJob)) if j.data.get('reason')=='source_deleted')
    assert s.db.scalar(select(StudioJob).where(StudioJob.status=='PENDING')).data['source_epoch']==1
    assert s.db.get(StudioSource,source['id']).text==''

def test_capture_bounds_missing_idempotency_and_purge(service):
    s,w=service;ident=active(s,w,'AUDIO_VIDEO')
    c=s.capture_create(ident,CaptureInput())
    s.chunk_put(c['id'],'audio',0,b'first',c['generation'],0,1000,'audio/webm')
    s.chunk_put(c['id'],'audio',0,b'first',c['generation'],0,1000,'audio/webm')
    with pytest.raises(HTTPException):s.chunk_put(c['id'],'audio',0,b'other',c['generation'],0,1000,'audio/webm')
    with pytest.raises(HTTPException):s.capture_seal(c['id'],SealInput(last_seq={'audio':1}))
    s.capture_seal(c['id'],SealInput(last_seq={'audio':0}))
    with pytest.raises(HTTPException):s.capture_create(ident,CaptureInput())
    s.session_delete(ident)
    assert not list(s.db.scalars(select(StudioChunk)))

def test_capture_generation_and_overlap(service):
    s,w=service;ident=active(s,w,'AUDIO_VIDEO');c=s.capture_create(ident,CaptureInput())
    with pytest.raises(HTTPException):s.chunk_put(c['id'],'audio',0,b'a',99,0,1000,'audio/webm')
    s.chunk_put(c['id'],'audio',0,b'a',c['generation'],0,1000,'audio/webm')
    with pytest.raises(HTTPException):s.chunk_put(c['id'],'audio',1,b'b',c['generation'],500,1500,'audio/webm')

def test_finalization_preserves_last_chunk_grace(service,monkeypatch):
    s,w=service;clock=[100.0];monkeypatch.setattr('app.studio.service.time.time',lambda:clock[0])
    ident=active(s,w,'AUDIO_VIDEO');c=s.capture_create(ident,CaptureInput())
    clock[0]=103;s.control(ident,'finish')
    clock[0]=105;s.chunk_put(c['id'],'audio',0,b'last',c['generation'],0,2000,'audio/webm')
    clock[0]=120
    with pytest.raises(HTTPException):s.chunk_put(c['id'],'audio',1,b'late',c['generation'],2000,3000,'audio/webm')
    assert s.session(ident).status=='FINALIZING'

def test_expired_media_cleaned(service,monkeypatch):
    s,w=service;ident=active(s,w,'AUDIO_VIDEO');c=s.capture_create(ident,CaptureInput())
    s.chunk_put(c['id'],'audio',0,b'private',c['generation'],0,1000,'audio/webm')
    monkeypatch.setattr('app.studio.service.time.time',lambda:c['expires_at']+1)
    s.cleanup_media()
    assert not list(s.db.scalars(select(StudioChunk)))

def test_transcript_confirmation_after_finish_does_not_restart_clock(service):
    s,w=service;ident=active(s,w,'AUDIO_VIDEO');c=s.capture_create(ident,CaptureInput())
    s.chunk_put(c['id'],'audio',0,b'not real media',c['generation'],0,1000,'audio/webm')
    s.capture_seal(c['id'],SealInput(last_seq={'audio':0}))
    s.control(ident,'finish')
    s.transcript_create(ident,TranscriptInput(turn_index=0,text='corrected transcript'))
    s.transcript_confirm(ident,0,1)
    drain(s)
    row=s.session(ident)
    assert row.status in ('FINALIZING','COMPLETED')
    assert 'active_since' not in row.data
    assert row.data['answers'][0]['assessment']['status']=='complete'

def test_content_retry_uses_original_turn_evidence(service, monkeypatch):
    s,w=service;ident=active(s,w)
    row=s.session(ident)
    data=dict(row.data)
    data['answers']=[{'text':'original answer','question':'original question','turn_index':0,'client_submission_id':'x'}]
    data['turn_evidence']={'0':[{'text':'original evidence'}]}
    data['question_evidence']=[{'text':'new unrelated evidence'}]
    row.status='COMPLETED';row.data=data
    import hashlib
    job=s.new_job(row,'CONTENT',{'answer_index':0,'text_hash':hashlib.sha256(b'original answer').hexdigest()})
    s.db.commit()
    contexts=[]
    def evaluate(question,text,context):
        contexts.append(context)
        return {'status':'complete','strengths':[],'improvements':[]}
    monkeypatch.setattr('app.studio.jobs.evaluate',evaluate)
    run_job(s.db,job.id)
    assert contexts==['original evidence']


def test_final_seal_rejects_unsealed_earlier_segment(service):
    s,w=service;ident=active(s,w,'AUDIO_VIDEO')
    first=s.capture_create(ident,CaptureInput())
    s.chunk_put(first['id'],'audio',0,b'one',first['generation'],0,1000,'audio/webm')
    s.control(ident,'pause');s.control(ident,'resume')
    second=s.capture_create(ident,CaptureInput(turn_offset_ms=1000))
    s.chunk_put(second['id'],'audio',0,b'two',second['generation'],0,1000,'audio/webm')
    with pytest.raises(HTTPException) as exc:
        s.capture_seal(second['id'],SealInput(last_seq={'audio':0}))
    assert exc.value.status_code==409
    assert not list(s.db.scalars(select(StudioJob).where(StudioJob.kind=='TRANSCRIBE')))
    s.capture_seal(first['id'],SealInput(last_seq={'audio':0},is_final_for_turn=False))
    s.capture_seal(second['id'],SealInput(last_seq={'audio':0}))
    assert s.session(ident).data['turn_capture_refs']['0']==[first['id'],second['id']]


@pytest.mark.parametrize('state',['COMPLETED','EXPIRED_DEADLINE','EXPIRED_MEDIA'])
def test_late_seal_creates_no_analysis_job(service,state):
    s,w=service;ident=active(s,w,'AUDIO_VIDEO')
    c=s.capture_create(ident,CaptureInput())
    s.chunk_put(c['id'],'audio',0,b'media',c['generation'],0,1000,'audio/webm')
    row=s.session(ident)
    if state=='COMPLETED':row.status='COMPLETED'
    elif state=='EXPIRED_DEADLINE':
        row.status='FINALIZING';row.data={**row.data,'finalize_deadline':0}
    else:
        capture=s.db.get(StudioCapture,c['id']);capture.data={**capture.data,'expires_at':0}
    s.db.commit()
    with pytest.raises(HTTPException):s.capture_seal(c['id'],SealInput(last_seq={'audio':0}))
    assert not list(s.db.scalars(select(StudioJob).where(StudioJob.kind=='TRANSCRIBE')))


def test_skipped_job_releases_transaction(service):
    s,w=service;ident=active(s,w)
    job=s.db.scalar(select(StudioJob).where(StudioJob.session_id==ident))
    assert job.status=='COMPLETED'
    run_job(s.db,job.id)
    assert not s.db.in_transaction()


def test_source_delete_replaces_finalization_job(service):
    s,w=service
    source=s.source_create(w.id,SourceInput(category='RESUME',title='R',text='evidence'))
    ident=s.create(SessionInput(workspace_id=w.id,source_ids=[source['id']]))['id']
    s.control(ident,'finish')
    s.source_delete(w.id,source['id'])
    pending=list(s.db.scalars(select(StudioJob).where(StudioJob.status=='PENDING')))
    assert len(pending)==1 and pending[0].kind=='FINALIZE'
    assert pending[0].data['source_epoch']==1
    drain(s)
    assert s.session(ident).status=='COMPLETED'


def test_pause_resume_transcript_review_excludes_time(service,monkeypatch):
    s,w=service;clock=[100.0]
    monkeypatch.setattr('app.studio.service.time.time',lambda:clock[0])
    monkeypatch.setattr('app.studio.jobs.transcribe',lambda *a:{'status':'unavailable','reason_code':'no_speech'})
    ident=active(s,w,'AUDIO_VIDEO');c=s.capture_create(ident,CaptureInput())
    s.chunk_put(c['id'],'audio',0,b'voice',c['generation'],0,1000,'audio/webm')
    clock[0]=110;s.capture_seal(c['id'],SealInput(last_seq={'audio':0}));drain(s)
    s.control(ident,'pause');clock[0]=200;s.control(ident,'resume');clock[0]=300
    row=s.session(ident)
    assert row.data['timer_phase']=='TRANSCRIPT_REVIEW'
    assert 'active_since' not in row.data
    assert s.remaining(row)==1190


@pytest.mark.parametrize('mode,reason',[('TEXT','text_mode'),('AUDIO_VIDEO','no_audio')])
def test_report_reasons_follow_collected_modalities(service,mode,reason):
    s,w=service;ident=active(s,w,mode)
    report=s.report(ident)
    assert report['modalities']['pronunciation']['reason_code']==reason
    assert report['modalities']['gaze']['reason_code']==('text_mode' if mode=='TEXT' else 'no_visual_samples')


def test_report_audio_provider_reason(service):
    s,w=service;ident=active(s,w,'AUDIO_VIDEO');c=s.capture_create(ident,CaptureInput())
    s.chunk_put(c['id'],'audio',0,b'audio',c['generation'],0,1000,'audio/webm')
    assert s.report(ident)['modalities']['pronunciation']['reason_code']=='provider_unavailable'


def test_silent_stt_has_no_empty_transcript_and_can_rerecord(service,monkeypatch,tmp_path):
    import sys
    from app.studio import analysis
    monkeypatch.setattr(analysis,'get_settings',lambda:SimpleNamespace(studio_stt_model_path=tmp_path))
    class SilentModel:
        def __init__(self,*a,**kw):
            assert kw['local_files_only'] is True
        def transcribe(self,*a,**kw):
            return iter([]),SimpleNamespace()
    monkeypatch.setitem(sys.modules,'faster_whisper',SimpleNamespace(WhisperModel=SilentModel))
    result=analysis.transcribe(b'silent audio','audio/webm')
    assert result['reason_code']=='no_speech'
    assert 'text' not in result
    monkeypatch.setattr('app.studio.jobs.transcribe',lambda *a:result)
    s,w=service;ident=active(s,w,'AUDIO_VIDEO');c=s.capture_create(ident,CaptureInput())
    s.chunk_put(c['id'],'audio',0,b'silent',c['generation'],0,1000,'audio/webm')
    s.capture_seal(c['id'],SealInput(last_seq={'audio':0}));drain(s)
    assert s.session(ident).data['transcripts']==[]
    assert s.session(ident).data['transcript_status']=='no_speech'
    retry=s.retry_answer(ident)
    assert retry['turn_index']==1
    assert s.capture_create(ident,CaptureInput())['turn_index']==1


def test_paused_content_completes_and_advances_without_running_clock(service,monkeypatch):
    s,w=service;clock=[100.0]
    monkeypatch.setattr('app.studio.service.time.time',lambda:clock[0])
    ident=active(s,w)
    clock[0]=110
    s.answer(ident,AnswerInput(text='first answer',client_submission_id='first'))
    def pause_during_provider(*args):
        assert s.db.scalar(select(StudioJob).where(StudioJob.kind=='CONTENT')).status=='RUNNING'
        s.control(ident,'pause')
        return {'status':'complete','strengths':[],'improvements':[]}
    monkeypatch.setattr('app.studio.jobs.evaluate',pause_during_provider)
    clock[0]=200;drain(s)
    row=s.session(ident)
    assert row.status=='PAUSED'
    assert row.data['turn_index']==1
    assert row.data['paused_timer_phase']=='QUESTION'
    assert 'active_since' not in row.data
    assert s.remaining(row)==1190
    clock[0]=300;s.control(ident,'resume');clock[0]=305
    assert s.remaining(s.session(ident))==1185
    s.answer(ident,AnswerInput(text='second answer',client_submission_id='second'))
    assert s.session(ident).data['answers'][1]['turn_index']==1


@pytest.mark.parametrize('paused',[False,True])
def test_source_deletion_after_audio_seal_uses_fresh_turn(service,monkeypatch,paused):
    s,w=service
    monkeypatch.setattr('app.studio.jobs.transcribe',lambda *a:{'status':'unavailable','reason_code':'no_speech'})
    source=s.source_create(w.id,SourceInput(category='RESUME',title='R',text='evidence'))
    ident=s.create(SessionInput(workspace_id=w.id,source_ids=[source['id']],input_mode='AUDIO_VIDEO'))['id']
    s.control(ident,'start');drain(s)
    c=s.capture_create(ident,CaptureInput())
    s.chunk_put(c['id'],'audio',0,b'voice',c['generation'],0,1000,'audio/webm')
    s.capture_seal(c['id'],SealInput(last_seq={'audio':0}))
    if paused:s.control(ident,'pause')
    s.source_delete(w.id,source['id']);drain(s)
    row=s.session(ident)
    assert row.data['turn_index']==1
    assert row.data['question']
    assert row.data['turn_capture_refs']['0']==[c['id']]
    assert s.db.get(StudioCapture,c['id']).sealed
    if paused:
        assert 'active_since' not in row.data
        assert row.data['paused_timer_phase']=='QUESTION'
        s.control(ident,'resume')
    new=s.capture_create(ident,CaptureInput())
    assert new['turn_index']==1


def test_source_delete_discards_open_capture_and_blocks_old_transcripts(service):
    s,w=service
    source=s.source_create(w.id,SourceInput(category='RESUME',title='R',text='evidence'))
    ident=s.create(SessionInput(workspace_id=w.id,source_ids=[source['id']],input_mode='AUDIO_VIDEO'))['id']
    s.control(ident,'start');drain(s)
    first=s.capture_create(ident,CaptureInput())
    s.chunk_put(first['id'],'audio',0,b'old voice',first['generation'],0,1000,'audio/webm')
    s.source_delete(w.id,source['id']);drain(s)
    assert s.db.get(StudioCapture,first['id']).data['discarded']
    assert not list(s.db.scalars(select(StudioChunk).where(StudioChunk.capture_id==first['id'])))
    with pytest.raises(HTTPException):s.capture_detail(first['id'])
    assert s.capture_create(ident,CaptureInput())['turn_index']==1
    with pytest.raises(HTTPException):s.transcript_create(ident,TranscriptInput(turn_index=0,text='discarded text'))
    with pytest.raises(HTTPException):s.transcript_confirm(ident,0,1)
    assert not list(s.db.scalars(select(StudioJob).where(StudioJob.kind=='CONTENT')))


def test_deleted_sealed_turn_rejects_old_revision_and_confirmation(service):
    s,w=service
    source=s.source_create(w.id,SourceInput(category='RESUME',title='R',text='evidence'))
    ident=s.create(SessionInput(workspace_id=w.id,source_ids=[source['id']],input_mode='AUDIO_VIDEO'))['id']
    s.control(ident,'start');drain(s)
    capture=s.capture_create(ident,CaptureInput())
    s.chunk_put(capture['id'],'audio',0,b'voice',capture['generation'],0,1000,'audio/webm')
    s.capture_seal(capture['id'],SealInput(last_seq={'audio':0}))
    s.transcript_create(ident,TranscriptInput(turn_index=0,text='old transcript'))
    s.source_delete(w.id,source['id']);drain(s)
    with pytest.raises(HTTPException):s.transcript_confirm(ident,0,1)
    with pytest.raises(HTTPException):s.transcript_create(ident,TranscriptInput(turn_index=0,text='another old transcript'))
    assert s.session(ident).data['transcripts'][0]['invalidated']
    assert s.session(ident).data['answers']==[]


def test_queued_releases_request_transaction_before_background(service):
    from app.studio.controller import queued
    from fastapi import BackgroundTasks
    s,w=service;ident=active(s,w)
    result=s.detail(s.session(ident))
    assert s.db.in_transaction()
    background=BackgroundTasks()
    assert queued(background,ident,result,s)==result
    assert not s.db.in_transaction()


def test_worker_expires_offline_session_and_finish_is_idempotent(service,monkeypatch):
    from contextlib import contextmanager
    from app.studio import worker
    s,w=service;clock=[100.0]
    monkeypatch.setattr('app.studio.service.time.time',lambda:clock[0])
    ident=active(s,w)
    @contextmanager
    def local():yield s.db
    monkeypatch.setattr(worker,'SessionLocal',local)
    clock[0]=1400
    worker.tick()
    row=s.session(ident)
    assert row.status=='COMPLETED'
    assert row.data['end_reason']=='time_limit'
    assert row.data['elapsed']==1200
    count=len(list(s.db.scalars(select(StudioJob).where(StudioJob.kind=='FINALIZE'))))
    s.control(ident,'finish')
    assert len(list(s.db.scalars(select(StudioJob).where(StudioJob.kind=='FINALIZE'))))==count==1

def test_completed_report_archive_is_immutable_and_scoped(service):
    s,w=service;ident=active(s,w)
    row=s.session(ident);row.status='COMPLETED';s.db.commit()
    first=s.report(ident)
    row=s.session(ident);d=dict(row.data);d['answers']=[{'text':'later','turn_index':0,'assessment':{'status':'complete','strengths':['changed']}}];row.data=d;s.db.commit()
    assert s.report(ident)==first
    assert s.report_revision(ident,0)==first
    s.user=SimpleNamespace(id=2)
    with pytest.raises(HTTPException):s.report_revision(ident,0)


def test_media_replay_sealed_order_expiry_and_owner(service,monkeypatch):
    s,w=service;ident=active(s,w,'AUDIO_VIDEO');c=s.capture_create(ident,CaptureInput())
    s.chunk_put(c['id'],'audio',0,b'head',c['generation'],0,1000,'audio/webm')
    with pytest.raises(HTTPException):s.media(c['id'],'audio')
    s.capture_seal(c['id'],SealInput(last_seq={'audio':0}))
    assert s.media(c['id'],'audio')==(b'head','audio/webm')
    s.user=SimpleNamespace(id=2)
    with pytest.raises(HTTPException):s.media(c['id'],'audio')
    s.user=SimpleNamespace(id=1)
    monkeypatch.setattr('app.studio.service.time.time',lambda:c['expires_at']+1)
    with pytest.raises(HTTPException):s.media(c['id'],'audio')


def test_enrollment_hidden_expired_and_deleted(service,monkeypatch,tmp_path):
    from app.core.config import get_settings
    import numpy as np
    s,w=service;ident=s.create(SessionInput(workspace_id=w.id,input_mode='AUDIO'))['id']
    monkeypatch.setattr(get_settings(),'upload_dir',tmp_path)
    monkeypatch.setattr('app.studio.local_audio.decode_audio',lambda content:np.ones(16000*6,dtype='float32')*.1)
    result=s.speaker_enrollment(ident,b'private speaker audio',True)
    assert result['status']=='enrolled'
    row=s.session(ident)
    assert '_speaker_enrollment_path' not in s.detail(row)
    stored=row.data['_speaker_enrollment_path']
    from pathlib import Path
    assert Path(stored).is_file()
    monkeypatch.setattr('app.studio.service.time.time',lambda:result['expires_at']+1)
    s.cleanup_media()
    assert not Path(stored).exists()
    assert s.session(ident).data['speaker_enrollment']['status']=='expired'

def test_followup_one_per_main_and_based_on_previous_answer(service,monkeypatch):
    s,w=service;ident=active(s,w)
    observed=[]
    def followup(question,text,settings):
        observed.append(text);return '구체적인 결과를 설명해주세요.','LLM_FOLLOWUP'
    monkeypatch.setattr('app.studio.jobs.generate_followup',followup)
    s.answer(ident,AnswerInput(text='특별한 실제 경험',client_submission_id='a'));drain(s)
    assert observed==['특별한 실제 경험']
    assert s.session(ident).data['followup_parents']=={'1':0}
    s.answer(ident,AnswerInput(text='결과 설명',client_submission_id='b'));drain(s)
    assert len(observed)==1
    assert s.session(ident).data['turn_index']==2


def test_audio_rate_excludes_uncertain_words_and_time(service):
    s,w=service;ident=active(s,w,'AUDIO');row=s.session(ident)
    d=dict(row.data);d['transcripts']=[{'origin':'ASR','turn_index':0,'segments':[{
      'status':'complete','speaker_analysis':{'status':'complete','intervals':[{'start':4,'end':8,'status':'excluded_uncertain'}]},
      'segments':[{'start':0,'end':4,'text':'지원자 답변 네 어절'}, {'start':4,'end':8,'text':'배경 화자 말'}, {'start':8,'end':12,'text':'본인 추가 답변 입니다'}]}]}]
    row.data=d;s.db.commit();report=s.report(ident)
    rate=report['modalities']['speech_rate']
    assert rate['eojeol_count']==8
    assert rate['measured_seconds']==8
    assert rate['excluded_seconds']==4
    assert rate['eojeol_per_minute']==60

def test_dropped_cross_boundary_segment_removes_entire_duration(service):
    s,w=service;ident=active(s,w,'AUDIO');row=s.session(ident)
    d=dict(row.data);d['transcripts']=[{'origin':'ASR','turn_index':0,'segments':[{
      'status':'complete','speaker_analysis':{'status':'complete','intervals':[{'start':4,'end':8,'status':'excluded_uncertain'}]},
      'segments':[{'start':0,'end':3,'text':'지원자 답변'}, {'start':3,'end':9,'text':'제외 전체 문장'}, {'start':9,'end':12,'text':'추가 답변'}]}]}]
    row.data=d;s.db.commit();rate=s.report(ident)['modalities']['speech_rate']
    assert rate['eojeol_count']==4
    assert rate['measured_seconds']==6
    assert rate['excluded_seconds']==6
    assert rate['eojeol_per_minute']==40


def test_old_acoustic_job_cannot_replace_new_confirmed_revision(service):
    s,w=service;ident=active(s,w,'AUDIO');row=s.session(ident)
    d=dict(row.data);d['transcripts']=[{'turn_index':0,'revision':1,'text':'old','confirmed':True},
        {'turn_index':0,'revision':2,'text':'new','confirmed':True}]
    d['audio_analyses']={'0':{'transcript_revision':2,'status':'complete'}}
    row.data=d
    job=s.new_job(row,'ACOUSTIC',{'turn_index':0,'transcript_revision':1,'reference_text':'old','capture_refs':[]})
    s.db.commit();run_job(s.db,job.id)
    assert s.db.get(StudioJob,job.id).status=='INVALIDATED'
    assert s.session(ident).data['audio_analyses']['0']['transcript_revision']==2

def test_model_versions_are_expected_provisioning_targets_not_verified_identity(service):
    s,w=service;ident=active(s,w)
    versions=s.report(ident)['pipeline_versions']
    assert versions['loaded_model_identity_verified'] is False
    assert 'model_revisions' not in versions
    assert versions['expected_model_revisions']['ecapa']=='0f99f2d0ebe89ac095bcc5903c4dd8f72b367286'
