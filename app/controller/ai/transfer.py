from fastapi import APIRouter, Request

from app.ai.transfer.schemas import TransferCheck, TransferDecision
from app.core.http import run_ai

router = APIRouter(prefix='/transfer', tags=['transfer'])


@router.post("/check", response_model=TransferDecision)
async def check_transfer(body: TransferCheck, request: Request):
    return await run_ai(request.app.state.ai_service.check_transfer(body))
