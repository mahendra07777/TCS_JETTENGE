"""
BugPulse AI - SQLite Persistence & Daily Pulse Engine
Includes:
1. SQLite schema for tickets and human RLHF feedback
2. Auto-seeding with 25 realistic enterprise tickets on initial run
3. Executive Daily Pulse aggregator (Feature 10)
4. Human 👍/👎 feedback logger (Feature 9)
"""

import os
import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Optional, Any

from schema import (
    ProcessedBugRecord,
    DailyPulseSummary,
    MaskingAuditReport,
    StructuredBugSummary,
    SecondAIQualityEvaluation,
    InputReportGrade,
    MissingInfoCheck,
    SuggestedPriority,
    EpistemicClaim
)
from preprocessor import Preprocessor
from agents_and_eval import BugSummarizerEngine, DuplicateBugClusterer
from fake_bug_factory import generate_sample_batch_csv


DB_PATH = os.path.join(os.path.dirname(__file__), "bugpulse_state.db")


class DatabaseManager:
    """Manages SQLite persistence and analytics aggregation for BugPulse AI."""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Initializes tables if they do not exist."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS processed_bugs (
                    bug_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    title TEXT NOT NULL,
                    component TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    reported_severity TEXT,
                    severity_mismatch_alert INTEGER DEFAULT 0,
                    grade TEXT NOT NULL,
                    numeric_score INTEGER NOT NULL,
                    masked_count INTEGER NOT NULL,
                    compression_ratio REAL NOT NULL,
                    quality_score REAL NOT NULL,
                    passed_85 INTEGER DEFAULT 1,
                    cluster_label TEXT,
                    human_feedback TEXT,
                    json_data TEXT NOT NULL
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS human_feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bug_id TEXT NOT NULL,
                    vote TEXT NOT NULL,
                    comment TEXT,
                    created_at TEXT NOT NULL
                )
            """)
            conn.commit()

    def count_records(self) -> int:
        """Returns total number of processed records in database."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM processed_bugs")
            return cursor.fetchone()[0]

    def save_processed_bug(self, record: ProcessedBugRecord):
        """Inserts or replaces a processed bug record."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO processed_bugs (
                    bug_id, created_at, title, component, priority,
                    reported_severity, severity_mismatch_alert, grade,
                    numeric_score, masked_count, compression_ratio,
                    quality_score, passed_85, cluster_label,
                    human_feedback, json_data
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record.bug_id,
                record.created_at,
                record.summary.title,
                record.summary.component,
                record.summary.suggested_priority.level,
                record.reported_severity or record.summary.suggested_priority.reported_severity,
                1 if record.summary.suggested_priority.severity_mismatch_alert else 0,
                record.summary.report_grade.letter_grade,
                record.summary.report_grade.numeric_score,
                record.audit.total_masked,
                record.audit.log_compression_ratio,
                record.evaluation.overall_quality_score,
                1 if record.evaluation.passed_85_gate else 0,
                record.duplicate_group_label,
                record.human_feedback,
                record.model_dump_json()
            ))
            conn.commit()

    def record_human_feedback(self, bug_id: str, vote: str, comment: Optional[str] = None):
        """Feature 9: Records human RLHF 👍 / 👎 feedback."""
        now = datetime.now().isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO human_feedback (bug_id, vote, comment, created_at)
                VALUES (?, ?, ?, ?)
            """, (bug_id, vote, comment, now))

            cursor.execute("""
                UPDATE processed_bugs
                SET human_feedback = ?
                WHERE bug_id = ?
            """, (vote, bug_id))
            conn.commit()

    def get_all_records(self) -> List[ProcessedBugRecord]:
        """Retrieves all processed bug records."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT json_data FROM processed_bugs ORDER BY created_at DESC")
            rows = cursor.fetchall()

        records = []
        for r in rows:
            data = json.loads(r["json_data"])
            records.append(ProcessedBugRecord(**data))
        return records

    def get_record(self, bug_id: str) -> Optional[ProcessedBugRecord]:
        """Fetches single record by bug_id."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT json_data FROM processed_bugs WHERE bug_id = ?", (bug_id,))
            row = cursor.fetchone()
            if row:
                return ProcessedBugRecord(**json.loads(row["json_data"]))
        return None

    def get_daily_pulse_summary(self) -> DailyPulseSummary:
        """Feature 10: Aggregates daily telemetry for executive ribbon & charts."""
        records = self.get_all_records()
        if not records:
            return DailyPulseSummary(
                executive_headline="Daily Pulse: No reports processed yet. Ready for ingestion.",
                total_reports=0,
                total_duplicates=0,
                high_priority_count=0,
                medium_priority_count=0,
                low_priority_count=0,
                avg_quality_score=0.0,
                target_85_met=True,
                component_breakdown={},
                human_approval_rate=100.0
            )

        total = len(records)
        high = sum(1 for r in records if r.summary.suggested_priority.level == "High")
        med = sum(1 for r in records if r.summary.suggested_priority.level == "Medium")
        low = sum(1 for r in records if r.summary.suggested_priority.level == "Low")

        dup_count = sum(1 for r in records if r.duplicate_group_label and not r.duplicate_group_label.startswith("1 report"))

        avg_q = round(sum(r.evaluation.overall_quality_score for r in records) / total, 1)

        # Component distribution
        comp_counts: Dict[str, int] = {}
        for r in records:
            c = r.summary.component
            comp_counts[c] = comp_counts.get(c, 0) + 1

        top_comp = max(comp_counts.items(), key=lambda x: x[1])[0] if comp_counts else "System"

        # Approval rate
        votes = [r.human_feedback for r in records if r.human_feedback is not None]
        if votes:
            approval_rate = round((sum(1 for v in votes if v == "UP") / len(votes)) * 100.0, 1)
        else:
            approval_rate = 100.0

        headline = (
            f"🔥 Daily Pulse: {high} serious bugs, {dup_count} duplicates grouped, "
            f"{top_comp} module requires immediate attention ({comp_counts.get(top_comp, 0)} reports)"
        )

        return DailyPulseSummary(
            executive_headline=headline,
            total_reports=total,
            total_duplicates=dup_count,
            high_priority_count=high,
            medium_priority_count=med,
            low_priority_count=low,
            avg_quality_score=avg_q,
            target_85_met=(avg_q >= 85.0),
            component_breakdown=comp_counts,
            human_approval_rate=approval_rate
        )

    def reseed_data(self, csv_path: Optional[str] = None):
        """Clears existing records and re-seeds with fresh enterprise batch."""
        with self._get_connection() as conn:
            c = conn.cursor()
            c.execute("DELETE FROM processed_bugs")
            c.execute("DELETE FROM human_feedback")
            conn.commit()
        self.seed_initial_enterprise_dataset(csv_path)

    def seed_initial_enterprise_dataset(self, csv_path: Optional[str] = None):
        """Pre-seeds the database with the 25-report realistic enterprise batch."""
        if self.count_records() > 0:
            return  # Already seeded

        if not csv_path or not os.path.exists(csv_path):
            csv_path = generate_sample_batch_csv(os.path.join(os.path.dirname(__file__), "sample_enterprise_bug_batch.csv"))

        import pandas as pd
        df = pd.read_csv(csv_path)

        engine = BugSummarizerEngine()
        prep = Preprocessor()

        raw_records_for_clustering = df.to_dict(orient="records")
        clusters = DuplicateBugClusterer.cluster_reports(raw_records_for_clustering, similarity_threshold=0.35)

        cluster_map: Dict[str, str] = {}
        for c in clusters:
            for b_id in c.bug_ids:
                cluster_map[b_id] = c.cluster_title

        now = datetime.now().isoformat()
        for _, row in df.iterrows():
            b_id = str(row.get("bug_id", "BUG-UNKNOWN"))
            title = str(row.get("title", ""))
            desc = str(row.get("description", ""))
            raw_text = f"{title}\n{desc}"
            reported_sev = str(row.get("reported_severity", "Medium"))
            comp = str(row.get("component", "General"))

            audit = prep.mask_pii_and_secrets(raw_text)
            summary, eval_res = engine.run_pipeline(
                raw_text=raw_text,
                reported_severity=reported_sev,
                component_hint=comp
            )

            record = ProcessedBugRecord(
                bug_id=b_id,
                created_at=now,
                reported_severity=reported_sev,
                reported_status=str(row.get("reported_status", "New")),
                audit=audit,
                summary=summary,
                evaluation=eval_res,
                duplicate_group_id=None,
                duplicate_group_label=cluster_map.get(b_id, "Individual Ticket"),
                human_feedback="UP" if eval_res.overall_quality_score >= 88.0 else None,
                human_comment=None
            )
            self.save_processed_bug(record)


# Singleton instance
db_instance = DatabaseManager()

if __name__ == "__main__":
    db_instance.seed_initial_enterprise_dataset()
    pulse = db_instance.get_daily_pulse_summary()
    print("Database seeded successfully!")
    print(pulse.executive_headline.encode('ascii', errors='replace').decode('ascii'))
    print(f"Total reports: {pulse.total_reports}, Avg Quality: {pulse.avg_quality_score}%")
