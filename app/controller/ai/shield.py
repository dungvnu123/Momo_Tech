from fastapi import APIRouter, Request

from app.ai.shield.schemas import ReportAnalysis, ReportRequest
from app.core.http import run_ai

router = APIRouter(prefix='/shield', tags=['shield'])


@router.post("/analyze", response_model=ReportAnalysis)
async def analyze_report(body: ReportRequest, request: Request):
    return await run_ai(request.app.state.ai_service.analyze_report(body.text))
