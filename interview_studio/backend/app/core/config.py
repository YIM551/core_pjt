from functools import lru_cache
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_upload_dir() -> Path:
    """Keep uploads stable when the server is started from a different cwd."""
    backend_root = Path(__file__).resolve().parents[2]
    project_root = backend_root.parent if backend_root.name == "backend" else backend_root
    return project_root / "uploads"


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://careerfit:careerfit@localhost:5432/careerfit"
    studio_stt_model_path: Path | None = Path(__file__).resolve().parents[2] / 'models' / 'faster-whisper-small'
    studio_stt_timeout_seconds: float = 60.0
    studio_pronunciation_model_path: Path | None = Path(__file__).resolve().parents[2] / 'models' / 'korean-ctc'
    studio_speaker_model_path: Path | None = Path(__file__).resolve().parents[2] / 'models' / 'ecapa'
    studio_separation_model_path: Path | None = Path(__file__).resolve().parents[2] / 'models' / 'sepformer'
    studio_max_media_mb: int = Field(default=200, ge=1, le=1000)
    studio_media_retention_hours: int = Field(default=24, ge=1, le=720)
    session_secret: str = "local-development-secret"
    llm_base_url: str = "http://localhost:8080/v1"
    llm_api_key: str = "local-key"
    llm_model: str = "qwen-model"
    llm_timeout_seconds: float = 60.0
    embedding_base_url: str = "http://localhost:8081/v1"
    embedding_api_key: str = "local-key"
    embedding_model: str = "Qwen3-Embedding-8B"
    embedding_dimension: int = 4096
    embedding_timeout_seconds: float = 30.0
    embedding_batch_size: int = 2
    personal_chat_max_cosine_distance: float = Field(default=0.45, ge=0.0, le=2.0)
    personal_retrieval_max_cosine_distance: float = Field(default=0.65, ge=0.0, le=2.0)
    company_retrieval_max_cosine_distance: float = Field(default=0.45, ge=0.0, le=2.0)
    retrieval_top_k: int = Field(default=6, ge=1, le=6)
    retrieval_per_document_limit: int = Field(default=6, ge=1, le=6)
    retrieval_context_char_budget: int = Field(default=6000, ge=200, le=12000)
    retrieval_request_max_tool_calls: int = Field(default=3, ge=1, le=8)
    retrieval_request_max_chunks: int = Field(default=8, ge=1, le=24)
    retrieval_request_char_budget: int = Field(default=6000, ge=200, le=16000)
    tool_call_max_rounds: int = Field(default=3, ge=1, le=3)
    cors_allowed_origin_regex: str = r"^http://(?:192\.168\.28\.33|localhost)(?::[0-9]{1,5})?$"
    upload_dir: Path = _default_upload_dir()
    max_upload_mb: int = 10
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
