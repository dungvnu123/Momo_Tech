from uuid import UUID

from fastapi import APIRouter, HTTPException, Request

from app.ai.pipeline.runner import PipelineBusyError
from app.ai.pipeline.schemas import PipelineRequest
from app.services.llm_client import LLMNotConfiguredError

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


@router.post("/run")
async def run_pipeline(body: PipelineRequest, request: Request):
    service = request.app.state.pipeline_service
    try:
        return await service.run(body)
    except PipelineBusyError:
        raise HTTPException(409, "A pipeline run is already active") from None
    except LLMNotConfiguredError:
        raise HTTPException(503, "Gemini client is not configured") from None
    except FileNotFoundError:
        raise HTTPException(503, "Build the backend database first") from None


@router.get("/runs/{run_id}")
async def get_pipeline_run(run_id: UUID, request: Request):
    try:
        return request.app.state.pipeline_service.read(run_id.hex)
    except FileNotFoundError:
        raise HTTPException(404, "Pipeline run not found") from None


@router.get("/runs/{run_id}/traces/{cluster_id}")
async def get_pipeline_trace(run_id: UUID, cluster_id: str, request: Request):
    try:
        return request.app.state.pipeline_service.read_trace(run_id.hex, cluster_id)
    except FileNotFoundError:
        raise HTTPException(404, "Pipeline trace not found") from None
