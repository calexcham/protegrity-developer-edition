"""
LLM provider factory — supports OpenAI, Anthropic, Groq.

Usage:
    from llm_providers import get_llm
    llm = get_llm()  # reads from orchestration_config
"""

from llm_providers.factory import get_llm, get_llm_for_langchain

__all__ = ["get_llm", "get_llm_for_langchain"]
