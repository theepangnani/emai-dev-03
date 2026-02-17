#!/usr/bin/env python3
"""
Production smoke test for ClassBridge.

Tests all critical API endpoints against a live environment.
Supports single-role or multi-role (all 4 roles in one run) testing.

Usage:
    # Single role (backward-compatible)
    python scripts/smoke-test.py --email admin@example.com --password secret

    # All 4 roles from a credentials file
    python scripts/smoke-test.py --credentials-file scripts/smoke-credentials.json

    # With SendGrid verification
    python scripts/smoke-test.py --credentials-file creds.json --sendgrid-key SG.xxx

    # Custom target
    python scripts/smoke-test.py --base-url http://localhost:8000 --email a@b.com --password pw

Environment variables (alternative to CLI args):
    SMOKE_BASE_URL, SMOKE_EMAIL, SMOKE_PASSWORD, SENDGRID_API_KEY

Credentials file format (scripts/smoke-credentials.json):
    {
      "admin":   {"email": "...", "password": "..."},
      "parent":  {"email": "...", "password": "..."},
      "teacher": {"email": "...", "password": "..."},
      "student": {"email": "...", "password": "..."}
    }
"""

import argparse
import json
import os
import sys
import time
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from urllib.error import HTTPError, URLError

# --- Formatting helpers ---

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"


class TestTracker:
    """Tracks test results with per-section grouping and timing."""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.skipped = 0
        self.results = []  # (status, name, detail, elapsed_ms, section)
        self._current_section = ""
        self._slow_threshold_ms = 5000

    def set_section(self, name):
        self._current_section = name

    def ok(self, name, detail="", elapsed_ms=0):
        self.passed += 1
        timing = f" {DIM}{elapsed_ms}ms{RESET}" if elapsed_ms else ""
        slow = f" {YELLOW}SLOW{RESET}" if elapsed_ms > self._slow_threshold_ms else ""
        msg = f"  {GREEN}PASS{RESET}  {name}{timing}{slow}"
        if detail:
            msg += f"  ({detail})"
        print(msg)
        self.results.append(("PASS", name, detail, elapsed_ms, self._current_section))

    def fail(self, name, detail="", elapsed_ms=0):
        self.failed += 1
        timing = f" {DIM}{elapsed_ms}ms{RESET}" if elapsed_ms else ""
        msg = f"  {RED}FAIL{RESET}  {name}{timing}"
        if detail:
            msg += f"  — {detail}"
        print(msg)
        self.results.append(("FAIL", name, detail, elapsed_ms, self._current_section))

    def skip(self, name, reason=""):
        self.skipped += 1
        msg = f"  {YELLOW}SKIP{RESET}  {name}"
        if reason:
            msg += f"  — {reason}"
        print(msg)
        self.results.append(("SKIP", name, reason, 0, self._current_section))

    @property
    def total(self):
        return self.passed + self.failed + self.skipped

    def to_dict(self):
        """Export results as a JSON-serializable dict."""
        sections = {}
        for status, name, detail, elapsed_ms, section in self.results:
            if section not in sections:
                sections[section] = []
            sections[section].append({
                "status": status,
                "test": name,
                "detail": detail,
                "elapsed_ms": elapsed_ms,
            })
        return {
            "passed": self.passed,
            "failed": self.failed,
            "skipped": self.skipped,
            "total": self.total,
            "sections": sections,
        }


# Global tracker
tracker = TestTracker()


# --- HTTP helpers ---

def _timed_request(func, *args, **kwargs):
    """Wrap an HTTP call and return (status, body, elapsed_ms)."""
    start = time.monotonic()
    code, body = func(*args, **kwargs)
    elapsed_ms = int((time.monotonic() - start) * 1000)
    return code, body, elapsed_ms


def api_get(base, path, token=None, timeout=30):
    """GET request, returns (status_code, json_body | None)."""
    url = f"{base}{path}"
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = Request(url, headers=headers, method="GET")
    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode()
            try:
                body = json.loads(raw)
            except (json.JSONDecodeError, ValueError):
                body = None
            return resp.status, body
    except HTTPError as e:
        try:
            body = json.loads(e.read().decode())
        except Exception:
            body = None
        return e.code, body
    except (URLError, TimeoutError) as e:
        return 0, {"error": str(e)}


