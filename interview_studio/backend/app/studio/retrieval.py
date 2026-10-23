"""Private studio ingestion and bounded retrieval; never queries COMPANY data."""
import math
import re
from sqlalchemy import select
from app.core.config import get_settings
from app.studio.analysis import local_url
from app.shared.clients.embedding import embed_documents, embedding, EmbeddingServiceError
from app.studio.models import StudioSourceChunk, StudioSource


def ingest(db, source):
    pieces = [source.text[i:i + 1000] for i in range(0, len(source.text), 850)][:120]
    vectors = None
    mode = 'LEXICAL'
    try:
        if not local_url(get_settings().embedding_base_url): raise EmbeddingServiceError('local only')
        vectors = embed_documents(pieces)
        mode = 'VECTOR'
    except EmbeddingServiceError:
        pass
    source_id=source.id
    db.expire_all()
    source=db.scalar(select(StudioSource).where(StudioSource.id==source_id).with_for_update())
    if not source or source.deleted_at:
        db.rollback()
        return
    for i, text in enumerate(pieces):
        db.add(StudioSourceChunk(source_id=source.id,ordinal=i,text=text,embedding=vectors[i] if vectors else None,embedding_model=get_settings().embedding_model if vectors else None))
    source.processing = {'status':'READY','retrieval_mode':mode,'embedding_dimension':4096,'chunk_count':len(pieces)}
    db.commit()


def retrieve(db, source_ids, query):
    # source_ids originate ONLY from an owner-validated session snapshot.
    rows=list(db.scalars(select(StudioSourceChunk).where(StudioSourceChunk.source_id.in_(source_ids),StudioSourceChunk.deleted_at.is_(None)))) if source_ids else []
    vector = None
    if any(r.embedding is not None for r in rows):
        try:
            if not local_url(get_settings().embedding_base_url): raise EmbeddingServiceError('local only')
            vector=embedding(query)
        except EmbeddingServiceError: pass
    terms=set(re.findall(r'[\w가-힣]{2,}',query.lower()))
    ranked=[]
    for row in rows:
        if vector is not None and row.embedding is not None and row.embedding_model==get_settings().embedding_model:
            score=sum(a*b for a,b in zip(vector,row.embedding))
            mode='VECTOR'
        else:
            score=sum(1 for t in terms if t in row.text.lower()) / max(1,len(terms))
            mode='LEXICAL'
        ranked.append((score,row,mode))
    ranked.sort(key=lambda item:item[0],reverse=True)
    per_source={};result=[]
    for score,row,mode in ranked:
        if per_source.get(row.source_id,0)>=2:continue
        result.append({'source_id':row.source_id,'chunk_id':row.id,'text':row.text,'mode':mode})
        per_source[row.source_id]=per_source.get(row.source_id,0)+1
        if len(result)==6:break
    return result
