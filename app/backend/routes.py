"""Attach backend web features after the AI routes."""
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi.staticfiles import StaticFiles
from feature_flow import create_app as create_flow_app

from pydantic import BaseModel, Field

from app import khach
from app.sim import SIM

from .http import alerts, live, metrics, shield, transfer
from .integration import BackendAI
from .store import Tools

ROOT = Path(__file__).resolve().parents[2]


def mount_backend(app, database):
    tools = Tools(database)
    app.state.backend_tools = tools
    adapter = BackendAI(app.state.ai_service, app.state.tool_llm_client, tools)
    metadata = {r["k"]: json.loads(r["v"]) for r in tools.q("SELECT k, v FROM meta")}
    previous_lifespan = app.router.lifespan_context

    @asynccontextmanager
    async def lifespan(application):
        try:
            async with previous_lifespan(application) as state:
                yield state
        finally:
            tools.db.close()

    app.router.lifespan_context = lifespan
    for feature in (shield, transfer, alerts, live, metrics):
        feature.register(app, tools, adapter, metadata)

    # App ví khách (/vi/ + /api/khach/*): dùng chung kết nối; AI thật qua adapter, chưa cấu hình → luật giả lập
    khach.tools, khach.adapter = tools, adapter
    app.include_router(khach.router)

    # Bộ mô phỏng hoạt động (đội rủi ro bật/tắt; luôn dùng luật giả lập để không tốn chi phí AI)
    class SimIn(BaseModel):
        interval: float = Field(default=2.0, ge=0.5, le=30)

    @app.get("/api/sim")
    def sim_status():
        return SIM.status()

    @app.post("/api/sim/start")
    async def sim_start(body: SimIn):
        SIM.start(body.interval)
        return SIM.status()

    @app.post("/api/sim/stop")
    def sim_stop():
        SIM.stop()
        return SIM.status()

    if os.environ.get("SIM_AUTOSTART") == "1":
        @app.on_event("startup")
        async def _autostart_sim():
            SIM.start(float(os.environ.get("SIM_INTERVAL", "3")))

    @app.get("/api/overview")
    def overview():
        return {**metadata, "ai_mode": "gemini", "cached_cases_mode": metadata.get("ai_mode", "mock")}

    app.mount("/flows", create_flow_app(ROOT / "docs" / "flows", can_edit=False, guides=False,
                                       title="Thien La", home={"url": "/", "label": "Thien La"}))
    app.mount("/", StaticFiles(directory=ROOT / "web", html=True), name="web")
