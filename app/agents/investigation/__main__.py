import argparse
import asyncio
import sys

from app.services.gemini_client import configured_tool_client
from app.types.schemas import AgentContext

from .agent import InvestigationAgent
from .demo import DemoInvestigationClient


async def execute(args):
    client = DemoInvestigationClient() if args.demo else configured_tool_client()
    agent = InvestigationAgent(client, database=args.database)
    context = AgentContext(metadata={"cluster_id": args.cluster_id} if args.cluster_id else {})
    if args.stream:
        async for event in agent.stream(args.app_id, context):
            print(event, end="", flush=True)
    else:
        result = await agent.investigate(args.app_id, context)
        print(result.model_dump_json(indent=2))


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Run the investigation Agent against a graph database")
    parser.add_argument("--app-id", required=True)
    parser.add_argument("--cluster-id")
    parser.add_argument("--database", default="data/graph.db")
    parser.add_argument("--demo", action="store_true", help="Scripted tool calls, no LLM API or fraud verdict")
    parser.add_argument("--stream", action="store_true")
    args = parser.parse_args()
    asyncio.run(execute(args))


if __name__ == "__main__":
    main()
