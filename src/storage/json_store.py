"""
JSON-file storage backend for MVP testing.

Stores all analysis data in local JSON files — no Docker/PostgreSQL needed.
Data lives in data/analyses/ directory.
"""
import json
import uuid
import os
from pathlib import Path
from datetime import datetime
from typing import Optional

from loguru import logger


DATA_DIR = Path(__file__).parent.parent.parent / "data" / "analyses"


class JSONStorage:
    """
    File-based storage for MVP testing.
    Each analysis gets its own JSON file in data/analyses/.
    """

    def __init__(self, data_dir: Optional[str] = None):
        self.data_dir = Path(data_dir) if data_dir else DATA_DIR
        self.data_dir.mkdir(parents=True, exist_ok=True)

    # ---- Analyses ----

    def create_analysis(
        self,
        ticker: str,
        company_name: str = "",
        sector: str = "",
        analysis_depth: str = "full",
        hitl_mode: str = "interactive",
        user_id: str = "default",
    ) -> str:
        """Create a new analysis. Returns analysis_id."""
        analysis_id = str(uuid.uuid4())[:8]  # Short ID for readability
        analysis = {
            "id": analysis_id,
            "company_ticker": ticker,
            "company_name": company_name,
            "sector": sector,
            "analysis_depth": analysis_depth,
            "status": "running",
            "risk_score": None,
            "findings_count": 0,
            "hitl_mode": hitl_mode,
            "user_id": user_id,
            "started_at": datetime.utcnow().isoformat(),
            "completed_at": None,
            "findings": [],
            "feedback": [],
            "report": {},
            "raw_data": {},
        }
        self._save(analysis_id, analysis)
        logger.info(f"Created analysis {analysis_id} for {ticker}")
        return analysis_id

    def update_analysis_status(
        self,
        analysis_id: str,
        status: str,
        risk_score: Optional[float] = None,
        findings_count: Optional[int] = None,
    ):
        """Update analysis status."""
        data = self._load(analysis_id)
        if not data:
            return
        data["status"] = status
        if risk_score is not None:
            data["risk_score"] = risk_score
        if findings_count is not None:
            data["findings_count"] = findings_count
        if status == "complete":
            data["completed_at"] = datetime.utcnow().isoformat()
        self._save(analysis_id, data)

    def get_analysis(self, analysis_id: str) -> Optional[dict]:
        return self._load(analysis_id)

    def get_recent_analyses(self, limit: int = 20) -> list[dict]:
        """Get recent analyses sorted by date."""
        analyses = []
        for f in sorted(self.data_dir.glob("*.json"), reverse=True):
            try:
                with open(f) as fh:
                    analyses.append(json.load(fh))
            except Exception:
                continue
            if len(analyses) >= limit:
                break
        return analyses

    # ---- Findings ----

    def store_finding(
        self,
        analysis_id: str,
        agent_name: str,
        finding_type: str,
        title: str,
        description: str,
        severity: str = "medium",
        confidence: float = 50.0,
        evidence: list = None,
        industry_benchmark: dict = None,
        requires_human_review: bool = False,
        iteration: int = 1,
    ) -> str:
        """Store a finding in the analysis file."""
        finding_id = str(uuid.uuid4())[:8]
        data = self._load(analysis_id)
        if not data:
            return finding_id

        finding = {
            "id": finding_id,
            "agent_name": agent_name,
            "finding_type": finding_type,
            "title": title,
            "description": description,
            "severity": severity,
            "confidence": confidence,
            "evidence": evidence or [],
            "industry_benchmark": industry_benchmark or {},
            "requires_human_review": requires_human_review,
            "user_validation": None,
            "iteration": iteration,
            "created_at": datetime.utcnow().isoformat(),
        }
        data["findings"].append(finding)
        self._save(analysis_id, data)
        return finding_id

    def get_findings(
        self, analysis_id: str, agent_name: Optional[str] = None
    ) -> list[dict]:
        data = self._load(analysis_id)
        if not data:
            return []
        findings = data.get("findings", [])
        if agent_name:
            findings = [f for f in findings if f["agent_name"] == agent_name]
        return findings

    def update_finding_validation(
        self, finding_id: str, analysis_id: str, validation: str,
        adjusted_confidence: Optional[float] = None,
    ):
        """Update user validation on a finding."""
        data = self._load(analysis_id)
        if not data:
            return
        for f in data.get("findings", []):
            if f["id"] == finding_id:
                f["user_validation"] = validation
                if adjusted_confidence is not None:
                    f["adjusted_confidence"] = adjusted_confidence
                break
        self._save(analysis_id, data)

    # ---- Feedback ----

    def store_feedback(
        self,
        feedback_type: str,
        content: str,
        finding_id: Optional[str] = None,
        analysis_id: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Store user feedback."""
        feedback_id = str(uuid.uuid4())[:8]
        feedback = {
            "id": feedback_id,
            "feedback_type": feedback_type,
            "content": content,
            "finding_id": finding_id,
            "created_at": datetime.utcnow().isoformat(),
            **{k: v for k, v in kwargs.items() if v},
        }

        if analysis_id:
            data = self._load(analysis_id)
            if data:
                data.setdefault("feedback", []).append(feedback)
                self._save(analysis_id, data)

        # Also save to global feedback file
        fb_file = self.data_dir / "_all_feedback.json"
        all_fb = []
        if fb_file.exists():
            with open(fb_file) as f:
                all_fb = json.load(f)
        all_fb.append(feedback)
        with open(fb_file, "w") as f:
            json.dump(all_fb, f, indent=2, default=str)

        return feedback_id

    def get_feedback_history(
        self, company_ticker: Optional[str] = None, **kwargs
    ) -> list[dict]:
        fb_file = self.data_dir / "_all_feedback.json"
        if not fb_file.exists():
            return []
        with open(fb_file) as f:
            all_fb = json.load(f)
        if company_ticker:
            all_fb = [
                fb for fb in all_fb
                if fb.get("company_ticker") == company_ticker
            ]
        return all_fb

    # ---- Session (minimal) ----

    def create_session(self, analysis_id: str) -> str:
        return analysis_id  # Session = analysis for MVP

    def update_session(self, session_id: str, **kwargs):
        pass  # No-op for MVP

    # ---- Storage helpers ----

    def save_report(self, analysis_id: str, report: dict):
        """Save the full report."""
        data = self._load(analysis_id)
        if data:
            data["report"] = report
            self._save(analysis_id, data)

    def save_raw_data(self, analysis_id: str, raw_data: dict):
        """Save raw scraped data for inspection."""
        data = self._load(analysis_id)
        if data:
            data["raw_data"] = raw_data
            self._save(analysis_id, data)

    def health_check(self) -> bool:
        return self.data_dir.exists()

    def _save(self, analysis_id: str, data: dict):
        filepath = self.data_dir / f"{analysis_id}.json"
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2, default=str)

    def _load(self, analysis_id: str) -> Optional[dict]:
        filepath = self.data_dir / f"{analysis_id}.json"
        if not filepath.exists():
            return None
        with open(filepath) as f:
            return json.load(f)
