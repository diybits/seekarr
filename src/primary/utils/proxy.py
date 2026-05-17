#!/usr/bin/env python3
"""
Trusted proxy WSGI middleware for Seekarr.

Only processes X-Forwarded-* headers when the direct upstream IP is in the
TRUSTED_PROXIES allowlist. Strips forwarded headers from untrusted connections
to prevent client spoofing.

TRUSTED_PROXIES env var (comma-separated):
  *                        trust all upstream IPs (simple LAN deployments)
  10.0.1.5                 single proxy IP
  10.0.0.0/8               CIDR range (Docker overlay, subnet, etc.)
  10.0.1.5,192.168.1.0/24  mix of IPs and CIDRs

If TRUSTED_PROXIES is unset or empty, all forwarded headers are stripped and
Seekarr behaves as if accessed directly.
"""

import ipaddress
import logging
import os
from typing import List, Union

logger = logging.getLogger("seekarr")

_FORWARDED_HEADERS = [
    "HTTP_X_FORWARDED_FOR",
    "HTTP_X_FORWARDED_PROTO",
    "HTTP_X_FORWARDED_HOST",
    "HTTP_X_FORWARDED_PORT",
    "HTTP_X_FORWARDED_PREFIX",
    "HTTP_X_REAL_IP",
]


class TrustedProxyMiddleware:
    """WSGI middleware that applies forwarded header processing only for trusted proxies."""

    def __init__(self, app):
        self.app = app
        self.trust_all = False
        self.trusted_networks: List[Union[ipaddress.IPv4Network, ipaddress.IPv6Network]] = []
        self.trusted_ips: List[Union[ipaddress.IPv4Address, ipaddress.IPv6Address]] = []

        raw = os.environ.get("TRUSTED_PROXIES", "").strip()
        if raw == "*":
            self.trust_all = True
            logger.info("TrustedProxyMiddleware: trusting ALL upstream proxies (TRUSTED_PROXIES=*)")
        elif raw:
            for entry in (e.strip() for e in raw.split(",") if e.strip()):
                try:
                    if "/" in entry:
                        self.trusted_networks.append(ipaddress.ip_network(entry, strict=False))
                    else:
                        self.trusted_ips.append(ipaddress.ip_address(entry))
                except ValueError:
                    logger.warning(f"TrustedProxyMiddleware: ignoring invalid entry '{entry}'")
            logger.info(
                f"TrustedProxyMiddleware: trusted proxies — "
                f"IPs: {[str(i) for i in self.trusted_ips]}, "
                f"CIDRs: {[str(n) for n in self.trusted_networks]}"
            )
        else:
            logger.info("TrustedProxyMiddleware: TRUSTED_PROXIES not set — forwarded headers stripped")

    def _is_trusted(self, addr: str) -> bool:
        if self.trust_all:
            return True
        try:
            ip = ipaddress.ip_address(addr)
            if ip in self.trusted_ips:
                return True
            return any(ip in network for network in self.trusted_networks)
        except ValueError:
            return False

    def __call__(self, environ, start_response):
        remote_addr = environ.get("REMOTE_ADDR", "")

        if not self._is_trusted(remote_addr):
            # Untrusted source — strip all forwarded headers to prevent spoofing
            for header in _FORWARDED_HEADERS:
                environ.pop(header, None)
            return self.app(environ, start_response)

        # Trusted proxy — rewrite environ from forwarded headers

        # Real client IP: take the leftmost entry in X-Forwarded-For
        # (the first IP the chain received from, before any proxies appended theirs)
        x_forwarded_for = environ.get("HTTP_X_FORWARDED_FOR", "")
        if x_forwarded_for:
            real_ip = x_forwarded_for.split(",")[0].strip()
            environ["REMOTE_ADDR"] = real_ip

        # Scheme (http vs https)
        x_forwarded_proto = environ.get("HTTP_X_FORWARDED_PROTO", "")
        if x_forwarded_proto:
            environ["wsgi.url_scheme"] = x_forwarded_proto.strip().lower()

        # Host/FQDN used by the client (used by url_for() to build absolute URLs)
        x_forwarded_host = environ.get("HTTP_X_FORWARDED_HOST", "")
        if x_forwarded_host:
            # Take only the first host if the header contains multiple values
            environ["HTTP_HOST"] = x_forwarded_host.split(",")[0].strip()

        # Subpath prefix (e.g. Nginx proxy_pass to /seekarr/)
        x_forwarded_prefix = environ.get("HTTP_X_FORWARDED_PREFIX", "")
        if x_forwarded_prefix:
            environ["SCRIPT_NAME"] = x_forwarded_prefix.rstrip("/")

        return self.app(environ, start_response)
