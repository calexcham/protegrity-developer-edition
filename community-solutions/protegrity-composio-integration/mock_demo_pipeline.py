"""
Mock end-to-end demo pipeline.

Simulates the Composio flow:
  [Inbound Email] → [GitHub Issues] → [Protegrity Gate 1: Protect]
  → [Semantic Guardrails] → [Outbound Email Reply] → [Google Drive Spreadsheet]

All source data is mocked.  Protegrity classify + SGR APIs are called for real.
"""
from __future__ import annotations

import json
from typing import Any, Dict, Optional

import protegrity_bridge as pb
from config import Config, load_config

# ── Mock data ─────────────────────────────────────────────────────────────────

MOCK_INBOUND_EMAIL = {
    "from": "Sarah Mitchell <s.mitchell@acme-corp.com>",
    "to": "devops-bot@company.internal",
    "subject": "Daily GitHub digest — top 5 issues from today",
    "date": "Mon, 17 Mar 2026 08:02:11 +0000",
    "body": (
        "Hi team,\n\n"
        "Can you please send me today's top 5 open issues from the "
        "microsoft/vscode repository? I need them for the morning stand-up.\n\n"
        "Also CC the report to john.dev@acme-corp.com and "
        "reach out to +1-415-555-0192 if urgent.\n\n"
        "Thanks,\nSarah Mitchell\n"
        "Senior Engineering Manager, ACME Corp\n"
        "SSN for identity verification: 078-05-1120\n"
        "Employee ID: EMP-9823"
    ),
}

MOCK_GITHUB_ISSUES = [
    {
        "number": 241891,
        "title": "Extension host crashes when user john.dev@acme-corp.com opens large JSON file",
        "state": "open",
        "created_at": "2026-03-17T06:14:32Z",
        "updated_at": "2026-03-17T07:45:19Z",
        "user": {"login": "jdeveloper", "email": "john.dev@acme-corp.com"},
        "labels": ["bug", "crash", "extension-host"],
        "body": (
            "Reported by John Developer (john.dev@acme-corp.com, +1-650-555-0147).\n"
            "Steps to reproduce:\n"
            "1. Open VS Code as Sarah Mitchell (s.mitchell@acme-corp.com)\n"
            "2. Open a JSON file larger than 50 MB\n"
            "3. Extension host crashes with 'SIGABRT'\n\n"
            "System: Windows 11, IP 192.168.1.45\n"
            "License key: XXXX-YYYY-ZZZZ-1234"
        ),
        "html_url": "https://github.com/microsoft/vscode/issues/241891",
    },
    {
        "number": 241885,
        "title": "Customer data leak in telemetry endpoint — PII sent to external server",
        "state": "open",
        "created_at": "2026-03-17T05:55:00Z",
        "updated_at": "2026-03-17T07:30:11Z",
        "user": {"login": "security-bot", "email": "security@microsoft.com"},
        "labels": ["security", "critical", "privacy"],
        "body": (
            "Telemetry pipeline is forwarding raw user payloads to analytics.thirdparty.io.\n"
            "Affected users include: alice@contoso.com, robert.brown@fabrikam.com.\n"
            "Phone contact for incident response: +1-202-555-0173 (Robert Brown)\n"
            "Internal ticket opened by compliance officer Maria Garcia "
            "(m.garcia@microsoft.com, SSN 123-45-6789)."
        ),
        "html_url": "https://github.com/microsoft/vscode/issues/241885",
    },
    {
        "number": 241870,
        "title": "Git blame shows wrong author — commit by dev.ops@acme-corp.com attributed to another user",
        "state": "open",
        "created_at": "2026-03-17T04:20:00Z",
        "updated_at": "2026-03-17T06:55:43Z",
        "user": {"login": "devops99", "email": "dev.ops@acme-corp.com"},
        "labels": ["git", "ux", "bug"],
        "body": (
            "Expected: commits by dev.ops@acme-corp.com appear with correct author.\n"
            "Actual: all commits attributed to 'Jane Doe' (jane.doe@acme-corp.com).\n"
            "Workaround: none. Reported by Mark Spencer (+1-312-555-0188).\n"
            "Credit card used for pro license: 4111-1111-1111-1111 (expires 09/27)."
        ),
        "html_url": "https://github.com/microsoft/vscode/issues/241870",
    },
    {
        "number": 241858,
        "title": "IntelliSense leaks API keys from .env files into hover tooltips",
        "state": "open",
        "created_at": "2026-03-17T03:10:00Z",
        "updated_at": "2026-03-17T05:10:00Z",
        "user": {"login": "carlos_m", "email": "carlos@startup.io"},
        "labels": ["security", "intellisense", "privacy"],
        "body": (
            "When hovering over a variable defined in a .env file, VS Code shows "
            "the raw value including secrets.\n"
            "Example token leaked: sk-proj-Ab3Xz9Lm2Qw7Rn4Pv6Yt1Ku8Ej5Sd0Fc.\n"
            "Reported by Carlos Martinez (carlos@startup.io, DOB 1988-04-15, "
            "phone +1-503-555-0122)."
        ),
        "html_url": "https://github.com/microsoft/vscode/issues/241858",
    },
    {
        "number": 241844,
        "title": "Remote SSH session disconnects when idle — impacts engineer Emily Chang",
        "state": "open",
        "created_at": "2026-03-17T01:30:00Z",
        "updated_at": "2026-03-17T04:40:00Z",
        "user": {"login": "echang", "email": "emily.chang@acme-corp.com"},
        "labels": ["remote-ssh", "reliability"],
        "body": (
            "Remote sessions drop after ~15 min of inactivity.\n"
            "Affects Emily Chang (emily.chang@acme-corp.com, employee 192.168.50.22).\n"
            "SSH key fingerprint: SHA256:xK9mQpLzR2nT4bW6vY8eC0jD1fG3hI5.\n"
            "Emergency contact: Tom Chang +1-408-555-0199."
        ),
        "html_url": "https://github.com/microsoft/vscode/issues/241844",
    },
]

