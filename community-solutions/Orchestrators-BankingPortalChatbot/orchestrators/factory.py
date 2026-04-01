"""
Orchestrator factory — returns the configured orchestrator instance.
"""

from config.orchestration_config import ORCHESTRATOR as _DEFAULT_ORCHESTRATOR
from orchestrators.base import BaseOrchestrator

# Mutable for testing
ORCHESTRATOR = _DEFAULT_ORCHESTRATOR


def get_orchestrator() -> BaseOrchestrator:
    if ORCHESTRATOR == "direct":
        from orchestrators.direct_orch import DirectOrchestrator
        return DirectOrchestrator()

    elif ORCHESTRATOR == "langgraph":
        from orchestrators.langgraph_orch import LangGraphOrchestrator
        return LangGraphOrchestrator()

    elif ORCHESTRATOR == "crewai":
        from orchestrators.crewai_orch import CrewAIOrchestrator
        return CrewAIOrchestrator()

    elif ORCHESTRATOR == "llamaindex":
        from orchestrators.llamaindex_orch import LlamaIndexOrchestrator
        return LlamaIndexOrchestrator()

    else:
        raise ValueError(f"Unknown orchestrator: {ORCHESTRATOR}")
