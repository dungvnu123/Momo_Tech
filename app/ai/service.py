from .common.runner import StructuredRunner
from .entities.service import EntityService
from .shield.service import ShieldService
from .transfer.service import TransferService
from .triage.service import TriageService


class AIService:
    def __init__(self, client, *, cache_path=None):
        self.runner = StructuredRunner(client, cache_path=cache_path)
        self.shield = ShieldService(self.runner)
        self.entities = EntityService(self.runner)
        self.screening = TriageService(self.runner)
        self.transfers = TransferService(self.runner)

    async def analyze_report(self, text):
        return await self.shield.analyze(text)

    async def resolve_entities(self, pairs):
        return await self.entities.resolve(pairs)

    async def triage(self, clusters):
        return await self.screening.screen(clusters)

    async def check_transfer(self, transfer):
        return await self.transfers.check(transfer)
