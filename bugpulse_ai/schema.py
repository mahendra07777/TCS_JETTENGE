"""
BugPulse AI - Canonical Pydantic v2 Data Contracts
Bounded context schema for all 11 enterprise features.
"""

from typing import List, Dict, Optional, Literal, Any
from pydantic import BaseModel, Field


class MaskingAuditReport(BaseModel):
    """Audit report for Pre-AI PII & Secret Masking and Log Compression."""
    total_masked: int = Field(default=0, description="Total sensitive entities masked")
    counts_by_type: Dict[str, int] = Field(
        default_factory=lambda: {"EMAIL": 0, "IP": 0, "PHONE": 0, "ID": 0, "TOKEN": 0, "PERSON": 0},
        description="Masked entity count per category"
    )
    token_map: Dict[str, str] = Field(
        default_factory=dict,
        description="Reversible mapping between masked tokens and raw values"
    )
    raw_text: str = Field(..., description="Original raw bug text before masking")
    masked_text: str = Field(..., description="Sanitized text with code-safe tokens sent to LLM")
    privacy_shield_status: str = Field(
        default="ACTIVE",
        description="Privacy shield compliance state (ACTIVE/BYPASSED)"
    )
    log_compression_ratio: float = Field(
        default=0.0,
        description="Percentage of log lines compressed via Drain3 (e.g., 82.5%)"
    )
    original_line_count: int = Field(default=0, description="Raw line count before compression")
    compressed_line_count: int = Field(default=0, description="Compressed line count sent to LLM")


class EpistemicClaim(BaseModel):
    """
    Epistemic claim badge representation.
    Ensures verifiable hallucination-free output with line citations.
    """
    label: Literal["FACT", "GUESS", "MISSING"] = Field(
        ...,
        description="Epistemic status: FACT (verified in source), GUESS (inferred), or MISSING (absent)"
    )
    text: str = Field(..., description="Content of the claim")
    source_line_number: Optional[int] = Field(
        default=None,
        description="1-based source line index [Lxx] where claim is grounded"
    )
    verbatim_quote: Optional[str] = Field(
        default=None,
        description="Exact substring quoted from the source report for fact-checking"
    )


class MissingInfoCheck(BaseModel):
    """Feature 4: Missing Information Detector and Auto-Drafted Reporter Question."""
    is_steps_missing: bool = Field(default=False, description="True if S2R is missing or vague")
    is_version_missing: bool = Field(default=False, description="True if software/release version is absent")
    is_browser_or_env_missing: bool = Field(default=False, description="True if OS/browser/device info is absent")
    missing_summary_flags: List[str] = Field(
        default_factory=list,
        description="Human-readable badges of missing fields (e.g. ['Steps Missing', 'Version Missing'])"
    )
    question_for_reporter: str = Field(
        default="",
        description="Polite, highly targeted follow-up question ready to send to reporter"
    )


class InputReportGrade(BaseModel):
    """Feature 5: Input Report Quality Grade (A to F) with explainable rubric."""
    letter_grade: Literal["A", "B", "C", "D", "F"] = Field(
        ...,
        description="Input quality letter grade"
    )
    numeric_score: int = Field(..., ge=0, le=100, description="Score from 0 to 100")
    grade_reason: str = Field(..., description="One-line human explanation of the grade")
    rubric_breakdown: Dict[str, int] = Field(
        default_factory=dict,
        description="Detailed score points (S2R, Behavior, Stack Trace/Logs, Environment)"
    )


class SuggestedPriority(BaseModel):
    """Feature 6: AI Calibrated Priority and Severity Mismatch Detection."""
    level: Literal["High", "Medium", "Low"] = Field(
        ...,
        description="AI recommended operational priority"
    )
    one_line_reason: str = Field(..., description="Concise justification citing blast radius or system risk")
    reported_severity: Optional[str] = Field(
        default=None,
        description="Original severity reported by user in ticket metadata"
    )
    severity_mismatch_alert: bool = Field(
        default=False,
        description="True if AI priority differs from reporter severity (e.g., user marked Low on a crash)"
    )


