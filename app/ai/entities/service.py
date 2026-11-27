from pathlib import Path

from .schemas import EntityBatch, EntityDecisions
from ..common.validation import _same_ids

PROMPT = Path(__file__).with_name("prompt.md")


def _validate_entities(result, request):
    _same_ids([item.pair_id for item in result.decisions], [item.pair_id for item in request.pairs])
    inputs = {pair.pair_id: pair for pair in request.pairs}
    if any(item.decision == "same" and inputs[item.pair_id].left.dob != inputs[item.pair_id].right.dob
           for item in result.decisions):
        raise ValueError("Different dates of birth cannot be merged")


class EntityService:
    def __init__(self, runner):
        self.runner = runner

    async def resolve(self, pairs) -> EntityDecisions:
        request = EntityBatch.model_validate({"pairs": pairs})
        _same_ids([pair.pair_id for pair in request.pairs], [pair.pair_id for pair in request.pairs])
        return await self.runner.run(
            "er_decisions", PROMPT.read_text(encoding="utf-8"), request.model_dump(),
            EntityDecisions, lambda result: _validate_entities(result, request),
        )