MOCK_SPREADSHEET_META = {
    "title": "GitHub Issues Digest — microsoft/vscode — 2026-03-17",
    "sheet_url": "https://docs.google.com/spreadsheets/d/MOCK_SHEET_ID/edit",
    "rows_written": 5,
    "columns": ["#", "Title", "Author", "Email", "Labels", "Created", "State", "URL"],
}


# ── Pipeline runner ────────────────────────────────────────────────────────────

def run_mock_pipeline(
    cfg: Optional[Config] = None,
    run_guardrails: bool = True,
) -> Dict[str, Any]:
    """
    Execute the mock demo pipeline and return all stage data.

    Stages returned:
      stage_0_email_in  — raw inbound email
      stage_1_github    — raw GitHub issues (with PII)
      stage_2_protect   — Protegrity Gate 1 output (issues JSON protected)
      stage_3_guardrail — Semantic Guardrail result on the protected body
      stage_4_email_out — Outbound email draft (protected & plain versions)
      stage_5_sheet     — Mock spreadsheet metadata
    """
    cfg = cfg or load_config()

    # ── Stage 0: inbound email (mock) ──────────────────────────────────────────
    stage_0 = dict(MOCK_INBOUND_EMAIL)

    # ── Stage 1: GitHub issues (mock) ─────────────────────────────────────────
    stage_1 = {
        "repo": "microsoft/vscode",
        "issues_count": len(MOCK_GITHUB_ISSUES),
        "issues": MOCK_GITHUB_ISSUES,
        "source": "mock",
    }

    # ── Stage 2: Protegrity Gate 1 — protect each issue field individually ──────
    # (We protect string fields one at a time; treating the whole JSON as text
    #  breaks numeric values like issue numbers when they get tagged.)
    def _protect_issue_fields(issue: dict) -> tuple:
        """Return a PII-protected copy of issue + list of all elements found."""
        p = dict(issue)
        elems: list = []
        for field in ("title", "body"):
            r = pb.find_and_protect(issue.get(field, ""), cfg=cfg)
            p[field] = r.protected
            elems.extend(r.elements_found)
        user = issue.get("user") or {}
        if isinstance(user, dict):
            p_user = dict(user)
            for uf in ("email", "login"):
                if user.get(uf):
                    r = pb.find_and_protect(user[uf], cfg=cfg)
                    p_user[uf] = r.protected
                    elems.extend(r.elements_found)
            p["user"] = p_user
        return p, elems

    protected_issues: list = []
    all_elements: list = []
    for issue in MOCK_GITHUB_ISSUES:
        p_issue, elems = _protect_issue_fields(issue)
        protected_issues.append(p_issue)
        all_elements.extend(elems)

    pii_count = len(all_elements)
    issues_raw_json = json.dumps(MOCK_GITHUB_ISSUES, indent=2)
    issues_protected_json = json.dumps(protected_issues, indent=2)

    # Also protect the inbound email body
    email_protect = pb.find_and_protect(stage_0["body"], cfg=cfg)

    stage_2 = {
        "issues_protected_json": issues_protected_json,
        "issues_raw_json": issues_raw_json,
        "email_body_protected": email_protect.protected,
        "email_body_raw": stage_0["body"],
        "pii_count": pii_count,
        "pii_elements": all_elements,
        "error": None,
    }

    # ── Stage 3: Semantic Guardrails ───────────────────────────────────────────
    sgr_result = {"accepted": True, "risk_score": 0.0, "outcome": "skipped", "raw": {}}
    if run_guardrails:
        # Use first two paragraphs of the raw issues body as the content to check
        check_text = "\n\n".join(i["body"] for i in MOCK_GITHUB_ISSUES[:2])
        sgr_result = pb.semantic_guardrail_check(check_text, cfg=cfg)

    stage_3 = {
        "risk_score": sgr_result.get("risk_score", 0.0),
        "outcome": sgr_result.get("outcome", "accepted"),
        "accepted": sgr_result.get("accepted", True),
        "note": (
            "Content flagged — includes security-sensitive text (PII, API keys)."
            if not sgr_result.get("accepted", True)
            else "Content passed semantic guardrails."
        ),
    }

    # ── Stage 4: Outbound email reply ─────────────────────────────────────────
    sep = "─" * 60

    def _fmt(issue: dict) -> str:
        body_text = issue.get("body", "")[:300]
        user = issue.get("user") or {}
        email_field = user.get("email", "") if isinstance(user, dict) else ""
        login = user.get("login", "") if isinstance(user, dict) else str(user)
        labels = ", ".join(issue.get("labels") or [])
        return (
            f"  #{issue['number']}: {issue['title']}\n"
            f"  Author:  {login} <{email_field}>\n"
            f"  Labels:  {labels}\n"
            f"  Created: {issue.get('created_at','')[:10]}\n"
            f"  URL:     {issue.get('html_url','')}\n"
            f"  Preview: {body_text[:200]}\n"
        )

    # Plain body uses original (unprotected) issue data
    plain_body = (
        f"Hi Sarah,\n\n"
        f"Here are today's top 5 open issues from microsoft/vscode:\n\n"
        f"{sep}\n"
        + f"\n{sep}\n".join(_fmt(i) for i in MOCK_GITHUB_ISSUES) +
        f"\n{sep}\n\n"
        f"This digest was secured by Protegrity — {pii_count} PII fields "
        f"tokenised during transmission.\n\n"
        f"— Composio Agentic Pipeline"
    )

    # Protected body uses tokenised issue data — PII values replaced with tokens
    protected_body_text = (
        f"Hi Sarah,\n\n"
        f"Here are today's top 5 open issues from microsoft/vscode:\n\n"
        f"{sep}\n"
        + f"\n{sep}\n".join(_fmt(i) for i in protected_issues) +
        f"\n{sep}\n\n"
        f"⚠ {pii_count} PII field(s) tokenised — only authorised recipients may "
        f"decrypt this data via Protegrity Gate 2.\n\n"
        f"— Composio Agentic Pipeline"
    )

    stage_4 = {
        "to": stage_0["from"],
        "subject": f"Re: {stage_0['subject']}",
        "body_plain": plain_body,
        "body_protected": protected_body_text,
        "pii_in_email": pii_count,
        "composio_action": "GMAIL_SEND_EMAIL",
    }

    # ── Stage 5: Spreadsheet (mock) ────────────────────────────────────────────
    def _sheet_row(issue: dict) -> list:
        user = issue.get("user") or {}
        email_field = user.get("email", "") if isinstance(user, dict) else ""
        login = user.get("login", "") if isinstance(user, dict) else str(user)
        return [
            f"#{issue['number']}",
            issue.get("title", ""),
            login,
            email_field,
            ", ".join(issue.get("labels") or []),
            (issue.get("created_at") or "")[:10],
            issue.get("state", ""),
            issue.get("html_url", ""),
        ]

    stage_5 = {
        **MOCK_SPREADSHEET_META,
        "composio_action": "GOOGLESHEETS_CREATE_SPREADSHEET",
        "rows_plain": [_sheet_row(i) for i in MOCK_GITHUB_ISSUES],
        "rows_protected": [_sheet_row(i) for i in protected_issues],
        "headers": MOCK_SPREADSHEET_META["columns"],
    }

    return {
        "stage_0_email_in": stage_0,
        "stage_1_github": stage_1,
        "stage_2_protect": stage_2,
        "stage_3_guardrail": stage_3,
        "stage_4_email_out": stage_4,
        "stage_5_sheet": stage_5,
        "summary": {
            "pii_count": pii_count,
            "guardrail_risk_score": stage_3["risk_score"],
            "guardrail_accepted": stage_3["accepted"],
            "email_sent": True,
            "sheet_created": True,
        },
    }
