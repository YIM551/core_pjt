"""Real PostgreSQL/HTTP regression, opt in with STUDIO_TEST_POSTGRES=1.
Uses migrated local database, creates and removes its own user and records.
"""
import os
from types import SimpleNamespace
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, delete
from sqlalchemy.orm import sessionmaker

pytestmark=pytest.mark.skipif(os.environ.get('STUDIO_TEST_POSTGRES')!='1',reason='requires migrated local PostgreSQL')


def test_http_background_jobs_release_postgres_request_locks(monkeypatch):
    from app.main import app
    from app.core.config import get_settings
    from app.core.database import get_db
    from app.core.dependencies import current_user
    from app.core import database
    from app.auth.entities.models import User
    from app.studio.models import StudioWorkspace,StudioSession,StudioJob
    from app.studio.service import StudioService
    engine=create_engine(get_settings().database_url,connect_args={'options':'-c lock_timeout=2000 -c statement_timeout=5000'})
    factory=sessionmaker(bind=engine,autoflush=False)
    monkeypatch.setattr(database,'SessionLocal',factory)
    monkeypatch.setattr('app.studio.jobs.generate_question',lambda *args:('경험을 설명해주세요.','FALLBACK'))
    monkeypatch.setattr('app.studio.jobs.transcribe',lambda *args:{'status':'complete','text':'합성 음성 답변입니다.','segments':[]})
    with factory() as db:
        user=User(email=f'studio-lock-{uuid4()}@test.invalid',name='integration test')
        db.add(user);db.commit();user_id=user.id
    def override_db():
        with factory() as db:yield db
    previous=dict(app.dependency_overrides)
    app.dependency_overrides[get_db]=override_db
    app.dependency_overrides[current_user]=lambda:SimpleNamespace(id=user_id)
    try:
        with TestClient(app) as client:
            workspace=client.post('/api/v2/studio/workspaces',json={'name':'lock test'}).json()
            session=client.post('/api/v2/studio/sessions',json={'workspace_id':workspace['id'],'input_mode':'AUDIO_VIDEO'}).json()
            ident=session['id'];prefix=f'/api/v2/studio/sessions/{ident}'
            response=client.post(prefix+'/start',json={'expected_control_version':0},headers={'Idempotency-Key':str(uuid4())})
            assert response.status_code==200,response.text
            # Force a pending job before GET, the exact previous self-deadlock trigger.
            with factory() as db:
                service=StudioService(db,SimpleNamespace(id=user_id));row=service.session(ident)
                data=dict(row.data);data['question']=None;data.pop('active_since',None);data['timer_phase']='ANALYZING';row.data=data
                service.new_job(row,'QUESTION');db.commit()
            assert client.get(prefix).status_code==200
            assert client.get(prefix).json()['question']=='경험을 설명해주세요.'
            with factory() as db:
                service=StudioService(db,SimpleNamespace(id=user_id));row=service.session(ident)
                service.new_job(row,'QUESTION');db.commit()
            assert client.get(prefix+'/report').status_code==200
            capture=client.post(prefix+'/captures',json={}).json()
            headers={'Content-Type':'audio/webm','X-Capture-Generation':str(capture['generation']),
                     'X-Media-Start-Ms':'0','X-Media-End-Ms':'1000'}
            response=client.put(f"/api/v2/studio/captures/{capture['id']}/chunks/audio/0",content=b'synthetic transport bytes',headers=headers)
            assert response.status_code==200,response.text
            response=client.post(f"/api/v2/studio/captures/{capture['id']}/seal",json={'last_seq':{'audio':0}})
            assert response.status_code==202,response.text
            transcripts=client.get(prefix+'/transcripts').json()
            assert transcripts[0]['text']=='합성 음성 답변입니다.'
            with factory() as db:
                assert all(j.status=='COMPLETED' for j in db.scalars(select(StudioJob).where(StudioJob.session_id==ident)))
    finally:
        app.dependency_overrides.clear();app.dependency_overrides.update(previous)
        with factory() as db:
            service=StudioService(db,SimpleNamespace(id=user_id))
            ids=list(db.scalars(select(StudioSession.id).where(StudioSession.user_id==user_id)))
            for ident in ids:service.session_delete(ident)
            db.execute(delete(StudioWorkspace).where(StudioWorkspace.user_id==user_id))
            db.execute(delete(User).where(User.id==user_id));db.commit()
        engine.dispose()
