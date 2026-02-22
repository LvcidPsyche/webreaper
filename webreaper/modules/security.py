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
