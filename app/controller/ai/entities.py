from fastapi import APIRouter, Request

from app.ai.entities.schemas import EntityBatch, EntityDecisions
from app.core.http import run_ai

router = APIRouter(prefix='/entities', tags=['entities'])


@router.post("/resolve", response_model=EntityDecisions)
async def resolve_entities(body: EntityBatch, request: Request):
    return await run_ai(request.app.state.ai_service.resolve_entities(body.pairs))
