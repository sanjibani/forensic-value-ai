"""
Basic tests for ForensicValue AI core modules.
"""
import json
import pytest
from unittest.mock import MagicMock, patch

# -- Config tests --

def test_config_loads():
    """Settings class initializes with defaults."""
    from src.config import Settings
    s = Settings(
        GOOGLE_API_KEY="test-key",
        POSTGRES_PORT=5433,
    )
    assert s.google_api_key == "test-key"
    assert s.postgres_port == 5433
    assert "postgresql://" in s.postgres_url


def test_config_postgres_url():
    from src.config import Settings
    s = Settings(
        POSTGRES_USER="user",
        POSTGRES_PASSWORD="pass",
        POSTGRES_HOST="localhost",
        POSTGRES_PORT=5433,
        POSTGRES_DB="testdb",
    )
    assert s.postgres_url == "postgresql://user:pass@localhost:5433/testdb"


# -- LLM Provider tests --

def test_llm_provider_no_keys():
    """Provider initializes with dummy provider when no keys set."""
    with patch.dict("os.environ", {}, clear=True):
        from src.llm.provider import LLMProvider, LLMProviderError
        provider = LLMProvider()
        assert len(provider._providers) >= 1
        assert provider._providers[-1]["name"] in ("none", "gemini", "antigravity", "openrouter")


def test_llm_parse_json_direct():
    """JSON parser handles direct JSON."""
    from src.llm.provider import LLMProvider
    result = LLMProvider._parse_json_response('{"key": "value"}')
    assert result == {"key": "value"}


def test_llm_parse_json_markdown():
    """JSON parser handles markdown-wrapped JSON."""
    from src.llm.provider import LLMProvider
    text = '```json\n{"key": "value"}\n```'
    result = LLMProvider._parse_json_response(text)
    assert result == {"key": "value"}


def test_llm_parse_json_embedded():
    """JSON parser handles JSON embedded in text."""
    from src.llm.provider import LLMProvider
    text = 'Here is the result:\n{"findings": [1, 2, 3]}\nDone.'
    result = LLMProvider._parse_json_response(text)
    assert result == {"findings": [1, 2, 3]}


# -- Agent tests --

def test_base_agent_extract_findings():
    """BaseAgent normalizes findings with defaults."""
    from src.agents.base import BaseAgent
    from src.llm.provider import LLMProvider

    class TestAgent(BaseAgent):
        agent_name = "test"
        def analyze(self, state):
            return state

    llm = MagicMock(spec=LLMProvider)
    agent = TestAgent(llm)

    result = {
        "findings": [
            {"title": "Test Finding", "confidence": 85, "severity": "high"},
            {"title": "Low Conf", "confidence": 40},
        ]
    }
    findings = agent._extract_findings(result)

    assert len(findings) == 2
    assert findings[0]["agent_name"] == "test"
    assert findings[0]["severity"] == "high"
    assert findings[0]["confidence"] == 85.0
    assert findings[0]["requires_human_review"] is False  # confidence > 70

    assert findings[1]["confidence"] == 40.0
    assert findings[1]["requires_human_review"] is True  # confidence < 70


def test_forensic_agent_sets_state():
    """ForensicAccountingAgent updates state correctly."""
    from src.agents.forensic import ForensicAccountingAgent
    from src.llm.provider import LLMProvider

    mock_llm = MagicMock(spec=LLMProvider)
    mock_response = MagicMock()
    mock_response.content = json.dumps({
        "findings": [
            {"finding_type": "revenue_quality", "title": "CFO/PAT low",
             "description": "test", "severity": "high", "confidence": 75}
        ],
        "summary": "Some concerns.",
        "overall_risk_score": 62
    })
    mock_llm.call.return_value = mock_response
    mock_llm._parse_json_response = LLMProvider._parse_json_response

    agent = ForensicAccountingAgent(mock_llm)
    state = {
        "company_data": {"ticker": "TEST", "company_name": "Test Ltd", "sector": "IT", "financials": {}},
        "memory_context": "None",
    }
    result = agent.analyze(state)

    assert "forensic_findings" in result
    assert len(result["forensic_findings"]) == 1
    assert result["forensic_risk_score"] == 62.0
    assert "forensic" in result["research_path"]


# -- Confidence adjustment tests --

def test_confidence_boost():
    from src.memory.confidence import calculate_adjusted_confidence
    adjusted, delta = calculate_adjusted_confidence(
        base_confidence=60.0,
        similar_approved=[{"score": 0.9}, {"score": 0.85}],
        similar_rejected=[],
        matching_patterns=[],
    )
    assert adjusted > 60.0
    assert delta > 0


def test_confidence_penalty():
    from src.memory.confidence import calculate_adjusted_confidence
    adjusted, delta = calculate_adjusted_confidence(
        base_confidence=60.0,
        similar_approved=[],
        similar_rejected=[{"score": 0.9}, {"score": 0.88}],
        matching_patterns=[],
    )
    assert adjusted < 60.0
    assert delta < 0


def test_confidence_clamped():
    from src.memory.confidence import calculate_adjusted_confidence
    # Very high base + big boost should not exceed 100
    adjusted, _ = calculate_adjusted_confidence(
        base_confidence=98.0,
        similar_approved=[{"score": 1.0}] * 5,
        similar_rejected=[],
        matching_patterns=[{"match": True}] * 3,
    )
    assert adjusted <= 100.0


# -- Data fetcher tests --

def test_sample_data():
    from src.data.fetcher import DataFetcher
    fetcher = DataFetcher()
    sample = fetcher.build_sample_data("INFY")
    assert sample["ticker"] == "INFY"
    assert "Revenue" in sample["financials"]
    assert "Promoter" in sample["shareholding"]
    assert "ratios" in sample


# -- State tests --

def test_state_keys():
    """ForensicState has expected keys."""
    from src.graph.state import ForensicState
    import typing
    hints = typing.get_type_hints(ForensicState)
    assert "company_data" in hints
    assert "forensic_findings" in hints
    assert "overall_risk_score" in hints
    assert "messages" in hints
