from pathlib import Path
import sys


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import SessionLocal  # noqa: E402
from app.company_corpus.services.service import replace_samsung_corpus  # noqa: E402


CORPUS_ROOT = BACKEND_ROOT / "data" / "samsung"


def main() -> None:
    db = SessionLocal()
    try:
        document_count, chunk_count = replace_samsung_corpus(db, CORPUS_ROOT)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    print(
        f"Indexed Samsung interview corpus: "
        f"{document_count} documents, {chunk_count} chunks"
    )


if __name__ == "__main__":
    main()
