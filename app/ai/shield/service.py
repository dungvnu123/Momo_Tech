from pathlib import Path

from .schemas import ReportAnalysis, ReportRequest
from .indicators import validate_report

PROMPT = Path(__file__).with_name("prompt.md")


class ShieldService:
    def __init__(self, runner):
        self.runner = runner

    async def analyze(self, text: str) -> ReportAnalysis:
        request = ReportRequest(text=text)
        return await self.runner.run(
            "report_verdict", PROMPT.read_text(encoding="utf-8"), request.model_dump(),
            ReportAnalysis, lambda result: validate_report(result, request.text),
        )
