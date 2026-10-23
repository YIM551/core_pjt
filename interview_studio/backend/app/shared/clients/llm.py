from langchain_openai import ChatOpenAI

from app.core.config import get_settings


def chat_model() -> ChatOpenAI:
    settings = get_settings()
    return ChatOpenAI(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        temperature=0,
        max_retries=0,
        request_timeout=settings.llm_timeout_seconds,
        extra_body={"chat_template_kwargs": {"enable_thinking": False}},
    )
