"""One durable event at a time; existing AI services and InvestigationAgent do the reasoning."""

import asyncio
import json
import logging
from collections import deque
from time import monotonic

from app.backend.integration import BackendAI
from app.backend.store import Tools
from app.backend.report_view import report_view
from app.graph.ingestion import ingest_event
from app.graph.ingestion.clusters import persist_cluster
from app.services.llm_client import LLMNotConfiguredError

from . import jobs
from .alerts import snapshot
from .features import summarize
from .scope import related_applications
from .source import source_record, report_analysis
from .candidates import candidates

logger = logging.getLogger(__name__)


class InvestigationIncomplete(RuntimeError):
    def __init__(self, case):
        super().__init__("Investigation did not complete")
        self.details = {"investigation": "incomplete", "trace": case}


class RealtimeService:
    def __init__(self, database, graph_database, service, client, *, max_per_minute=6):
        self.database, self.graph_database = database, graph_database
        self.service, self.client = service, client
        self.max_per_minute = max_per_minute
        self.recent = deque()
        self.lock = asyncio.Lock()
        self.task = None

    def start(self):
        if self.task is None or self.task.done():
            self.task = asyncio.create_task(self._loop())

    async def close(self):
        if self.task is not None:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass

    async def _loop(self):
        while True:
            try:
                worked = await self.process_one()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.error("Realtime worker iteration failed")
                worked = False
            await asyncio.sleep(0.1 if worked else 1)

    async def process_one(self):
        async with self.lock:
            while self.recent and self.recent[0] < monotonic() - 60:
                self.recent.popleft()
            if len(self.recent) >= self.max_per_minute:
                return False
            store = Tools(self.database)
            try:
                event = jobs.claim(store)
                if event is None:
                    return False
                try:
                    await self._process(store, event)
                except LLMNotConfiguredError:
                    jobs.wait_for_model(store, event)
                except asyncio.CancelledError:
                    # The lease is recoverable if the app shuts down during a model call.
                    raise
                except Exception as error:
                    jobs.fail(store, event, error)
                    logger.warning(
                        "Realtime event failed: event_id=%s code=%s",
                        event["event_id"],
                        type(error).__name__,
                    )
                return True
            finally:
                store.db.close()

    async def _process(self, store, event):
        source = source_record(store, event)
        app = store.apps([event["app_id"]])[0]
        analysis = None
        official = (
            event["kind"] == "report"
            and json.loads(source["analysis"]).get("mode") == "kênh xác thực"
        )
        if event["kind"] == "report" and not official and not event["payload"].get("simulated"):
            self.client.ensure_ready()
            self.recent.append(monotonic())
            analysis = await report_analysis(self.service, self.client, source)
        await asyncio.to_thread(
            ingest_event, self.graph_database, event, app, source, analysis=analysis
        )
        if analysis is not None:
            store.run(
                "UPDATE reports SET analysis=? WHERE report_id=?",
                json.dumps(report_view(analysis), ensure_ascii=False),
                event["source_id"],
            )
        if official:
            jobs.finish(
                store,
                event,
                {
                    "investigation": "not_requested",
                    "mode": "verified_channel",
                    "graph_updated": True,
                },
            )
            return
        if event["payload"].get("simulated"):
            jobs.finish(
                store,
                event,
                {"investigation": "not_requested", "mode": "simulation", "graph_updated": True},
            )
            return
        ids, truncated = related_applications(
            self.graph_database, event["app_id"], event["occurred_at"], sequence=event["sequence"]
        )
        discovered = set(ids) | candidates(store, event, app, source)
        truncated |= len(discovered) > 100
        ids = sorted({event["app_id"], *sorted(discovered - {event["app_id"]})[:99]})
        alert = snapshot(store, event, ids, truncated=truncated)
        summary, relevant = summarize(store, alert, truncated=truncated)
        relevant |= analysis is not None and analysis.verdict != "safe"
        if not relevant:
            store.run("UPDATE alerts SET latest=FALSE WHERE alert_id=?", alert["alert_id"])
            jobs.finish(
                store,
                event,
                {
                    "triage": "not_requested",
                    "reason": "No candidate pattern in bounded snapshot",
                    "graph_updated": True,
                },
            )
            return
        self.client.ensure_ready()
        if event["kind"] != "report":
            self.recent.append(monotonic())
        saved = store.q("SELECT body FROM cases WHERE alert_id=?", alert["alert_id"])
        if saved and json.loads(saved[0]["body"]).get("status") == "completed":
            jobs.finish(
                store,
                event,
                {"alert_id": alert["alert_id"], "investigation": "completed", "reused": True},
            )
            return
        decision = (await self.service.triage([summary.model_dump()])).decisions[0]
        await asyncio.to_thread(
            persist_cluster, self.graph_database, store.apps(ids), summary, decision
        )
        if decision.decision == "skip":
            store.run(
                "UPDATE alerts SET reason=? WHERE alert_id=?", decision.reason, alert["alert_id"]
            )
            jobs.finish(
                store,
                event,
                {"alert_id": alert["alert_id"], "triage": "skip", "scope_truncated": truncated},
            )
            return
        store.run(
            "UPDATE alerts SET title=?,reason=?,severity='cao',priority=20 WHERE alert_id=?",
            "AI đề nghị điều tra dữ liệu mới",
            decision.reason,
            alert["alert_id"],
        )
        case = None
        async for response in BackendAI(self.service, self.client, store).investigate(alert):
            if response["type"] == "case":
                case = response["case"]
        if not case or case.get("status") != "completed":
            raise InvestigationIncomplete(case)
        jobs.finish(
            store,
            event,
            {
                "alert_id": alert["alert_id"],
                "triage": "investigate",
                "investigation": "completed",
                "scope_truncated": truncated,
                "run_id": case["run_id"],
            },
        )
