"""
PostgreSQL storage manager for ForensicValue AI.
"""
import uuid
from typing import Optional
from datetime import datetime

import psycopg2
import psycopg2.extras
from loguru import logger

from src.config import settings

# Register UUID adapter
psycopg2.extras.register_uuid()


class PostgresManager:
    """Manages PostgreSQL connections and operations."""

    def __init__(self):
        self._conn_params = {
            "dbname": settings.postgres_db,
            "user": settings.postgres_user,
            "password": settings.postgres_password,
            "host": settings.postgres_host,
            "port": settings.postgres_port,
        }

    def _connect(self):
        return psycopg2.connect(**self._conn_params)

    # ---- Stock Analyses ----

    def create_analysis(
        self,
        ticker: str,
        company_name: str = "",
        sector: str = "",
        analysis_depth: str = "full",
        hitl_mode: str = "interactive",
        user_id: str = "default",
    ) -> str:
        """Create a new stock analysis record. Returns analysis_id."""
        analysis_id = str(uuid.uuid4())
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO stock_analyses
                        (id, company_ticker, company_name, sector,
                         analysis_depth, hitl_mode, user_id, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 'running')
                    """,
                    (analysis_id, ticker, company_name, sector,
                     analysis_depth, hitl_mode, user_id),
                )
                conn.commit()
        logger.info(f"Created analysis {analysis_id} for {ticker}")
        return analysis_id

    def update_analysis_status(
        self,
        analysis_id: str,
        status: str,
        risk_score: Optional[float] = None,
        findings_count: Optional[int] = None,
    ):
        """Update analysis status and optional fields."""
        with self._connect() as conn:
            with conn.cursor() as cur:
                updates = ["status = %s", "updated_at = NOW()"]
                params = [status]

                if risk_score is not None:
                    updates.append("risk_score = %s")
                    params.append(risk_score)
                if findings_count is not None:
                    updates.append("findings_count = %s")
                    params.append(findings_count)
                if status == "complete":
                    updates.append("completed_at = NOW()")

                params.append(analysis_id)
                cur.execute(
                    f"UPDATE stock_analyses SET {', '.join(updates)} WHERE id = %s",
                    params,
                )
                conn.commit()

    def get_analysis(self, analysis_id: str) -> Optional[dict]:
        """Get a single analysis by ID."""
        with self._connect() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM stock_analyses WHERE id = %s", (analysis_id,)
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def get_recent_analyses(self, limit: int = 20) -> list[dict]:
        """Get recent analyses ordered by creation date."""
        with self._connect() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """SELECT * FROM stock_analyses
                       ORDER BY created_at DESC LIMIT %s""",
                    (limit,),
                )
                return [dict(row) for row in cur.fetchall()]

    # ---- Agent Findings ----

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
        """Store an agent finding. Returns finding_id."""
        finding_id = str(uuid.uuid4())
        import json

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO agent_findings
                        (id, analysis_id, agent_name, finding_type, title,
                         description, severity, confidence, evidence,
                         industry_benchmark, requires_human_review, iteration)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        finding_id, analysis_id, agent_name, finding_type,
                        title, description, severity, confidence,
                        json.dumps(evidence or []),
                        json.dumps(industry_benchmark or {}),
                        requires_human_review, iteration,
                    ),
                )
                conn.commit()
        return finding_id

    def get_findings(
        self,
        analysis_id: str,
        agent_name: Optional[str] = None,
    ) -> list[dict]:
        """Get findings for an analysis, optionally filtered by agent."""
        with self._connect() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                query = "SELECT * FROM agent_findings WHERE analysis_id = %s"
                params = [analysis_id]
                if agent_name:
                    query += " AND agent_name = %s"
                    params.append(agent_name)
                query += " ORDER BY CASE severity WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END"
                cur.execute(query, params)
                return [dict(row) for row in cur.fetchall()]

    def update_finding_validation(
        self,
        finding_id: str,
        validation: str,
        adjusted_confidence: Optional[float] = None,
    ):
        """Update user validation on a finding."""
        with self._connect() as conn:
            with conn.cursor() as cur:
                updates = ["user_validation = %s"]
                params = [validation]
                if adjusted_confidence is not None:
                    updates.append("adjusted_confidence = %s")
                    params.append(adjusted_confidence)
                params.append(finding_id)
                cur.execute(
                    f"UPDATE agent_findings SET {', '.join(updates)} WHERE id = %s",
                    params,
                )
                conn.commit()

    # ---- User Feedback ----

    def store_feedback(
        self,
        feedback_type: str,
        content: str,
        finding_id: Optional[str] = None,
        analysis_id: Optional[str] = None,
        user_id: str = "default",
        company_ticker: str = "",
        sector: str = "",
        agent_name: str = "",
        finding_type: str = "",
        status: str = "",
        reasoning: str = "",
        confidence_adjustment: float = 0.0,
        apply_to_future: bool = False,
        metadata: dict = None,
    ) -> str:
        """Store user feedback. Returns feedback_id."""
        import json

        feedback_id = str(uuid.uuid4())
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO user_feedback
                        (id, finding_id, analysis_id, user_id, feedback_type,
                         company_ticker, sector, agent_name, finding_type,
                         status, content, reasoning, confidence_adjustment,
                         apply_to_future, metadata)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (
                        feedback_id, finding_id, analysis_id, user_id,
                        feedback_type, company_ticker, sector, agent_name,
                        finding_type, status, content, reasoning,
                        confidence_adjustment, apply_to_future,
                        json.dumps(metadata or {}),
                    ),
                )
                conn.commit()
        logger.info(f"Stored feedback {feedback_id} ({feedback_type})")
        return feedback_id

    def get_feedback_history(
        self,
        company_ticker: Optional[str] = None,
        sector: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict]:
        """Get feedback history with optional filters."""
        with self._connect() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                query = "SELECT * FROM user_feedback WHERE 1=1"
                params = []
                if company_ticker:
                    query += " AND company_ticker = %s"
                    params.append(company_ticker)
                if sector:
                    query += " AND sector = %s"
                    params.append(sector)
                query += " ORDER BY created_at DESC LIMIT %s"
                params.append(limit)
                cur.execute(query, params)
                return [dict(row) for row in cur.fetchall()]

    # ---- Analysis Sessions ----

    def create_session(self, analysis_id: str) -> str:
        """Create a workflow session for tracking state."""
        session_id = str(uuid.uuid4())
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO analysis_sessions (id, analysis_id)
                    VALUES (%s, %s)
                    """,
                    (session_id, analysis_id),
                )
                conn.commit()
        return session_id

    def update_session(
        self,
        session_id: str,
        current_step: Optional[str] = None,
        workflow_state: Optional[dict] = None,
        agent_outputs: Optional[dict] = None,
        iteration_count: Optional[int] = None,
    ):
        """Update workflow session state."""
        import json

        with self._connect() as conn:
            with conn.cursor() as cur:
                updates = ["updated_at = NOW()"]
                params = []
                if current_step is not None:
                    updates.append("current_step = %s")
                    params.append(current_step)
                if workflow_state is not None:
                    updates.append("workflow_state = %s")
                    params.append(json.dumps(workflow_state))
                if agent_outputs is not None:
                    updates.append("agent_outputs = %s")
                    params.append(json.dumps(agent_outputs))
                if iteration_count is not None:
                    updates.append("iteration_count = %s")
                    params.append(iteration_count)

                params.append(session_id)
                cur.execute(
                    f"UPDATE analysis_sessions SET {', '.join(updates)} WHERE id = %s",
                    params,
                )
                conn.commit()

    def health_check(self) -> bool:
        """Test database connectivity."""
        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    return True
        except Exception as e:
            logger.error(f"PostgreSQL health check failed: {e}")
            return False
