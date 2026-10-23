from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import current_user
from app.candidate.dto.chat import ChatRequest
from app.candidate.services.chat import CandidateChatService

router = APIRouter(prefix="/candidate", tags=["candidate"])


@router.post("/chat")
def personal_chat(payload: ChatRequest, db: Session = Depends(get_db), user = Depends(current_user)):
    return CandidateChatService(db).answer(user, payload)