class StructuredBugSummary(BaseModel):
    """
    Feature 2: Canonical 6-Block Structured Bug Summary Card.
    All claims carry epistemic badges ([FACT — Lxx], [GUESS], [MISSING]).
    """
    title: str = Field(
        ...,
        description="[Component] Concise root issue under trigger condition (<15 words)"
    )
    component: str = Field(
        ...,
        description="Primary affected software module (e.g., Payments, Auth, Checkout, Database)"
    )
    steps_to_reproduce: List[EpistemicClaim] = Field(
        default_factory=list,
        description="Actionable, numbered steps to reproduce the issue"
    )
    expected_behavior: EpistemicClaim = Field(
        ...,
        description="What should have happened according to system specifications"
    )
    actual_behavior: EpistemicClaim = Field(
        ...,
        description="What actually occurred (crash, error code, freeze, timeout)"
    )
    error_details: List[EpistemicClaim] = Field(
        default_factory=list,
        description="Exception classes, HTTP status codes, and compressed log signatures"
    )
    impact: EpistemicClaim = Field(
        ...,
        description="Blast radius: user impact, service disruption, and SLA risk"
    )
    missing_info: MissingInfoCheck = Field(
        ...,
        description="Missing information check and reporter question"
    )
    report_grade: InputReportGrade = Field(
        ...,
        description="Input report quality grade (A-F)"
    )
    suggested_priority: SuggestedPriority = Field(
        ...,
        description="AI suggested priority and mismatch status"
    )


class SecondAIQualityEvaluation(BaseModel):
    """
    Feature 9: Second-AI Quality Judge with 4-Pillar Metric and Reflexion Gate.
    Formula: Q = 0.30*Semantic + 0.25*EntityRecall + 0.25*Structure + 0.20*Faithfulness
    """
    overall_quality_score: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Composite Quality Score out of 100%"
    )
    semantic_coverage_score: float = Field(..., ge=0.0, le=100.0, description="Semantic coverage score (30% weight)")
    entity_recall_score: float = Field(..., ge=0.0, le=100.0, description="Critical entity retention score (25% weight)")
    structural_completeness_score: float = Field(..., ge=0.0, le=100.0, description="CTQRS structural completeness (25% weight)")
    faithfulness_score: float = Field(..., ge=0.0, le=100.0, description="Faithfulness / Zero hallucination (20% weight)")
    passed_85_gate: bool = Field(..., description="True if overall_quality_score >= 85.0%")
    retry_triggered: bool = Field(default=False, description="True if self-healing reflexion retry was executed")
    initial_score_before_retry: Optional[float] = Field(
        default=None,
        description="Quality score prior to self-healing retry"
    )
    critic_reasoning: str = Field(..., description="Judge critique explaining score and feedback")


class ProcessedBugRecord(BaseModel):
    """Complete persistent entity model stored in SQLite and displayed across UI tabs."""
    bug_id: str = Field(..., description="Unique ticket identifier (e.g. BUG-2026-001)")
    created_at: str = Field(..., description="ISO 8601 timestamp")
    reported_severity: Optional[str] = Field(default=None, description="Original reporter severity")
    reported_status: Optional[str] = Field(default="New", description="Ticket status")
    audit: MaskingAuditReport = Field(..., description="Privacy and log compression audit")
    summary: StructuredBugSummary = Field(..., description="Canonical 6-block structured summary")
    evaluation: SecondAIQualityEvaluation = Field(..., description="Second AI evaluation metrics")
    duplicate_group_id: Optional[str] = Field(default=None, description="ID of clustered duplicate group")
    duplicate_group_label: Optional[str] = Field(default=None, description="Human title for duplicate cluster")
    human_feedback: Optional[Literal["UP", "DOWN"]] = Field(default=None, description="Human RLHF vote")
    human_comment: Optional[str] = Field(default=None, description="Optional feedback note")


class DuplicateClusterGroup(BaseModel):
    """Feature 8: Duplicate Cluster Model."""
    cluster_id: str
    cluster_title: str
    report_count: int
    bug_ids: List[str]
    sample_summary: str
    primary_component: str
    primary_priority: str


class DailyPulseSummary(BaseModel):
    """Feature 10: Executive Daily Pulse Banner & Metric Cards."""
    executive_headline: str = Field(..., description="E.g., '5 serious bugs, 12 duplicates, payments module getting worse'")
    total_reports: int = Field(default=0)
    total_duplicates: int = Field(default=0)
    high_priority_count: int = Field(default=0)
    medium_priority_count: int = Field(default=0)
    low_priority_count: int = Field(default=0)
    avg_quality_score: float = Field(default=0.0)
    target_85_met: bool = Field(default=True)
    component_breakdown: Dict[str, int] = Field(default_factory=dict)
    human_approval_rate: float = Field(default=100.0)

