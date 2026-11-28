from pathlib import Path
import sys

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from flows.registry import BUILDERS

OUT = Path(__file__).resolve().parents[1] / "docs" / "flows"

if __name__ == "__main__":
    for build in BUILDERS:
        print("saved:", build().save(OUT))
