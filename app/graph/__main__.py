import argparse
import json
from pathlib import Path

from .builder import build_graph
from .store import GraphStore


def main():
    parser = argparse.ArgumentParser(description="Build and inspect the Thiên La evidence graph")
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build")
    build.add_argument("--data-dir", type=Path, default=Path("data"))
    build.add_argument("--database", type=Path, default=Path("data/graph.db"))
    build.add_argument("--replace", action="store_true")
    inspect = commands.add_parser("inspect")
    inspect.add_argument("node_id")
    inspect.add_argument("--database", type=Path, default=Path("data/graph.db"))
    inspect.add_argument("--depth", type=int, default=2)
    inspect.add_argument("--output", type=Path, default=Path("data/subgraph.json"))
    args = parser.parse_args()
    if args.command == "build":
        result = build_graph(args.data_dir, args.database, replace=args.replace)
    else:
        if not args.database.is_file():
            parser.error("Database does not exist; run build first")
        with GraphStore(args.database) as store:
            graph = store.neighborhood(args.node_id, depth=args.depth)
            result = {
                "metadata": graph.graph,
                "nodes": [{"id": node, **attributes} for node, attributes in graph.nodes(data=True)],
                "edges": [{"id": key, "source": source, "target": target, **attributes}
                          for source, target, key, attributes in graph.edges(keys=True, data=True)],
            }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        result = {"output": str(args.output), "nodes": len(graph), "edges": graph.number_of_edges(),
                  "truncated": graph.graph["truncated"]}
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
