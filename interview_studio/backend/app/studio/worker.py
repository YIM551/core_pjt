"""Local durable job and retention worker: python -m app.studio.worker --watch."""
import argparse
import time
from copy import deepcopy
from types import SimpleNamespace
from sqlalchemy import select
from app.core.database import SessionLocal
from app.studio.models import StudioJob, StudioSession
from app.studio.jobs import run_job
from app.studio.service import StudioService


def tick():
    with SessionLocal() as db:
        StudioService(db, SimpleNamespace(id=0)).cleanup_media()
        # Enforce the server clock even when the browser is closed or offline.
        active = list(db.execute(select(StudioSession.id, StudioSession.user_id).where(StudioSession.status == 'ACTIVE')))
        db.rollback()
        for session_id, user_id in active:
            service = StudioService(db, SimpleNamespace(id=user_id))
            row = db.scalar(select(StudioSession).where(StudioSession.id == session_id).with_for_update())
            if row and row.status == 'ACTIVE':
                service.session(session_id)
            db.commit()
        # Recover jobs interrupted by process termination; never duplicate an in-flight job.
        running = list(db.execute(select(StudioJob.id, StudioJob.session_id).where(StudioJob.status == 'RUNNING')))
        db.rollback()
        for job_id, session_id in running:
            db.scalar(select(StudioSession).where(StudioSession.id == session_id).with_for_update())
            job = db.scalar(select(StudioJob).where(StudioJob.id == job_id).with_for_update())
            if job and job.status == 'RUNNING' and time.time() - job.data.get('started_at', time.time()) > 600:
                job.status = 'FAILED'
                job.data = {**deepcopy(job.data), 'reason': '이전 작업 프로세스가 중단되었습니다. 재시도할 수 있습니다.'}
            db.commit()
        ids = list(db.scalars(select(StudioJob.id).where(StudioJob.status == 'PENDING').order_by(StudioJob.id).limit(100)))
        for ident in ids:
            run_job(db, ident)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--watch', action='store_true')
    args = parser.parse_args()
    while True:
        tick()
        if not args.watch:
            break
        time.sleep(2)

if __name__ == '__main__':
    main()
