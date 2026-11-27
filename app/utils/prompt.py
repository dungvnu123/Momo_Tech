from pathlib import Path


def get_prompt_from_md(path: str | Path, default: str = "") -> str:
    prompt_path = Path(path)
    if prompt_path.is_dir():
        prompt_path /= "prompt.md"
    if not prompt_path.is_file():
        return default
    return prompt_path.read_text(encoding="utf-8-sig").strip() or default
