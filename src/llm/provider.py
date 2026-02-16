"""
LLM Provider — Multi-provider abstraction with automatic fallback.

Supports:
  1. Google Gemini (free tier)
  2. Antigravity Claude Proxy (free, Anthropic-compatible)
  3. OpenRouter (paid fallback)
"""
import json
import time
from typing import Optional
from dataclasses import dataclass, field

import requests
from loguru import logger

from src.config import settings


@dataclass
class TokenUsage:
    """Track token usage across providers."""
    input_tokens: int = 0
    output_tokens: int = 0
    provider: str = ""
    model: str = ""
    latency_ms: float = 0


@dataclass
class LLMResponse:
    """Standardized response from any provider."""
    content: str
    usage: TokenUsage = field(default_factory=TokenUsage)
    raw_response: Optional[dict] = None


class LLMProviderError(Exception):
    """Raised when an LLM provider call fails."""
    pass


class RateLimitError(LLMProviderError):
    """Raised when rate limited by a provider."""
    pass


class LLMProvider:
    """
    Multi-provider LLM client with automatic fallback.

    Falls back through providers in order:
    Gemini → Antigravity Proxy → OpenRouter
    """

    GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models"
    GEMINI_MODEL = "gemini-2.5-pro-preview-06-05"

    def __init__(self):
        self._providers = self._build_provider_chain()
        self._current_idx = 0
        self._total_usage = {"input": 0, "output": 0, "calls": 0}
        logger.info(
            f"LLM provider initialized with {len(self._providers)} providers: "
            f"{[p['name'] for p in self._providers]}"
        )

    def _build_provider_chain(self) -> list[dict]:
        """Build ordered list of available providers."""
        providers = []

        # 1. Google Gemini (free tier)
        if settings.google_api_key:
            providers.append({
                "name": "gemini",
                "call": self._call_gemini,
                "free": True,
            })

        # 2. Antigravity Claude Proxy
        if settings.antigravity_enabled:
            providers.append({
                "name": "antigravity",
                "call": self._call_antigravity,
                "free": True,
            })

        # 3. OpenRouter (paid fallback)
        if settings.openrouter_api_key:
            providers.append({
                "name": "openrouter",
                "call": self._call_openrouter,
                "free": False,
            })

        if not providers:
            logger.warning(
                "No LLM providers configured! Set GOOGLE_API_KEY, "
                "ANTIGRAVITY_ENABLED, or OPENROUTER_API_KEY in .env"
            )
            # Add a dummy provider that returns helpful errors
            providers.append({
                "name": "none",
                "call": self._call_none,
                "free": True,
            })

        return providers

    def call(
        self,
        prompt: str,
        system_prompt: str = "",
        json_mode: bool = False,
        max_tokens: int = 4096,
        temperature: float = 0.2,
    ) -> LLMResponse:
        """
        Call the LLM with automatic provider fallback.

        Args:
            prompt: User prompt text
            system_prompt: System/context prompt
            json_mode: Request JSON-formatted output
            max_tokens: Maximum output tokens
            temperature: Sampling temperature (lower = more deterministic)

        Returns:
            LLMResponse with content and usage stats
        """
        errors = []

        for attempt in range(len(self._providers)):
            idx = (self._current_idx + attempt) % len(self._providers)
            provider = self._providers[idx]

            try:
                start = time.time()
                response = provider["call"](
                    prompt=prompt,
                    system_prompt=system_prompt,
                    json_mode=json_mode,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                elapsed = (time.time() - start) * 1000
                response.usage.latency_ms = elapsed
                response.usage.provider = provider["name"]

                self._total_usage["input"] += response.usage.input_tokens
                self._total_usage["output"] += response.usage.output_tokens
                self._total_usage["calls"] += 1

                logger.debug(
                    f"[{provider['name']}] {elapsed:.0f}ms | "
                    f"in={response.usage.input_tokens} out={response.usage.output_tokens}"
                )
                return response

            except RateLimitError as e:
                logger.warning(f"[{provider['name']}] Rate limited: {e}")
                errors.append(f"{provider['name']}: rate limited")
                continue

            except Exception as e:
                logger.error(f"[{provider['name']}] Failed: {e}")
                errors.append(f"{provider['name']}: {e}")
                continue

        raise LLMProviderError(
            f"All LLM providers failed. Errors: {'; '.join(errors)}"
        )

    def call_json(
        self,
        prompt: str,
        system_prompt: str = "",
        max_tokens: int = 4096,
        temperature: float = 0.1,
    ) -> dict:
        """Call LLM and parse the response as JSON."""
        response = self.call(
            prompt=prompt,
            system_prompt=system_prompt,
            json_mode=True,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return self._parse_json_response(response.content)

    def get_usage_stats(self) -> dict:
        return dict(self._total_usage)

    # ---- Provider-specific implementations ----

    def _call_gemini(
        self, prompt: str, system_prompt: str, json_mode: bool,
        max_tokens: int, temperature: float,
    ) -> LLMResponse:
        """Call Google Gemini API directly."""
        url = f"{self.GEMINI_URL}/{self.GEMINI_MODEL}:generateContent"
        params = {"key": settings.google_api_key}

        contents = []
        if system_prompt:
            contents.append({
                "role": "user",
                "parts": [{"text": f"[System Instructions]\n{system_prompt}"}],
            })
            contents.append({
                "role": "model",
                "parts": [{"text": "I understand. I will follow these instructions."}],
            })
        contents.append({"role": "user", "parts": [{"text": prompt}]})

        body = {
            "contents": contents,
            "generationConfig": {
                "maxOutputTokens": max_tokens,
                "temperature": temperature,
            },
        }
        if json_mode:
            body["generationConfig"]["responseMimeType"] = "application/json"

        resp = requests.post(url, params=params, json=body, timeout=120)

        if resp.status_code == 429:
            raise RateLimitError("Gemini rate limit reached")
        if resp.status_code != 200:
            raise LLMProviderError(
                f"Gemini API error {resp.status_code}: {resp.text[:300]}"
            )

        data = resp.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        usage_meta = data.get("usageMetadata", {})

        return LLMResponse(
            content=text,
            usage=TokenUsage(
                input_tokens=usage_meta.get("promptTokenCount", 0),
                output_tokens=usage_meta.get("candidatesTokenCount", 0),
                model=self.GEMINI_MODEL,
            ),
            raw_response=data,
        )

    def _call_antigravity(
        self, prompt: str, system_prompt: str, json_mode: bool,
        max_tokens: int, temperature: float,
    ) -> LLMResponse:
        """Call Antigravity Claude Proxy (Anthropic-compatible API)."""
        url = f"{settings.antigravity_proxy_url}/v1/messages"
        headers = {
            "Content-Type": "application/json",
            "x-api-key": "dummy-key",  # Proxy handles auth
            "anthropic-version": "2023-06-01",
        }

        messages = [{"role": "user", "content": prompt}]
        body = {
            "model": "claude-sonnet-4-20250514",
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": messages,
        }
        if system_prompt:
            body["system"] = system_prompt

        resp = requests.post(url, headers=headers, json=body, timeout=120)

        if resp.status_code == 429:
            raise RateLimitError("Antigravity proxy rate limit")
        if resp.status_code != 200:
            raise LLMProviderError(
                f"Antigravity error {resp.status_code}: {resp.text[:300]}"
            )

        data = resp.json()
        text = data["content"][0]["text"]
        usage = data.get("usage", {})

        return LLMResponse(
            content=text,
            usage=TokenUsage(
                input_tokens=usage.get("input_tokens", 0),
                output_tokens=usage.get("output_tokens", 0),
                model=data.get("model", "antigravity-proxy"),
            ),
            raw_response=data,
        )

    def _call_openrouter(
        self, prompt: str, system_prompt: str, json_mode: bool,
        max_tokens: int, temperature: float,
    ) -> LLMResponse:
        """Call OpenRouter API (OpenAI-compatible)."""
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.openrouter_api_key}",
            "Content-Type": "application/json",
        }

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        body = {
            "model": "google/gemini-2.5-pro-preview",
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}

        resp = requests.post(url, headers=headers, json=body, timeout=120)

        if resp.status_code == 429:
            raise RateLimitError("OpenRouter rate limit")
        if resp.status_code != 200:
            raise LLMProviderError(
                f"OpenRouter error {resp.status_code}: {resp.text[:300]}"
            )

        data = resp.json()
        text = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})

        return LLMResponse(
            content=text,
            usage=TokenUsage(
                input_tokens=usage.get("prompt_tokens", 0),
                output_tokens=usage.get("completion_tokens", 0),
                model=data.get("model", "openrouter"),
            ),
            raw_response=data,
        )

    def _call_none(self, **kwargs) -> LLMResponse:
        raise LLMProviderError(
            "No LLM providers configured. "
            "Please set GOOGLE_API_KEY in your .env file."
        )

    @staticmethod
    def _parse_json_response(text: str) -> dict:
        """Extract and parse JSON from LLM response text."""
        text = text.strip()

        # Try direct parse first
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try extracting from markdown code blocks
        if "```json" in text:
            start = text.index("```json") + 7
            end = text.index("```", start)
            try:
                return json.loads(text[start:end].strip())
            except json.JSONDecodeError:
                pass

        if "```" in text:
            start = text.index("```") + 3
            end = text.index("```", start)
            try:
                return json.loads(text[start:end].strip())
            except json.JSONDecodeError:
                pass

        # Try finding JSON object boundaries
        brace_start = text.find("{")
        brace_end = text.rfind("}") + 1
        if brace_start != -1 and brace_end > brace_start:
            try:
                return json.loads(text[brace_start:brace_end])
            except json.JSONDecodeError:
                pass

        # Fallback: Use json_repair
        try:
            import json_repair
            repaired = json_repair.loads(text)
            logger.warning("Repaired malformed JSON with json_repair")
            return repaired
        except Exception as e:
            logger.error(f"json_repair failed: {e}")

        raise ValueError(f"Could not parse JSON from LLM response: {text[:200]}")
