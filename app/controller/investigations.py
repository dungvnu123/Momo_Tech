from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.agents.investigation.schemas import InvestigationRequest, InvestigationResult
from app.services.llm_client import LLMNotConfiguredError
from app.types.schemas import AgentContext

router = APIRouter(prefix="/api/investigations", tags=["investigations"])


@router.post("", response_model=InvestigationResult)
async def investigate(body: InvestigationRequest, request: Request):
    agent = request.app.state.investigation_agent
    try:
        agent.llm_client.ensure_ready()
    except LLMNotConfiguredError:
        raise HTTPException(status_code=503, detail="Tool-calling LLM client is not configured") from None
    from app import db
    if not db.exists(agent.database):
        raise HTTPException(status_code=503, detail="Build the graph database first")
    context = AgentContext(conversation_id=body.conversation_id,
                           metadata={"cluster_id": body.cluster_id} if body.cluster_id else {})
    if body.stream_response:
        return StreamingResponse(agent.stream(body.app_id, context), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
    return await agent.investigate(body.app_id, context)
