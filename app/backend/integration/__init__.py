from .reports import analyze_report
from .transfers import check_transfer
from .investigation import investigate


class BackendAI:
    def __init__(self, service, client, store):
        self.service, self.client, self.store = service, client, store

    def ready(self):
        try:
            self.client.ensure_ready()
            return True
        except Exception:
            return False

    async def analyze_report(self, text):
        return await analyze_report(self, text)

    async def check_transfer(self, ctx):
        return await check_transfer(self, ctx)

    async def investigate(self, alert):
        async for event in investigate(self, alert):
            yield event


__all__ = ["BackendAI"]
