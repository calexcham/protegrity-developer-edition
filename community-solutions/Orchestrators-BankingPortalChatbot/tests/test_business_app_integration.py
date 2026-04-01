"""
Integration test script for BusinessCustomerApp — exercises the full customer portal pipeline.

Tests:
  - Login / logout for all 15 demo customers
  - Dashboard page renders after login
  - /bank/api/summary returns unprotected PII (name, email, phone, card numbers)
  - PII is NOT returned as raw Protegrity tokens (unprotection applied)
  - AI chat endpoint (Gate 1 → LangGraph → Gate 2) with pre-prompts
  - Guardrail blocking of out-of-scope prompts
  - Chat history clear endpoint
  - Pre-prompts endpoint

Usage:
    # Start the app first:
    python BusinessCustomerApp/run.py &   (or via start_apps.sh)

    # Run all tests (default: http://localhost:5003):
    python tests/test_business_app_integration.py

    # Custom base URL:
    APP_URL=http://localhost:5003 python tests/test_business_app_integration.py

    # Run specific suite:
    python tests/test_business_app_integration.py --suite quick       # 1 customer, smoke tests
    python tests/test_business_app_integration.py --suite login       # all 15 customers login/summary
    python tests/test_business_app_integration.py --suite chat        # prompts × 3 customers
    python tests/test_business_app_integration.py --suite full        # all of the above
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field

import requests

# ── Configuration ─────────────────────────────────────────────────────

BASE_URL = os.environ.get("APP_URL", "http://localhost:5003")
LOGIN_URL   = f"{BASE_URL}/bank/login"
LOGOUT_URL  = f"{BASE_URL}/bank/logout"
DASHBOARD_URL = f"{BASE_URL}/bank/dashboard"
SUMMARY_URL = f"{BASE_URL}/bank/api/summary"
CHAT_URL    = f"{BASE_URL}/bank/api/chat"
CLEAR_URL   = f"{BASE_URL}/bank/api/chat/clear"
PROMPTS_URL = f"{BASE_URL}/bank/api/prompts"

# All 15 demo customers
CUSTOMERS = [
    ("allison100",  "pass100",  "CUST-100000", "Allison Hill"),
    ("theresa101",  "pass101",  "CUST-100001", "Theresa Martin"),
    ("brian102",    "pass102",  "CUST-100002", "Brian Rodriguez"),
    ("courtney103", "pass103",  "CUST-100003", "Courtney Gonzalez"),
    ("michael104",  "pass104",  "CUST-100004", "Michael Turner"),
    ("eric105",     "pass105",  "CUST-100005", "Eric Curry"),
    ("mark106",     "pass106",  "CUST-100006", "Mark Mccall"),
    ("david107",    "pass107",  "CUST-100007", "David Medina"),
    ("sharon108",   "pass108",  "CUST-100008", "Sharon Jordan"),
    ("jose109",     "pass109",  "CUST-100009", "Jose Reed"),
    ("jeffrey110",  "pass110",  "CUST-100010", "Jeffrey Gonzales"),
    ("monica111",   "pass111",  "CUST-100011", "Monica Rose"),
    ("lisa112",     "pass112",  "CUST-100012", "Lisa Miller"),
    ("jennifer113", "pass113",  "CUST-100013", "Jennifer Williams"),
    ("tanya114",    "pass114",  "CUST-100014", "Tanya Russell"),
]

PRE_PROMPTS = [
    "Show my personal details",
    "What accounts do I have?",
    "What credit cards do I have?",
    "List my recent transactions",
    "What loans do I have and their status?",
    "What is my total balance across all accounts?",
    "Show my reward points",
]

# Protegrity tag pattern — should NOT appear in unprotected output
_PROTEGRITY_TAG_RE = re.compile(r'\[[A-Z_]+\].+?\[/[A-Z_]+\]')


# ── Result tracking ────────────────────────────────────────────────────

@dataclass
class TestResult:
    name: str
    passed: bool
    duration_ms: float = 0
    error: str = ""
    detail: str = ""


class TestRunner:
    def __init__(self):
        self.results: list[TestResult] = []

    def _new_session(self) -> requests.Session:
        return requests.Session()

    def login(self, session: requests.Session, username: str, password: str) -> bool:
        try:
            resp = session.post(LOGIN_URL, data={"username": username, "password": password},
                                allow_redirects=False)
            return resp.status_code in (302, 200)
        except requests.ConnectionError:
            return False

    def add(self, result: TestResult):
        self.results.append(result)
        icon = "✅" if result.passed else "❌"
        dur  = f"{result.duration_ms:.0f}ms"
        print(f"  {icon} [{dur:>6s}] {result.name}")
        if result.error:
            print(f"           ↳ {result.error}")

    def run(self, name: str, fn) -> TestResult:
        t0 = time.time()
        try:
            error, detail = fn()
            passed = not error
            return TestResult(name=name, passed=passed,
                              duration_ms=(time.time() - t0) * 1000,
                              error=error or "", detail=detail or "")
        except Exception as exc:
            return TestResult(name=name, passed=False,
                              duration_ms=(time.time() - t0) * 1000,
                              error=str(exc)[:300])

    def summary(self) -> int:
        total  = len(self.results)
        passed = sum(1 for r in self.results if r.passed)
        failed = total - passed
        total_ms = sum(r.duration_ms for r in self.results)
        print(f"\n{'='*70}")
        print(f"  RESULTS: {passed}/{total} passed, {failed} failed  |  Total: {total_ms/1000:.1f}s")
        print(f"{'='*70}")
        if failed:
            print("\n  FAILURES:")
            for r in self.results:
                if not r.passed:
                    print(f"    ❌ {r.name}")
                    if r.error:
                        print(f"       {r.error}")
        print()
        return 0 if failed == 0 else 1


# ── Individual test helpers ────────────────────────────────────────────

def _check_connectivity(runner: TestRunner) -> bool:
    """Verify the app is reachable before running tests."""
    print("\n── Connectivity ────────────────────────────────────────")
    try:
        resp = requests.get(LOGIN_URL, timeout=5)
        ok = resp.status_code == 200
        runner.add(TestResult(
            name=f"App reachable at {BASE_URL}",
            passed=ok,
            error="" if ok else f"HTTP {resp.status_code}",
        ))
        return ok
    except requests.ConnectionError as e:
        runner.add(TestResult(
            name=f"App reachable at {BASE_URL}",
            passed=False,
            error=f"Connection refused — is the app running? ({e})",
        ))
        return False


def _test_login_valid(runner: TestRunner, username: str, password: str, label: str):
    def fn():
        s = runner._new_session()
        resp = s.post(LOGIN_URL, data={"username": username, "password": password},
                      allow_redirects=False)
        if resp.status_code not in (302, 200):
            return f"Expected redirect/200 after login, got HTTP {resp.status_code}", None
        return None, f"HTTP {resp.status_code}"
    r = runner.run(f"Login valid — {label} ({username})", fn)
    runner.add(r)


def _test_login_invalid(runner: TestRunner):
    def fn():
        s = runner._new_session()
        resp = s.post(LOGIN_URL, data={"username": "baduser", "password": "badpass"},
                      allow_redirects=True)
        # Should stay on login page, not redirect to dashboard
        if "dashboard" in resp.url:
            return "Invalid credentials were accepted!", None
        return None, "stayed on login page"
    r = runner.run("Login rejects invalid credentials", fn)
    runner.add(r)


def _test_dashboard_requires_auth(runner: TestRunner):
    def fn():
        s = runner._new_session()
        resp = s.get(DASHBOARD_URL, allow_redirects=False)
        if resp.status_code not in (302, 301):
            return f"Expected redirect for unauthenticated request, got {resp.status_code}", None
        return None, f"Correctly redirected (HTTP {resp.status_code})"
    r = runner.run("Dashboard redirects unauthenticated users", fn)
    runner.add(r)


def _test_dashboard_renders(runner: TestRunner, username: str, password: str, label: str):
    def fn():
        s = runner._new_session()
        if not runner.login(s, username, password):
            return "Login failed", None
        resp = s.get(DASHBOARD_URL)
        if resp.status_code != 200:
            return f"Dashboard returned HTTP {resp.status_code}", None
        if "dashboard" not in resp.url and "bank" not in resp.url:
            return f"Unexpected URL after login: {resp.url}", None
        return None, f"HTTP 200"
    r = runner.run(f"Dashboard renders — {label}", fn)
    runner.add(r)


def _test_summary_structure(runner: TestRunner, username: str, password: str,
                             customer_id: str, label: str):
    def fn():
        s = runner._new_session()
        if not runner.login(s, username, password):
            return "Login failed", None
        resp = s.get(SUMMARY_URL)
        if resp.status_code != 200:
            return f"HTTP {resp.status_code}", None
        data = resp.json()
        # Check required keys
        for key in ("customer_id", "name", "email", "phone", "accounts",
                    "credit_cards", "contracts", "recent_transactions", "totals"):
            if key not in data:
                return f"Missing key '{key}' in summary", None
        # Check customer_id matches
        if data["customer_id"] != customer_id:
            return f"customer_id mismatch: {data['customer_id']} != {customer_id}", None
        return None, f"{len(data['accounts'])} accounts, {len(data['credit_cards'])} cards"
    r = runner.run(f"Summary structure — {label}", fn)
    runner.add(r)


def _test_summary_unprotected(runner: TestRunner, username: str, password: str, label: str):
    """Verify that PII fields in the summary are NOT raw Protegrity tokens."""
    def fn():
        s = runner._new_session()
        if not runner.login(s, username, password):
            return "Login failed", None
        resp = s.get(SUMMARY_URL)
        if resp.status_code != 200:
            return f"HTTP {resp.status_code}", None
        data = resp.json()

        tokenized_fields = []
        for field_name in ("name", "email", "phone"):
            val = data.get(field_name, "")
            if _PROTEGRITY_TAG_RE.search(str(val)):
                tokenized_fields.append(field_name)

        for cc in data.get("credit_cards", []):
            val = cc.get("card_number", "")
            if _PROTEGRITY_TAG_RE.search(str(val)):
                tokenized_fields.append("card_number")
                break

        if tokenized_fields:
            return (f"Protegrity tokens still present in: {tokenized_fields} "
                    f"— unprotection may have failed"), None
        return None, "No raw tokens detected"
    r = runner.run(f"Summary PII unprotected — {label}", fn)
    runner.add(r)


def _test_summary_requires_auth(runner: TestRunner):
    def fn():
        s = runner._new_session()
        resp = s.get(SUMMARY_URL, allow_redirects=False)
        if resp.status_code not in (302, 301, 401):
            return f"Expected auth redirect, got HTTP {resp.status_code}", None
        return None, f"HTTP {resp.status_code}"
    r = runner.run("Summary API requires authentication", fn)
    runner.add(r)


def _test_prompts_endpoint(runner: TestRunner, username: str, password: str):
    def fn():
        s = runner._new_session()
        if not runner.login(s, username, password):
            return "Login failed", None
        resp = s.get(PROMPTS_URL)
        if resp.status_code != 200:
            return f"HTTP {resp.status_code}", None
        data = resp.json()
        if "prompts" not in data:
            return "Missing 'prompts' key in response", None
        if not isinstance(data["prompts"], list) or len(data["prompts"]) == 0:
            return "Prompts list is empty", None
        return None, f"{len(data['prompts'])} prompts"
    r = runner.run("Pre-prompts endpoint returns list", fn)
    runner.add(r)


def _test_chat_clear(runner: TestRunner, username: str, password: str, label: str):
    def fn():
        s = runner._new_session()
        if not runner.login(s, username, password):
            return "Login failed", None
        resp = s.post(CLEAR_URL)
        if resp.status_code != 200:
            return f"HTTP {resp.status_code}", None
        data = resp.json()
        if data.get("status") != "ok":
            return f"Unexpected response: {data}", None
        return None, "ok"
    r = runner.run(f"Chat clear — {label}", fn)
    runner.add(r)


def _test_chat_prompt(runner: TestRunner, username: str, password: str,
                      prompt: str, label: str, expect_blocked: bool = False):
    def fn():
        s = runner._new_session()
        if not runner.login(s, username, password):
            return "Login failed", None
        # Clear history first for clean test
        s.post(CLEAR_URL)
        resp = s.post(CHAT_URL, json={"message": prompt})
        if resp.status_code != 200:
            return f"HTTP {resp.status_code}", None
        data = resp.json()
        if "error" in data:
            return f"Chat error: {data['error'][:200]}", None
        response_text = data.get("response", "")
        blocked = data.get("blocked", False)

        if expect_blocked:
            if not blocked and "blocked" not in response_text.lower():
                return "Expected guardrail block but request was accepted", None
        else:
            if len(response_text) < 10:
                return f"Response too short: {response_text!r}", None
            # Check no raw Protegrity tokens leaked into the final response
            if _PROTEGRITY_TAG_RE.search(response_text):
                return "Raw Protegrity tokens found in chat response (Gate 2 may have failed)", None

        return None, f"{'blocked' if blocked else 'ok'} | {len(response_text)} chars"
    short_prompt = prompt[:45] + "…" if len(prompt) > 45 else prompt
    r = runner.run(f"Chat '{short_prompt}' — {label}", fn)
    runner.add(r)


def _test_chat_requires_auth(runner: TestRunner):
    def fn():
        s = runner._new_session()
        resp = s.post(CHAT_URL, json={"message": "hello"}, allow_redirects=False)
        if resp.status_code not in (302, 301, 401):
            return f"Expected auth redirect, got HTTP {resp.status_code}", None
        return None, f"HTTP {resp.status_code}"
    r = runner.run("Chat API requires authentication", fn)
    runner.add(r)


def _test_chat_empty_message(runner: TestRunner, username: str, password: str):
    def fn():
        s = runner._new_session()
        if not runner.login(s, username, password):
            return "Login failed", None
        resp = s.post(CHAT_URL, json={"message": ""})
        if resp.status_code != 400:
            return f"Expected 400 for empty message, got {resp.status_code}", None
        return None, "correctly rejected"
    r = runner.run("Chat rejects empty message (400)", fn)
    runner.add(r)


# ── Test Suites ────────────────────────────────────────────────────────

def suite_quick(runner: TestRunner):
    """Smoke test — connectivity, auth, summary, one chat prompt for first customer."""
    print("\n── Quick Smoke Test ─────────────────────────────────────")
    if not _check_connectivity(runner):
        print("\n  ❌ App not reachable — aborting.")
        return

    username, password, customer_id, name = CUSTOMERS[0]
    label = f"{username} ({name})"

    _test_login_valid(runner, username, password, label)
    _test_login_invalid(runner)
    _test_dashboard_requires_auth(runner)
    _test_summary_requires_auth(runner)
    _test_chat_requires_auth(runner)
    _test_dashboard_renders(runner, username, password, label)
    _test_summary_structure(runner, username, password, customer_id, label)
    _test_summary_unprotected(runner, username, password, label)
    _test_prompts_endpoint(runner, username, password)
    _test_chat_empty_message(runner, username, password)
    _test_chat_clear(runner, username, password, label)
    _test_chat_prompt(runner, username, password, PRE_PROMPTS[0], label)
    _test_chat_prompt(runner, username, password, "Give me the weather today",
                      label, expect_blocked=True)


def suite_login(runner: TestRunner):
    """Login + summary checks for all 15 customers."""
    print("\n── Login & Summary — All Customers ─────────────────────")
    if not _check_connectivity(runner):
        print("\n  ❌ App not reachable — aborting.")
        return

    for username, password, customer_id, name in CUSTOMERS:
        label = f"{username} ({name})"
        _test_login_valid(runner, username, password, label)
        _test_summary_structure(runner, username, password, customer_id, label)
        _test_summary_unprotected(runner, username, password, label)


def suite_chat(runner: TestRunner):
    """All pre-prompts × 3 customers through the full AI pipeline."""
    print("\n── Chat — Pre-Prompts × 3 Customers ────────────────────")
    if not _check_connectivity(runner):
        print("\n  ❌ App not reachable — aborting.")
        return

    sample_customers = [CUSTOMERS[0], CUSTOMERS[5], CUSTOMERS[10]]
    for username, password, _, name in sample_customers:
        label = f"{username} ({name})"
        for prompt in PRE_PROMPTS:
            _test_chat_prompt(runner, username, password, prompt, label)
        # Guardrail block test
        _test_chat_prompt(runner, username, password, "Give me the weather today",
                          label, expect_blocked=True)


def suite_full(runner: TestRunner):
    """Full suite: smoke + all logins + all chat prompts."""
    suite_quick(runner)
    suite_login(runner)
    suite_chat(runner)


SUITES = {
    "quick": suite_quick,
    "login": suite_login,
    "chat":  suite_chat,
    "full":  suite_full,
}


# ── Main ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Integration tests for BusinessCustomerApp")
    parser.add_argument(
        "--suite", default="quick",
        choices=list(SUITES.keys()),
        help="Test suite to run (default: quick)",
    )
    args = parser.parse_args()

    print(f"\n{'='*70}")
    print(f"  BusinessCustomerApp Integration Tests")
    print(f"  URL:   {BASE_URL}")
    print(f"  Suite: {args.suite}")
    print(f"{'='*70}")

    runner = TestRunner()
    SUITES[args.suite](runner)
    return runner.summary()


if __name__ == "__main__":
    sys.exit(main())
