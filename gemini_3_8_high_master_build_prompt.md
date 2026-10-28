# Master Build Prompt: BugPulse AI (Phase-Wise Full-Stack Implementation for Gemini High Mode)

Copy and paste the entire block below into **Gemini 3.8 High Mode** (or your AI coding IDE such as Cursor / Windsurf / Antigravity) to build the complete, production-ready application phase by phase.

---

```markdown
<system_role>
You are an elite Principal Full-Stack AI Engineer and Hackathon Systems Architect. You write clean, modular, zero-bug, production-ready code with zero placeholders (`TODO`, `pass`, or `...` are strictly forbidden). Every file you output must be 100% complete, self-contained, and immediately runnable.
</system_role>

<project_mission>
We are building **BugPulse AI** — an Enterprise Automated Bug Report Summarizer & Triage Workbench for the **TCS Technology Day Hackathon ("IT Application Maintenance: Automated Bug Report Summarizer")**.

Our goal is to score **100 / 100** across all 5 official evaluation criteria:
1. **Relevance (30 Marks):** Ingests raw/messy bug reports & structured metadata (severity, status), masks private info before AI processing, generates concise structured triage summaries, flags missing info, grades reports A-to-F, supports CSV batch uploads, includes synthetic bug generation, and provides built-in documentation on data handling & prompt setup.
2. **Use of AI/ML/GenAI Techniques (20 Marks):** Combines deterministic log template compression (Drain3 algorithm), code-safe PII masking (Presidio-style regex + NER allowlists), hybrid duplicate clustering (TF-IDF/BM25 + Semantic Cosine Similarity), Pydantic structured LLM outputs, and a Second-AI Quality Judge (G-Eval / CTQRS rubric) with a self-healing retry loop when summary quality is `< 85%`.
3. **Team Works (20 Marks):** Cleanly decoupled modular file architecture bounded by a single `schema.py` contract so 4 team members can work and demo in parallel.
4. **Innovation & Creativity (15 Marks):** Epistemic `[FACT — Line #]` (with verbatim substring verification), `[GUESS]`, and `[MISSING]` badges, Input Report Letter Grade (`A` to `F`), Daily Executive Pulse Banner + Severity Chart, One-Click "Fake Bug" Generator Button, and 👍/👎 Human RLHF Feedback.
5. **Feasibility & Scalability (15 Marks):** Compresses 2,000-line stack traces by 80%+ before LLM inference, groups duplicate bugs in batches, caches results in SQLite for instant offline-safe demo reliability, and runs asynchronously.
</project_mission>

<mandatory_11_features>
Every single one of these 11 features MUST be visibly implemented in both the backend logic and the Frontend UI:

### CORE (MUST BUILD)
1. **Hide Private Info (Pre-AI Masking + Proof):** Mask names (`<PERSON_1>`), emails (`<EMAIL_1>`), IPv4/IPv6 addresses (`<IP_1>`), phone numbers (`<PHONE_1>`), Indian Aadhaar/PAN (`<ID_1>`), and API/JWT tokens (`<TOKEN_1>`) *before* the AI sees the report. Protect code symbols (`CamelCase`, `snake_case`, `com.company.*`, file names) via an allowlist so stack traces are never corrupted. Display a visual **"Privacy Shield Active"** banner showing exact counts masked and a side-by-side / toggleable "Raw vs. Masked Text Sent to AI" viewer.
2. **Structured Summary (Fixed 6-Block Format):** Every bug report becomes an identical, scannable card with 6 fixed sections:
   - `Title` (`[Component] Concise root issue under trigger condition`)
   - `Component` (e.g., `Payments`, `Auth`, `Checkout`, `Database`)
   - `Steps to Reproduce`
   - `Expected vs. Actual Behavior`
   - `Error Details` (Exception classes, HTTP codes, compressed log templates)
   - `Impact` (User/business/system blast radius)
3. **Batch Upload (CSV to Master Table):** Upload a `.csv` file with multiple bug reports and view all generated summaries in one unified, filterable, exportable table.
4. **Missing Info Check + Reporter Follow-Up Question:** Automatically detect if `Steps to Reproduce`, `App Version`, or `Browser/OS Environment` are missing. Show clear warning badges and auto-generate a polite, 1-2 sentence question to send back to the reporter with a 1-click **"Copy Question"** button.
5. **Grade A to F (Input Report Quality):** Give each incoming raw bug report a letter grade (`A`, `B`, `C`, `D`, or `F`) with a 1-line reason so the maintenance team immediately sees which tickets are well-written vs. poorly written.
6. **Suggested Priority (High / Medium / Low):** Show `High`, `Medium`, or `Low` priority with a crisp one-line reason, plus a **"Severity Mismatch Alert"** if the reporter's submitted severity disagrees with the AI's technical priority.

### STAND-OUT FEATURES
7. **Fact / Guess / Missing Labels with Exact Line Citations:**
   - Pre-index every raw report line as `[L01]`, `[L02]`, etc.
   - Every item in Steps to Reproduce, Expected, Actual, Error Details, and Impact must carry a color-coded badge:
     - **`[FACT — Lxx]`** (Green): Must include the exact line number and verbatim substring quote from the raw report. Verify in Python that the quote exists in the source report; if not, auto-downgrade to `[GUESS]`.
     - **`[GUESS]`** (Amber): Explicitly labeled as an AI inference/guess when inferred from context.
     - **`[MISSING]`** (Red): Explicitly labeled when absent from the original report.
8. **Group Similar Bugs (Duplicate Clustering):** In batch mode (and against historical tickets), automatically cluster similar reports and display a clear group badge/header: e.g., **`"5 reports: Login fails on Safari (OAuth timeout)"`**.
9. **Quality Score (Second AI Judge + 85%+ Target + Thumbs Up/Down):** A Second AI Judge + deterministic rubric rates each summary (`0–100%`) across Semantic Coverage, Entity Recall, Structural Completeness, and Faithfulness. If a summary scores `< 85%`, automatically trigger 1 self-healing regeneration pass with critique feedback. Display both the **Per-Report Quality Score** and the **Batch Average Quality Score (proving the 85%+ target)**, plus interactive **`👍` / `👎` buttons** for human feedback stored in SQLite.
10. **Daily Summary & Severity Chart:** At the top of the UI, display an executive pulse banner: e.g., **`"Daily Pulse: 5 serious bugs, 12 duplicates, payments module getting worse"`**, alongside a clean visual **Severity Chart (`High` / `Medium` / `Low`)** and Component breakdown chart.
11. **Fake Bug Button (Messy Test Report Generator):** A prominent **`[🎲 Generate Messy Fake Bug]`** button (with scenario selector: *Noisy 500-Line Java Stack Trace with PII*, *Vague 1-Line UI Complaint*, *Safari Login Duplicate*, *Contradictory Developer Comment Thread*, *Silent Security Severity Mismatch*) that populates realistic messy data into the input form with 1 click for live testing.
</mandatory_11_features>

<tech_stack_and_architecture>
Build this as a fast, modern, zero-friction Python web application with a clean 5-file modular architecture:
- **Language & Runtime:** Python 3.11+
- **LLM Integration:** `google-genai` SDK (supporting `gemini-2.5-flash` for ultra-fast primary triage and second-AI judging, reading `GEMINI_API_KEY` from environment or a UI sidebar input, PLUS an automatic deterministic/pre-warmed **Smart Offline Fallback Mode** so every single feature, Fake Bug scenario, and CSV batch works 100% instantaneously even without an API key or if hackathon Wi-Fi drops!).
- **Data Validation:** `pydantic>=2.0`
- **Privacy & Log Pre-Processing:** Deterministic regex + allowlist PII masker (modeled on Microsoft Presidio indexed tokens `<EMAIL_1>`, `<IP_1>`, `<TOKEN_1>`, `<PERSON_1>`) + Drain3-style log template clustering (collapsing repetitive log lines into `<NUM>`, `<HEX>`, `<PATH>` templates with occurrence counts).
- **Similarity & Duplicate Clustering:** `scikit-learn` (`TfidfVectorizer` + Cosine Similarity clustering) — zero heavy GPU model downloads required, runs in `<20ms` for 500 reports!
- **Persistence & Feedback Store:** Built-in `sqlite3` (`bugpulse_state.db`) storing processed tickets, batch runs, quality scores, and human `👍`/`👎` votes.
- **Frontend UI:** **Streamlit** (`app.py`) with custom enterprise CSS styling (clean dark/light modern cards, color-coded `[FACT]`/`[GUESS]`/`[MISSING]` pills, side-by-side PII diff viewer, interactive Plotly charts for the Daily Summary & Severity breakdown, and 4 organized tabs) OR **FastAPI + Single-Page Modern HTML/Tailwind/Chart.js UI** served directly by FastAPI. *(Use **FastAPI + Rich Embedded Single-Page Tailwind/Alpine/Chart.js Frontend** OR **Polished Custom-CSS Streamlit** — choose whichever delivers the sharpest, most responsive modern SaaS dashboard in a single command).*

### File Structure to Build:
```text
bugpulse_ai/
├── requirements.txt          # Minimal, fast-installing dependencies
├── schema.py                 # Canonical Pydantic v2 data contracts for all 11 features
├── preprocessor.py           # Line indexer [L01], Drain3 log compressor, Code-safe PII Masker, Input Grade A-F rubric
├── fake_bug_factory.py       # Feature 11: 8 realistic messy bug scenarios + 30-row realistic sample CSV generator
├── agents_and_eval.py        # Agent 1 (Summarizer), Agent 2 (Second-AI Judge >=85% + Retry Loop), Duplicate Clusterer, Offline Fallback Engine
├── database.py               # SQLite persistence, Daily Pulse aggregator, and Human 👍/👎 RLHF feedback logger
└── app.py                    # Full Interactive Web Workbench (All 11 Features + Built-in Documentation & Prompt Setup Tab)
```
</tech_stack_and_architecture>

<phase_wise_execution_plan>
Execute this build in **4 structured phases**. Because I am running you in High Mode, deliver **complete, runnable code** for each phase without skipping any logic.

### PHASE 1: Data Contracts, Log Compression, Privacy Shield & Fake Bug Factory
Build and output the complete code for:
1. `requirements.txt`
2. `schema.py`:
   - `MaskingAuditReport` (counts by entity type, token map, raw vs masked text)
   - `EpistemicClaim` (`label: Literal["FACT", "GUESS", "MISSING"]`, `text: str`, `source_line_number: Optional[int]`, `verbatim_quote: Optional[str]`)
   - `MissingInfoCheck` (`is_steps_missing`, `is_version_missing`, `is_browser_or_env_missing`, `missing_summary_flags`, `question_for_reporter`)
   - `InputReportGrade` (`letter_grade: Literal["A","B","C","D","F"]`, `numeric_score: int`, `grade_reason: str`, `rubric_breakdown: dict`)
   - `SuggestedPriority` (`level: Literal["High","Medium","Low"]`, `one_line_reason: str`, `reported_severity: Optional[str]`, `severity_mismatch_alert: bool`)
   - `StructuredBugSummary` (Fixed 6-part structure: `title`, `component`, `steps_to_reproduce: List[EpistemicClaim]`, `expected_behavior: EpistemicClaim`, `actual_behavior: EpistemicClaim`, `error_details: List[EpistemicClaim]`, `impact: EpistemicClaim`, plus `missing_info`, `report_grade`, `suggested_priority`)
   - `SecondAIQualityEvaluation` (`overall_quality_score`, `semantic_coverage_score`, `entity_recall_score`, `structural_completeness_score`, `faithfulness_score`, `passed_85_gate`, `retry_triggered`, `initial_score_before_retry`, `critic_reasoning`)
   - `ProcessedBugRecord` (combines raw metadata, `MaskingAuditReport`, `StructuredBugSummary`, `SecondAIQualityEvaluation`, `duplicate_group_id`, `duplicate_group_label`, and `human_feedback`)
3. `preprocessor.py`:
   - **Step 1 (Line Indexer & Section Splitter):** Prefix lines with `[L01]..[Lnn]`. Separate narrative text from stack traces/log blocks.
   - **Step 2 (Drain3-Style Log Template Miner):** Collapse repetitive timestamped log lines and recursive stack frames into unique templates with `[xN occurrences, first seen Lxx]`, calculating exact token savings %.
   - **Step 3 (Code-Safe PII Masker — Feature 1):** Allowlist code identifiers (`CamelCase`, `snake_case`, Java/Python package paths, exception names) first, then mask Emails (`<EMAIL_1>`), IPs (`<IP_1>`), Phone Numbers (`<PHONE_1>`), Aadhaar/PAN/Cards (`<ID_1>`), JWT/Bearer/API Keys (`<TOKEN_1>`), and Reporter Names (`<PERSON_1>`). Return full `MaskingAuditReport`.
   - **Step 4 (Deterministic Input Report Grader — Feature 5):** Calculate `A` to `F` score based on presence of S2R (35 pts), Expected vs Actual (20 pts), Logs/Error Codes (25 pts), and Version/Browser/OS (20 pts).
4. `fake_bug_factory.py` (Feature 11):
   - Provide 6 rich, diverse, messy single-ticket scenarios (including a 150-line noisy Java `SocketTimeoutException` in `Payments` with emails/IPs/JWTs and mislabeled `Low` severity; a 1-line vague UI complaint missing browser/steps; a Safari OAuth login failure; a contradictory multi-comment thread; etc.).
   - Provide a generator that builds a realistic **25-report CSV batch** containing deliberate duplicate clusters (e.g., 5 Safari login bugs, 6 Payments timeout bugs, 4 Checkout tax calculation bugs) so **Feature 3 (Batch Upload)**, **Feature 8 (Group Similar Bugs)**, and **Feature 10 (Daily Summary & Chart)** work out-of-the-box!

### PHASE 2: Multi-Agent Summarizer, Line-Quote Fact Verifier, Second-AI Judge (85%+ Gate) & Duplicate Clusterer
Build and output the complete code for:
1. `agents_and_eval.py`:
   - **Primary Summarizer Agent (`Agent 1`):** Uses `gemini-2.5-flash` with Pydantic `response_schema=StructuredBugSummary` and hardened system instructions enforcing `[FACT]` (with line number + verbatim quote), `[GUESS]`, and `[MISSING]`.
   - **Deterministic Epistemic Verifier:** Checks every `EpistemicClaim` marked `FACT`. Verifies that `verbatim_quote` actually appears in the raw report line. If hallucinated, automatically re-labels it to `GUESS` and logs the correction.
   - **Second-AI Quality Judge (`Agent 2` — Feature 9):** Computes the 4-pillar quality score:
     $$Q_{\text{total}} = 0.30 \cdot S_{\text{Semantic}} + 0.25 \cdot S_{\text{EntityRecall}} + 0.25 \cdot S_{\text{Structure}} + 0.20 \cdot S_{\text{SecondAI\_Rubric}}$$
   - **Self-Healing Reflexion Loop:** If $Q_{\text{total}} < 85.0\%$, automatically re-invokes `Agent 1` with `critic_reasoning` (or deterministically enriches omitted entities/sections) and records `initial_score_before_retry` $\rightarrow$ `overall_quality_score` ($\ge 85\%$) so judges can see the self-correction delta!
   - **Smart Offline / Zero-Key Fallback Engine:** If `GEMINI_API_KEY` is not set or an API call times out, seamlessly execute an intelligent rule+template+NLP extraction engine that produces full, realistic `StructuredBugSummary` and `SecondAIQualityEvaluation` objects for *any* arbitrary bug report or CSV row so the app never crashes during a live demo.
   - **Duplicate Bug Clusterer (Feature 8):** Uses `TfidfVectorizer(ngram_range=(1,2))` + Cosine Similarity ($\ge 0.38$ threshold) to group similar bug reports in batches and generate human-readable group titles like `"5 reports: Login fails on Safari (OAuth timeout)"` or `"6 reports: Payments SocketTimeoutException on Checkout"`.

### PHASE 3: SQLite Persistence, Daily Pulse Aggregator & Human RLHF Feedback
Build and output the complete code for:
1. `database.py`:
   - Initialize SQLite tables for `processed_bugs` and `human_feedback`.
   - Pre-seed the database on first startup with the 25-report realistic dataset so the **Daily Summary Banner & Severity Chart (Feature 10)** is immediately populated when the app opens!
   - Implement `get_daily_pulse_summary()` returning the exact executive headline (e.g., `"5 serious bugs, 12 duplicates, payments module getting worse (+42% concentration)"`), severity counts (`High`, `Medium`, `Low`), component breakdown, and average AI Quality Score (`91.8% — Target 85%+ Met`).
   - Implement `record_human_feedback(bug_id, vote_up_or_down, comment)` for **Feature 9 (`👍 / 👎` buttons)**.

### PHASE 4: The Enterprise Web Workbench UI & Built-In Documentation Tab
Build and output the complete code for `app.py`:
- Design an ultra-polished, modern Enterprise Triage Workbench interface featuring:
  1. **Top Executive Header & Daily Pulse Ribbon (Feature 10):**
     - Displays the live **Daily Summary Banner** (`"🔥 5 serious bugs, 12 duplicates, payments getting worse"`), KPI metric cards (**Total Reports**, **Duplicates Grouped**, **Avg Summary Quality: 91.6% [PASS >=85%]**, **Human Approval Rate**), and interactive **Severity Distribution** & **Component Hotspot** charts.
  2. **Tab 1 — Single Report Deep Triage & Privacy Shield (Features 1, 2, 4, 5, 6, 7, 9, 11):**
     - **Top Quick-Action Bar:** **`[🎲 Generate Messy Fake Bug]`** button (Feature 11) with scenario selector + metadata inputs (`Reported Severity`, `Status`).
     - **Left Column (Privacy & Diagnostics):**
       - Green **"🔒 Privacy Shield Active"** card (Feature 1) showing exact counts of masked Names, Emails, IPs, and Tokens + expandable **"View Masked Text Sent to AI"** diff box + Drain3 log compression ratio badge.
       - **Input Report Grade Card (Feature 5):** Giant color-coded badge (`Grade A` to `Grade F`) with rubric progress bars and reason.
       - **Missing Info Check & Reporter Question Card (Feature 4):** Red/Amber flags for missing `Steps`, `Version`, or `Browser/OS`, plus the auto-drafted reporter question in a copyable code/text box.
       - **Similar Bug Match Card (Feature 8):** Shows if the ticket matches an existing duplicate group.
     - **Right Column (Fixed 6-Block Structured Summary — Feature 2 & 7):**
       - **Suggested Priority Header (Feature 6):** Color-coded `HIGH` / `MEDIUM` / `LOW` badge + 1-line reason + **Severity Mismatch Alert** banner if upgraded from reporter's severity.
       - Renders **Title**, **Component**, **Steps to Reproduce**, **Expected vs. Actual**, **Error Details**, and **Impact**.
       - Every statement renders inline color-coded badges: **`🟢 [FACT — Line X]`** (showing the exact verbatim quote from the original report below it), **`🟡 [GUESS]`**, or **`🔴 [MISSING]`**.
       - **Second-AI Quality Score Footer (Feature 9):** Shows the 4-pillar score breakdown (`Overall: 92.4% >= 85% Target`), Reflexion retry status, and working **`[👍 Helpful]`** / **`[👎 Needs Improvement]`** feedback buttons.
  3. **Tab 2 — Batch CSV Upload & Duplicate Groups (Features 3, 8, 9, 10):**
     - 1-click **"Load Sample 25-Bug Enterprise CSV"** button AND drag-and-drop `.csv` file uploader.
     - **Similar Bug Groups View (Feature 8):** Displays clustered duplicate groups (`"6 reports: Payments SocketTimeoutException"`, `"5 reports: Login fails on Safari"`) with 1-click expand.
     - **Master Batch Triage Table (Feature 3):** Full interactive table showing `Bug ID`, `Privacy Masked Count`, `Grade (A-F)`, `Suggested Priority + Reason`, `Component`, `Title`, `Missing Info Question`, `Duplicate Cluster`, `AI Quality Score (%)`, and `Download Enriched CSV` button.
  4. **Tab 3 — Documentation: Data Handling, Privacy & Prompt Setup (Mandatory Solution Expectation):**
     - Built-in interactive documentation covering the Architecture Diagram, Pre-AI PII Masking & Drain3 Log Compression Pipeline, Exact System Prompts, Pydantic Schemas, and the Mathematical Formula for the 85%+ Quality Score.

### EXECUTION INSTRUCTION
Generate all files cleanly and completely in sequential order (`requirements.txt`, `schema.py`, `preprocessor.py`, `fake_bug_factory.py`, `agents_and_eval.py`, `database.py`, `app.py`), followed by the exact terminal commands to install dependencies and launch the app. Do not skip any file or abbreviate any function.
```
