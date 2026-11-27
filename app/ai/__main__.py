import argparse
import asyncio
import json
import sys
import os
from pathlib import Path

from app.graph.ai_store import AIStore
from app.services.gemini_client import configured_tool_client
from app.core.config import load_environment

from .evaluation import evaluate
from .pipeline import analyze_stored_reports, resolve_stored_entities, triage_groups
from .service import AIService
from .pipeline.runner import PipelineService
from .pipeline.schemas import PipelineRequest


async def execute(args):
    client = configured_tool_client()
    service = AIService(client, cache_path=args.cache) if args.command != "pipeline" else None
    if args.command == "pipeline":
        config = PipelineRequest(report_limit=args.report_limit, entity_pair_limit=args.entity_pair_limit,
                                 cluster_limit=args.cluster_limit, investigation_limit=args.investigation_limit)
        runner = PipelineService(client, args.backend_database, args.runs_dir)
        result = await runner.run(config, progress=lambda stage, status: print(
            json.dumps({"stage": stage, "status": status}), flush=True))
    elif args.command == "evaluate":
        result = await evaluate(service, client, args.database, args.data_dir,
                                report_limit=args.report_limit, investigation_limit=args.investigation_limit)
    elif args.command == "reports":
        with AIStore(args.database) as store:
            ids = [row[0] for row in store.connection.execute("SELECT id FROM scam_reports ORDER BY id LIMIT ?", (args.limit,))]
        analyses = await analyze_stored_reports(service, args.database, ids)
        result = {"processed": len(analyses), "report_ids": [item["report_id"] for item in analyses]}
    elif args.command == "entities":
        decisions = await resolve_stored_entities(service, args.database, limit=args.limit)
        result = {"processed": len(decisions), "decisions": [item.model_dump() for item in decisions]}
    else:
        groups = json.loads(args.groups.read_text(encoding="utf-8"))
        summaries, decisions = await triage_groups(service, args.database, groups)
        result = {"summaries": [item.model_dump() for item in summaries], "decisions": [item.model_dump() for item in decisions]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "summary": result.get("summary", {"processed": result.get("processed")}),
                      "model_calls": result.get("model_calls", result.get("structured_model_calls", service.runner.model_calls if service else 0)),
                      "cache_hits": result.get("cache_hits", service.runner.cache_hits if service else 0)}, ensure_ascii=False))
    return result


def main():
    load_environment()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Thiên La AI processing and measured evaluation")
    parser.add_argument("command", choices=["reports", "entities", "triage", "evaluate", "pipeline"])
    parser.add_argument("--database", type=Path, default=Path("data/graph.db"))
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--cache", type=Path, default=Path("data/ai-cache.db"))
    parser.add_argument("--output", type=Path, default=Path("data/ai-evaluation.json"))
    parser.add_argument("--limit", type=int, choices=range(1, 201), default=20)
    parser.add_argument("--report-limit", type=int, choices=range(1, 201))
    parser.add_argument("--investigation-limit", type=int, choices=range(0, 13))
    parser.add_argument("--groups", type=Path)
    parser.add_argument("--backend-database", type=Path, default=Path(os.environ.get("THIENLA_DB", "thienla.db")))
    parser.add_argument("--runs-dir", type=Path, default=Path(os.environ.get("AI_PIPELINE_DIR", "data/ai-pipeline")))
    parser.add_argument("--cluster-limit", type=int, choices=range(1, 7), default=4)
    parser.add_argument("--entity-pair-limit", type=int, choices=range(0, 21), default=10)
    args = parser.parse_args()
    args.report_limit = args.report_limit if args.report_limit is not None else (8 if args.command == "pipeline" else 12)
    args.investigation_limit = args.investigation_limit if args.investigation_limit is not None else (2 if args.command == "pipeline" else 4)
    if args.command == "pipeline" and (args.report_limit > 12 or args.investigation_limit > 4):
        parser.error("Pipeline limits: at most 12 reports and 4 investigations")
    from app import db
    if args.command == "pipeline" and not db.exists(args.backend_database):
        parser.error("Build the backend database before running the pipeline")
    if args.command != "pipeline" and not db.exists(args.database):
        parser.error("Build the graph database before running AI processing")
    if args.command == "triage" and args.groups is None:
        parser.error("triage requires --groups with a JSON list of cluster_id/app_ids")
    result = asyncio.run(execute(args))
    if args.command == "pipeline" and result["status"] in {"failed", "cancelled"}:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
