# CORS Security & Verification Guide

This document outlines the security architecture for Cross-Origin Resource Sharing (CORS) within the bits&bytes™ Motherboard application. It serves as a guide for developers to configure, audit, and test CORS policies to prevent unauthorized data access.

---

## 1. CORS Risk Model

When the FastAPI backend communicates with the Next.js frontend or external integrations, the browser enforces the Same-Origin Policy (SOP). CORS allows the backend to selectively bypass SOP. If misconfigured, this bypass can expose authenticated user data.

### 1.1 Dynamic Origin Reflection
* **The Risk:** Reading the incoming `Origin` header and reflecting it back in `Access-Control-Allow-Origin` while setting `Access-Control-Allow-Credentials: true`. This allows any malicious site to read response data from authenticated sessions.
* **Motherboard Policy:** Never dynamically reflect untrusted origins. The API must validate incoming origins against a strict, predefined whitelist.

### 1.2 The `null` Origin Trust
* **The Risk:** Configuring `Access-Control-Allow-Origin: null`. Sandboxed iframes, local files, and certain redirects send `Origin: null`. Trusting `null` allows an attacker to wrap code in a sandboxed iframe to bypass access controls.
* **Motherboard Policy:** Never specify `null` in allowed origins.

### 1.3 Regex and Substring Validation Bypasses
* **The Risk:** Using weak validation logic to verify subdomains. For example, a regex like `.*\.example\.com` can be bypassed by an origin like `attacker-example.com` or `example.com.attacker.com`.
* **Motherboard Policy:** All regular expressions used for origin validation must be strictly anchored (`^` and `$`) and escape special characters correctly (e.g., `^https://[a-zA-Z0-9-]+\.gobitsnbytes\.org$`).

---

## 2. Secure Implementation in FastAPI

The Motherboard backend uses FastAPI's `CORSMiddleware` with explicit configuration parameters:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Strict list of canonical origins
ALLOWED_ORIGINS = [
    "https://gobitsnbytes.org",
    "https://motherboard.gobitsnbytes.org",
    "http://localhost:3000",  # Development environment
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,  # Mandatory for session cookie sharing
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
    max_age=3600,
)
```

---

## 3. Verification & Automated Testing

To ensure that CORS configurations do not degrade over time, developers must write integration tests verifying the API's behavior against both whitelisted and malicious origins.

### 3.1 Example CORS Test Suite (using `pytest`)

```python
from fastapi.testclient import TestClient
import pytest
from app.main import app

client = TestClient(app)

def test_cors_allowed_origin():
    # Verify that a whitelisted origin receives appropriate CORS headers
    headers = {"Origin": "https://gobitsnbytes.org"}
    response = client.get("/health/", headers=headers)
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "https://gobitsnbytes.org"
    assert response.headers.get("access-control-allow-credentials") == "true"

def test_cors_disallowed_origin():
    # Verify that an untrusted origin is not reflected in CORS headers
    headers = {"Origin": "https://attacker.com"}
    response = client.get("/health/", headers=headers)
    # The request should succeed, but CORS headers must not reflect the attacker origin
    assert response.headers.get("access-control-allow-origin") is None

def test_cors_null_origin():
    # Verify that the null origin is explicitly rejected/ignored
    headers = {"Origin": "null"}
    response = client.get("/health/", headers=headers)
    assert response.headers.get("access-control-allow-origin") is None
```
