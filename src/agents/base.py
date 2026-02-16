"""
Base agent class for forensic accounting analysis.

All agents inherit from BaseAgent and implement the analyze() method.
Each agent receives the LangGraph state, performs its analysis, and
returns the updated state with findings.
"""
import json
from abc import ABC, abstractmethod
from typing import Any

from loguru import logger

from src.llm.provider import LLMProvider, LLMProviderError


class BaseAgent(ABC):
    """
    Abstract base class for all forensic analysis agents.

    Each agent:
    1. Receives the workflow state
    2. Formats its prompt with data and memory context
    3. Calls the LLM
    4. Parses the structured JSON response
    5. Returns findings in standardized format
    """

    agent_name: str = "base"

    def __init__(self, llm: LLMProvider):
        self.llm = llm

    def __call__(self, state: dict) -> dict:
        """LangGraph-compatible call interface."""
        return self.analyze(state)

    @abstractmethod
    def analyze(self, state: dict) -> dict:
        """
        Run the agent's analysis and update the state.

        Args:
            state: LangGraph workflow state dict

        Returns:
            Updated state dict with agent findings
        """
        ...

    def _call_llm_json(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 4096,
    ) -> dict:
        """
        Call LLM expecting JSON response, with retry on parse failure.

        Args:
            system_prompt: System instructions
            user_prompt: User/data prompt
            max_tokens: Max output tokens

        Returns:
            Parsed JSON dict
        """
        for attempt in range(2):
            try:
                response = self.llm.call(
                    prompt=user_prompt,
                    system_prompt=system_prompt,
                    json_mode=True,
                    max_tokens=max_tokens,
                    temperature=0.1,
                )
                return self.llm._parse_json_response(response.content)
            except (ValueError, json.JSONDecodeError) as e:
                error_msg = str(e)
                if attempt == 0:
                    logger.warning(
                        f"[{self.agent_name}] JSON parse failed, retrying: {error_msg}"
                    )
                    # Retry with explicit instruction and specific error
                    user_prompt += (
                        f"\n\nIMPORTANT: Your previous response was invalid JSON. "
                        f"Error: {error_msg}\n"
                        "Please fix this error and respond ONLY with valid JSON. "
                        "No markdown, no explanation, just the JSON object."
                    )
                else:
                    logger.error(
                        f"[{self.agent_name}] JSON parse failed on retry: {error_msg}"
                    )
                    # Use a fallback empty result or raise? 
                    # Raising allows the dashboard to show the error.
                    raise
            except LLMProviderError as e:
                logger.error(f"[{self.agent_name}] LLM call failed: {e}")
                raise

    def _extract_findings(self, result: dict) -> list[dict]:
        """
        Extract and normalize findings from agent response.

        Ensures each finding has required fields with defaults.
        """
        findings = result.get("findings", [])
        normalized = []

        for f in findings:
            normalized.append({
                "agent_name": self.agent_name,
                "finding_type": f.get("finding_type", "unknown"),
                "title": f.get("title", "Untitled Finding"),
                "description": f.get("description", ""),
                "severity": f.get("severity", "medium").lower(),
                "confidence": float(f.get("confidence", 50)),
                "evidence": f.get("evidence", []),
                "industry_benchmark": f.get("industry_benchmark", {}),
                "requires_human_review": (
                    float(f.get("confidence", 50)) < 70
                    or f.get("severity", "").lower() == "critical"
                ),
            })

        return normalized

    def _format_data_for_prompt(self, data: dict, max_chars: int = 8000) -> str:
        """Format financial data dict into readable text for the prompt."""
        text = json.dumps(data, indent=2, default=str)
        if len(text) > max_chars:
            text = text[:max_chars] + "\n... [truncated]"
        return text
