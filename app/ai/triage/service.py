from pathlib import Path

from .schemas import TriageBatch, TriageDecisions
from ..common.validation import _same_ids

PROMPT = Path(__file__).with_name("prompt.md")


class TriageService:
    def __init__(self, runner):
        self.runner = runner

    async def screen(self, clusters) -> TriageDecisions:
        request = TriageBatch.model_validate({"clusters": clusters})
        _same_ids([item.cluster_id for item in request.clusters], [item.cluster_id for item in request.clusters])
        return await self.runner.run(
            "triage", PROMPT.read_text(encoding="utf-8"), request.model_dump(),
            TriageDecisions, lambda result: _same_ids([item.cluster_id for item in result.decisions],
                                                     [item.cluster_id for item in request.clusters]),
        )
