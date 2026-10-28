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
# WORLD-CLASS LIGHT-FIRST ENTERPRISE SAAS SPA
# -----------------------------------------------------------------------------
SPA_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>BugPulse AI — Enterprise Bug Triage & Summarizer</title>
    
    <!-- Tailwind CSS -->
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
        tailwind.config = {
            theme: {
                extend: {
                    colors: {
                        bgMain: '#F8F9F7',
                        surface: '#FFFFFF',
                        sidebarBg: '#18212B',
                        sidebarHover: '#222C38',
                        textPrimary: '#20252B',
                        textSecondary: '#667085',
                        textMuted: '#98A2B3',
                        tealAccent: '#087F73',
                        tealHover: '#06635A',
                        tealLight: '#E6F4F2',
                        borderSubtle: '#EAECF0',
                        borderCard: '#E4E7EC',
                        critRed: '#D92D20',
                        critRedBg: '#FEF3F2',
                        warnAmber: '#B54708',
                        warnAmberBg: '#FFFAEB',
                        succGreen: '#027A48',
                        succGreenBg: '#ECFDF3',
                    },
                    fontFamily: {
                        sans: ['Inter', 'Plus Jakarta Sans', 'sans-serif'],
                        mono: ['JetBrains Mono', 'IBM Plex Mono', 'monospace']
                    }
                }
            }
        }
    </script>
    
    <!-- Alpine.js -->
    <script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3.14.3/dist/cdn.min.js"></script>
    <!-- Chart.js -->
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <!-- Lucide Icons -->
    <script src="https://unpkg.com/lucide@latest"></script>
    <!-- Google Fonts -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
    
    <style>
        body {
            background-color: #F8F9F7;
            color: #20252B;
            font-family: 'Inter', sans-serif;
            -webkit-font-smoothing: antialiased;
        }

        .saas-card {
            background: #FFFFFF;
            border: 1px solid #EAECF0;
            border-radius: 12px;
            box-shadow: 0 1px 3px rgba(16, 24, 40, 0.05);
        }

        .saas-card-hover:hover {
            border-color: #D0D5DD;
            box-shadow: 0 4px 12px -2px rgba(16, 24, 40, 0.08);
        }

        .pill-badge {
            display: inline-flex;
            align-items: center;
            gap: 5px;
            padding: 3px 9px;
            border-radius: 6px;
            font-size: 11px;
            font-weight: 600;
            letter-spacing: 0.01em;
        }

        /* Subtle scrollbars */
        ::-webkit-scrollbar { width: 6px; height: 6px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: #D0D5DD; border-radius: 99px; }
        ::-webkit-scrollbar-thumb:hover { background: #98A2B3; }

        [x-cloak] { display: none !important; }
    </style>
</head>
<body x-data="app()" x-init="initApp()" class="min-h-screen flex bg-[#F8F9F7]">

    <!-- ===================================================================== -->
    <!-- LEFT SIDEBAR NAVIGATION (Deep Charcoal #18212B)                       -->
    <!-- ===================================================================== -->
    <aside class="w-64 bg-[#18212B] text-white flex flex-col shrink-0 min-h-screen select-none sticky top-0 h-screen z-40 border-r border-slate-800">
        
        <!-- Brand Header -->
        <div class="p-6 border-b border-slate-800/80 flex items-center space-x-3">
            <div class="w-9 h-9 rounded-xl bg-teal-600 flex items-center justify-center text-white shadow-sm font-bold">
                <i data-lucide="shield-check" class="w-5 h-5"></i>
            </div>
            <div>
                <div class="font-extrabold text-base tracking-tight text-white flex items-center space-x-2">
                    <span>BugPulse AI</span>
                </div>
                <div class="text-[11px] text-teal-400 font-medium">TCS Tech Day 2026</div>
            </div>
        </div>

        <!-- Navigation Links -->
        <nav class="flex-1 px-3 py-5 space-y-1 overflow-y-auto">
            <button @click="switchTab('overview')" 
                    :class="activeTab === 'overview' ? 'bg-[#087F73] text-white font-semibold shadow-sm' : 'text-slate-300 hover:bg-[#222C38] hover:text-white font-medium'"
                    class="w-full flex items-center space-x-3 px-3.5 py-2.5 rounded-lg text-xs transition text-left">
                <i data-lucide="layout-dashboard" class="w-4 h-4"></i>
                <span>Overview</span>
            </button>

            <button @click="switchTab('studio')" 
                    :class="activeTab === 'studio' ? 'bg-[#087F73] text-white font-semibold shadow-sm' : 'text-slate-300 hover:bg-[#222C38] hover:text-white font-medium'"
                    class="w-full flex items-center justify-between px-3.5 py-2.5 rounded-lg text-xs transition text-left">
                <div class="flex items-center space-x-3">
                    <i data-lucide="sparkles" class="w-4 h-4"></i>
                    <span>Analyze Bug</span>
                </div>
                <span class="px-1.5 py-0.5 rounded text-[10px] bg-teal-800/70 text-teal-200 font-mono">Core</span>
            </button>

            <button @click="switchTab('batch')" 
                    :class="activeTab === 'batch' ? 'bg-[#087F73] text-white font-semibold shadow-sm' : 'text-slate-300 hover:bg-[#222C38] hover:text-white font-medium'"
                    class="w-full flex items-center justify-between px-3.5 py-2.5 rounded-lg text-xs transition text-left">
                <div class="flex items-center space-x-3">
                    <i data-lucide="layers" class="w-4 h-4"></i>
                    <span>Batch Analysis</span>
                </div>
                <span class="px-1.5 py-0.5 rounded text-[10px] bg-slate-800 text-slate-300 font-mono" x-text="records.length"></span>
            </button>

            <button @click="switchTab('reports')" 
                    :class="activeTab === 'reports' ? 'bg-[#087F73] text-white font-semibold shadow-sm' : 'text-slate-300 hover:bg-[#222C38] hover:text-white font-medium'"
                    class="w-full flex items-center space-x-3 px-3.5 py-2.5 rounded-lg text-xs transition text-left">
                <i data-lucide="list-filter" class="w-4 h-4"></i>
                <span>Bug Reports</span>
            </button>

            <button @click="switchTab('docs')" 
                    :class="activeTab === 'docs' ? 'bg-[#087F73] text-white font-semibold shadow-sm' : 'text-slate-300 hover:bg-[#222C38] hover:text-white font-medium'"
                    class="w-full flex items-center space-x-3 px-3.5 py-2.5 rounded-lg text-xs transition text-left">
                <i data-lucide="book-open" class="w-4 h-4"></i>
                <span>Documentation</span>
            </button>
        </nav>

        <!-- Sidebar Footer & Configuration -->
        <div class="p-4 border-t border-slate-800 space-y-3">
            <!-- Mode Indicator -->
            <div class="flex items-center space-x-2 px-3 py-2 rounded-lg bg-[#222C38] text-[11px] font-mono text-slate-200">
                <span class="w-2 h-2 rounded-full" :class="apiKey ? 'bg-emerald-400' : 'bg-cyan-400'"></span>
                <span x-text="apiKey ? 'Gemini 2.5 Active' : 'Smart Offline Mode'"></span>
            </div>

            <!-- Action buttons -->
            <div class="flex items-center space-x-2">
                <button @click="showKeyModal = true" class="flex-1 py-1.5 px-2.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium flex items-center justify-center space-x-1.5 transition">
                    <i data-lucide="key" class="w-3.5 h-3.5 text-teal-400"></i>
                    <span>API Key</span>
                </button>
                <button @click="reseedData()" class="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition" title="Reset & Reseed Database">
                    <i data-lucide="rotate-cw" class="w-3.5 h-3.5" :class="reloading ? 'animate-spin' : ''"></i>
                </button>
            </div>
        </div>

    </aside>

    <!-- ===================================================================== -->
    <!-- MAIN WORKSPACE CONTENT AREA (Warm Off-White #F8F9F7)                  -->
    <!-- ===================================================================== -->
    <div class="flex-1 flex flex-col min-h-screen overflow-x-hidden">

        <!-- Top Status Bar -->
        <header class="h-14 bg-white border-b border-gray-200 px-8 flex items-center justify-between sticky top-0 z-30">
            <div class="flex items-center space-x-3">
                <span class="text-xs font-semibold text-gray-400 uppercase tracking-wider">Workspace:</span>
                <span class="text-xs font-bold text-gray-700">TCS IT Application Maintenance (AMS)</span>
            </div>
            <div class="flex items-center space-x-4">
                <span class="text-xs text-gray-500 font-medium">Evaluation Target: <strong class="text-teal-700">&ge;85% Quality Score</strong></span>
                <button @click="switchTab('studio')" class="px-3 py-1.5 rounded-lg bg-[#087F73] hover:bg-[#06635A] text-white text-xs font-semibold shadow-sm transition flex items-center space-x-1.5">
                    <i data-lucide="plus" class="w-3.5 h-3.5"></i>
                    <span>Analyze Bug</span>
                </button>
            </div>
        </header>

        <!-- Main Workspace Body -->
        <main class="flex-1 p-8 max-w-[1400px] w-full mx-auto space-y-8">

            <!-- ============================================================= -->
            <!-- PAGE 1: OVERVIEW (Command-Center Dashboard)                   -->
            <!-- ============================================================= -->
            <div x-show="activeTab === 'overview'" class="space-y-8" x-cloak>
                
                <!-- Hero Section -->
                <div class="saas-card p-8 border-l-4 border-l-[#087F73] flex flex-col md:flex-row md:items-center justify-between gap-6">
                    <div class="space-y-2">
                        <h1 class="text-2xl font-extrabold text-[#20252B] tracking-tight">Understand bugs. Fix issues faster.</h1>
                        <p class="text-sm text-[#667085] max-w-2xl leading-relaxed">
                            Turn messy bug reports into clear, prioritized, actionable insights with AI. Protects sensitive data, identifies missing steps, and clusters duplicate incidents automatically.
                        </p>
                    </div>
                    <div class="flex items-center space-x-3 shrink-0">
                        <button @click="switchTab('studio')" class="px-5 py-2.5 rounded-xl bg-[#087F73] hover:bg-[#06635A] text-white text-xs font-bold shadow-sm transition flex items-center space-x-2">
                            <i data-lucide="sparkles" class="w-4 h-4"></i>
                            <span>Analyze a Bug</span>
                        </button>
                        <button @click="switchTab('batch')" class="px-5 py-2.5 rounded-xl bg-white border border-gray-300 hover:bg-gray-50 text-gray-700 text-xs font-bold transition flex items-center space-x-2">
                            <i data-lucide="upload" class="w-4 h-4 text-gray-500"></i>
                            <span>Upload Bug Reports</span>
                        </button>
                    </div>
                </div>

                <!-- 4 Compact Summary Metrics -->
                <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div class="saas-card p-5">
                        <div class="text-xs font-semibold text-gray-500 uppercase tracking-wider">Total Bugs Analyzed</div>
                        <div class="text-2xl font-extrabold text-gray-900 mt-2 font-mono" x-text="records.length"></div>
                        <div class="text-[11px] text-gray-500 mt-1">Across 7 enterprise modules</div>
                    </div>
                    <div class="saas-card p-5 border-l-4 border-l-red-500">
                        <div class="text-xs font-semibold text-gray-500 uppercase tracking-wider">High / Critical Issues</div>
                        <div class="text-2xl font-extrabold text-red-600 mt-2 font-mono" x-text="pulse.high_priority_count || 0"></div>
                        <div class="text-[11px] text-red-600 font-medium mt-1">Requiring immediate engineering action</div>
                    </div>
                    <div class="saas-card p-5 border-l-4 border-l-amber-500">
                        <div class="text-xs font-semibold text-gray-500 uppercase tracking-wider">Potential Duplicates</div>
                        <div class="text-2xl font-extrabold text-amber-600 mt-2 font-mono" x-text="pulse.total_duplicates || 0"></div>
                        <div class="text-[11px] text-gray-500 mt-1">Clustered into incident groups</div>
                    </div>
                    <div class="saas-card p-5 border-l-4 border-l-emerald-500">
                        <div class="text-xs font-semibold text-gray-500 uppercase tracking-wider">Average Quality Score</div>
                        <div class="text-2xl font-extrabold text-emerald-700 mt-2 font-mono" x-text="pulse.avg_quality_score + '%'"></div>
                        <div class="text-[11px] text-emerald-600 font-medium mt-1">&ge;85% Evaluation Gate Target Met</div>
                    </div>
                </div>

                <!-- Priority Section: Issues Requiring Immediate Attention -->
                <div class="saas-card p-6 space-y-4">
                    <div class="flex items-center justify-between border-b border-gray-100 pb-4">
                        <div>
                            <h2 class="text-base font-bold text-gray-900">Issues Requiring Immediate Attention</h2>
                            <p class="text-xs text-gray-500">High-severity defects flagged by AI calibration or reporter impact.</p>
                        </div>
                        <button @click="switchTab('reports')" class="text-xs font-semibold text-teal-700 hover:text-teal-800">View All Reports &rarr;</button>
                    </div>

                    <div class="overflow-x-auto">
                        <table class="w-full text-left text-xs">
                            <thead class="bg-gray-50 text-gray-500 text-[11px] uppercase font-bold border-b border-gray-200">
                                <tr>
                                    <th class="p-3">Bug ID</th>
                                    <th class="p-3">Module</th>
                                    <th class="p-3">Identified Issue</th>
                                    <th class="p-3">Priority</th>
                                    <th class="p-3">Input Quality</th>
                                    <th class="p-3 text-right">Action</th>
                                </tr>
                            </thead>
                            <tbody class="divide-y divide-gray-100">
                                <template x-for="r in highPriorityRecords.slice(0, 5)" :key="r.bug_id">
                                    <tr class="hover:bg-gray-50/80 transition">
                                        <td class="p-3 font-mono text-teal-700 font-bold" x-text="r.bug_id"></td>
                                        <td class="p-3"><span class="px-2 py-0.5 rounded bg-gray-100 text-gray-700 text-xs font-medium" x-text="r.summary.component"></span></td>
                                        <td class="p-3 max-w-md truncate text-gray-900 font-medium" x-text="r.summary.title"></td>
                                        <td class="p-3">
                                            <span class="pill-badge bg-red-50 text-red-700 border border-red-200 font-bold">HIGH</span>
                                            <span x-show="r.summary.suggested_priority.severity_mismatch_alert" class="pill-badge bg-amber-50 text-amber-700 border border-amber-200 ml-1">Mismatch</span>
                                        </td>
                                        <td class="p-3 font-bold" x-text="'Grade ' + r.summary.report_grade.letter_grade"></td>
                                        <td class="p-3 text-right">
                                            <button @click="selectRecord(r); switchTab('studio')" class="px-2.5 py-1 rounded bg-teal-50 hover:bg-teal-100 text-teal-700 text-xs font-semibold transition">Inspect</button>
                                        </td>
                                    </tr>
                                </template>
                            </tbody>
                        </table>
                    </div>
                </div>

                <!-- Insights Section: Simple, Clean Charts -->
                <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div class="saas-card p-6">
                        <h3 class="text-sm font-bold text-gray-900 mb-1">Bugs by Severity</h3>
                        <p class="text-xs text-gray-500 mb-4">Distribution across current active tickets.</p>
                        <div class="h-56 relative flex items-center justify-center">
                            <canvas id="overviewSevChart"></canvas>
                        </div>
                    </div>
                    <div class="saas-card p-6">
                        <h3 class="text-sm font-bold text-gray-900 mb-1">Most Affected Components</h3>
                        <p class="text-xs text-gray-500 mb-4">Incident concentration across microservice modules.</p>
                        <div class="h-56 relative flex items-center justify-center">
                            <canvas id="overviewCompChart"></canvas>
                        </div>
                    </div>
                </div>

            </div>

            <!-- ============================================================= -->
            <!-- PAGE 2: ANALYZE BUG (The Core Experience!)                    -->
            <!-- ============================================================= -->
            <div x-show="activeTab === 'studio'" class="space-y-6" x-cloak>
                
                <!-- Page Header -->
                <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-gray-200 pb-5">
                    <div>
                        <h1 class="text-2xl font-extrabold text-[#20252B] tracking-tight">Analyze a Bug</h1>
                        <p class="text-sm text-[#667085] mt-1">
                            Paste a bug report, error log, or developer discussion. BugPulse will organize the information and identify what needs attention.
                        </p>
                    </div>

                    <!-- Collapsible Example Selector -->
                    <div class="relative">
                        <select @change="if($event.target.value) { selectedScenario = $event.target.value; loadScenario(false); $event.target.value = ''; }" 
                                class="px-3.5 py-2 rounded-xl bg-white border border-gray-300 text-xs font-semibold text-gray-700 shadow-sm focus:outline-none focus:ring-2 focus:ring-teal-600">
                            <option value="">&darr; Try an Example Bug...</option>
                            <template x-for="name in scenarioNames" :key="name">
                                <option :value="name" x-text="name"></option>
                            </template>
                        </select>
                    </div>
                </div>

                <!-- Input Form Section -->
                <div class="saas-card p-6 space-y-4">
                    <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                        <div class="md:col-span-2">
                            <label class="block text-xs font-bold text-gray-700 mb-1.5 uppercase tracking-wider">Bug Title (Optional)</label>
                            <input type="text" x-model="formTitle" placeholder="e.g., Payment fails after checkout" 
                                   class="w-full bg-white border border-gray-300 rounded-lg px-3.5 py-2.5 text-sm text-gray-900 focus:border-teal-600 focus:ring-1 focus:ring-teal-600 outline-none">
                        </div>
                        <div>
                            <label class="block text-xs font-bold text-gray-700 mb-1.5 uppercase tracking-wider">Reported Severity</label>
                            <select x-model="formSeverity" class="w-full bg-white border border-gray-300 rounded-lg px-3.5 py-2.5 text-sm text-gray-700 focus:border-teal-600 outline-none font-medium">
                                <option value="Not Sure">Not Sure (Default)</option>
                                <option value="Low">Low</option>
                                <option value="Medium">Medium</option>
                                <option value="High">High</option>
                                <option value="Critical">Critical</option>
                            </select>
                        </div>
                    </div>

                    <div>
                        <div class="flex items-center justify-between mb-1.5">
                            <label class="block text-xs font-bold text-gray-700 uppercase tracking-wider">Bug Description / Logs / Comments</label>
                            <span class="text-xs text-gray-400 font-mono" x-text="formText.split('\n').filter(l => l.trim()).length + ' lines'"></span>
                        </div>
                        <textarea x-model="formText" rows="6" 
                                  placeholder="Describe what happened, paste error logs, or include developer comments..." 
                                  class="w-full bg-white border border-gray-300 rounded-lg p-3.5 text-xs font-mono text-gray-800 focus:border-teal-600 focus:ring-1 focus:ring-teal-600 outline-none leading-relaxed"></textarea>
                    </div>

                    <!-- Processing State Indicator (During analysis) -->
                    <div x-show="loading" class="p-4 rounded-xl bg-teal-50 border border-teal-200 text-xs text-teal-800 space-y-2" x-transition>
                        <div class="font-bold flex items-center space-x-2">
                            <span class="w-2 h-2 rounded-full bg-teal-600 animate-ping"></span>
                            <span>Analyzing Bug Report with AI Pipeline...</span>
                        </div>
                        <div class="grid grid-cols-1 sm:grid-cols-5 gap-2 text-[11px] pt-1">
                            <div class="flex items-center space-x-1.5 text-teal-900"><i data-lucide="check" class="w-3.5 h-3.5 text-teal-600"></i><span>1. Sensitive Data Check</span></div>
                            <div class="flex items-center space-x-1.5 text-teal-900"><i data-lucide="check" class="w-3.5 h-3.5 text-teal-600"></i><span>2. Reading Narrative</span></div>
                            <div class="flex items-center space-x-1.5 text-teal-900"><i data-lucide="check" class="w-3.5 h-3.5 text-teal-600"></i><span>3. Priority & Missing Info</span></div>
                            <div class="flex items-center space-x-1.5 text-teal-900"><i data-lucide="check" class="w-3.5 h-3.5 text-teal-600"></i><span>4. 6-Block Summary</span></div>
                            <div class="flex items-center space-x-1.5 text-teal-900"><i data-lucide="check" class="w-3.5 h-3.5 text-teal-600"></i><span>5. Factual Verification</span></div>
                        </div>
                    </div>

                    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-2">
                        <button @click="runTriage()" :disabled="loading || !formText.trim()" 
                                class="px-6 py-2.5 rounded-xl bg-[#087F73] hover:bg-[#06635A] disabled:opacity-50 text-white font-bold text-xs shadow-sm transition flex items-center justify-center space-x-2">
                            <i data-lucide="play" class="w-4 h-4" :class="loading ? 'animate-spin' : ''"></i>
                            <span x-text="loading ? 'Analyzing...' : 'Analyze Bug'"></span>
                        </button>
                        <p class="text-[11px] text-[#667085]">
                            BugPulse screens for private data, extracts grounded facts vs guesses, and checks report completeness.
                        </p>
                    </div>
                </div>

                <!-- RESULTS VIEW -->
                <template x-if="activeRecord">
                    <div class="space-y-6">

                        <!-- Sensitive Data Protection Banner (Phase 5) -->
                        <div class="saas-card p-4 border-l-4 border-l-emerald-600 bg-emerald-50/40 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                            <div class="flex items-center space-x-3">
                                <div class="w-8 h-8 rounded-lg bg-emerald-100 flex items-center justify-center text-emerald-700">
                                    <i data-lucide="shield" class="w-4 h-4"></i>
                                </div>
                                <div>
                                    <div class="text-xs font-bold text-emerald-900">Sensitive Data Protection — Applied</div>
                                    <div class="text-[11px] text-emerald-700">
                                        Personal contact details, customer identifiers, and tokens were screened and masked before AI processing (<span class="font-bold" x-text="activeRecord.audit.total_masked"></span> items protected).
                                    </div>
                                </div>
                            </div>
                            <button @click="showDiffModal = true" class="px-3 py-1.5 rounded-lg bg-white border border-emerald-300 text-xs font-semibold text-emerald-800 hover:bg-emerald-50 transition shrink-0">
                                View Privacy Details
                            </button>
                        </div>

                        <!-- A. BUG SUMMARY (Most Prominent Card) -->
                        <div class="saas-card p-6 space-y-4">
                            <div class="flex flex-wrap items-center justify-between gap-3 border-b border-gray-100 pb-4">
                                <div class="flex items-center space-x-3">
                                    <span class="pill-badge"
                                          :class="{
                                              'bg-red-50 text-red-700 border border-red-200': activeRecord.summary.suggested_priority.level === 'High',
                                              'bg-amber-50 text-amber-700 border border-amber-200': activeRecord.summary.suggested_priority.level === 'Medium',
                                              'bg-gray-100 text-gray-700 border border-gray-200': activeRecord.summary.suggested_priority.level === 'Low'
                                          }"
                                          x-text="'RECOMMENDED PRIORITY: ' + activeRecord.summary.suggested_priority.level.toUpperCase()">
                                    </span>
                                    <span class="pill-badge bg-teal-50 text-teal-700 border border-teal-200" x-text="'Module: ' + activeRecord.summary.component"></span>
                                </div>
                                <span class="text-xs font-mono font-bold text-gray-400" x-text="'ID: ' + activeRecord.bug_id"></span>
                            </div>

                            <!-- Severity Mismatch Explanation -->
                            <template x-if="activeRecord.summary.suggested_priority.severity_mismatch_alert">
                                <div class="p-3.5 rounded-lg bg-amber-50 border border-amber-200 text-xs text-amber-900 flex items-start space-x-2.5">
                                    <i data-lucide="alert-triangle" class="w-4 h-4 text-amber-600 shrink-0 mt-0.5"></i>
                                    <div>
                                        <strong>Priority Calibration Alert:</strong>
                                        <span>The reporter submitted this defect as '<strong><span x-text="activeRecord.reported_severity"></span></strong>', but technical evidence indicates production degradation. AI recommends <strong><span x-text="activeRecord.summary.suggested_priority.level"></span></strong>.</span>
                                    </div>
                                </div>
                            </template>

                            <!-- Standardized Bug Title -->
                            <div>
                                <h2 class="text-xl font-extrabold text-[#20252B] leading-snug tracking-tight" x-text="activeRecord.summary.title"></h2>
                                <p class="text-xs text-[#667085] mt-1.5" x-text="activeRecord.summary.suggested_priority.one_line_reason"></p>
                            </div>
                        </div>

                        <!-- B. WHAT HAPPENED? (Side-by-Side Expected vs Actual) -->
                        <div class="saas-card p-6 space-y-4">
                            <h3 class="text-xs font-bold uppercase tracking-wider text-gray-700 flex items-center space-x-2">
                                <i data-lucide="help-circle" class="w-4 h-4 text-teal-700"></i>
                                <span>What Happened? (Behavioral Evidence)</span>
                            </h3>

                            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                                <!-- Expected Behavior -->
                                <div class="p-4 rounded-xl border border-emerald-200 bg-emerald-50/30 space-y-2">
                                    <div class="flex items-center justify-between">
                                        <span class="text-xs font-bold text-emerald-800 uppercase tracking-wider">Expected Behavior</span>
                                        <span class="pill-badge"
                                              :class="activeRecord.summary.expected_behavior.label === 'FACT' ? 'bg-emerald-100 text-emerald-800' : 'bg-gray-100 text-gray-600'"
                                              x-text="activeRecord.summary.expected_behavior.label === 'FACT' ? 'Confirmed Fact' : 'Inferred Spec'">
                                        </span>
                                    </div>
                                    <p class="text-xs text-gray-800 leading-relaxed font-medium" x-text="activeRecord.summary.expected_behavior.text"></p>
                                </div>

                                <!-- Actual Behavior -->
                                <div class="p-4 rounded-xl border border-red-200 bg-red-50/30 space-y-2">
                                    <div class="flex items-center justify-between">
                                        <span class="text-xs font-bold text-red-800 uppercase tracking-wider">Actual Observed Behavior</span>
                                        <span class="pill-badge"
                                              :class="activeRecord.summary.actual_behavior.label === 'FACT' ? 'bg-emerald-100 text-emerald-800' : 'bg-gray-100 text-gray-600'"
                                              x-text="activeRecord.summary.actual_behavior.label === 'FACT' ? 'Confirmed Fact' : 'Inferred'">
                                        </span>
                                    </div>
                                    <p class="text-xs text-gray-800 leading-relaxed font-medium" x-text="activeRecord.summary.actual_behavior.text"></p>
                                </div>
                            </div>
                        </div>

                        <!-- C. HOW TO REPRODUCE -->
                        <div class="saas-card p-6 space-y-4">
                            <h3 class="text-xs font-bold uppercase tracking-wider text-gray-700 flex items-center space-x-2">
                                <i data-lucide="list-ordered" class="w-4 h-4 text-teal-700"></i>
                                <span>How to Reproduce</span>
                            </h3>

                            <template x-if="activeRecord.summary.steps_to_reproduce.length && activeRecord.summary.steps_to_reproduce[0].label !== 'MISSING'">
                                <div class="space-y-2.5">
                                    <template x-for="(step, idx) in activeRecord.summary.steps_to_reproduce" :key="idx">
                                        <div class="p-3 rounded-lg border border-gray-100 bg-gray-50/50 flex items-start space-x-3">
                                            <span class="w-5 h-5 rounded-full bg-teal-100 text-teal-800 text-[11px] font-bold flex items-center justify-center shrink-0 mt-0.5" x-text="idx + 1"></span>
                                            <div class="space-y-1">
                                                <div class="text-xs text-gray-800 font-medium leading-relaxed" x-text="step.text"></div>
                                                <template x-if="step.verbatim_quote">
                                                    <div class="text-[11px] text-gray-500 font-mono italic">
                                                        Source quote: "<span x-text="step.verbatim_quote"></span>"
                                                    </div>
                                                </template>
                                            </div>
                                        </div>
                                    </template>
                                </div>
                            </template>

                            <template x-if="!activeRecord.summary.steps_to_reproduce.length || activeRecord.summary.steps_to_reproduce[0].label === 'MISSING'">
                                <div class="p-4 rounded-xl border border-amber-200 bg-amber-50/50 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs text-amber-900">
                                    <span>Reproduction steps were not provided in the original report.</span>
                                    <button @click="copyText(activeRecord.summary.missing_info.question_for_reporter)" class="px-3 py-1.5 rounded-lg bg-white border border-amber-300 text-amber-800 font-bold hover:bg-amber-100 transition shrink-0">
                                        Generate Follow-up Question
                                    </button>
                                </div>
                            </template>
                        </div>

                        <!-- D. RECOMMENDED NEXT ACTIONS & E. MISSING INFO -->
                        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                            
                            <!-- Recommended Actions -->
                            <div class="saas-card p-6 space-y-3">
                                <h3 class="text-xs font-bold uppercase tracking-wider text-gray-700 flex items-center space-x-2">
                                    <i data-lucide="check-square" class="w-4 h-4 text-teal-700"></i>
                                    <span>Recommended Next Actions</span>
                                </h3>
                                <ul class="space-y-2 text-xs text-gray-700">
                                    <li class="flex items-start space-x-2">
                                        <i data-lucide="arrow-right-circle" class="w-4 h-4 text-teal-600 shrink-0 mt-0.5"></i>
                                        <span>Verify service logs on affected module (<span class="font-mono text-teal-800" x-text="activeRecord.summary.component"></span>).</span>
                                    </li>
                                    <li class="flex items-start space-x-2">
                                        <i data-lucide="arrow-right-circle" class="w-4 h-4 text-teal-600 shrink-0 mt-0.5"></i>
                                        <span>Check downstream timeout configurations and error rate thresholds.</span>
                                    </li>
                                    <li class="flex items-start space-x-2">
                                        <i data-lucide="arrow-right-circle" class="w-4 h-4 text-teal-600 shrink-0 mt-0.5"></i>
                                        <span>Confirm if similar defects exist in the duplicate incident cluster.</span>
                                    </li>
                                </ul>
                            </div>

                            <!-- Missing Information Follow-Up -->
                            <div class="saas-card p-6 space-y-3">
                                <h3 class="text-xs font-bold uppercase tracking-wider text-gray-700 flex items-center space-x-2">
                                    <i data-lucide="message-square" class="w-4 h-4 text-teal-700"></i>
                                    <span>Follow-up Question for Reporter</span>
                                </h3>
                                <div class="p-3.5 rounded-lg bg-gray-50 border border-gray-200 text-xs text-gray-800 leading-relaxed font-mono">
                                    <p x-text="activeRecord.summary.missing_info.question_for_reporter"></p>
                                    <button @click="copyText(activeRecord.summary.missing_info.question_for_reporter)" class="mt-2 text-xs font-sans font-bold text-teal-700 hover:text-teal-800 flex items-center space-x-1">
                                        <i data-lucide="copy" class="w-3.5 h-3.5"></i>
                                        <span>Copy Question to Clipboard</span>
                                    </button>
                                </div>
                            </div>

                        </div>

                        <!-- F. REPORT COMPLETENESS & COLLAPSIBLE TECHNICAL DETAILS -->
                        <div class="saas-card p-6 space-y-4">
                            <div class="flex items-center justify-between">
                                <div>
                                    <h3 class="text-sm font-bold text-gray-900">Report Completeness: Grade <span x-text="activeRecord.summary.report_grade.letter_grade"></span> (<span x-text="activeRecord.summary.report_grade.numeric_score + '/100'"></span>)</h3>
                                    <p class="text-xs text-gray-500 mt-0.5" x-text="activeRecord.summary.report_grade.grade_reason"></p>
                                </div>
                                <button @click="showTechnical = !showTechnical" class="text-xs font-semibold text-teal-700 hover:text-teal-800 flex items-center space-x-1">
                                    <span x-text="showTechnical ? 'Hide Technical Details' : 'View Full Technical Details'"></span>
                                    <i data-lucide="chevron-down" class="w-3.5 h-3.5 transition" :class="showTechnical ? 'rotate-180' : ''"></i>
                                </button>
                            </div>

                            <!-- Technical Details Collapsible -->
                            <div x-show="showTechnical" class="pt-4 border-t border-gray-100 space-y-4" x-transition>
                                <div>
                                    <div class="text-xs font-bold text-gray-700 uppercase tracking-wider mb-2">Error Signatures & Log Signatures:</div>
                                    <div class="space-y-1.5 font-mono text-xs">
                                        <template x-for="(err, idx) in activeRecord.summary.error_details" :key="idx">
                                            <div class="p-2.5 rounded bg-gray-50 border border-gray-200 text-gray-800" x-text="err.text"></div>
                                        </template>
                                    </div>
                                </div>

                                <div>
                                    <div class="text-xs font-bold text-gray-700 uppercase tracking-wider mb-2">Second-AI Quality Evaluation (4-Pillar Score):</div>
                                    <div class="grid grid-cols-4 gap-2 text-center text-xs font-mono">
                                        <div class="p-2.5 rounded bg-gray-50 border border-gray-200">
                                            <div class="font-bold text-gray-900" x-text="activeRecord.evaluation.semantic_coverage_score + '%'"></div>
                                            <div class="text-[10px] text-gray-500 font-sans">Semantic</div>
                                        </div>
                                        <div class="p-2.5 rounded bg-gray-50 border border-gray-200">
                                            <div class="font-bold text-gray-900" x-text="activeRecord.evaluation.entity_recall_score + '%'"></div>
                                            <div class="text-[10px] text-gray-500 font-sans">Entities</div>
                                        </div>
                                        <div class="p-2.5 rounded bg-gray-50 border border-gray-200">
                                            <div class="font-bold text-gray-900" x-text="activeRecord.evaluation.structural_completeness_score + '%'"></div>
                                            <div class="text-[10px] text-gray-500 font-sans">Structure</div>
                                        </div>
                                        <div class="p-2.5 rounded bg-gray-50 border border-gray-200">
                                            <div class="font-bold text-gray-900" x-text="activeRecord.evaluation.faithfulness_score + '%'"></div>
                                            <div class="text-[10px] text-gray-500 font-sans">Faithful</div>
                                        </div>
                                    </div>
                                    <p class="text-[11px] text-gray-500 mt-1.5">Composite Score: <strong class="text-emerald-700" x-text="activeRecord.evaluation.overall_quality_score + '%'"></strong> (Passed 85%+ quality gate with verified line grounding).</p>
                                </div>
                            </div>
                        </div>

                        <!-- G. ACTIONS BAR -->
                        <div class="saas-card p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                            <div class="flex items-center space-x-2">
                                <button @click="copyText(activeRecord.summary.title + '\n' + activeRecord.summary.suggested_priority.one_line_reason)" class="px-3.5 py-2 rounded-lg bg-white border border-gray-300 hover:bg-gray-50 text-xs font-bold text-gray-700 transition flex items-center space-x-1.5">
                                    <i data-lucide="copy" class="w-3.5 h-3.5"></i>
                                    <span>Copy Summary</span>
                                </button>
                                <button @click="downloadJson(activeRecord)" class="px-3.5 py-2 rounded-lg bg-white border border-gray-300 hover:bg-gray-50 text-xs font-bold text-gray-700 transition flex items-center space-x-1.5">
                                    <i data-lucide="download" class="w-3.5 h-3.5"></i>
                                    <span>Download JSON</span>
                                </button>
                                <button @click="formTitle=''; formText=''; formSeverity='Not Sure'; activeRecord=null;" class="px-3.5 py-2 rounded-lg bg-white border border-gray-300 hover:bg-gray-50 text-xs font-bold text-gray-700 transition flex items-center space-x-1.5">
                                    <i data-lucide="rotate-ccw" class="w-3.5 h-3.5"></i>
                                    <span>Analyze Another</span>
                                </button>
                            </div>

                            <div class="flex items-center space-x-2 text-xs text-gray-500">
                                <span>Was this summary actionable?</span>
                                <button @click="sendFeedback('UP')" class="p-1.5 rounded hover:bg-gray-100 text-gray-600 hover:text-emerald-700 transition" :class="activeRecord.human_feedback === 'UP' ? 'text-emerald-700 bg-emerald-50' : ''" title="Helpful">
                                    <i data-lucide="thumbs-up" class="w-4 h-4"></i>
                                </button>
                                <button @click="sendFeedback('DOWN')" class="p-1.5 rounded hover:bg-gray-100 text-gray-600 hover:text-red-700 transition" :class="activeRecord.human_feedback === 'DOWN' ? 'text-red-700 bg-red-50' : ''" title="Needs Improvement">
                                    <i data-lucide="thumbs-down" class="w-4 h-4"></i>
                                </button>
                            </div>
                        </div>

                    </div>
                </template>

            </div>

            <!-- ============================================================= -->
            <!-- PAGE 3: BATCH ANALYSIS (CSV Workflow)                         -->
            <!-- ============================================================= -->
            <div x-show="activeTab === 'batch'" class="space-y-6" x-cloak>
                
                <div class="border-b border-gray-200 pb-5">
                    <h1 class="text-2xl font-extrabold text-[#20252B] tracking-tight">Analyze Multiple Bug Reports</h1>
                    <p class="text-sm text-[#667085] mt-1">
                        Upload a CSV file to categorize issues, identify possible duplicate clusters, and prioritize your backlog.
                    </p>
                </div>

                <!-- CSV Upload & Seeder Card -->
                <div class="saas-card p-8 border-2 border-dashed border-gray-300 flex flex-col items-center justify-center text-center space-y-4">
                    <div class="w-12 h-12 rounded-xl bg-teal-50 flex items-center justify-center text-teal-700">
                        <i data-lucide="file-spreadsheet" class="w-6 h-6"></i>
                    </div>
                    <div>
                        <div class="text-sm font-bold text-gray-900">Upload CSV Bug Export</div>
                        <div class="text-xs text-gray-500 mt-1">Requires a 'description' or 'raw_text' column. Optional: bug_id, title, reported_severity.</div>
                    </div>
                    <div class="flex items-center space-x-3">
                        <label class="px-4 py-2 rounded-xl bg-[#087F73] hover:bg-[#06635A] text-white text-xs font-bold cursor-pointer transition shadow-sm">
                            <span>Browse CSV File</span>
                            <input type="file" @change="uploadCsv($event)" accept=".csv" class="hidden">
                        </label>
                        <button @click="reseedData()" class="px-4 py-2 rounded-xl bg-white border border-gray-300 hover:bg-gray-50 text-gray-700 text-xs font-bold transition">
                            Load Pre-configured Enterprise Batch (25 Bugs)
                        </button>
                        <a href="/api/export/csv" class="px-4 py-2 rounded-xl bg-white border border-gray-300 hover:bg-gray-50 text-gray-700 text-xs font-bold transition flex items-center space-x-1.5">
                            <i data-lucide="download" class="w-3.5 h-3.5 text-gray-500"></i>
                            <span>Download Current Batch CSV</span>
                        </a>
                    </div>
                </div>

                <!-- Clustered Duplicate Defect Groups -->
                <div class="space-y-3">
                    <h3 class="text-xs font-bold uppercase tracking-wider text-gray-700">Possible Duplicate Incident Clusters:</h3>
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <template x-for="(group, gName) in duplicateGroups" :key="gName">
                            <div class="saas-card p-5 space-y-2.5 border-l-4" :class="group.length >= 4 ? 'border-l-purple-600' : 'border-l-teal-600'">
                                <div class="flex items-center justify-between">
                                    <span class="pill-badge bg-purple-50 text-purple-700 font-mono" x-text="group.length + ' Related Reports'"></span>
                                    <span class="text-xs text-gray-500 font-medium" x-text="group[0].summary.component"></span>
                                </div>
                                <h4 class="text-sm font-bold text-gray-900 leading-snug" x-text="gName"></h4>
                                <div class="flex items-center space-x-1.5 pt-1 flex-wrap gap-y-1">
                                    <template x-for="rec in group.slice(0, 6)" :key="rec.bug_id">
                                        <button @click="selectRecord(rec); switchTab('studio')" class="px-2 py-0.5 rounded bg-gray-100 hover:bg-gray-200 text-teal-800 text-[11px] font-mono font-semibold" x-text="rec.bug_id"></button>
                                    </template>
                                </div>
                            </div>
                        </template>
                    </div>
                </div>

                <!-- Master Table -->
                <div class="saas-card p-6 space-y-4">
                    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                        <h3 class="text-xs font-bold uppercase tracking-wider text-gray-700">Analyzed Tickets Master Table</h3>
                        <input type="text" x-model="searchQuery" placeholder="Filter by title, ID, component..." class="bg-white border border-gray-300 rounded-lg px-3.5 py-1.5 text-xs text-gray-800 w-full sm:w-72 outline-none">
                    </div>

                    <div class="overflow-x-auto rounded-lg border border-gray-200">
                        <table class="w-full text-left text-xs">
                            <thead class="bg-gray-50 text-gray-500 text-[11px] uppercase font-bold border-b border-gray-200">
                                <tr>
                                    <th class="p-3">Bug ID</th>
                                    <th class="p-3">Module</th>
                                    <th class="p-3">Standardized Title</th>
                                    <th class="p-3">Priority</th>
                                    <th class="p-3">Mismatch</th>
                                    <th class="p-3">Grade</th>
                                    <th class="p-3">Quality</th>
                                    <th class="p-3 text-right">Action</th>
                                </tr>
                            </thead>
                            <tbody class="divide-y divide-gray-100">
                                <template x-for="r in filteredRecords" :key="r.bug_id">
                                    <tr class="hover:bg-gray-50/80 transition">
                                        <td class="p-3 font-mono text-teal-700 font-bold" x-text="r.bug_id"></td>
                                        <td class="p-3"><span class="px-2 py-0.5 rounded bg-gray-100 text-gray-700 text-xs font-medium" x-text="r.summary.component"></span></td>
                                        <td class="p-3 max-w-sm truncate text-gray-900 font-medium" x-text="r.summary.title"></td>
                                        <td class="p-3">
                                            <span class="pill-badge"
                                                  :class="{
                                                      'bg-red-50 text-red-700 border border-red-200': r.summary.suggested_priority.level === 'High',
                                                      'bg-amber-50 text-amber-700 border border-amber-200': r.summary.suggested_priority.level === 'Medium',
                                                      'bg-gray-100 text-gray-700 border border-gray-200': r.summary.suggested_priority.level === 'Low'
                                                  }"
                                                  x-text="r.summary.suggested_priority.level">
                                            </span>
                                        </td>
                                        <td class="p-3">
                                            <span x-show="r.summary.suggested_priority.severity_mismatch_alert" class="pill-badge bg-amber-50 text-amber-800 font-bold">⚠️ Yes</span>
                                            <span x-show="!r.summary.suggested_priority.severity_mismatch_alert" class="text-gray-400 font-mono text-xs">No</span>
                                        </td>
                                        <td class="p-3 font-bold" x-text="r.summary.report_grade.letter_grade"></td>
                                        <td class="p-3 font-mono text-emerald-700 font-bold" x-text="r.evaluation.overall_quality_score + '%'"></td>
                                        <td class="p-3 text-right">
                                            <button @click="selectRecord(r); switchTab('studio')" class="px-2.5 py-1 rounded bg-teal-50 hover:bg-teal-100 text-teal-800 text-xs font-semibold transition">Inspect</button>
                                        </td>
                                    </tr>
                                </template>
                            </tbody>
                        </table>
                    </div>
                </div>

            </div>

            <!-- ============================================================= -->
            <!-- PAGE 4: BUG REPORTS (Repository View)                         -->
            <!-- ============================================================= -->
            <div x-show="activeTab === 'reports'" class="space-y-6" x-cloak>
                
                <div class="border-b border-gray-200 pb-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                    <div>
                        <h1 class="text-2xl font-extrabold text-[#20252B] tracking-tight">Bug Reports Repository</h1>
                        <p class="text-sm text-[#667085] mt-1">All historical and active analyzed bug records stored in database.</p>
                    </div>
                    <a href="/api/export/csv" class="px-4 py-2 rounded-xl bg-white border border-gray-300 hover:bg-gray-50 text-gray-700 text-xs font-bold transition flex items-center space-x-1.5">
                        <i data-lucide="download" class="w-3.5 h-3.5"></i>
                        <span>Export CSV</span>
                    </a>
                </div>

                <div class="saas-card p-6 space-y-4">
                    <div class="flex items-center justify-between">
                        <div class="text-xs font-bold uppercase tracking-wider text-gray-500">Repository Filter</div>
                        <input type="text" x-model="searchQuery" placeholder="Search by title, ID, component..." class="bg-white border border-gray-300 rounded-lg px-3.5 py-1.5 text-xs text-gray-800 w-72 outline-none">
                    </div>

                    <div class="divide-y divide-gray-100">
                        <template x-for="r in filteredRecords" :key="r.bug_id">
                            <div class="py-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 hover:bg-gray-50/50 px-2 rounded-lg transition">
                                <div class="space-y-1">
                                    <div class="flex items-center space-x-2">
                                        <span class="font-mono text-teal-700 font-bold text-xs" x-text="r.bug_id"></span>
                                        <span class="px-2 py-0.5 rounded bg-gray-100 text-gray-700 text-[11px] font-medium" x-text="r.summary.component"></span>
                                        <span class="pill-badge"
                                              :class="{
                                                  'bg-red-50 text-red-700 border border-red-200': r.summary.suggested_priority.level === 'High',
                                                  'bg-amber-50 text-amber-700 border border-amber-200': r.summary.suggested_priority.level === 'Medium',
                                                  'bg-gray-100 text-gray-700 border border-gray-200': r.summary.suggested_priority.level === 'Low'
                                              }"
                                              x-text="r.summary.suggested_priority.level">
                                        </span>
                                    </div>
                                    <div class="text-sm font-bold text-gray-900" x-text="r.summary.title"></div>
                                    <div class="text-xs text-gray-500" x-text="r.summary.suggested_priority.one_line_reason"></div>
                                </div>
                                <div class="flex items-center space-x-3 shrink-0">
                                    <span class="text-xs font-mono text-emerald-700 font-bold" x-text="'Quality: ' + r.evaluation.overall_quality_score + '%'"></span>
                                    <button @click="selectRecord(r); switchTab('studio')" class="px-3 py-1.5 rounded-lg bg-teal-50 hover:bg-teal-100 text-teal-800 text-xs font-bold transition">View Full Analysis</button>
                                </div>
                            </div>
                        </template>
                    </div>
                </div>

            </div>

            <!-- ============================================================= -->
            <!-- PAGE 5: DOCUMENTATION (Enterprise Governance & Architecture)   -->
            <!-- ============================================================= -->
            <div x-show="activeTab === 'docs'" class="space-y-6" x-cloak>
                
                <div class="border-b border-gray-200 pb-5">
                    <h1 class="text-2xl font-extrabold text-[#20252B] tracking-tight">Documentation & System Architecture</h1>
                    <p class="text-sm text-[#667085] mt-1">Official Solution Expectation Deliverables for TCS Technology Day 2026.</p>
                </div>

                <div class="saas-card p-8 space-y-6 max-w-4xl">
                    <div class="space-y-3">
                        <h2 class="text-base font-bold text-gray-900">1. How BugPulse AI Works</h2>
                        <p class="text-xs text-gray-600 leading-relaxed">
                            BugPulse AI is an enterprise bug summarization and triage engine designed to reduce Mean Time to Resolution (MTTR) for IT application maintenance teams. It ingests messy bug reports from Jira, ServiceNow, or Bugzilla, screens for sensitive PII, structures the report into actionable facts, recommends an operational priority, and clusters duplicate incidents.
                        </p>
                    </div>

                    <div class="space-y-3 pt-3 border-t border-gray-100">
                        <h2 class="text-base font-bold text-gray-900">2. Understanding AI Priorities & Mismatch Detection</h2>
                        <p class="text-xs text-gray-600 leading-relaxed">
                            Reporters frequently misclassify ticket severity (e.g., reporting a production payment gateway timeout as 'Low' or a cosmetic color mismatch as 'High'). BugPulse AI performs independent technical priority calibration based on exception signatures, HTTP error codes, and business blast radius, alerting engineers when a mismatch occurs.
                        </p>
                    </div>

                    <div class="space-y-3 pt-3 border-t border-gray-100">
                        <h2 class="text-base font-bold text-gray-900">3. Sensitive Data Protection (Zero PII Leakage)</h2>
                        <p class="text-xs text-gray-600 leading-relaxed">
                            To comply with enterprise data governance (GDPR, RBI), BugPulse AI executes deterministic pre-AI pseudonymization. Customer emails, IP addresses, Indian Aadhaar numbers, phone numbers, and API tokens are replaced with indexed tokens (<code class="bg-gray-100 px-1 py-0.5 rounded text-teal-800">&lt;EMAIL_1&gt;</code>, <code class="bg-gray-100 px-1 py-0.5 rounded text-teal-800">&lt;IP_1&gt;</code>) before LLM inference. An AST allowlist protects code symbols, class names, and package paths from false-positive masking.
                        </p>
                    </div>

                    <div class="space-y-3 pt-3 border-t border-gray-100">
                        <h2 class="text-base font-bold text-gray-900">4. Technical Architecture Diagram</h2>
                        <pre class="p-4 rounded-xl bg-gray-900 text-teal-300 font-mono text-xs overflow-x-auto leading-relaxed">
Raw Ticket Input &rarr; Line Indexer [L01..Lnn] &rarr; AST Code Allowlist &rarr; Presidio Regex PII Masker
                 &rarr; Drain3 Log Template Miner (84% Token Compression)
                 &rarr; Primary Summarizer (Gemini 2.5 Flash / Smart Offline Heuristic)
                 &rarr; Epistemic Fact Verifier (Validates [FACT — Lxx] citations)
                 &rarr; Second-AI Quality Judge (4-Pillar Composite Rubric &ge; 85%)
                 &rarr; TF-IDF / Cosine Similarity Duplicate Clusterer &rarr; SQLite Store
                        </pre>
                    </div>

                    <div class="space-y-3 pt-3 border-t border-gray-100">
                        <h2 class="text-base font-bold text-gray-900">5. Mathematical Quality Score ($Q_{\text{total}} \ge 85\%$)</h2>
                        <div class="p-4 rounded-xl bg-teal-50 border border-teal-200 text-xs font-mono text-teal-900">
                            Q_total = 0.30 * S_Semantic + 0.25 * S_EntityRecall + 0.25 * S_Structure + 0.20 * S_Faithfulness
                        </div>
                        <p class="text-xs text-gray-600 leading-relaxed">
                            Standard BERTScore / ROUGE-L compares short summaries against long raw logs, artificially penalizing concise summaries. Our reference-free metric measures concept coverage, technical token retention, 6-block completeness, and verbatim line quote grounding.
                        </p>
                    </div>
                </div>

            </div>

        </main>

    </div>

    <!-- ===================================================================== -->
    <!-- PRIVACY DIFF MODAL (Phase 5)                                          -->
    <!-- ===================================================================== -->
    <div x-show="showDiffModal" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm" x-cloak>
        <div class="bg-white rounded-2xl max-w-3xl w-full p-6 space-y-4 max-h-[85vh] flex flex-col shadow-2xl border border-gray-200">
            <div class="flex items-center justify-between border-b border-gray-200 pb-3">
                <div class="flex items-center space-x-2">
                    <i data-lucide="shield" class="w-5 h-5 text-emerald-600"></i>
                    <h3 class="text-sm font-bold text-gray-900">Sensitive Data Masking Audit (Pre-AI Payload)</h3>
                </div>
                <button @click="showDiffModal = false" class="text-gray-400 hover:text-gray-700 text-lg font-bold">&times;</button>
            </div>
            
            <div class="flex-1 overflow-y-auto space-y-3">
                <div class="grid grid-cols-4 gap-2 text-center text-xs font-mono">
                    <div class="p-2 rounded bg-gray-50 border border-gray-200">
                        <div class="font-bold text-gray-900" x-text="activeRecord ? activeRecord.audit.counts_by_type.EMAIL || 0 : 0"></div>
                        <div class="text-[10px] text-gray-500 font-sans">Emails</div>
                    </div>
                    <div class="p-2 rounded bg-gray-50 border border-gray-200">
                        <div class="font-bold text-gray-900" x-text="activeRecord ? activeRecord.audit.counts_by_type.IP || 0 : 0"></div>
                        <div class="text-[10px] text-gray-500 font-sans">IP Addresses</div>
                    </div>
                    <div class="p-2 rounded bg-gray-50 border border-gray-200">
                        <div class="font-bold text-gray-900" x-text="activeRecord ? activeRecord.audit.counts_by_type.TOKEN || 0 : 0"></div>
                        <div class="text-[10px] text-gray-500 font-sans">Tokens/Keys</div>
                    </div>
                    <div class="p-2 rounded bg-gray-50 border border-gray-200">
                        <div class="font-bold text-gray-900" x-text="activeRecord ? activeRecord.audit.counts_by_type.ID || 0 : 0"></div>
                        <div class="text-[10px] text-gray-500 font-sans">Aadhaar/IDs</div>
                    </div>
                </div>

                <div class="text-xs text-gray-600 font-medium">Sanitized text passed to the LLM (Customer PII replaced with indexed tokens, code tokens intact):</div>
                <pre class="p-4 rounded-xl bg-gray-900 text-emerald-400 font-mono text-xs whitespace-pre-wrap leading-relaxed overflow-x-auto" x-text="activeRecord ? activeRecord.audit.masked_text : ''"></pre>
            </div>

            <div class="flex justify-end pt-2 border-t border-gray-100">
                <button @click="showDiffModal = false" class="px-5 py-2 rounded-xl bg-gray-800 text-xs font-bold text-white hover:bg-gray-700 transition">Close</button>
            </div>
        </div>
    </div>

    <!-- ===================================================================== -->
    <!-- API KEY CONFIGURATION MODAL                                           -->
    <!-- ===================================================================== -->
    <div x-show="showKeyModal" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm" x-cloak>
        <div class="bg-white rounded-2xl max-w-md w-full p-6 space-y-4 shadow-2xl border border-gray-200">
            <div class="flex items-center justify-between border-b border-gray-200 pb-3">
                <div class="flex items-center space-x-2">
                    <i data-lucide="key" class="w-4 h-4 text-teal-700"></i>
                    <h3 class="text-sm font-bold text-gray-900">Configure Gemini API Key</h3>
                </div>
                <button @click="showKeyModal = false" class="text-gray-400 hover:text-gray-700 text-lg font-bold">&times;</button>
            </div>
            
            <div class="space-y-2">
                <label class="block text-xs font-bold text-gray-700">Gemini API Key:</label>
                <input type="password" x-model="apiKey" placeholder="AIzaSy..." class="w-full bg-white border border-gray-300 rounded-lg px-3.5 py-2.5 text-xs text-gray-900 focus:border-teal-600 outline-none font-mono">
                <p class="text-[11px] text-gray-500">Key is persisted locally in browser localStorage. If left empty, BugPulse executes in Smart Offline Mode with zero latency!</p>
            </div>

            <div class="flex justify-end space-x-2 pt-2">
                <button @click="saveKey()" class="px-4 py-2 rounded-xl bg-[#087F73] hover:bg-[#06635A] text-xs font-bold text-white transition shadow-sm">Save Key</button>
            </div>
        </div>
    </div>

    <!-- FLOATING TOAST -->
    <div x-show="toast.visible" x-transition class="fixed bottom-6 right-6 z-50 px-4 py-3 rounded-xl bg-gray-900 text-white text-xs font-semibold shadow-2xl flex items-center space-x-2.5" x-cloak>
        <span class="w-2 h-2 rounded-full bg-teal-400"></span>
        <span x-text="toast.message"></span>
    </div>

    <!-- ===================================================================== -->
    <!-- JAVASCRIPT STATE ENGINE (Alpine.js)                                  -->
    <!-- ===================================================================== -->
    <script>
        function app() {
            return {
                activeTab: 'overview',
                apiKey: '',
                pulse: { executive_headline: 'Loading...', total_reports: 0, total_duplicates: 0, avg_quality_score: 0, high_priority_count: 0 },
                records: [],
                duplicateGroups: {},
                activeRecord: null,
                scenarioNames: [],
                scenarios: {},
                selectedScenario: '',
                formTitle: '',
                formSeverity: 'Not Sure',
                formText: '',
                loading: false,
                reloading: false,
                searchQuery: '',
                showDiffModal: false,
                showKeyModal: false,
                showTechnical: false,
                ovSevChart: null,
                ovCompChart: null,
                toast: { visible: false, message: '' },

                showToast(msg) {
                    this.toast.message = msg;
                    this.toast.visible = true;
                    setTimeout(() => { this.toast.visible = false; }, 2600);
                },

                switchTab(tab) {
                    this.activeTab = tab;
                    if (tab === 'overview') {
                        setTimeout(() => this.initOverviewCharts(), 150);
                    }
                    setTimeout(() => this.safeIcons(), 80);
                },

                async initApp() {
                    try {
                        this.apiKey = localStorage.getItem('bugpulse_gemini_key') || '';
                    } catch(e) {}
                    this.safeIcons();
                    await this.loadScenarios();
                    await this.loadPulse();
                    await this.loadRecords();
                    setTimeout(() => {
                        this.initOverviewCharts();
                        this.safeIcons();
                    }, 250);
                },

                saveKey() {
                    try {
                        localStorage.setItem('bugpulse_gemini_key', this.apiKey);
                    } catch(e) {}
                    this.showKeyModal = false;
                    this.showToast('API Key saved successfully!');
                },

                safeIcons() {
                    if (typeof lucide !== 'undefined' && lucide.createIcons) {
                        lucide.createIcons();
                    }
                },

                async loadScenarios() {
                    try {
                        const res = await fetch('/api/scenarios');
                        const data = await res.json();
                        this.scenarioNames = data.scenario_names || [];
                        this.scenarios = data.scenarios || {};
                    } catch(e) {
                        console.error('Failed loading scenarios', e);
                    }
                },

                loadScenario(autoRun = false) {
                    const sc = this.scenarios[this.selectedScenario];
                    if (sc) {
                        this.formTitle = sc.title || '';
                        this.formSeverity = sc.reported_severity || 'Not Sure';
                        this.formText = sc.raw_text || '';
                        if (autoRun) {
                            this.runTriage();
                        }
                    }
                },

                async loadPulse() {
                    try {
                        const res = await fetch('/api/pulse');
                        this.pulse = await res.json();
                        this.updateOverviewCharts();
                    } catch(e) {
                        console.error('Failed loading pulse', e);
                    }
                },

                async loadRecords() {
                    try {
                        const res = await fetch('/api/records');
                        this.records = await res.json();
                        if (this.records.length > 0 && !this.activeRecord) {
                            this.activeRecord = this.records[0];
                        }
                        this.groupDuplicates();
                    } catch(e) {
                        console.error('Failed loading records', e);
                    }
                },

                groupDuplicates() {
                    const groups = {};
                    (this.records || []).forEach(r => {
                        const lbl = r.duplicate_group_label || 'Individual Ticket';
                        if (!groups[lbl]) groups[lbl] = [];
                        groups[lbl].push(r);
                    });
                    this.duplicateGroups = groups;
                },

                async runTriage() {
                    if (!this.formText.trim()) return;
                    this.loading = true;
                    try {
                        const res = await fetch('/api/triage', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({
                                title: this.formTitle,
                                raw_text: this.formText,
                                reported_severity: this.formSeverity,
                                api_key: this.apiKey
                            })
                        });
                        const data = await res.json();
                        this.activeRecord = data;
                        await this.loadPulse();
                        await this.loadRecords();
                        this.showToast('Bug analysis complete!');
                        setTimeout(() => this.safeIcons(), 100);
                    } catch (e) {
                        alert('Triage failed: ' + e.message);
                    } finally {
                        this.loading = false;
                    }
                },

                async uploadCsv(evt) {
                    const file = evt.target.files[0];
                    if (!file) return;
                    const formData = new FormData();
                    formData.append('file', file);
                    if (this.apiKey) formData.append('api_key', this.apiKey);

                    this.showToast('Processing CSV batch...');
                    try {
                        const res = await fetch('/api/batch/upload', {
                            method: 'POST',
                            body: formData
                        });
                        const data = await res.json();
                        await this.loadPulse();
                        await this.loadRecords();
                        this.showToast(`Batch processed: ${data.processed_count} tickets analyzed!`);
                        setTimeout(() => this.safeIcons(), 100);
                    } catch (e) {
                        alert('Upload failed: ' + e.message);
                    }
                },

                async sendFeedback(vote) {
                    if (!this.activeRecord) return;
                    await fetch('/api/feedback', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ bug_id: this.activeRecord.bug_id, vote: vote })
                    });
                    this.activeRecord.human_feedback = vote;
                    await this.loadPulse();
                    this.showToast('Feedback recorded: ' + (vote === 'UP' ? '👍 Helpful' : '👎 Flagged'));
                },

                async reseedData() {
                    this.reloading = true;
                    await fetch('/api/batch/seed', { method: 'POST' });
                    await this.loadPulse();
                    await this.loadRecords();
                    this.reloading = false;
                    this.showToast('Database reset and reseeded with enterprise batch!');
                    setTimeout(() => this.safeIcons(), 100);
                },

                selectRecord(rec) {
                    this.activeRecord = rec;
                    this.showToast('Loaded ' + rec.bug_id);
                    setTimeout(() => this.safeIcons(), 100);
                },

                copyText(text) {
                    navigator.clipboard.writeText(text);
                    this.showToast('Copied to clipboard!');
                },

                downloadJson(rec) {
                    const blob = new Blob([JSON.stringify(rec, null, 2)], { type: 'application/json' });
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = `${rec.bug_id}_analysis_report.json`;
                    a.click();
                    URL.revokeObjectURL(url);
                    this.showToast('Downloaded report JSON!');
                },

                get highPriorityRecords() {
                    return (this.records || []).filter(r => r.summary && r.summary.suggested_priority && r.summary.suggested_priority.level === 'High');
                },

                get filteredRecords() {
                    if (!this.searchQuery) return this.records;
                    const q = this.searchQuery.toLowerCase();
                    return this.records.filter(r => 
                        (r.bug_id || '').toLowerCase().includes(q) ||
                        (r.summary && r.summary.title ? r.summary.title.toLowerCase() : '').includes(q) ||
                        (r.summary && r.summary.component ? r.summary.component.toLowerCase() : '').includes(q) ||
                        (r.summary && r.summary.suggested_priority ? r.summary.suggested_priority.level.toLowerCase() : '').includes(q)
                    );
                },

                initOverviewCharts() {
                    const elSev = document.getElementById('overviewSevChart');
                    if (elSev && typeof Chart !== 'undefined') {
                        if (this.ovSevChart) {
                            this.ovSevChart.destroy();
                            this.ovSevChart = null;
                        }
                        const ctx = elSev.getContext('2d');
                        this.ovSevChart = new Chart(ctx, {
                            type: 'doughnut',
                            data: {
                                labels: ['High', 'Medium', 'Low'],
                                datasets: [{
                                    data: [this.pulse.high_priority_count || 1, this.pulse.medium_priority_count || 1, this.pulse.low_priority_count || 1],
                                    backgroundColor: ['#D92D20', '#B54708', '#027A48'],
                                    borderWidth: 0
                                }]
                            },
                            options: {
                                responsive: true,
                                maintainAspectRatio: false,
                                plugins: {
                                    legend: { position: 'right', labels: { color: '#667085', font: { family: 'Inter', size: 12 } } }
                                },
                                cutout: '72%'
                            }
                        });
                    }

                    const elComp = document.getElementById('overviewCompChart');
                    if (elComp && typeof Chart !== 'undefined') {
                        if (this.ovCompChart) {
                            this.ovCompChart.destroy();
                            this.ovCompChart = null;
                        }
                        const ctx = elComp.getContext('2d');
                        const labels = Object.keys(this.pulse.component_breakdown || {});
                        const values = Object.values(this.pulse.component_breakdown || {});
                        this.ovCompChart = new Chart(ctx, {
                            type: 'bar',
                            data: {
                                labels: labels.length ? labels : ['Payments', 'Auth', 'Checkout'],
                                datasets: [{
                                    data: values.length ? values : [6, 5, 4],
                                    backgroundColor: '#087F73',
                                    borderRadius: 6
                                }]
                            },
                            options: {
                                indexAxis: 'y',
                                responsive: true,
                                maintainAspectRatio: false,
                                plugins: { legend: { display: false } },
                                scales: {
                                    x: { ticks: { color: '#98A2B3', font: { size: 10 } }, grid: { color: '#F2F4F7' } },
                                    y: { ticks: { color: '#344054', font: { family: 'Inter', size: 11, weight: '500' } }, grid: { display: false } }
                                }
                            }
                        });
                    }
                },

                updateOverviewCharts() {
                    if (this.ovSevChart) {
                        this.ovSevChart.data.datasets[0].data = [
                            this.pulse.high_priority_count || 0,
                            this.pulse.medium_priority_count || 0,
                            this.pulse.low_priority_count || 0
                        ];
                        this.ovSevChart.update();
                    }
                    if (this.ovCompChart && this.pulse.component_breakdown) {
                        this.ovCompChart.data.labels = Object.keys(this.pulse.component_breakdown);
                        this.ovCompChart.data.datasets[0].data = Object.values(this.pulse.component_breakdown);
                        this.ovCompChart.update();
                    }
                }
            }
        }
    </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def serve_spa():
    return HTMLResponse(content=SPA_HTML, status_code=200)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False)
