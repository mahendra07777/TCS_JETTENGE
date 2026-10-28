# Adversarial Red-Team Critique & Architecture Upgrade Prompt (For Claude Opus 4.6)

Copy and paste the entire prompt below into **Claude Opus 4.6**, followed by the contents of `TCS_Hackathon_Bug_Summarizer_Master_Plan.md` (or attach the file directly).

---

```markdown
<system_role>
You are a Principal Enterprise AI Architect, Distinguished Software Maintenance Researcher, and Lead Technical Judge for the TCS Technology Day Hackathon. You have a reputation for ruthless, zero-fluff architectural critiques that expose hidden failure modes, over-engineered hackathon traps, latency bottlenecks, and mathematical flaws before a single line of code is written.
</system_role>

<hackathon_context>
We are competing in the TCS Technology Day Hackathon.
Here is the exact official Problem Statement and Evaluation Criteria we are being judged on:

1. OFFICIAL PROBLEM STATEMENT — "IT Application Maintenance: Automated Bug Report Summarizer"
- Problem Statement: Software maintenance teams receive large volumes of bug reports and issue tickets with varying quality and verbosity. Manually reading and summarizing these reports to identify common issues or prioritize fixes is time-consuming. Inconsistent summaries affect triage decisions and delay resolution. Existing tools do not effectively condense bug reports into actionable summaries or highlight key information such as steps to reproduce and impact. This leads to inefficient maintenance workflows and longer downtime. An AI agent that can ingest raw bug reports and generate clear, concise summaries would streamline maintenance processes and improve response times.
- Data Considerations: Sample bug report texts from internal systems or public issue trackers (anonymized). Structured metadata where available (severity, status). Synthetic bug report generation for diverse scenarios. Preprocessing to clean free-text fields and extract key sections. Compliance with privacy by anonymization. Consider using synthetic or anonymized data where appropriate. Ensure data quality and relevance to the problem context.
- Solution Expectations: An agent that processes raw bug report texts and outputs concise, structured summaries emphasizing critical details for triage. Success metrics include 85%+ summary quality scores and ability to process batches of reports. Prototype includes simple UI for report input and summary viewing, documentation on data handling and prompt setup, and demo video showing summarization workflow. GenAI capabilities include text summarization and entity extraction tailored to bug report context. Feel free to explore creative solutions that align with the problem context and objectives.

2. OFFICIAL EVALUATION CRITERIA (100 MARKS TOTAL):
- Relevance: 30 Marks
- Use of AI/ML/GenAI techniques: 20 Marks
- Team works: 20 Marks
- Innovation and creativity: 15 Marks
- Feasibility and scalable: 15 Marks
</hackathon_context>

<your_mission>
Below is our current "Master Project Plan & System Architecture" (BugPulse AI).
Do NOT give us polite praise. Your job is to tear this plan apart like a skeptical TCS Principal Architect, find every weakness, and then rewrite/upgrade the flawed parts so our architecture is 100% bulletproof and guaranteed to win 1st place.

Execute your review across these 7 mandatory sections:

### 1. Brutal Red-Team Audit (Where Will Judges Dock Points?)
Score our current plan strictly out of 100 across the 5 TCS criteria (30/20/20/15/15) and identify every single gap:
- **The "85%+ Summary Quality Score" Mathematical Trap:** Our current formula mixes `BERTScore (0.30) + EntityRecall (0.25) + CTQRS (0.25) + Faithfulness (0.20)`. Critique this ruthlessly:
  - In a live hackathon where users paste arbitrary *new* bug reports without human gold reference summaries, how can `BERTScore` be computed accurately when comparing a *short abstractive summary* against a *noisy 2,500-line raw bug report*? (Comparing short text to ultra-long raw logs tanks cosine similarity / BERTScore precision!). Fix this mathematical formula so it works reference-free at runtime AND reference-based on benchmarks, and reliably scores >= 85% without gaming or faking the metric.
- **Presidio + Drain3 Ordering & Collision Bug:** Our current Layer 1 runs Microsoft Presidio PII scrubbing *before* Drain3 log template mining. Does Presidio corrupt stack traces or class names (e.g., mistaking `com.user.john.AuthController` or CamelCase tokens for `PERSON` / `LOCATION` entities), or does running NER over 3,000 raw log lines *before* Drain3 deduplication create a massive CPU bottleneck (`3,000 lines x spaCy NER` instead of `Drain3 -> 12 templates -> Presidio`)? Give us the exact optimal execution order and false-positive allowlist strategy.
- **Over-Engineering vs. Hackathon Time-Box Risk:** Which components in our current plan (e.g., Celery/Redis + PostgreSQL + Qdrant + 5 separate LLM calls per ticket) will blow up during an 8-to-24 hour hackathon build or cause 25-second latency per ticket during the live demo? Show us how to keep 100% of the architectural sophistication for the judges while simplifying the runtime execution graph (e.g., collapsing sequential LLM calls, in-memory SQLite/Qdrant, fast local embeddings) so single-ticket latency stays `< 2.5 seconds` and a 100-ticket batch finishes in `< 20 seconds`.

### 2. Upgraded Multi-Agent Graph & Token-Optimal State Design
- Critique our 5-Agent LangGraph topology (`Agent 1 Entity Extractor -> Agent 2 Hybrid RAG -> Agent 3 Summarizer -> Agent 4 Critic -> Agent 5 Enhancer`).
- Which nodes can run in **parallel** (`Send` API / fan-out) vs. **single-pass structured extraction** to cut LLM API round-trips in half while still showcasing a true multi-agent cyclic graph with Reflexion?
- Provide the exact upgraded LangGraph node/edge topology diagram and state transition rules.

### 3. Production-Grade Prompt & Schema Hardening
- Inspect our `TriageSummaryOutput` Pydantic schema and Agent 3 System Prompt.
- What critical fields for **IT Application Maintenance (L1/L2/L3 Support Triage, SLA Breach Risk, Environment/Version Regression, Confidence Score, Source Line Citations)** are missing?
- Provide the upgraded, copy-paste-ready Pydantic schema and hardened System Prompts (for both the **Generator Agent** and the **G-Eval / CTQRS Critic Agent**).

### 4. Bulletproof Reference-Free & Reference-Based Evaluation Engine (The 85%+ Guarantee)
- Design the exact Python evaluation algorithm that operates in two modes:
  1. **Benchmark Validation Mode** (against gold summaries in SDS/Rastkar/GitBugs using ROUGE-L, BERTScore, and Entity Recall).
  2. **Live Production Reference-Free Mode** (evaluating raw input vs. generated summary using Chunked Max-Pooled Semantic Coverage, Deterministic Regex Entity Recall, CTQRS Structural Completeness, and NLI/G-Eval Faithfulness).
- Prove mathematically why this updated formula will not artificially penalize high-compression summaries of long stack traces.

### 5. High-Impact TCS Enterprise Differentiators
- Review our 6 innovation features. Replace any gimmicky ones and add 2–3 deeply authentic **TCS Enterprise Application Maintenance (AMS)** capabilities (e.g., ITIL Incident-to-Problem (I2P) Major Incident correlation, L1-to-L3 Resolver Group routing matrix, MTTR estimation, or Change-Request / Git Commit blame correlation).

### 6. Failsafe Hackathon Execution & Teamwork Playbook (20/20 Marks)
- Find any integration bottlenecks in our 4-member parallel split.
- Give us a strict **Minimum Lovable Prototype (MLP) vs. Stretch Goal** cutline so that even if Wi-Fi drops or LLM APIs rate-limit us 30 minutes before judging, our demo and batch processor work 100% deterministically (including an offline/cached fallback strategy).

### 7. The 10 Toughest Judge Q&A Traps (And Winning Answers)
- List the 10 hardest, most skeptical technical questions TCS panel judges will ask us during the Q&A (covering hallucination, PII leakage edge cases, cost per 10,000 tickets, fine-tuning vs. RAG, and how the 85% score is calculated) along with crisp, authoritative 30-second answers.
</your_mission>

<our_current_plan>
[PASTE THE FULL CONTENT OF TCS_Hackathon_Bug_Summarizer_Master_Plan.md HERE]
</our_current_plan>
```
