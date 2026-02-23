"""Tests for security.py — passive and active scanner."""

import pytest
from webreaper.modules.security import SecurityScanner


@pytest.fixture
def scanner():
    return SecurityScanner()


# ── Header detection ─────────────────────────────────────────

def test_missing_hsts_creates_finding(scanner):
    headers = {
        "X-Frame-Options": "DENY",
        "X-Content-Type-Options": "nosniff",
        "Content-Security-Policy": "default-src 'self'",
        # No Strict-Transport-Security
    }
    findings = scanner._check_headers(headers)
    types = [f["type"] for f in findings]
    assert "Missing Security Header" in types
    hsts_finding = next(f for f in findings if f.get("header") == "Strict-Transport-Security")
    assert hsts_finding["severity"] == "Low"


def test_cors_wildcard_detected(scanner):
    headers = {"Access-Control-Allow-Origin": "*"}
    findings = scanner._check_headers(headers)
    cors = [f for f in findings if f["type"] == "CORS Misconfiguration"]
    assert len(cors) == 1
    assert cors[0]["severity"] == "Medium"


def test_all_security_headers_present_no_missing_finding(scanner):
    headers = {
        "Content-Security-Policy": "default-src 'self'",
        "X-Frame-Options": "DENY",
        "X-Content-Type-Options": "nosniff",
        "Strict-Transport-Security": "max-age=31536000",
        "X-XSS-Protection": "1; mode=block",
        "Referrer-Policy": "no-referrer",
        "Permissions-Policy": "geolocation=()",
    }
    findings = scanner._check_headers(headers)
    missing = [f for f in findings if f["type"] == "Missing Security Header"]
    assert len(missing) == 0


# ── JWT exposure ─────────────────────────────────────────────

def test_jwt_exposure_detected(scanner):
    jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
    findings = scanner._check_jwt(f'var token = "{jwt}";', {})
    assert len(findings) >= 1
    assert findings[0]["type"] == "JWT Exposure"
    assert findings[0]["severity"] == "High"


def test_no_jwt_no_finding(scanner):
    findings = scanner._check_jwt("no tokens here", {})
    assert findings == []


# ── Sensitive data patterns ──────────────────────────────────

def test_aws_key_detected(scanner):
    body = 'var key = "AKIAIOSFODNN7EXAMPLE";'
    findings = scanner._check_sensitive_exposure(body)
    types = [f["type"] for f in findings]
    assert "Sensitive Data Exposure" in types


def test_github_token_detected(scanner):
    body = 'const token = "ghp_1234567890abcdefghij1234567890abcdef";'
    findings = scanner._check_sensitive_exposure(body)
    types = [f["type"] for f in findings]
    assert "Sensitive Data Exposure" in types


def test_no_sensitive_data_no_finding(scanner):
    body = "<html><body>Hello world, no secrets here.</body></html>"
    findings = scanner._check_sensitive_exposure(body)
    assert findings == []


# ── Tech fingerprinting ──────────────────────────────────────

def test_wordpress_detected_from_body(scanner):
    body = '<link rel="stylesheet" href="/wp-content/themes/theme/style.css">'
    tech = scanner.fingerprint_tech("https://example.com", {}, body)
    assert "WordPress" in tech["CMS"]


def test_nextjs_detected_from_body(scanner):
    body = '<script src="/_next/static/chunks/main.js"></script>'
    tech = scanner.fingerprint_tech("https://example.com", {}, body)
    assert "Next.js" in tech["Framework"]


def test_cloudflare_detected_from_headers(scanner):
    headers = {"cf-ray": "8abc123-SFO"}
    tech = scanner.fingerprint_tech("https://example.com", headers, "")
    cdn = tech["CDN / Proxy"]
    assert "Cloudflare" in cdn


# ── XSS reflection ──────────────────────────────────────────

def test_xss_reflection_in_dangerous_context(scanner):
    url = "https://example.com/search?q=<script>alert(1)</script>"
    body = '<html><body><script>alert(1)</script></body></html>'
    findings = scanner._check_reflected_xss(url, body)
    # Script tag is a dangerous context
    assert len(findings) >= 1


# ── SSRF parameter detection ─────────────────────────────────

def test_ssrf_url_param_flagged(scanner):
    url = "https://example.com/fetch?url=http://example.org"
    findings = scanner._check_ssrf_params(url)
    assert len(findings) >= 1
    assert findings[0]["type"] == "Potential SSRF Vector"


def test_ssrf_no_match_on_safe_params(scanner):
    url = "https://example.com/search?q=hello&page=2"
    findings = scanner._check_ssrf_params(url)
    assert findings == []


# ── generate_report ──────────────────────────────────────────

def test_generate_report_counts(scanner):
    scanner.findings = [
        {"severity": "High"},
        {"severity": "High"},
        {"severity": "Medium"},
        {"severity": "Low"},
    ]
    report = scanner.generate_report()
    assert report["total_findings"] == 4
    assert report["severity_breakdown"]["High"] == 2
    assert report["severity_breakdown"]["Medium"] == 1
