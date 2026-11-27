from fastapi import APIRouter, Request

from app.ai.triage.schemas import TriageBatch, TriageDecisions
from app.core.http import run_ai

router = APIRouter(prefix='', tags=['triage'])


@router.post("/triage", response_model=TriageDecisions)
async def triage(body: TriageBatch, request: Request):
    return await run_ai(request.app.state.ai_service.triage(body.clusters))
