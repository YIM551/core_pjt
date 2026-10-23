import math

import httpx

from app.core.config import get_settings

QUERY_INSTRUCTION = "Given a Korean career interview query, retrieve relevant candidate and Samsung Electronics evidence."


class EmbeddingServiceError(RuntimeError):
    pass


def _normalize_vector(value: object, expected_dimension: int) -> list[float]:
    if not isinstance(value, list) or len(value) != expected_dimension:
        raise EmbeddingServiceError("Embedding dimension mismatch.")
    try:
        vector = [float(item) for item in value]
    except (TypeError, ValueError) as exc:
        raise EmbeddingServiceError("Embedding contains a non-numeric value.") from exc
    if not all(math.isfinite(item) for item in vector):
        raise EmbeddingServiceError("Embedding contains a non-finite value.")
    norm = math.sqrt(sum(item * item for item in vector))
    if norm <= 0 or not math.isfinite(norm):
        raise EmbeddingServiceError("Embedding vector must be non-zero.")
    return [item / norm for item in vector]


def embed_documents(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    settings = get_settings()
    vectors: list[list[float]] = []
    headers = {"Authorization": f"Bearer {settings.embedding_api_key}"}
    try:
        with httpx.Client(timeout=settings.embedding_timeout_seconds) as client:
            batch_size = max(1, settings.embedding_batch_size)
            for start in range(0, len(texts), batch_size):
                batch = texts[start:start + batch_size]
                response = client.post(f"{settings.embedding_base_url.rstrip('/')}/embeddings", headers=headers, json={"model": settings.embedding_model, "input": batch})
                response.raise_for_status()
                data = response.json().get("data")
                if not isinstance(data, list) or len(data) != len(batch):
                    raise EmbeddingServiceError("Embedding response count mismatch.")
                ordered = sorted(data, key=lambda item: item["index"])
                vectors.extend(_normalize_vector(item.get("embedding"), settings.embedding_dimension) for item in ordered)
    except EmbeddingServiceError:
        raise
    except (httpx.HTTPError, ValueError, TypeError, KeyError) as exc:
        raise EmbeddingServiceError("Embedding service is unavailable.") from exc
    return vectors


def embedding(text: str) -> list[float]:
    return embed_documents([text])[0]


def embed_query(text: str) -> list[float]:
    return embedding(f"Instruct: {QUERY_INSTRUCTION}\\nQuery:{text}")


def embedding_metadata(profile: str) -> dict[str, object]:
    settings = get_settings()
    return {"embedding_model": settings.embedding_model, "embedding_dimension": settings.embedding_dimension, "embedding_profile": profile}
