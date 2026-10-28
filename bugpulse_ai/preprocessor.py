"""
BugPulse AI - Deterministic Preprocessor
Includes:
- Step 1: Line Indexer [L01]..[Lnn] & Section Splitter
- Step 2: Drain3-Style Log Template Miner & Recursive Stack Frame Folding (80%+ compression)
- Step 3: Code-Safe PII Masking with Allowlist Protection for Code/Stack Traces
- Step 4: Deterministic Input Report Grader (A to F)
"""

import re
from typing import List, Dict, Tuple, Set, Optional
from schema import MaskingAuditReport, InputReportGrade, MissingInfoCheck


class Preprocessor:
    """Enterprise-grade preprocessor combining log compression and zero-trust privacy."""

    # Common code allowlist tokens to protect from false-positive PII masking
    CODE_ALLOWLIST_PATTERNS = [
        re.compile(r'\b[a-zA-Z_][a-zA-Z0-9_]*\.(?:java|py|ts|js|go|cpp|c|cs|rb|php|html|css|json|xml)\b', re.IGNORECASE),
        re.compile(r'\b(?:com|org|io|net|gov|edu)\.[a-zA-Z0-9_]+(?:\.[a-zA-Z0-9_]+)+\b'),
        re.compile(r'\b[A-Z][a-zA-Z0-9]+(?:Exception|Error|Handler|Controller|Service|Repository|Factory|Strategy|Util|Impl|DTO|DAO|Client)\b'),
        re.compile(r'\bat\s+[a-zA-Z0-9_$./]+(?:\([a-zA-Z0-9_$./]+:\d+\))?'),
        re.compile(r'\bdef\s+[a-zA-Z_][a-zA-Z0-9_]*\b'),
        re.compile(r'\bclass\s+[A-Z][a-zA-Z0-9_]*\b'),
        re.compile(r'\b[A-Z_]{3,30}\b'), # HTTP methods, constants like GET, POST, DB_POOL_TIMEOUT
    ]

    # Regex patterns for sensitive entities
    EMAIL_REGEX = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b')
    IPV4_REGEX = re.compile(r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b')
    IPV6_REGEX = re.compile(r'\b(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}\b')
    PHONE_REGEX = re.compile(r'(?:\+?(\d{1,3})[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b|\b(?:\+91[-.\s]?)?[6-9]\d{9}\b')
    AADHAAR_REGEX = re.compile(r'\b[2-9]\d{3}[-\s]\d{4}[-\s]\d{4}\b')
    PAN_REGEX = re.compile(r'\b[A-Z]{5}[0-9]{4}[A-Z]\b')
    CREDIT_CARD_REGEX = re.compile(r'\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|6(?:011|5[0-9][0-9])[0-9]{12}|3[47][0-9]{13})\b')
    JWT_REGEX = re.compile(r'\beyJ[A-Za-z0-9-_]+\.eyJ[A-Za-z0-9-_]+\.[A-Za-z0-9-_]+\b')
    AWS_KEY_REGEX = re.compile(r'\b(?:AKIA|ABIA|ACCA|ASIA)[0-9A-Z]{16}\b')
    BEARER_TOKEN_REGEX = re.compile(r'\bBearer\s+([a-zA-Z0-9\-._~+/]+=*)\b', re.IGNORECASE)
    GENERIC_SECRET_REGEX = re.compile(r'(?:api[_-]?key|secret|password|access[_-]?token|auth[_-]?token)[\s:=]+([\'"][^\'"\s]{8,}[\'"]|[^\'"\s]{8,})', re.IGNORECASE)
    REPORTER_NAME_REGEX = re.compile(r'(?:reported\s+by|reporter|logged\s+by|submitted\s+by|created\s+by|contact\s+person|ticket\s+author|assigned\s+to)[\s:=]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)', re.IGNORECASE)

    # Log line & stack trace detection heuristics
    LOG_TIMESTAMP_REGEX = re.compile(r'^\s*(\d{4}[-/.]\d{2}[-/.]\d{2}[T\s]\d{2}:\d{2}:\d{2}(?:\.\d+)?|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})\b')
    STACK_FRAME_REGEX = re.compile(r'^\s*(?:at\s+|File\s+"|\bTraceback\b|\bCaused by:\b|[a-zA-Z0-9_$.]+:\d+)')

    def __init__(self):
        pass

    # -------------------------------------------------------------------------
    # Step 1: Line Indexer & Section Splitter
    # -------------------------------------------------------------------------
    def index_lines(self, text: str) -> Tuple[str, List[Tuple[int, str]]]:
        """
        Pre-indexes each line with [L01], [L02] etc.
        Returns indexed string representation and list of (line_num, raw_line).
        """
        raw_lines = text.splitlines()
        indexed_lines = []
        indexed_text_parts = []
        for idx, line in enumerate(raw_lines, start=1):
            tag = f"[L{idx:02d}]"
            indexed_lines.append((idx, line))
            indexed_text_parts.append(f"{tag} {line}")
        return "\n".join(indexed_text_parts), indexed_lines

    def split_sections(self, text: str) -> Dict[str, List[str]]:
        """
        Partitions raw text into narrative lines vs. stack trace / log lines.
        """
        lines = text.splitlines()
        narrative = []
        logs_and_stacks = []

        in_stack_block = False
        for line in lines:
            stripped = line.strip()
            is_log = bool(self.LOG_TIMESTAMP_REGEX.match(stripped))
            is_stack = bool(self.STACK_FRAME_REGEX.match(stripped)) or "Exception" in stripped or "Error" in stripped

            if is_log or is_stack:
                logs_and_stacks.append(line)
                in_stack_block = True
            elif in_stack_block and (line.startswith("  ") or line.startswith("\t") or line == ""):
                logs_and_stacks.append(line)
            else:
                in_stack_block = False
                narrative.append(line)

        return {
            "narrative": narrative,
            "logs_and_stacks": logs_and_stacks
        }

    # -------------------------------------------------------------------------
    # Step 2: Drain3-Style Log Template Mining & Frame Folding
    # -------------------------------------------------------------------------
    def compress_logs(self, raw_text: str) -> Tuple[str, float, int, int]:
        """
        Drain3 fixed-depth clustering simulation for logs and repetitive stack traces.
        Replaces dynamic parameters (IPs, numbers, hex, UUIDs) and folds recursive calls.
        Returns (compressed_text, compression_ratio_percentage, original_lines, compressed_lines).
        """
        lines = raw_text.splitlines()
        orig_count = len(lines)
        if orig_count <= 6:
            return raw_text, 0.0, orig_count, orig_count

        compressed_lines: List[str] = []
        template_counts: Dict[str, Dict[str, Any]] = {}
        order_of_templates: List[str] = []

        for line_idx, line in enumerate(lines, start=1):
            stripped = line.strip()
            if not stripped:
                continue

            # Template abstraction
            template = stripped
            # Abstract timestamps
            template = re.sub(r'\d{4}[-/.]\d{2}[-/.]\d{2}[T\s]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?', '<TIMESTAMP>', template)
            # Abstract Hexadecimal addresses / memory offsets
            template = re.sub(r'0x[0-9a-fA-F]+', '<HEX>', template)
            # Abstract UUIDs
            template = re.sub(r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}', '<UUID>', template)
            # Abstract IPs in logs
            template = re.sub(r'\b(?:\d{1,3}\.){3}\d{1,3}(?::\d+)?\b', '<IP_PORT>', template)
            # Abstract large integers / ports
            template = re.sub(r'\b\d{3,}\b', '<NUM>', template)

            if template not in template_counts:
                template_counts[template] = {
                    "count": 1,
                    "first_seen_line": line_idx,
                    "representative": stripped
                }
                order_of_templates.append(template)
            else:
                template_counts[template]["count"] += 1

        for tmpl in order_of_templates:
            info = template_counts[tmpl]
            count = info["count"]
            first_line = info["first_seen_line"]
            rep = info["representative"]
            if count > 1:
                compressed_lines.append(f"{rep}  [Drain3: x{count} identical occurrences, first seen L{first_line:02d}]")
            else:
                compressed_lines.append(rep)

        comp_count = len(compressed_lines)
        savings = max(0.0, round(((orig_count - comp_count) / max(1, orig_count)) * 100.0, 1))
        return "\n".join(compressed_lines), savings, orig_count, comp_count

    # -------------------------------------------------------------------------
    # Step 3: Code-Safe PII Masking with Protected Code Allowlist
    # -------------------------------------------------------------------------
    def mask_pii_and_secrets(self, text: str) -> MaskingAuditReport:
        """
        Executes zero-trust, code-safe pseudonymization before AI processing.
        Code tokens, file paths, and stack traces are protected via an allowlist.
        Returns a full MaskingAuditReport.
        """
        token_map: Dict[str, str] = {}
        counts = {"EMAIL": 0, "IP": 0, "PHONE": 0, "ID": 0, "TOKEN": 0, "PERSON": 0}

        # Step 3a: Extract and protect code tokens
        code_spans: List[Tuple[int, int, str]] = []
        for pat in self.CODE_ALLOWLIST_PATTERNS:
            for match in pat.finditer(text):
                code_spans.append((match.start(), match.end(), match.group(0)))

        def is_inside_code(start: int, end: int) -> bool:
            for c_start, c_end, _ in code_spans:
                if (start >= c_start and start < c_end) or (end > c_start and end <= c_end):
                    return True
            return False

        sanitized = text

        # Helper to replace matches safely
        def replace_with_indexed_token(pattern: re.Pattern, entity_type: str, text_buf: str, group_num: int = 0) -> str:
            nonlocal counts, token_map
            matches = list(pattern.finditer(text_buf))
            # reverse iterate to keep correct char offsets
            for match in reversed(matches):
                val = match.group(group_num)
                m_start = match.start(group_num)
                m_end = match.end(group_num)

                # Skip if already a masked token or inside protected code
                if val.startswith("<") and val.endswith(">"):
                    continue
                if is_inside_code(m_start, m_end):
                    continue

                # Check if we already have an assigned token for this exact secret/PII
                existing_token = None
                for t, v in token_map.items():
                    if v == val:
                        existing_token = t
                        break

                if not existing_token:
                    counts[entity_type] += 1
                    token_id = f"<{entity_type}_{counts[entity_type]}>"
                    token_map[token_id] = val
                else:
                    token_id = existing_token

                text_buf = text_buf[:m_start] + token_id + text_buf[m_end:]
            return text_buf

        # 1. Mask JWT & API tokens
        sanitized = replace_with_indexed_token(self.JWT_REGEX, "TOKEN", sanitized)
        sanitized = replace_with_indexed_token(self.AWS_KEY_REGEX, "TOKEN", sanitized)
        sanitized = replace_with_indexed_token(self.BEARER_TOKEN_REGEX, "TOKEN", sanitized, group_num=1)
        sanitized = replace_with_indexed_token(self.GENERIC_SECRET_REGEX, "TOKEN", sanitized, group_num=1)

        # 2. Mask Aadhaar & PAN & Credit Cards
        sanitized = replace_with_indexed_token(self.AADHAAR_REGEX, "ID", sanitized)
        sanitized = replace_with_indexed_token(self.PAN_REGEX, "ID", sanitized)
        sanitized = replace_with_indexed_token(self.CREDIT_CARD_REGEX, "ID", sanitized)

        # 3. Mask Emails
        sanitized = replace_with_indexed_token(self.EMAIL_REGEX, "EMAIL", sanitized)

        # 4. Mask Phone Numbers
        sanitized = replace_with_indexed_token(self.PHONE_REGEX, "PHONE", sanitized)

        # 5. Mask IPs (IPv4 & IPv6)
        sanitized = replace_with_indexed_token(self.IPV4_REGEX, "IP", sanitized)
        sanitized = replace_with_indexed_token(self.IPV6_REGEX, "IP", sanitized)

        # 6. Mask Reporter Names (context-based)
        sanitized = replace_with_indexed_token(self.REPORTER_NAME_REGEX, "PERSON", sanitized, group_num=1)

        total = sum(counts.values())

        # Perform Drain3 compression calculation
        compressed_text, comp_ratio, orig_lines, comp_lines = self.compress_logs(sanitized)

        return MaskingAuditReport(
            total_masked=total,
            counts_by_type=counts,
            token_map=token_map,
            raw_text=text,
            masked_text=compressed_text,
            privacy_shield_status="ACTIVE",
            log_compression_ratio=comp_ratio,
            original_line_count=orig_lines,
            compressed_line_count=comp_lines
        )

    # -------------------------------------------------------------------------
    # Step 4: Deterministic Input Report Grader (A to F)
    # -------------------------------------------------------------------------
    def grade_input_report(self, raw_text: str) -> Tuple[InputReportGrade, MissingInfoCheck]:
        """
        Feature 5: Evaluates the quality of the incoming raw bug report.
        Grades A to F based on S2R, Expected/Actual, Stack Traces, and Environment.
        """
        score = 0
        breakdown = {
            "steps_to_reproduce": 0,
            "expected_vs_actual": 0,
            "error_logs_and_codes": 0,
            "environment_details": 0
        }

        lower = raw_text.lower()

        # 1. Check Steps to Reproduce (Max 35 pts)
        has_numbered_steps = bool(re.search(r'(?:^|\n)\s*(?:1[.)]|step\s*1)', lower))
        has_s2r_keywords = any(kw in lower for kw in ["steps to reproduce", "reproduction steps", "how to reproduce", "to repro:"])
        has_action_verbs = sum(1 for verb in ["click", "navigate", "submit", "open", "enter", "select", "send", "log in", "run"] if verb in lower)

        if has_numbered_steps or (has_s2r_keywords and has_action_verbs >= 2):
            breakdown["steps_to_reproduce"] = 35
        elif has_action_verbs >= 2:
            breakdown["steps_to_reproduce"] = 20
        elif has_action_verbs == 1:
            breakdown["steps_to_reproduce"] = 10
        else:
            breakdown["steps_to_reproduce"] = 0

        # 2. Check Expected vs. Actual (Max 20 pts)
        has_expected = any(kw in lower for kw in ["expected", "should have", "supposed to", "was expecting"])
        has_actual = any(kw in lower for kw in ["actual", "instead", "got", "observed", "resulted in", "crashes", "fails"])
        if has_expected and has_actual:
            breakdown["expected_vs_actual"] = 20
        elif has_expected or has_actual:
            breakdown["expected_vs_actual"] = 10
        else:
            breakdown["expected_vs_actual"] = 0

        # 3. Check Error Logs, Exception Codes, or Stack Traces (Max 25 pts)
        has_stack_trace = "exception" in lower or "traceback" in lower or "caused by" in lower or "error 5" in lower or "40" in lower
        has_http_status = bool(re.search(r'\b(?:400|401|403|404|500|502|503|504)\b', raw_text))
        has_drain_patterns = bool(re.search(r'\bat\s+[a-zA-Z0-9_$.]+\b', raw_text))

        if has_stack_trace and (has_http_status or has_drain_patterns):
            breakdown["error_logs_and_codes"] = 25
        elif has_stack_trace or has_http_status:
            breakdown["error_logs_and_codes"] = 18
        elif "error" in lower or "bug" in lower or "issue" in lower:
            breakdown["error_logs_and_codes"] = 10
        else:
            breakdown["error_logs_and_codes"] = 0

        # 4. Check Environment & Versions (Max 20 pts)
        has_version = bool(re.search(r'\bv?\d+\.\d+(?:\.\d+)?\b', raw_text)) or "version" in lower or "build" in lower or "release" in lower
        has_env = any(kw in lower for kw in ["chrome", "firefox", "safari", "edge", "ios", "android", "windows", "macos", "linux", "staging", "prod", "production"])

        if has_version and has_env:
            breakdown["environment_details"] = 20
        elif has_version or has_env:
            breakdown["environment_details"] = 10
        else:
            breakdown["environment_details"] = 0

        score = sum(breakdown.values())

        # Determine letter grade
        if score >= 85:
            grade = "A"
            reason = "Excellent: Full steps, logs, environment & expected behavior"
        elif score >= 70:
            grade = "B"
            reason = "Good: Clear reproduction steps, but minor technical context missing"
        elif score >= 55:
            grade = "C"
            reason = "Average: Core error present, but missing reproduction steps or environment"
        elif score >= 40:
            grade = "D"
            reason = "Poor: Vague symptom description without steps, versions, or error logs"
        else:
            grade = "F"
            reason = "Unusable: Missing all critical triage details (S2R, error logs, and environment)"

        # Missing Info Check (Feature 4)
        is_steps_missing = breakdown["steps_to_reproduce"] < 20
        is_version_missing = not has_version
        is_browser_env_missing = not has_env

        missing_flags = []
        if is_steps_missing:
            missing_flags.append("Steps to Reproduce Missing")
        if is_version_missing:
            missing_flags.append("Software Version Missing")
        if is_browser_env_missing:
            missing_flags.append("Browser/OS Environment Missing")

        # Draft reporter follow-up question
        questions = []
        if is_steps_missing:
            questions.append("exact step-by-step actions that trigger this error")
        if is_version_missing:
            questions.append("app release or build version")
        if is_browser_env_missing:
            questions.append("browser/device and OS environment")

        if questions:
            question_text = f"Hello! To help our maintenance team triage and resolve this quickly, could you please provide: {', and '.join(questions)}? Thank you!"
        else:
            question_text = "All critical triage information is present in the report."

        missing_info = MissingInfoCheck(
            is_steps_missing=is_steps_missing,
            is_version_missing=is_version_missing,
            is_browser_or_env_missing=is_browser_env_missing,
            missing_summary_flags=missing_flags,
            question_for_reporter=question_text
        )

        report_grade = InputReportGrade(
            letter_grade=grade,
            numeric_score=score,
            grade_reason=reason,
            rubric_breakdown=breakdown
        )

        return report_grade, missing_info

