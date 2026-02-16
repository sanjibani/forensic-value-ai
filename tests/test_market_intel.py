import pytest
from unittest.mock import MagicMock, patch
from src.agents.market_intelligence import MarketIntelligenceAgent
from src.llm.provider import LLMProvider, LLMResponse, TokenUsage

@pytest.fixture
def mock_llm():
    llm = MagicMock(spec=LLMProvider)
    llm.call.return_value = LLMResponse(
        content='{"findings": [{"title": "Fraud Allegation", "severity": "high", "confidence": 90}], "summary": "Bad news found", "sentiment_score": 20}',
        usage=TokenUsage(input_tokens=10, output_tokens=10, model="test-model")
    )
    llm._parse_json_response.return_value = {
        "findings": [{"title": "Fraud Allegation", "severity": "high", "confidence": 90}],
        "summary": "Bad news found",
        "sentiment_score": 20
    }
    return llm

@pytest.fixture
def agent(mock_llm):
    return MarketIntelligenceAgent(mock_llm)

@patch("src.agents.market_intelligence.DDGS")
def test_analyze_with_search(mock_ddgs_cls, agent):
    # Mock DDGS instance
    mock_ddgs_inst = MagicMock()
    mock_ddgs_cls.return_value = mock_ddgs_inst
    
    # Mock search results
    mock_ddgs_inst.text.return_value = [
        {"title": "BCG Fraud", "href": "http://news.com", "body": "SEBI banned BCG"}
    ]
    
    state = {
        "company_data": {"ticker": "BCG", "company_name": "Brightcom Group"},
        "memory_context": ""
    }
    
    result = agent.analyze(state)
    
    assert "market_intel_findings" in result
    assert len(result["market_intel_findings"]) == 1
    assert result["market_intel_findings"][0]["title"] == "Fraud Allegation"
    assert result["market_sentiment_score"] == 20.0
    
    # Verify search was called
    assert mock_ddgs_inst.text.called

@patch("src.agents.market_intelligence.DDGS", None)
def test_analyze_without_search_lib(agent):
    # Simulate ImportErrpr by mocking DDGS as None
    state = {
        "company_data": {"ticker": "BCG"},
        "memory_context": ""
    }
    
    result = agent.analyze(state)
    
    # Should still run LLM with "unavailable" message
    assert "market_intel_findings" in result
    assert result["market_sentiment_score"] == 20.0
