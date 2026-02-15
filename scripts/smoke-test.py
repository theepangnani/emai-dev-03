#!/usr/bin/env python3
"""
Production smoke test for ClassBridge.

Tests all critical API endpoints against a live environment.
Usage:
    python scripts/smoke-test.py
    python scripts/smoke-test.py --base-url https://www.classbridge.ca
    python scripts/smoke-test.py --email admin@example.com --password secret

Environment variables (alternative to CLI args):
    SMOKE_BASE_URL, SMOKE_EMAIL, SMOKE_PASSWORD
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

passed = 0
failed = 0
skipped = 0
results = []


def ok(name, detail=""):
    global passed
    passed += 1
    msg = f"  {GREEN}PASS{RESET}  {name}"
    if detail:
        msg += f"  ({detail})"
    print(msg)
    results.append(("PASS", name))


def fail(name, detail=""):
    global failed
    failed += 1
    msg = f"  {RED}FAIL{RESET}  {name}"
    if detail:
        msg += f"  — {detail}"
    print(msg)
    results.append(("FAIL", name))


def skip(name, reason=""):
    global skipped
    skipped += 1
    msg = f"  {YELLOW}SKIP{RESET}  {name}"
    if reason:
        msg += f"  — {reason}"
    print(msg)
    results.append(("SKIP", name))


# --- HTTP helpers ---

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
    print(f"\n{BOLD}Health & Connectivity{RESET}")
    code, body = api_get(base, "/health")
    if code == 200 and body and body.get("status") == "healthy":
        ok("GET /health", f"status={body['status']}")
    else:
        fail("GET /health", f"code={code}")

    # OpenAPI docs should be accessible (returns HTML, not JSON)
    try:
        req = Request(f"{base}/docs")
        with urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                ok("GET /docs (Swagger UI)")
            else:
                fail("GET /docs", f"code={resp.status}")
    except (HTTPError, URLError) as e:
        code = e.code if isinstance(e, HTTPError) else 0
        fail("GET /docs", f"code={code}")


def test_auth(base, email, password):
    print(f"\n{BOLD}Authentication{RESET}")

    # Login
    code, body = api_post_form(base, "/api/auth/login", {
        "username": email,
        "password": password,
    })
    if code == 200 and body and "access_token" in body:
        ok("POST /api/auth/login", "token received")
        token = body["access_token"]
    else:
        detail = body.get("detail", "") if body else ""
        fail("POST /api/auth/login", f"code={code} {detail}")
        return None, None

    # Get current user
    code, body = api_get(base, "/api/users/me", token)
    if code == 200 and body and "email" in body:
        role = body.get("role", "unknown")
        ok("GET /api/users/me", f"role={role}")
        return token, role
    else:
        fail("GET /api/users/me", f"code={code}")
        return token, None


def test_common_endpoints(base, token):
    """Endpoints accessible to any authenticated user."""
    print(f"\n{BOLD}Common Endpoints (any role){RESET}")

    code, body = api_get(base, "/api/courses/", token)
    if code == 200 and isinstance(body, list):
        ok("GET /api/courses/", f"{len(body)} courses")
    else:
        fail("GET /api/courses/", f"code={code}")

    code, body = api_get(base, "/api/notifications/", token)
    if code == 200 and isinstance(body, list):
        ok("GET /api/notifications/", f"{len(body)} notifications")
    else:
        fail("GET /api/notifications/", f"code={code}")

    code, body = api_get(base, "/api/tasks/", token)
    if code == 200 and isinstance(body, list):
        ok("GET /api/tasks/", f"{len(body)} tasks")
    else:
        fail("GET /api/tasks/", f"code={code}")

    code, body = api_get(base, "/api/conversations/", token)
    if code == 200 and isinstance(body, list):
        ok("GET /api/conversations/", f"{len(body)} conversations")
    else:
        fail("GET /api/conversations/", f"code={code}")

    code, body = api_get(base, "/api/inspiration/random", token)
    if code == 200 and body and "message" in body:
        ok("GET /api/inspiration/random", f"'{body['message'][:40]}...'")
    elif code == 404:
        ok("GET /api/inspiration/random", "no messages seeded yet")
    else:
        fail("GET /api/inspiration/random", f"code={code}")

    code, body = api_get(base, "/api/search?q=test", token)
    if code == 200 and isinstance(body, dict):
        ok("GET /api/search?q=test")
    else:
        fail("GET /api/search?q=test", f"code={code}")


def test_parent_endpoints(base, token):
    print(f"\n{BOLD}Parent Endpoints{RESET}")

    code, body = api_get(base, "/api/parent/children", token)
    if code == 200 and isinstance(body, list):
        ok("GET /api/parent/children", f"{len(body)} children")
    else:
        fail("GET /api/parent/children", f"code={code}")

    code, body = api_get(base, "/api/parent/dashboard", token)
    if code == 200 and isinstance(body, dict):
        ok("GET /api/parent/dashboard")
    else:
        fail("GET /api/parent/dashboard", f"code={code}")


def test_teacher_endpoints(base, token):
    print(f"\n{BOLD}Teacher Endpoints{RESET}")

    code, body = api_get(base, "/api/courses/teaching", token)
    if code == 200 and isinstance(body, list):
        ok("GET /api/courses/teaching", f"{len(body)} courses")
    else:
        fail("GET /api/courses/teaching", f"code={code}")

    code, body = api_get(base, "/api/students/", token)
    if code == 200 and isinstance(body, list):
        ok("GET /api/students/", f"{len(body)} students")
    else:
        fail("GET /api/students/", f"code={code}")


def test_student_endpoints(base, token):
    print(f"\n{BOLD}Student Endpoints{RESET}")

    code, body = api_get(base, "/api/courses/enrolled/me", token)
    if code == 200 and isinstance(body, list):
        ok("GET /api/courses/enrolled/me", f"{len(body)} courses")
    else:
        fail("GET /api/courses/enrolled/me", f"code={code}")

    code, body = api_get(base, "/api/assignments/", token)
    if code == 200 and isinstance(body, list):
        ok("GET /api/assignments/", f"{len(body)} assignments")
    else:
        fail("GET /api/assignments/", f"code={code}")


def test_admin_endpoints(base, token):
    print(f"\n{BOLD}Admin Endpoints{RESET}")

    code, body = api_get(base, "/api/admin/stats", token)
    if code == 200 and isinstance(body, dict):
        users = body.get("total_users", "?")
        ok("GET /api/admin/stats", f"total_users={users}")
    else:
        fail("GET /api/admin/stats", f"code={code}")

    code, body = api_get(base, "/api/admin/users?limit=5", token)
    if code == 200 and isinstance(body, dict) and "users" in body:
        ok("GET /api/admin/users", f"{len(body['users'])} returned")
    else:
        fail("GET /api/admin/users", f"code={code}")

    code, body = api_get(base, "/api/admin/audit-logs?limit=5", token)
    if code == 200 and isinstance(body, dict) and "logs" in body:
        ok("GET /api/admin/audit-logs", f"{len(body['logs'])} entries")
    else:
        fail("GET /api/admin/audit-logs", f"code={code}")


def test_unauthenticated_protection(base):
    """Verify that protected endpoints reject unauthenticated requests."""
    print(f"\n{BOLD}Auth Protection (no token -> 401){RESET}")

    for path in ["/api/users/me", "/api/courses/", "/api/tasks/", "/api/admin/stats"]:
        code, _ = api_get(base, path)
        if code == 401:
            ok(f"GET {path} -> 401")
        else:
            fail(f"GET {path} -> expected 401", f"got {code}")


# --- Main ---

def main():
    parser = argparse.ArgumentParser(description="ClassBridge production smoke test")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("SMOKE_BASE_URL", "https://www.classbridge.ca"),
        help="Base URL of the ClassBridge API",
    )
    parser.add_argument("--email", default=os.environ.get("SMOKE_EMAIL"), help="Login email")
    parser.add_argument("--password", default=os.environ.get("SMOKE_PASSWORD"), help="Login password")
    args = parser.parse_args()

    base = args.base_url.rstrip("/")
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

    # Authenticated tests require credentials
    if args.email and args.password:
        token, role = test_auth(base, args.email, args.password)

        if token:
            test_common_endpoints(base, token)

            if role == "admin":
                test_admin_endpoints(base, token)
            elif role == "parent":
                test_parent_endpoints(base, token)
            elif role == "teacher":
                test_teacher_endpoints(base, token)
            elif role == "student":
                test_student_endpoints(base, token)

            # Suggest running with other roles
            other_roles = {"admin", "parent", "teacher", "student"} - {role}
            print(f"\n{YELLOW}Tip: re-run with a {'/'.join(other_roles)} account to test those endpoints{RESET}")
    else:
        skip("Authenticated tests", "pass --email and --password (or set SMOKE_EMAIL, SMOKE_PASSWORD)")

    # Summary
    print(f"\n{BOLD}{'=' * 45}{RESET}")
    total = passed + failed + skipped
    color = GREEN if failed == 0 else RED
    print(f"{color}{BOLD}{passed} passed{RESET}, {RED if failed else ''}{failed} failed{RESET}, {skipped} skipped — {total} total")

    if failed > 0:
        print(f"\n{RED}Failed tests:{RESET}")
        for status, name in results:
            if status == "FAIL":
                print(f"  - {name}")

    print()
    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()
