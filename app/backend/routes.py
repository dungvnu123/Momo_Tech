"""Attach backend web features after the AI routes."""

import json
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi.staticfiles import StaticFiles
from feature_flow import create_app as create_flow_app

from .wallet import WalletContext, create_router
from .simulation import Simulator
from .simulation.routes import register as register_simulation

from .http import alerts, live, metrics, shield, transfer
from .integration import BackendAI
from .store import Tools

ROOT = Path(__file__).resolve().parents[2]


def mount_backend(app, database):
    tools = Tools(database)
    from .events import ensure_schema
    from app.ai.realtime import RealtimeService

    enabled = ensure_schema(tools)
    realtime = (
        RealtimeService(
            database,
            app.state.investigation_agent.database,
            app.state.ai_service,
            app.state.tool_llm_client,
        )
        if enabled
        else None
    )
    app.state.realtime_service = realtime
    app.state.backend_tools = tools
    adapter = BackendAI(app.state.ai_service, app.state.tool_llm_client, tools)
    wallet = WalletContext(tools, adapter)
    simulator = Simulator(wallet)
    app.state.wallet = wallet
    app.state.simulator = simulator
    metadata = {r["k"]: json.loads(r["v"]) for r in tools.q("SELECT k, v FROM meta")}
    previous_lifespan = app.router.lifespan_context

    @asynccontextmanager
    async def lifespan(application):
        try:
            async with previous_lifespan(application) as state:
                if realtime and os.environ.get("AI_REALTIME_ENABLED", "1") == "1":
                    realtime.start()
                yield state
        finally:
            if realtime:
                await realtime.close()
            tools.db.close()

    app.router.lifespan_context = lifespan
    for feature in (shield, transfer, alerts, live, metrics):
        feature.register(app, tools, adapter, metadata)

    app.include_router(create_router(wallet))
    register_simulation(app, simulator)

    @app.get("/api/overview")
    def overview():
        return {
            **metadata,
            "ai_mode": "gemini",
            "cached_cases_mode": metadata.get("ai_mode", "mock"),
        }

    app.mount(
        "/flows",
        create_flow_app(
            ROOT / "docs" / "flows",
            can_edit=False,
            guides=False,
            title="Thien La",
            home={"url": "/", "label": "Thien La"},
        ),
    )
    app.mount("/", StaticFiles(directory=ROOT / "web", html=True), name="web")
