import os
from pydantic import BaseModel, Field


class SimIn(BaseModel):
    interval: float = Field(default=2.0, ge=0.5, le=30)


def register(app, simulator):
    @app.get("/api/sim")
    def sim_status():
        return simulator.status()

    @app.post("/api/sim/start")
    async def sim_start(body: SimIn):
        simulator.start(body.interval)
        return simulator.status()

    @app.post("/api/sim/stop")
    def sim_stop():
        simulator.stop()
        return simulator.status()

    if os.environ.get("SIM_AUTOSTART") == "1":

        @app.on_event("startup")
        async def _autostart_sim():
            simulator.start(float(os.environ.get("SIM_INTERVAL", "3")))
