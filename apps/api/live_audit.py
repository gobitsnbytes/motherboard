#!/usr/bin/env python3
"""
Rigorous Live Backend Auditor for GOBITSNBYTES motherboard.
Performs end-to-end security, structure, and functional health validation
against the live API at api.gobitsnbytes.org.
"""

import sys
import json
import urllib.request
import urllib.error
import time

LIVE_HOST = "https://api.gobitsnbytes.org"

# ANSI color codes for pretty output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

def print_section(title: str):
    print(f"\n{BOLD}{CYAN}=== {title} ==={RESET}")

def assert_endpoint(
    path: str,
    method: str = "GET",
    headers: dict = None,
    expected_status: int = 200,
    expected_body_contains: str = None,
    expected_body_keys: list = None,
    expected_headers: dict = None,
):
    url = f"{LIVE_HOST}{path}"
    headers = headers or {}
    
    # Standard headers for user agent
    if "User-Agent" not in headers:
        headers["User-Agent"] = "Antigravity-Live-Auditor/1.0"
        
    req = urllib.request.Request(url, headers=headers, method=method)
    
    print(f"Testing {BOLD}{method}{RESET} {path}...", end=" ")
    sys.stdout.flush()
    
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            status = response.status
            body = response.read().decode("utf-8")
            res_headers = {k.lower(): v for k, v in response.getheaders()}
    except urllib.error.HTTPError as e:
        status = e.code
        body = e.read().decode("utf-8")
        res_headers = {k.lower(): v for k, v in e.headers.items()}
    except Exception as e:
        print(f"{RED}FAILED{RESET} (Connection Error: {e})")
        return False

    # 1. Assert status code
    if status != expected_status:
        print(f"{RED}FAILED{RESET}")
        print(f"  Expected Status: {expected_status}, Got: {status}")
        print(f"  Response Body: {body}")
        return False
        
    # 2. Assert body contents
    if expected_body_contains:
        if expected_body_contains not in body:
            print(f"{RED}FAILED{RESET}")
            print(f"  Expected substring '{expected_body_contains}' not found in body: {body}")
            return False
            
    # 3. Assert body keys (if JSON)
    if expected_body_keys:
        try:
            data = json.loads(body)
            for key in expected_body_keys:
                if key not in data:
                    print(f"{RED}FAILED{RESET}")
                    print(f"  Expected key '{key}' not found in response JSON: {data}")
                    return False
        except json.JSONDecodeError:
            print(f"{RED}FAILED{RESET} (Invalid JSON response)")
            print(f"  Body: {body}")
            return False

    # 4. Assert response headers
    if expected_headers:
        for k, v in expected_headers.items():
            k_lower = k.lower()
            if k_lower not in res_headers:
                print(f"{RED}FAILED{RESET}")
                print(f"  Expected response header '{k}' missing.")
                return False
            if v is not None and res_headers[k_lower] != v.lower():
                print(f"{RED}FAILED{RESET}")
                print(f"  Expected response header '{k}' to be '{v}', got '{res_headers[k_lower]}'")
                return False

    print(f"{GREEN}PASSED{RESET} (Status: {status})")
    return True