def api_post_form(base, path, data, timeout=30):
    """POST form-encoded data, returns (status_code, json_body | None)."""
    url = f"{base}{path}"
    encoded = urlencode(data).encode()
    req = Request(url, data=encoded, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode())
            return resp.status, body
    except HTTPError as e:
        try:
            body = json.loads(e.read().decode())
        except Exception:
            body = None
        return e.code, body
    except (URLError, TimeoutError) as e:
        return 0, {"error": str(e)}


def api_post_json(base, path, data, token=None, timeout=30):
    """POST JSON data, returns (status_code, json_body | None)."""
    url = f"{base}{path}"
    encoded = json.dumps(data).encode()
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = Request(url, data=encoded, headers=headers, method="POST")
    try:
        with urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode())
            return resp.status, body
    except HTTPError as e:
        try:
            body = json.loads(e.read().decode())
        except Exception:
            body = None
        return e.code, body
    except (URLError, TimeoutError) as e:
        return 0, {"error": str(e)}


# --- Test groups ---

def test_health(base):
    tracker.set_section("Health & Connectivity")
    print(f"\n{BOLD}Health & Connectivity{RESET}")

    code, body, ms = _timed_request(api_get, base, "/health")
    if code == 200 and body and body.get("status") == "healthy":
        tracker.ok("GET /health", f"status={body['status']}", ms)
    else:
        tracker.fail("GET /health", f"code={code}", ms)

    code, _, ms = _timed_request(api_get, base, "/docs")
    if code == 200:
        tracker.ok("GET /docs (Swagger UI)", elapsed_ms=ms)
    else:
        tracker.fail("GET /docs", f"code={code}", ms)


def test_unauthenticated_protection(base):
    """Verify that protected endpoints reject unauthenticated requests."""
    tracker.set_section("Auth Protection")
    print(f"\n{BOLD}Auth Protection (no token -> 401){RESET}")

    for path in ["/api/users/me", "/api/courses/", "/api/tasks/", "/api/admin/stats"]:
        code, _, ms = _timed_request(api_get, base, path)
        if code == 401:
            tracker.ok(f"GET {path} -> 401", elapsed_ms=ms)
        else:
            tracker.fail(f"GET {path} -> expected 401", f"got {code}", ms)


def test_auth(base, email, password, role_label=""):
    """Login and return (token, role). Returns (None, None) on failure."""
    section = f"Auth [{role_label}]" if role_label else "Auth"
    tracker.set_section(section)
    label = f" ({role_label})" if role_label else ""
    print(f"\n{BOLD}Authentication{label}{RESET}")

    code, body, ms = _timed_request(api_post_form, base, "/api/auth/login", {
        "username": email,
        "password": password,
    })
    if code == 200 and body and "access_token" in body:
        tracker.ok("POST /api/auth/login", "token received", ms)
        token = body["access_token"]
    else:
        detail = body.get("detail", "") if body else ""
        tracker.fail("POST /api/auth/login", f"code={code} {detail}", ms)
        return None, None

    code, body, ms = _timed_request(api_get, base, "/api/users/me", token)
    if code == 200 and body and "email" in body:
        role = body.get("role", "unknown")
        tracker.ok("GET /api/users/me", f"role={role}", ms)
        return token, role
    else:
        tracker.fail("GET /api/users/me", f"code={code}", ms)
        return token, None


def test_common_endpoints(base, token, role_label=""):
    """Endpoints accessible to any authenticated user."""
    section = f"Common [{role_label}]" if role_label else "Common"
    tracker.set_section(section)
    label = f" [{role_label}]" if role_label else ""
    print(f"\n{BOLD}Common Endpoints{label}{RESET}")

    endpoints = [
        ("/api/courses/", "list", lambda b: isinstance(b, list), lambda b: f"{len(b)} courses"),
        ("/api/notifications/", "list", lambda b: isinstance(b, list), lambda b: f"{len(b)} notifications"),
        ("/api/notifications/unread-count", "dict", lambda b: isinstance(b, dict), lambda b: f"count={b.get('count', '?')}"),
        ("/api/tasks/", "list", lambda b: isinstance(b, list), lambda b: f"{len(b)} tasks"),
        ("/api/messages/conversations", "list", lambda b: isinstance(b, list), lambda b: f"{len(b)} conversations"),
        ("/api/search?q=test", "dict", lambda b: isinstance(b, dict), lambda _: ""),
    ]

    for path, _type, check, detail_fn in endpoints:
        code, body, ms = _timed_request(api_get, base, path, token)
        if code == 200 and body is not None and check(body):
            tracker.ok(f"GET {path}", detail_fn(body), ms)
        else:
            tracker.fail(f"GET {path}", f"code={code}", ms)

    # Inspiration — 404 is acceptable (no messages seeded)
    code, body, ms = _timed_request(api_get, base, "/api/inspiration/random", token)
    if code == 200 and body and "text" in body:
        tracker.ok("GET /api/inspiration/random", f"'{body['text'][:40]}...'", ms)
    elif code == 404:
        tracker.ok("GET /api/inspiration/random", "no messages seeded yet", ms)
    else:
        tracker.fail("GET /api/inspiration/random", f"code={code}", ms)


