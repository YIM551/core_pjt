from pydantic import Field

from app.shared.http.dto import RequestDTO


class ChatRequest(RequestDTO):
    question: str = Field(min_length=1)
