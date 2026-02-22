"""Infrastructure X-Ray — DNS, SSL, CDN, WHOIS, and subdomain discovery.

Maps the full infrastructure behind a domain: DNS chain, SSL certificates,
CDN detection, WHOIS data, and subdomain enumeration via Certificate
Transparency logs.
"""

import asyncio
import json
import logging
import ssl
import socket
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import httpx

logger = logging.getLogger("webreaper.xray")


@dataclass
class InfraReport:
    """Full infrastructure report for a domain."""
    domain: str
    dns_records: dict = field(default_factory=dict)
    ssl_info: dict = field(default_factory=dict)
    cdn_info: dict = field(default_factory=dict)
    whois_info: dict = field(default_factory=dict)
    subdomains: list[str] = field(default_factory=list)
    related_domains: list[str] = field(default_factory=list)
    ip_addresses: list[str] = field(default_factory=list)


class InfraXray:
    """Maps infrastructure behind a domain."""

    def __init__(self):
        self._cache: dict[str, InfraReport] = {}

    async def scan(self, domain: str) -> InfraReport:
        """Run full infrastructure scan on a domain."""
        if domain in self._cache:
            return self._cache[domain]

        report = InfraReport(domain=domain)

        # Run all scans concurrently
        results = await asyncio.gather(
            self._dns_lookup(domain),
            self._ssl_info(domain),
            self._cdn_detect(domain),
            self._subdomain_enum(domain),
            return_exceptions=True,
        )

        if not isinstance(results[0], Exception):
            report.dns_records = results[0]
            report.ip_addresses = results[0].get("A", [])
        if not isinstance(results[1], Exception):
            report.ssl_info = results[1]
        if not isinstance(results[2], Exception):
            report.cdn_info = results[2]
        if not isinstance(results[3], Exception):
            report.subdomains = results[3]

        # WHOIS (slower, do separately)
        try:
            report.whois_info = await self._whois_lookup(domain)
        except Exception as e:
            logger.warning(f"WHOIS failed for {domain}: {e}")

        self._cache[domain] = report
        return report

    async def _dns_lookup(self, domain: str) -> dict:
        """Query DNS records (A, AAAA, CNAME, MX, TXT, NS)."""
        records = {}
        try:
            import dns.resolver
            resolver = dns.resolver.Resolver()
            resolver.timeout = 5
            resolver.lifetime = 10

            for rdtype in ["A", "AAAA", "CNAME", "MX", "TXT", "NS"]:
                try:
                    answers = resolver.resolve(domain, rdtype)
                    records[rdtype] = [str(r) for r in answers]
                except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN, dns.resolver.NoNameservers):
                    pass
        except ImportError:
            # Fallback: basic socket lookup
            try:
                ips = socket.getaddrinfo(domain, None)
                records["A"] = list(set(ip[4][0] for ip in ips if ip[0] == socket.AF_INET))
                records["AAAA"] = list(set(ip[4][0] for ip in ips if ip[0] == socket.AF_INET6))
            except socket.gaierror:
                pass
        return records

    async def _ssl_info(self, domain: str) -> dict:
        """Get SSL certificate details."""
        try:
            ctx = ssl.create_default_context()
            loop = asyncio.get_event_loop()

            def _get_cert():
                conn = ctx.wrap_socket(socket.socket(), server_hostname=domain)
                conn.settimeout(5)
                conn.connect((domain, 443))
                cert = conn.getpeercert()
                conn.close()
                return cert

            cert = await loop.run_in_executor(None, _get_cert)

            subject = dict(x[0] for x in cert.get("subject", ()))
            issuer = dict(x[0] for x in cert.get("issuer", ()))
            san = [entry[1] for entry in cert.get("subjectAltName", ())]

            return {
                "subject": subject.get("commonName", ""),
                "issuer": issuer.get("organizationName", ""),
                "issuer_cn": issuer.get("commonName", ""),
                "valid_from": cert.get("notBefore", ""),
                "valid_to": cert.get("notAfter", ""),
                "san": san,
                "serial": cert.get("serialNumber", ""),
                "version": cert.get("version", ""),
            }
        except Exception as e:
            return {"error": str(e)}

    async def _cdn_detect(self, domain: str) -> dict:
        """Detect CDN/WAF from response headers."""
        try:
            async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
                resp = await client.head(f"https://{domain}")
                headers = dict(resp.headers)

            cdn = None
            waf = None

            # CDN detection
            if "cf-ray" in headers:
                cdn = "Cloudflare"
            elif "x-amz-cf-id" in headers:
                cdn = "AWS CloudFront"
            elif "x-fastly-request-id" in headers:
                cdn = "Fastly"
            elif "x-cache" in headers and "akamai" in headers.get("server", "").lower():
                cdn = "Akamai"
            elif "x-vercel-id" in headers:
                cdn = "Vercel"
            elif "x-netlify" in headers or "netlify" in headers.get("server", "").lower():
                cdn = "Netlify"

            # WAF detection
            if "x-sucuri-id" in headers:
                waf = "Sucuri"
            elif cdn == "Cloudflare":
                waf = "Cloudflare WAF"

            return {
                "cdn": cdn,
                "waf": waf,
                "server": headers.get("server", ""),
                "headers": {k: v for k, v in headers.items() if k.startswith("x-")},
            }
        except Exception as e:
            return {"error": str(e)}

    async def _subdomain_enum(self, domain: str) -> list[str]:
        """Enumerate subdomains via Certificate Transparency logs (crt.sh)."""
        subdomains = set()
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"https://crt.sh/?q=%.{domain}&output=json",
                    headers={"User-Agent": "WebReaper/2.0"},
                )
                if resp.status_code == 200:
                    entries = resp.json()
                    for entry in entries:
                        name = entry.get("name_value", "")
                        for sub in name.split("\n"):
                            sub = sub.strip().lower()
                            if sub.endswith(domain) and "*" not in sub:
                                subdomains.add(sub)
        except Exception as e:
            logger.warning(f"crt.sh lookup failed: {e}")

        return sorted(subdomains)

    async def _whois_lookup(self, domain: str) -> dict:
        """WHOIS lookup for domain registration info."""
        try:
            import whois
            loop = asyncio.get_event_loop()
            w = await loop.run_in_executor(None, whois.whois, domain)
            return {
                "registrar": w.registrar,
                "creation_date": str(w.creation_date),
                "expiration_date": str(w.expiration_date),
                "name_servers": w.name_servers if isinstance(w.name_servers, list) else [w.name_servers] if w.name_servers else [],
                "status": w.status if isinstance(w.status, list) else [w.status] if w.status else [],
                "org": w.org,
                "country": w.country,
            }
        except ImportError:
            return {"error": "python-whois not installed"}
        except Exception as e:
            return {"error": str(e)}