def test_parent_endpoints(base, token):
    tracker.set_section("Parent Endpoints")
    print(f"\n{BOLD}Parent Endpoints{RESET}")

    code, body, ms = _timed_request(api_get, base, "/api/parent/children", token)
    if code == 200 and isinstance(body, list):
        tracker.ok("GET /api/parent/children", f"{len(body)} children", ms)
    else:
        tracker.fail("GET /api/parent/children", f"code={code}", ms)

    code, body, ms = _timed_request(api_get, base, "/api/parent/dashboard", token)
    if code == 200 and isinstance(body, dict):
        tracker.ok("GET /api/parent/dashboard", elapsed_ms=ms)
    else:
        tracker.fail("GET /api/parent/dashboard", f"code={code}", ms)

    # Study guides
    code, body, ms = _timed_request(api_get, base, "/api/study/guides", token)
    if code == 200 and isinstance(body, list):
        tracker.ok("GET /api/study/guides", f"{len(body)} guides", ms)
    else:
        tracker.fail("GET /api/study/guides", f"code={code}", ms)

    code, body, ms = _timed_request(api_get, base, "/api/study/upload/formats", token)
    if code == 200 and isinstance(body, dict):
        tracker.ok("GET /api/study/upload/formats", elapsed_ms=ms)
    else:
        tracker.fail("GET /api/study/upload/formats", f"code={code}", ms)

    # Messages
    code, body, ms = _timed_request(api_get, base, "/api/messages/conversations", token)
    if code == 200 and isinstance(body, list):
        tracker.ok("GET /api/messages/conversations", f"{len(body)} conversations", ms)
    else:
        tracker.fail("GET /api/messages/conversations", f"code={code}", ms)

    code, body, ms = _timed_request(api_get, base, "/api/messages/unread-count", token)
    if code == 200 and isinstance(body, dict):
        tracker.ok("GET /api/messages/unread-count", f"count={body.get('count', '?')}", ms)
    else:
        tracker.fail("GET /api/messages/unread-count", f"code={code}", ms)

    code, body, ms = _timed_request(api_get, base, "/api/messages/recipients", token)
    if code == 200 and isinstance(body, list):
        tracker.ok("GET /api/messages/recipients", f"{len(body)} recipients", ms)
    else:
        tracker.fail("GET /api/messages/recipients", f"code={code}", ms)

    # Notification settings
    code, body, ms = _timed_request(api_get, base, "/api/notifications/settings", token)
    if code == 200 and isinstance(body, dict):
        tracker.ok("GET /api/notifications/settings", elapsed_ms=ms)
    else:
        tracker.fail("GET /api/notifications/settings", f"code={code}", ms)


def test_teacher_endpoints(base, token):
    tracker.set_section("Teacher Endpoints")
    print(f"\n{BOLD}Teacher Endpoints{RESET}")

    code, body, ms = _timed_request(api_get, base, "/api/courses/teaching", token)
    if code == 200 and isinstance(body, list):
        tracker.ok("GET /api/courses/teaching", f"{len(body)} courses", ms)
    else:
        tracker.fail("GET /api/courses/teaching", f"code={code}", ms)

    code, body, ms = _timed_request(api_get, base, "/api/students/", token)
    if code == 200 and isinstance(body, list):
        tracker.ok("GET /api/students/", f"{len(body)} students", ms)
    else:
        tracker.fail("GET /api/students/", f"code={code}", ms)

    code, body, ms = _timed_request(api_get, base, "/api/messages/conversations", token)
    if code == 200 and isinstance(body, list):
        tracker.ok("GET /api/messages/conversations", f"{len(body)} conversations", ms)
    else:
        tracker.fail("GET /api/messages/conversations", f"code={code}", ms)

    code, body, ms = _timed_request(api_get, base, "/api/messages/recipients", token)
    if code == 200 and isinstance(body, list):
        tracker.ok("GET /api/messages/recipients", f"{len(body)} recipients", ms)
    else:
        tracker.fail("GET /api/messages/recipients", f"code={code}", ms)


