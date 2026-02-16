import sys
import os

# Add src to path
sys.path.append(os.getcwd())

from src.agents.rpt import RPTAgent
from duckduckgo_search import DDGS

try:
    agent = RPTAgent(llm=None) # Mock LLM
    print("Testing RPT Search...")
    results = agent._perform_rpt_searches("Brightcom Group Ltd", "BCG", DDGS)
    print("Search Results Sample:\n")
    print(results[:500] + "...")
    print("\n✅ RPT Search verification successful")
except Exception as e:
    print(f"❌ RPT Search failed: {e}")
