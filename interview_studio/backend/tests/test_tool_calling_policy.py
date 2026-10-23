from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.shared.ai.runtime import ToolCallingUnavailable
from app.shared.http.problems import tool_calling_exception_handler


def test_native_tool_protocol_failure_uses_the_public_503_code():
    app = FastAPI()
    app.add_exception_handler(ToolCallingUnavailable, tool_calling_exception_handler)

    @app.get("/tool-failure")
    def tool_failure():
        raise ToolCallingUnavailable()

    response = TestClient(app).get("/tool-failure")
    assert response.status_code == 503
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "LLM_TOOL_CALLING_UNAVAILABLE"
