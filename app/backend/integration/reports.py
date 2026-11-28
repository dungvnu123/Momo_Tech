from app.backend import mock_ai
from app.backend.knowledge.reports import report_view

RULES = "luật (chưa cấu hình AI)"


async def analyze_report(self, text):
    if not self.ready():
        return {**mock_ai.analyze_report(text), "mode": RULES}
    result = await self.service.analyze_report(text)
    return report_view(result)