def run_audit():
    print(f"{BOLD}{YELLOW}Starting Rigorous Live Backend Audit for {LIVE_HOST}{RESET}")
    start_time = time.time()
    
    success = True

    # --- Section 1: Public Health & Info Endpoints ---
    print_section("Public Health & Info Endpoints")
    
    # Base health
    success &= assert_endpoint(
        "/health",
        expected_status=200,
        expected_body_contains='"status":"ok"'
    )
    
    # Finance health
    success &= assert_endpoint(
        "/api/finance/health",
        expected_status=200,
        expected_body_contains='"status":"ok"',
        expected_body_keys=["status", "service"]
    )
    
    # Finance info
    success &= assert_endpoint(
        "/api/finance/info",
        expected_status=200,
        expected_body_contains="GOBITSNBYTES FOUNDATION",
        expected_body_keys=["status", "organization"]
    )

    # --- Section 2: OpenAPI & Docs Availability ---
    print_section("API OpenAPI Documentation")
    
    # OpenAPI json spec
    success &= assert_endpoint(
        "/api/openapi.json",
        expected_status=200,
        expected_body_keys=["openapi", "paths", "components"]
    )

    # --- Section 3: Auth Security Gate Checks (Missing Headers) ---
    print_section("IAM Security Gates (Missing Headers)")
    
    endpoints_to_block = [
        "/api/users/",
        "/api/groups/",
        "/api/forks/",
        "/api/iam/discord-roles",
        "/api/finance/accounts",
        "/api/sync/runs",
    ]
    
    for path in endpoints_to_block:
        success &= assert_endpoint(
            path,
            expected_status=401,
            expected_body_contains="Missing internal authentication headers"
        )

    # --- Section 4: Auth Security Gate Checks (Tampered/Malformed Headers) ---
    print_section("IAM Security Gates (Malformed & Stale Credentials)")
    
    # 1. Partial headers
    success &= assert_endpoint(
        "/api/users/",
        headers={"X-Internal-User-Id": "1234"},
        expected_status=401,
        expected_body_contains="Missing internal authentication headers"
    )
    
    # 2. Invalid timestamp format
    success &= assert_endpoint(
        "/api/users/",
        headers={
            "X-Internal-User-Id": "1234",
            "X-Internal-Timestamp": "not-a-number",
            "X-Internal-Signature": "abc",
        },
        expected_status=401,
        expected_body_contains="Invalid internal authentication timestamp"
    )
    
    # 3. Stale timestamp (more than 300s in past)
    stale_ts = str(int(time.time()) - 400)
    success &= assert_endpoint(
        "/api/users/",
        headers={
            "X-Internal-User-Id": "1234",
            "X-Internal-Timestamp": stale_ts,
            "X-Internal-Signature": "abc",
        },
        expected_status=401,
        expected_body_contains="Stale internal authentication timestamp"
    )
    
    # 4. Invalid HMAC signature
    fresh_ts = str(int(time.time()))
    success &= assert_endpoint(
        "/api/users/",
        headers={
            "X-Internal-User-Id": "50e41369-b4be-4f4b-bd22-d7b322a36b5c",
            "X-Internal-Timestamp": fresh_ts,
            "X-Internal-Signature": "wrong-signature-value-here",
        },
        expected_status=401,
        expected_body_contains="Invalid internal authentication signature"
    )

    # --- Section 5: CORS Configuration Verification ---
    print_section("CORS Origin Checks")
    
    # Untrusted origin check (CORS headers should NOT be present)
    url = f"{LIVE_HOST}/health"
    req = urllib.request.Request(url, headers={"Origin": "https://evil.com"})
    print("Testing CORS disallowed origin (https://evil.com)...", end=" ")
    try:
        with urllib.request.urlopen(req) as resp:
            headers = {k.lower(): v for k, v in resp.getheaders()}
            if "access-control-allow-origin" in headers:
                print(f"{RED}FAILED{RESET} (CORS headers present for evil.com: {headers.get('access-control-allow-origin')})")
                success = False
            else:
                print(f"{GREEN}PASSED{RESET}")
    except Exception as e:
         print(f"{RED}FAILED{RESET} (Error: {e})")
         success = False

    # --- Summary ---
    duration = time.time() - start_time
    print("\n" + "="*40)
    if success:
        print(f"{GREEN}{BOLD}AUDIT SUCCESSFUL: Live backend is fully healthy and secure!{RESET}")
        print(f"Completed in {duration:.2f} seconds.")
        return 0
    else:
        print(f"{RED}{BOLD}AUDIT FAILED: One or more assertions did not pass.{RESET}")
        print(f"Completed in {duration:.2f} seconds.")
        return 1

if __name__ == "__main__":
    sys.exit(run_audit())
