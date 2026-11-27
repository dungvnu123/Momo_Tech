from fastapi import FastAPI

from app.agents.default import DefaultAgent
from app.agents.manager import AgentManager
from app.controller.agents import router as agent_router
from app.services.llm_client import LLMClient, UnconfiguredLLMClient


def create_app(llm_client: LLMClient | None = None) -> FastAPI:
    application = FastAPI(title="Thiên La Agent Service", version="0.1.0")
    client = llm_client if llm_client is not None else UnconfiguredLLMClient()
    application.state.agent_manager = AgentManager([DefaultAgent(client)])
    application.include_router(agent_router)

    @application.get("/health")
    async def health_check() -> dict[str, str]:
        return {"status": "ok", "service": "thien-la-agent"}

    return application


app = create_app()
