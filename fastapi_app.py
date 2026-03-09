from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from rag_service import answer_question

app = FastAPI(title="Zalando FAQ RAG API", version="1.0.0")


class AskRequest(BaseModel):
    question: str = Field(min_length=1, description="Domanda utente")
    top_k: int = Field(default=3, ge=1, le=10)


class SourceItem(BaseModel):
    category: str
    url: str
    distance: float


class AskResponse(BaseModel):
    answer: str
    used_fallback: bool
    model: str
    top_k: int
    sources: list[SourceItem]
    intent: str
    is_small_talk: bool


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/ask", response_model=AskResponse)
def ask(payload: AskRequest) -> AskResponse:
    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="La domanda non può essere vuota")

    result = answer_question(question=question, top_k=payload.top_k)
    return AskResponse(**result)
