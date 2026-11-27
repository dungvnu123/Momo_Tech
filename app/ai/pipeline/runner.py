import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from app.graph import build_graph
from app.ai.service import AIService

from . import enrichment
from .investigations import investigate_groups
from .schemas import PipelineRequest
from .source import export_backend
from .triage import triage_groups


class PipelineBusyError(RuntimeError):
    pass


class PipelineService:
    def __init__(self, client, backend_database, directory="data/ai-pipeline"):
        self.client = client
        self.backend_database = Path(backend_database) if backend_database else None
        self.directory = Path(directory)
        self.lock = asyncio.Lock()

    def read(self, run_id):
        if len(run_id) != 32 or any(c not in "0123456789abcdef" for c in run_id):
            raise FileNotFoundError(run_id)
        return json.loads((self.directory / run_id / "result.json").read_text(encoding="utf-8"))

    def read_trace(self, run_id, cluster_id):
        result = self.read(run_id)
        item = next((c for c in result["clusters"] if c["cluster_id"] == cluster_id and c.get("trace_file")), None)
        if item is None:
            raise FileNotFoundError(cluster_id)
        path = self.directory / run_id / item["trace_file"]
        if path.resolve().parent != (self.directory / run_id).resolve():
            raise FileNotFoundError(cluster_id)
        return json.loads(path.read_text(encoding="utf-8"))

    async def run(self, request: PipelineRequest, *, progress=None):
        if self.lock.locked():
            raise PipelineBusyError("A pipeline run is already active")
        self.client.ensure_ready()
        from app import db
        if not self.backend_database or not db.exists(self.backend_database):
            raise FileNotFoundError("Backend database is unavailable")
        async with self.lock:
            run_id = uuid4().hex
            directory = self.directory / run_id
            directory.mkdir(parents=True, exist_ok=False)
            graph = directory / "graph.db"
            service = AIService(self.client, cache_path=self.directory / "cache.db")
            started = perf_counter()
            result = {"run_id": run_id, "created_at": datetime.now(timezone.utc).isoformat(),
                      "model": getattr(self.client, "model", type(self.client).__name__),
                      "status": "running", "limits": request.model_dump(), "stages": {}, "clusters": [],
                      "scope": "bounded_pipeline_preview; skipped_or_deferred_does_not_mean_benign; not_full_population_recall"}

            def save():
                temp = directory / "result.tmp"
                temp.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
                temp.replace(directory / "result.json")

            async def stage(name, operation):
                mark = perf_counter()
                result["stages"][name] = {"status": "running"}
                save()
                if progress:
                    progress(name, "running")
                try:
                    output = await operation()
                except Exception as error:
                    result["stages"][name] = {"status": "failed", "error": type(error).__name__,
                                              "elapsed_seconds": round(perf_counter() - mark, 3)}
                    save()
                    raise
                result["stages"][name] = {"status": "completed", "elapsed_seconds": round(perf_counter() - mark, 3),
                                          "result": output}
                save()
                if progress:
                    progress(name, "completed")
                return output

            try:
                source = await stage("snapshot", lambda: asyncio.to_thread(export_backend, self.backend_database,
                                                                 directory / "source", request))
                result["candidates"] = source["groups"]
                await stage("graph", lambda: asyncio.to_thread(build_graph, directory / "source", graph))
                reports = await stage("reports", lambda: enrichment.reports(service, graph, source["report_ids"]))
                await stage("entities", lambda: enrichment.entities(service, graph, source["groups"], request.entity_pair_limit))

                async def screen():
                    summaries, decisions = await triage_groups(service, graph, source["groups"])
                    return {"summaries": [s.model_dump() for s in summaries], "decisions": [d.model_dump() for d in decisions]}

                if source["groups"]:
                    triage = await stage("triage", screen)
                    from app.ai.triage.schemas import TriageDecision
                    decisions = [TriageDecision.model_validate(item) for item in triage["decisions"]]
                    def keep_cluster_results(items):
                        result["clusters"] = items
                        save()
                        if progress:
                            progress("investigation:" + items[-1]["cluster_id"], items[-1]["status"])

                    result["clusters"] = await stage("investigations", lambda: investigate_groups(
                        self.client, graph, source["groups"], decisions, request.investigation_limit, directory,
                        on_result=keep_cluster_results))
                else:
                    result["stages"]["triage"] = {"status": "skipped", "reason": "no_candidate_clusters"}
                    result["stages"]["investigations"] = {"status": "skipped", "reason": "no_candidate_clusters"}
                result["status"] = "partial" if reports["errors"] or any(
                    c["status"] in {"failed", "limit_reached", "deferred_by_limit"} for c in result["clusters"]) else "completed"
            except asyncio.CancelledError:
                result["status"] = "cancelled"
                raise
            except Exception as error:
                result["status"] = "failed"
                result["error"] = type(error).__name__
            finally:
                result["elapsed_seconds"] = round(perf_counter() - started, 3)
                result["structured_model_calls"] = service.runner.model_calls
                result["cache_hits"] = service.runner.cache_hits
                result["investigation_model_turns"] = sum(c.get("model_turns", 0) for c in result["clusters"])
                result["model_calls"] = result["structured_model_calls"] + result["investigation_model_turns"]
                result["summary"] = {
                    "selected_clusters": len(result.get("candidates", [])),
                    "investigations_completed": sum(c["status"] == "completed" for c in result["clusters"]),
                    "inconclusive": sum(c["status"] == "completed" and c.get("case", {}).get("verdict") == "inconclusive"
                                        for c in result["clusters"]),
                    "skipped_by_triage": sum(c["status"] == "skipped_by_triage" for c in result["clusters"]),
                    "deferred_by_limit": sum(c["status"] == "deferred_by_limit" for c in result["clusters"]),
                }
                save()
            return result
