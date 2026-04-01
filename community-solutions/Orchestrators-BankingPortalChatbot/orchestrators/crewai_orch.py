"""
CrewAI orchestrator — multi-agent pipeline (protected-in, protected-out).

Agents:
  1. Research Agent   — KB / RAG retrieval over pre-protected data
  2. Response Agent   — LLM generation using tokenized context

Gate 1 and Gate 2 are handled by the caller.
"""

from __future__ import annotations
import logging
from pathlib import Path
from typing import Dict, List, Optional

from crewai import Agent, Task, Crew, Process

from orchestrators.base import BaseOrchestrator, PipelineResult
from common.protegrity_gates import register_context_tokens
from llm_providers.factory import get_llm_provider
from config.orchestration_config import KB_ENABLED

log = logging.getLogger(__name__)

KB_DIR = Path(__file__).resolve().parent.parent / "banking_data" / "knowledge_base"

SYSTEM_PROMPT = (
    "You are a helpful banking assistant for SecureBank. "
    "Be concise, professional, and accurate. "
    "IMPORTANT: Preserve all PII tags like [PERSON]value[/PERSON] exactly as they appear."
)


class CrewAIOrchestrator(BaseOrchestrator):

    @property
    def name(self) -> str:
        return "CrewAI"

    def run(
        self,
        user_message: str,
        *,
        customer_id: Optional[str] = None,
        conversation_history: Optional[List[Dict]] = None,
        protected_context: Optional[str] = None,
    ) -> PipelineResult:
        # ── Step 1: Retrieval (Research Agent logic) ──
        kb_context = protected_context or ""
        if not kb_context and KB_ENABLED and customer_id:
            kb_file = KB_DIR / f"{customer_id}.txt"
            if kb_file.exists():
                kb_context = kb_file.read_text().strip()
        if kb_context:
            register_context_tokens(kb_context)

        # ── Step 2: LLM via CrewAI agents ──
        system_context = SYSTEM_PROMPT
        if kb_context:
            system_context += f"\n\nCustomer Data:\n{kb_context}"

        research_agent = Agent(
            role="Banking Research Analyst",
            goal="Retrieve relevant customer data from the knowledge base.",
            backstory=(
                "You have access to pre-protected customer records. "
                "All PII is tokenized — never attempt to decode tokens."
            ),
            verbose=False,
            allow_delegation=False,
        )

        response_agent = Agent(
            role="Customer Service Representative",
            goal="Answer the customer's banking question accurately using tokenized data.",
            backstory=(
                f"{system_context}\n\n"
                "You must preserve all [TAG]value[/TAG] tokens exactly as they appear."
            ),
            verbose=False,
            allow_delegation=False,
        )

        # Tasks
        research_task = Task(
            description=(
                f"Retrieve relevant information for customer {customer_id or 'unknown'}.\n"
                f"Available context:\n{kb_context[:2000] if kb_context else 'No KB data available.'}"
            ),
            expected_output="Relevant customer data from the knowledge base.",
            agent=research_agent,
        )

        response_task = Task(
            description=(
                f"Answer the following banking question using the provided context.\n"
                f"Question (tokenized): {user_message}\n\n"
                f"IMPORTANT: Preserve all [TAG]value[/TAG] tokens exactly."
            ),
            expected_output="A helpful, concise answer with PII tags preserved.",
            agent=response_agent,
        )

        crew = Crew(
            agents=[research_agent, response_agent],
            tasks=[research_task, response_task],
            process=Process.sequential,
            verbose=False,
        )

        try:
            crew_output = crew.kickoff()
            raw_response = str(crew_output)
        except Exception as e:
            log.error("CrewAI execution failed: %s", e)
            # Fallback to direct LLM call
            provider_fn = get_llm_provider()
            messages = [{"role": "system", "content": system_context}]
            for m in conversation_history or []:
                messages.append({"role": m["role"], "content": m["content"]})
            messages.append({"role": "user", "content": user_message})
            raw_response = provider_fn(messages)

        return PipelineResult(
            answer=raw_response,
            raw_llm_response=raw_response,
            metadata={"orchestrator": self.name},
        )
