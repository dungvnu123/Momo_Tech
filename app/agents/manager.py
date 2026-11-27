from collections.abc import Iterable

from app.agents.base import BaseAgent


class AgentManager:
    def __init__(self, agents: Iterable[BaseAgent] = ()) -> None:
        self._agents: dict[str, BaseAgent] = {}
        for agent in agents:
            self.register(agent)

    def register(self, agent: BaseAgent) -> None:
        if not agent.agent_id.strip():
            raise ValueError("agent_id cannot be blank")
        if agent.agent_id in self._agents:
            raise ValueError(f"Duplicate agent_id: {agent.agent_id}")
        self._agents[agent.agent_id] = agent

    def get_agent(self, agent_id: str) -> BaseAgent:
        return self._agents[agent_id]

    def list_agents(self) -> list[str]:
        return sorted(self._agents)
