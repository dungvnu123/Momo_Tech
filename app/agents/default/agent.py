from pathlib import Path

from app.agents.base import BaseAgent


class DefaultAgent(BaseAgent):
    agent_id = "default"
    name = "Default Agent"
    prompt_file = Path(__file__).with_name("prompt.md")
    fallback_system_prompt = "Bạn là trợ lý AI của dự án Thiên La. Trả lời bằng tiếng Việt."
