from pathlib import Path
import sys

from sqlalchemy import select


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import SessionLocal  # noqa: E402
from app.core.entity_registry import Document, DocumentChunk  # noqa: E402
from app.shared.clients.embedding import embed_documents, embedding_metadata  # noqa: E402


def reindex_active_personal_chunks(db) -> int:
    chunks = db.scalars(
        select(DocumentChunk)
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(
            DocumentChunk.scope == "PERSONAL",
            Document.scope == "PERSONAL",
            DocumentChunk.deleted_at.is_(None),
            Document.deleted_at.is_(None),
            Document.processing_status == "COMPLETED",
        )
        .order_by(DocumentChunk.id)
    ).all()
    if not chunks:
        return 0

    # Make a model transition fail closed: after this commit, a failed remote
    # call cannot leave vectors from a previous embedding space searchable.
    for chunk in chunks:
        chunk.embedding = None
        chunk.metadata_json = {
            key: value
            for key, value in (chunk.metadata_json or {}).items()
            if key not in {
                "embedding_model",
                "embedding_dimension",
                "embedding_profile",
            }
        }
    db.commit()

    vectors = embed_documents([chunk.content for chunk in chunks])
    provenance = embedding_metadata("document")
    for chunk, vector in zip(chunks, vectors, strict=True):
        chunk.embedding = vector
        chunk.metadata_json = {**(chunk.metadata_json or {}), **provenance}
    db.commit()
    return len(chunks)


def main() -> None:
    db = SessionLocal()
    try:
        count = reindex_active_personal_chunks(db)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    print(f"Reindexed active PERSONAL chunks: {count}")


if __name__ == "__main__":
    main()
