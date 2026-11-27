import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from app.agents.manager import AgentManager
from app.services.llm_client import LLMNotConfiguredError
from app.types.schemas import AgentContext, ChatRequest

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/agents", tags=["agents"])


def get_agent_manager(request: Request) -> AgentManager:
    return request.app.state.agent_manager


ManagerDependency = Annotated[AgentManager, Depends(get_agent_manager)]


@router.get("")
async def list_agents(manager: ManagerDependency) -> dict[str, list[str]]:
    return {"agents": manager.list_agents()}


@router.get("/ids")
async def list_agent_ids(manager: ManagerDependency) -> dict[str, list[str]]:
    return {"agent_ids": manager.list_agents()}


async def run_agent_request(request: ChatRequest, manager: AgentManager):
    try:
        agent = manager.get_agent(request.agent_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Unknown agent_id") from None
    context = AgentContext(**request.model_dump(exclude={"agent_id", "message"}))
    try:
        return await agent.respond_text(request.message, context)
    except LLMNotConfiguredError:
        raise HTTPException(status_code=503, detail="LLM client is not configured") from None
    except TimeoutError:
        raise HTTPException(status_code=504, detail="LLM request timed out") from None
    except Exception:
        logger.error("Agent request failed for agent_id=%s", request.agent_id)
        raise HTTPException(status_code=502, detail="LLM request failed") from None


@router.post("/run")
async def run_agent(request: ChatRequest, manager: ManagerDependency):
    return await run_agent_request(request, manager)
