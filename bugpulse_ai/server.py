"""
BugPulse AI - Enterprise Automated Bug Report Summarizer & Triage Workbench
World-Class SaaS UI & UX Redesign for TCS Technology Day 2026
Light-First Design System:
- Palette: Warm off-white (#F8F9F7), White cards (#FFFFFF), Near-black text (#20252B), Muted slate (#667085)
- Sidebar: Deep charcoal (#18212B) with Sophisticated Teal brand accent (#087F73)
- Information Architecture:
  1. Overview (Command Center & Insights)
  2. Analyze Bug (Single bug triage & verification)
  3. Batch Analysis (CSV multi-ticket triage & duplicate clustering)
  4. Bug Reports (Repository of all analyzed bugs)
  5. Documentation (Architecture, governance & demo guide)
"""

import os
import io
import json
from datetime import datetime
from typing import List, Dict, Optional, Any
import pandas as pd
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from schema import ProcessedBugRecord
from preprocessor import Preprocessor
from agents_and_eval import BugSummarizerEngine, DuplicateBugClusterer
from fake_bug_factory import SCENARIOS, get_scenario_names, get_scenario, generate_sample_batch_csv
from database import db_instance

# Ensure database is pre-seeded
db_instance.seed_initial_enterprise_dataset()

app = FastAPI(
    title="BugPulse AI",
    description="Enterprise Automated Bug Report Summarizer & Triage Engine (TCS Technology Day 2026)",
    version="4.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class TriageRequest(BaseModel):
    title: Optional[str] = None
    raw_text: str
    reported_severity: str = "Not Sure"
    reported_status: str = "New"
    component_hint: Optional[str] = None
    api_key: Optional[str] = None


class FeedbackRequest(BaseModel):
    bug_id: str
    vote: str
    comment: Optional[str] = None


@app.get("/api/scenarios")
def api_get_scenarios():
    return {
        "scenario_names": get_scenario_names(),
        "scenarios": SCENARIOS
    }


@app.get("/api/pulse")
def api_get_pulse():
    pulse = db_instance.get_daily_pulse_summary()
    return pulse.model_dump()


@app.get("/api/records")
def api_get_records():
    records = db_instance.get_all_records()
    return [r.model_dump() for r in records]


@app.post("/api/triage")
def api_run_triage(req: TriageRequest):
    if not req.raw_text.strip():
        raise HTTPException(status_code=400, detail="Raw bug report text cannot be empty.")

    prep = Preprocessor()
    audit = prep.mask_pii_and_secrets(req.raw_text)
    engine = BugSummarizerEngine(api_key=req.api_key)

    sev_clean = req.reported_severity if req.reported_severity in ["Low", "Medium", "High", "Critical"] else "Low"

    summary, eval_res = engine.run_pipeline(
        raw_text=req.raw_text,
        reported_severity=sev_clean,
        component_hint=req.component_hint
    )

    # If user provided a title, preserve or integrate it
    if req.title and req.title.strip():
        summary.title = f"[{summary.component}] {req.title.strip()}"

    cluster_label = "Individual Ticket"
    all_records = db_instance.get_all_records()
    if all_records:
        sample_list = [{"bug_id": r.bug_id, "title": r.summary.title, "description": r.audit.raw_text, "component": r.summary.component} for r in all_records]
        sample_list.append({"bug_id": "NEW-TICKET", "title": summary.title, "description": req.raw_text, "component": summary.component})
        clusterer = DuplicateBugClusterer()
        clusters = clusterer.cluster_reports(sample_list)
        for c in clusters:
            if "NEW-TICKET" in c.bug_ids and len(c.bug_ids) > 1:
                cluster_label = c.cluster_title
                break

    bug_id = f"TCS-{datetime.now().strftime('%M%S')}"
    record = ProcessedBugRecord(
        bug_id=bug_id,
        created_at=datetime.now().isoformat(),
        reported_severity=req.reported_severity,
        reported_status=req.reported_status,
        audit=audit,
        summary=summary,
        evaluation=eval_res,
        duplicate_group_id=None,
        duplicate_group_label=cluster_label,
        human_feedback="UP" if eval_res.overall_quality_score >= 88.0 else None
    )

    db_instance.save_processed_bug(record)
    return record.model_dump()


@app.post("/api/batch/seed")
def api_reseed():
    db_instance.reseed_data()
    return {"status": "success", "message": "Database reseeded with enterprise batch."}


@app.post("/api/batch/upload")
async def api_upload_csv(file: UploadFile = File(...), api_key: Optional[str] = Form(None)):
    contents = await file.read()
    try:
        df = pd.read_csv(io.BytesIO(contents))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid CSV format: {str(e)}")

    if "description" not in df.columns and "raw_text" not in df.columns:
        raise HTTPException(status_code=400, detail="CSV must contain a 'description' or 'raw_text' column.")

    engine = BugSummarizerEngine(api_key=api_key)
    prep = Preprocessor()

    tickets_for_clustering = []
    for idx, row in df.iterrows():
        b_id = str(row.get("bug_id", f"CSV-{idx+1:03d}"))
        desc = str(row.get("description", row.get("raw_text", "")))
        title = str(row.get("title", f"Defect {b_id}"))
        comp = str(row.get("component", "General"))
        tickets_for_clustering.append({"bug_id": b_id, "title": title, "description": desc, "component": comp})

    clusterer = DuplicateBugClusterer()
    clusters = clusterer.cluster_reports(tickets_for_clustering)
    cluster_map = {}
    for c in clusters:
        for tid in c.bug_ids:
            cluster_map[tid] = c.cluster_title

    now = datetime.now().isoformat()
    processed_count = 0
    for idx, row in df.iterrows():
        b_id = str(row.get("bug_id", f"CSV-{idx+1:03d}"))
        title = str(row.get("title", "Defect"))
        desc = str(row.get("description", ""))
        raw_text = f"{title}\n{desc}"
        sev = str(row.get("reported_severity", "Medium"))
        comp = str(row.get("component", "General"))

        audit = prep.mask_pii_and_secrets(raw_text)
        summary, eval_res = engine.run_pipeline(raw_text, reported_severity=sev, component_hint=comp)

        record = ProcessedBugRecord(
            bug_id=b_id,
            created_at=now,
            reported_severity=sev,
            reported_status=str(row.get("reported_status", "New")),
            audit=audit,
            summary=summary,
            evaluation=eval_res,
            duplicate_group_id=None,
            duplicate_group_label=cluster_map.get(b_id, "Individual Ticket"),
            human_feedback="UP" if eval_res.overall_quality_score >= 88.0 else None
        )
        db_instance.save_processed_bug(record)
        processed_count += 1

    return {"status": "success", "processed_count": processed_count}


@app.post("/api/feedback")
def api_record_feedback(req: FeedbackRequest):
    db_instance.record_human_feedback(req.bug_id, req.vote, req.comment)
    return {"status": "success", "bug_id": req.bug_id, "vote": req.vote}


@app.get("/api/export/csv")
def api_export_csv():
    records = db_instance.get_all_records()
    table_rows = []
    for r in records:
        table_rows.append({
            "Bug ID": r.bug_id,
            "Title": r.summary.title,
            "Component": r.summary.component,
            "AI Priority": r.summary.suggested_priority.level,
            "Reported Severity": r.reported_severity or "None",
            "Severity Mismatch": "YES" if r.summary.suggested_priority.severity_mismatch_alert else "NO",
            "Input Grade": r.summary.report_grade.letter_grade,
            "Quality Score": f"{r.evaluation.overall_quality_score}%",
            "Masked PII Count": r.audit.total_masked,
            "Log Compression": f"{r.audit.log_compression_ratio}%",
            "Cluster Group": r.duplicate_group_label or "Individual",
            "Reporter Follow-Up Question": r.summary.missing_info.question_for_reporter
        })
    df = pd.DataFrame(table_rows)
    stream = io.StringIO()
    df.to_csv(stream, index=False)
    return StreamingResponse(
        io.BytesIO(stream.getvalue().encode('utf-8')),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=bugpulse_enriched_triage_batch.csv"}
    )


# -----------------------------------------------------------------------------
# -----------------------------------------------------------------------------
# HIGH-DENSITY LINEAR/SENTRY GRADE WORKBENCH SPA
# -----------------------------------------------------------------------------
TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), 'templates', 'index.html')


def get_spa_html() -> str:
    if os.path.exists(TEMPLATE_PATH):
        with open(TEMPLATE_PATH, 'r', encoding='utf-8') as f:
            return f.read()
    return '<h1>BugPulse AI Workbench</h1>'


@app.get('/', response_class=HTMLResponse)
def serve_spa():
    return HTMLResponse(content=get_spa_html(), status_code=200)


if __name__ == '__main__':
    import uvicorn
    uvicorn.run('server:app', host='0.0.0.0', port=8000, reload=False)