def test_student_endpoints(base, token):
    tracker.set_section("Student Endpoints")
    print(f"\n{BOLD}Student Endpoints{RESET}")

    code, body, ms = _timed_request(api_get, base, "/api/courses/enrolled/me", token)
    if code == 200 and isinstance(body, list):
        tracker.ok("GET /api/courses/enrolled/me", f"{len(body)} courses", ms)
    else:
        tracker.fail("GET /api/courses/enrolled/me", f"code={code}", ms)

    code, body, ms = _timed_request(api_get, base, "/api/assignments/", token)
    if code == 200 and isinstance(body, list):
        tracker.ok("GET /api/assignments/", f"{len(body)} assignments", ms)
    else:
        tracker.fail("GET /api/assignments/", f"code={code}", ms)

    code, body, ms = _timed_request(api_get, base, "/api/study/guides", token)
    if code == 200 and isinstance(body, list):
        tracker.ok("GET /api/study/guides", f"{len(body)} guides", ms)
    else:
        tracker.fail("GET /api/study/guides", f"code={code}", ms)


def test_admin_endpoints(base, token):
    tracker.set_section("Admin Endpoints")
    print(f"\n{BOLD}Admin Endpoints{RESET}")

    code, body, ms = _timed_request(api_get, base, "/api/admin/stats", token)
    if code == 200 and isinstance(body, dict):
        users = body.get("total_users", "?")
        tracker.ok("GET /api/admin/stats", f"total_users={users}", ms)
    else:
        tracker.fail("GET /api/admin/stats", f"code={code}", ms)

    code, body, ms = _timed_request(api_get, base, "/api/admin/users?limit=5", token)
    if code == 200 and isinstance(body, dict) and "users" in body:
        tracker.ok("GET /api/admin/users", f"{len(body['users'])} returned", ms)
    else:
        tracker.fail("GET /api/admin/users", f"code={code}", ms)

    code, body, ms = _timed_request(api_get, base, "/api/admin/audit-logs?limit=5", token)
    if code == 200 and isinstance(body, dict) and "items" in body:
        tracker.ok("GET /api/admin/audit-logs", f"{len(body['items'])} entries", ms)
    else:
        tracker.fail("GET /api/admin/audit-logs", f"code={code}", ms)

    code, body, ms = _timed_request(api_get, base, "/api/inspiration/messages", token)
    if code == 200 and isinstance(body, list):
        tracker.ok("GET /api/inspiration/messages", f"{len(body)} messages", ms)
    else:
        tracker.fail("GET /api/inspiration/messages", f"code={code}", ms)


def test_smtp(smtp_user, smtp_password, smtp_host="smtp.gmail.com", smtp_port=587):
    """Verify SMTP credentials by connecting and authenticating."""
    tracker.set_section("Email Verification")
    print(f"\n{BOLD}Email Verification (SMTP){RESET}")

    import smtplib

    try:
        start = time.monotonic()
        with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
        ms = int((time.monotonic() - start) * 1000)
        tracker.ok("SMTP login", f"{smtp_user} via {smtp_host}:{smtp_port}", ms)
    except Exception as e:
        ms = int((time.monotonic() - start) * 1000) if 'start' in dir() else 0
        tracker.fail("SMTP login", f"{e}", ms)


