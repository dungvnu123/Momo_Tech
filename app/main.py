from fastapi import FastAPI
import os
from pathlib import Path

from app.agents.default import DefaultAgent
from app.agents.manager import AgentManager
from app.agents.investigation import InvestigationAgent
from app.controller.agents import router as agent_router
from app.controller.investigations import router as investigation_router
from app.controller.ai import router as ai_router
from app.ai.service import AIService
from app.ai.pipeline.runner import PipelineService
from app.services.gemini_client import configured_tool_client
from app.services.llm_client import LLMClient, UnconfiguredLLMClient
from app.core.config import configured_service_key, load_environment
from app.core.http import unhandled_error
from app.core.logging import configure_request_logging
from app.core.openapi import configure_service_security
from app.middleware import configure_middleware
from app.security import WebSecurityPolicy


def create_app(llm_client: LLMClient | None = None, *, tool_llm_client=None,
               graph_database=None, ai_cache=None,
               service_api_key: str | None = None, backend_database=None,
               web_password: str | None = None, web_secret: str | None = None,
               pipeline_directory=None) -> FastAPI:
    load_environment()
    configure_request_logging()
    key = configured_service_key() if service_api_key is None else service_api_key
    policy = WebSecurityPolicy(password=web_password, secret=web_secret, service_api_key=key)
    application = FastAPI(title="Thiên La Agent Service", version="0.1.0",
                          docs_url=None if policy.password else "/docs",
                          redoc_url=None if policy.password else "/redoc",
                          openapi_url=None if policy.password else "/openapi.json")
    application.state.web_security = policy
    configure_middleware(application, service_api_key=key, web_policy=policy)
    from app.backend.http.auth import register as register_auth
    register_auth(application)
    application.add_exception_handler(Exception, unhandled_error)
    if key:
        configure_service_security(application)
    client = llm_client if llm_client is not None else UnconfiguredLLMClient()
    application.state.agent_manager = AgentManager([DefaultAgent(client)])
    application.include_router(agent_router)
    tool_client = tool_llm_client if tool_llm_client is not None else configured_tool_client()
    application.state.tool_llm_client = tool_client
    database_path = graph_database or os.environ.get("GRAPH_DATABASE", "data/graph.db")
    application.state.investigation_agent = InvestigationAgent(tool_client, database=database_path, require_assessments=True)
    application.include_router(investigation_router)
    application.state.ai_service = AIService(tool_client, cache_path=ai_cache)
    backend_path = None if backend_database is False else backend_database or os.environ.get("THIENLA_DB", "thienla.db")
    application.state.pipeline_service = PipelineService(tool_client, backend_path,
        pipeline_directory or os.environ.get("AI_PIPELINE_DIR", "data/ai-pipeline"))
    application.include_router(ai_router)

    @application.get("/health")
    async def health_check() -> dict[str, str]:
        return {"status": "ok", "service": "thien-la-agent"}

    database = Path(backend_database or os.environ.get("THIENLA_DB", "thienla.db"))
    if backend_database is False:
        return application
    from app import db
    if db.exists(database):   # PostgreSQL: schema của "database" kiểu cũ đã có dữ liệu (build.py)
        from app.backend.routes import mount_backend
        mount_backend(application, database)
    elif backend_database is not None:
        raise FileNotFoundError(database)

    return application


app = create_app()
