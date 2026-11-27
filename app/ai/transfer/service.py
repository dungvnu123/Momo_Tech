from pathlib import Path

from .schemas import TransferCheck, TransferDecision

PROMPT = Path(__file__).with_name("prompt.md")


class TransferService:
    def __init__(self, runner):
        self.runner = runner

    async def check(self, transfer) -> TransferDecision:
        request = TransferCheck.model_validate(transfer)

        def validate(result):
            if result.decision == "hold" and not (request.simo_flag or request.reported_recipient_count
                                                  or request.recipient_ring_senders or request.customer_says_coached):
                raise ValueError("Hold requires a recorded recipient warning; otherwise use warn")

        return await self.runner.run(
            "transfer_verdict", PROMPT.read_text(encoding="utf-8"),
            request.model_dump(), TransferDecision, validate,
        )