def test_sendgrid(sendgrid_key):
    """Verify SendGrid API key and sender authentication status."""
    tracker.set_section("Email Verification")
    print(f"\n{BOLD}Email Verification (SendGrid){RESET}")

    if not sendgrid_key or not sendgrid_key.startswith("SG."):
        tracker.fail("SendGrid API key", "key missing or does not start with SG.")
        return

    # Verify the key works by listing authenticated senders
    url = "https://api.sendgrid.com/v3/verified_senders"
    headers = {
        "Authorization": f"Bearer {sendgrid_key}",
        "Content-Type": "application/json",
    }
    req = Request(url, headers=headers, method="GET")
    try:
        start = time.monotonic()
        with urlopen(req, timeout=15) as resp:
            ms = int((time.monotonic() - start) * 1000)
            body = json.loads(resp.read().decode())
            senders = body.get("results", [])
            verified = [s for s in senders if s.get("verified", False)]
            tracker.ok(
                "SendGrid API key valid",
                f"{len(verified)} verified sender(s)",
                ms,
            )
            for s in verified:
                email = s.get("from_email", "?")
                print(f"    {DIM}verified sender: {email}{RESET}")
    except HTTPError as e:
        ms = 0
        if e.code == 401:
            tracker.fail("SendGrid API key", "401 Unauthorized — invalid key", ms)
        elif e.code == 403:
            tracker.fail("SendGrid API key", "403 Forbidden — insufficient permissions", ms)
        else:
            tracker.fail("SendGrid API key", f"HTTP {e.code}", ms)
    except (URLError, TimeoutError) as e:
        tracker.fail("SendGrid API key", f"connection error: {e}")

    # Check sender authentication (domain auth)
    url = "https://api.sendgrid.com/v3/whitelabel/domains"
    req = Request(url, headers=headers, method="GET")
    try:
        start = time.monotonic()
        with urlopen(req, timeout=15) as resp:
            ms = int((time.monotonic() - start) * 1000)
            domains = json.loads(resp.read().decode())
            if isinstance(domains, list) and len(domains) > 0:
                valid = [d for d in domains if d.get("valid")]
                tracker.ok(
                    "SendGrid domain authentication",
                    f"{len(valid)}/{len(domains)} domain(s) verified",
                    ms,
                )
                for d in domains:
                    status = "verified" if d.get("valid") else "UNVERIFIED"
                    print(f"    {DIM}domain: {d.get('domain', '?')} ({status}){RESET}")
            else:
                tracker.skip("SendGrid domain authentication", "no domains configured")
    except HTTPError as e:
        tracker.skip("SendGrid domain authentication", f"HTTP {e.code} (may need admin scope)")
    except (URLError, TimeoutError):
        tracker.skip("SendGrid domain authentication", "connection error")


def run_role_tests(base, token, role):
    """Run role-specific endpoint tests."""
    role_dispatch = {
        "admin": test_admin_endpoints,
        "parent": test_parent_endpoints,
        "teacher": test_teacher_endpoints,
        "student": test_student_endpoints,
    }
    fn = role_dispatch.get(role)
    if fn:
        fn(base, token)
    else:
        tracker.skip(f"Role-specific tests for '{role}'", "unknown role")


