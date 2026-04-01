"""
Protegrity Dual-Gate wrapper — shared across all orchestrators.

Gate 1 (Input):  classify PII → tokenize → semantic guardrail risk score
Gate 2 (Output): find tagged tokens → detokenize (per-user or superuser)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

from services.protegrity_guard import get_guard, register_tokens_from_context, _strip_pii_tags


@dataclass
class Gate1Result:
    original_text: str
    protected_text: str
    pii_entities: list = field(default_factory=list)
    risk_score: float = 0.0
    blocked: bool = False
    guardrail_explanation: str = ""


@dataclass
class Gate2Result:
    tokenized_text: str
    restored_text: str
    tokens_resolved: int = 0


def gate1_protect(
    text: str,
    *,
    skip_gates: bool = False,
    skip_guardrail: bool = True,
    risk_threshold: float = 0.7,
) -> Gate1Result:
    """Run Gate 1: classify + tokenize + optional semantic guardrail."""
    if skip_gates:
        return Gate1Result(original_text=text, protected_text=text)

    guard = get_guard()
    result = guard.gate1_input(text, risk_threshold=risk_threshold)

    # Support both GateResult dataclass and dict returns
    if isinstance(result, dict):
        return Gate1Result(
            original_text=text,
            protected_text=result.get("protected_text", text),
            pii_entities=result.get("pii_entities", []),
            risk_score=result.get("risk_score", 0.0),
            blocked=result.get("blocked", False),
            guardrail_explanation=result.get("explanation", ""),
        )

    return Gate1Result(
        original_text=text,
        protected_text=result.transformed_text,
        pii_entities=result.elements_found,
        risk_score=result.risk_score or 0.0,
        blocked=not result.risk_accepted,
        guardrail_explanation=result.metadata.get("explanation", ""),
    )


def gate2_unprotect(
    text: str,
    *,
    skip_gates: bool = False,
    protegrity_user: Optional[str] = None,
) -> Gate2Result:
    """Run Gate 2: detokenize LLM output. Optional per-user policy."""
    if skip_gates:
        return Gate2Result(tokenized_text=text, restored_text=text)

    guard = get_guard()

    if protegrity_user and protegrity_user != "superuser":
        # Per-user unprotection (CS Portal style)
        try:
            from InternalCustomerServiceApp.protegrity_user_gate import user_unprotect
            restored = user_unprotect(text, protegrity_user)
        except Exception:
            gate2 = guard.find_and_unprotect(text)
            restored = gate2.transformed_text if hasattr(gate2, "transformed_text") else str(gate2)
    else:
        gate2 = guard.find_and_unprotect(text)
        restored = gate2.transformed_text if hasattr(gate2, "transformed_text") else str(gate2)

    if not restored or restored == text:
        restored = _strip_pii_tags(text)

    return Gate2Result(
        tokenized_text=text,
        restored_text=restored,
    )


def register_context_tokens(context_text: str) -> None:
    """Register tokens from pre-protected KB/RAG context for Gate 2 resolution."""
    register_tokens_from_context(context_text)