def print_summary(base, start_time, json_output=None):
    """Print final summary report and optionally write JSON."""
    elapsed_total = time.monotonic() - start_time
    print(f"\n{BOLD}{'=' * 55}{RESET}")
    print(f"{BOLD}Summary{RESET}  —  {base}")
    print(f"{'=' * 55}")

    # Per-section breakdown
    sections_seen = []
    for _, _, _, _, section in tracker.results:
        if section not in sections_seen:
            sections_seen.append(section)

    for section in sections_seen:
        section_results = [r for r in tracker.results if r[4] == section]
        p = sum(1 for r in section_results if r[0] == "PASS")
        f = sum(1 for r in section_results if r[0] == "FAIL")
        s = sum(1 for r in section_results if r[0] == "SKIP")
        total = p + f + s
        color = GREEN if f == 0 else RED
        print(f"  {color}{'PASS' if f == 0 else 'FAIL'}{RESET}  {section}: {p}/{total} passed", end="")
        if s:
            print(f" ({s} skipped)", end="")
        print()

    # Totals
    print(f"\n  {BOLD}Total:{RESET} ", end="")
    color = GREEN if tracker.failed == 0 else RED
    print(f"{color}{BOLD}{tracker.passed} passed{RESET}, ", end="")
    print(f"{RED + str(tracker.failed) + RESET if tracker.failed else '0'} failed, ", end="")
    print(f"{tracker.skipped} skipped — {tracker.total} tests")
    print(f"  {DIM}Completed in {elapsed_total:.1f}s{RESET}")

    # Failed test list
    if tracker.failed > 0:
        print(f"\n  {RED}{BOLD}Failed tests:{RESET}")
        for status, name, detail, _, section in tracker.results:
            if status == "FAIL":
                print(f"    {RED}x{RESET} [{section}] {name}" + (f" — {detail}" if detail else ""))

    # JSON report
    if json_output:
        report = tracker.to_dict()
        report["target"] = base
        report["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        report["elapsed_seconds"] = round(elapsed_total, 1)
        with open(json_output, "w") as f:
            json.dump(report, f, indent=2)
        print(f"\n  {DIM}JSON report written to {json_output}{RESET}")

    overall = "PASS" if tracker.failed == 0 else "FAIL"
    emoji = GREEN + "ALL PASS" if tracker.failed == 0 else RED + "FAILURES DETECTED"
    print(f"\n  {BOLD}{emoji}{RESET}")
    print()


# --- Main ---

def main():
    parser = argparse.ArgumentParser(
        description="ClassBridge production smoke test",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Single role
  python scripts/smoke-test.py --email admin@x.com --password pw

  # All 4 roles from file
  python scripts/smoke-test.py --credentials-file scripts/smoke-credentials.json

  # With SendGrid check
  python scripts/smoke-test.py --credentials-file creds.json --sendgrid-key SG.xxx
""",
    )
    parser.add_argument(
        "--base-url",
        default=os.environ.get("SMOKE_BASE_URL", "https://www.classbridge.ca"),
        help="Base URL of the ClassBridge API (default: https://www.classbridge.ca)",
    )
    parser.add_argument("--email", default=os.environ.get("SMOKE_EMAIL"), help="Login email (single-role mode)")
    parser.add_argument("--password", default=os.environ.get("SMOKE_PASSWORD"), help="Login password (single-role mode)")
    parser.add_argument(
        "--credentials-file",
        default=os.environ.get("SMOKE_CREDENTIALS_FILE"),
        help="Path to JSON file with credentials for all 4 roles",
    )
    parser.add_argument(
        "--sendgrid-key",
        default=os.environ.get("SENDGRID_API_KEY"),
        help="SendGrid API key for email delivery verification",
    )
    parser.add_argument(
        "--smtp-user",
        default=os.environ.get("SMTP_USER"),
        help="SMTP username for email delivery verification (e.g. user@gmail.com)",
    )
    parser.add_argument(
        "--smtp-password",
        default=os.environ.get("SMTP_PASSWORD"),
        help="SMTP password / app password",
    )
    parser.add_argument(
        "--json-output",
        default=os.environ.get("SMOKE_JSON_OUTPUT"),
        help="Path to write JSON results report (e.g. smoke-results.json)",
    )
    args = parser.parse_args()

    base = args.base_url.rstrip("/")
    start_time = time.monotonic()

    print(f"{BOLD}{CYAN}=== ClassBridge Production Smoke Test ==={RESET}")
    print(f"Target: {base}")
    print(f"Time:   {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}")

    # Warm up (Cloud Run cold start can take 10-20s)
    print(f"\nWarming up (cold start may take up to 30s)...", end=" ", flush=True)
    code, _ = api_get(base, "/health", timeout=60)
    if code == 200:
        print("ready.")
    else:
        print(f"warning: health returned {code}")

    # Always run health + auth protection tests
    test_health(base)
    test_unauthenticated_protection(base)

    # Build credentials list: either multi-role file or single --email/--password
    credentials = {}
    if args.credentials_file:
        try:
            with open(args.credentials_file) as f:
                credentials = json.load(f)
            roles_found = [r for r in ["admin", "parent", "teacher", "student"] if r in credentials]
            print(f"\n{CYAN}Loaded credentials for {len(roles_found)} role(s): {', '.join(roles_found)}{RESET}")
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"\n{RED}Error loading credentials file: {e}{RESET}")
            sys.exit(2)
    elif args.email and args.password:
        # Single-role mode — role determined after login
        credentials = {"_single": {"email": args.email, "password": args.password}}

    if credentials:
        for role_key, creds in credentials.items():
            email = creds.get("email")
            password = creds.get("password")
            if not email or not password:
                tracker.skip(f"Login as {role_key}", "missing email or password in credentials")
                continue

            role_label = role_key if role_key != "_single" else ""
            token, actual_role = test_auth(base, email, password, role_label)

            if token and actual_role:
                # Warn if credential file role doesn't match actual role
                if role_key != "_single" and actual_role != role_key:
                    print(f"  {YELLOW}WARNING: expected role '{role_key}' but got '{actual_role}'{RESET}")

                test_common_endpoints(base, token, actual_role)
                run_role_tests(base, token, actual_role)
    else:
        tracker.skip("Authenticated tests", "pass --email/--password or --credentials-file")

    # Email delivery verification (SMTP or SendGrid)
    if args.smtp_user and args.smtp_password:
        test_smtp(args.smtp_user, args.smtp_password)
    elif args.sendgrid_key:
        test_sendgrid(args.sendgrid_key)
    else:
        tracker.set_section("Email Verification")
        tracker.skip("Email verification", "pass --smtp-user/--smtp-password or --sendgrid-key")

    # Summary
    print_summary(base, start_time, args.json_output)
    sys.exit(1 if tracker.failed > 0 else 0)


if __name__ == "__main__":
    main()
