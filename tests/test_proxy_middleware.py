"""Tests for src/primary/utils/proxy.py — TrustedProxyMiddleware."""
import os
from unittest.mock import MagicMock

import pytest

from src.primary.utils.proxy import TrustedProxyMiddleware


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_middleware(trusted_proxies: str):
    """Build a middleware instance with TRUSTED_PROXIES set to *trusted_proxies*."""
    app = MagicMock(return_value=iter([b""]))
    env = os.environ.copy()
    env["TRUSTED_PROXIES"] = trusted_proxies
    old = os.environ.get("TRUSTED_PROXIES")
    os.environ["TRUSTED_PROXIES"] = trusted_proxies
    try:
        mw = TrustedProxyMiddleware(app)
    finally:
        if old is None:
            os.environ.pop("TRUSTED_PROXIES", None)
        else:
            os.environ["TRUSTED_PROXIES"] = old
    mw._app = app
    return mw


def _make_environ(**kwargs):
    """Minimal WSGI environ dict."""
    base = {
        "REMOTE_ADDR": "1.2.3.4",
        "wsgi.url_scheme": "http",
        "HTTP_HOST": "seekarr.local",
        "SCRIPT_NAME": "",
    }
    base.update(kwargs)
    return base


def _call(mw, environ):
    """Invoke the middleware and return the (possibly mutated) environ."""
    mw(environ, MagicMock())
    return environ


# ── Constructor — TRUSTED_PROXIES parsing ─────────────────────────────────────

def test_trust_all_wildcard(monkeypatch):
    monkeypatch.setenv("TRUSTED_PROXIES", "*")
    mw = TrustedProxyMiddleware(MagicMock())
    assert mw.trust_all is True


def test_empty_trusted_proxies_no_trust_all(monkeypatch):
    monkeypatch.setenv("TRUSTED_PROXIES", "")
    mw = TrustedProxyMiddleware(MagicMock())
    assert mw.trust_all is False
    assert mw.trusted_ips == []
    assert mw.trusted_networks == []


def test_single_ip_parsed(monkeypatch):
    monkeypatch.setenv("TRUSTED_PROXIES", "10.0.1.5")
    mw = TrustedProxyMiddleware(MagicMock())
    import ipaddress
    assert ipaddress.ip_address("10.0.1.5") in mw.trusted_ips


def test_cidr_range_parsed(monkeypatch):
    monkeypatch.setenv("TRUSTED_PROXIES", "10.0.0.0/8")
    mw = TrustedProxyMiddleware(MagicMock())
    import ipaddress
    assert any(str(n) == "10.0.0.0/8" for n in mw.trusted_networks)


def test_mixed_ip_and_cidr_parsed(monkeypatch):
    monkeypatch.setenv("TRUSTED_PROXIES", "10.0.1.5,192.168.0.0/16")
    mw = TrustedProxyMiddleware(MagicMock())
    assert len(mw.trusted_ips) == 1
    assert len(mw.trusted_networks) == 1


def test_invalid_entry_is_ignored(monkeypatch):
    monkeypatch.setenv("TRUSTED_PROXIES", "not-an-ip,10.0.1.5")
    mw = TrustedProxyMiddleware(MagicMock())
    assert len(mw.trusted_ips) == 1  # only the valid one


def test_unset_trusted_proxies_no_trust(monkeypatch):
    monkeypatch.delenv("TRUSTED_PROXIES", raising=False)
    mw = TrustedProxyMiddleware(MagicMock())
    assert mw.trust_all is False
    assert mw.trusted_ips == []


# ── _is_trusted ───────────────────────────────────────────────────────────────

def test_is_trusted_trust_all(monkeypatch):
    monkeypatch.setenv("TRUSTED_PROXIES", "*")
    mw = TrustedProxyMiddleware(MagicMock())
    assert mw._is_trusted("1.2.3.4") is True


def test_is_trusted_specific_ip_match(monkeypatch):
    monkeypatch.setenv("TRUSTED_PROXIES", "10.0.1.5")
    mw = TrustedProxyMiddleware(MagicMock())
    assert mw._is_trusted("10.0.1.5") is True


def test_is_trusted_specific_ip_no_match(monkeypatch):
    monkeypatch.setenv("TRUSTED_PROXIES", "10.0.1.5")
    mw = TrustedProxyMiddleware(MagicMock())
    assert mw._is_trusted("10.0.1.6") is False


def test_is_trusted_cidr_match(monkeypatch):
    monkeypatch.setenv("TRUSTED_PROXIES", "192.168.0.0/16")
    mw = TrustedProxyMiddleware(MagicMock())
    assert mw._is_trusted("192.168.1.100") is True


def test_is_trusted_cidr_no_match(monkeypatch):
    monkeypatch.setenv("TRUSTED_PROXIES", "192.168.0.0/16")
    mw = TrustedProxyMiddleware(MagicMock())
    assert mw._is_trusted("10.0.0.1") is False


def test_is_trusted_invalid_addr_returns_false(monkeypatch):
    monkeypatch.setenv("TRUSTED_PROXIES", "10.0.0.1")
    mw = TrustedProxyMiddleware(MagicMock())
    assert mw._is_trusted("not-an-ip") is False


def test_is_trusted_no_proxies_configured(monkeypatch):
    monkeypatch.setenv("TRUSTED_PROXIES", "")
    mw = TrustedProxyMiddleware(MagicMock())
    assert mw._is_trusted("10.0.0.1") is False


# ── __call__ — untrusted source strips headers ────────────────────────────────

def test_untrusted_strips_x_forwarded_for(monkeypatch):
    monkeypatch.setenv("TRUSTED_PROXIES", "10.0.1.5")
    mw = TrustedProxyMiddleware(MagicMock(return_value=iter([b""])))
    environ = _make_environ(
        REMOTE_ADDR="1.2.3.4",
        HTTP_X_FORWARDED_FOR="5.5.5.5",
    )
    _call(mw, environ)
    assert "HTTP_X_FORWARDED_FOR" not in environ


def test_untrusted_strips_x_forwarded_proto(monkeypatch):
    monkeypatch.setenv("TRUSTED_PROXIES", "10.0.1.5")
    mw = TrustedProxyMiddleware(MagicMock(return_value=iter([b""])))
    environ = _make_environ(
        REMOTE_ADDR="1.2.3.4",
        HTTP_X_FORWARDED_PROTO="https",
    )
    _call(mw, environ)
    assert "HTTP_X_FORWARDED_PROTO" not in environ


def test_untrusted_remote_addr_unchanged(monkeypatch):
    monkeypatch.setenv("TRUSTED_PROXIES", "10.0.1.5")
    mw = TrustedProxyMiddleware(MagicMock(return_value=iter([b""])))
    environ = _make_environ(
        REMOTE_ADDR="1.2.3.4",
        HTTP_X_FORWARDED_FOR="9.9.9.9",
    )
    _call(mw, environ)
    assert environ["REMOTE_ADDR"] == "1.2.3.4"


# ── __call__ — trusted source rewrites environ ────────────────────────────────

def test_trusted_rewrites_remote_addr_from_x_forwarded_for(monkeypatch):
    monkeypatch.setenv("TRUSTED_PROXIES", "10.0.1.5")
    mw = TrustedProxyMiddleware(MagicMock(return_value=iter([b""])))
    environ = _make_environ(
        REMOTE_ADDR="10.0.1.5",
        HTTP_X_FORWARDED_FOR="203.0.113.1, 10.0.1.5",
    )
    _call(mw, environ)
    assert environ["REMOTE_ADDR"] == "203.0.113.1"


def test_trusted_rewrites_scheme_from_x_forwarded_proto(monkeypatch):
    monkeypatch.setenv("TRUSTED_PROXIES", "10.0.1.5")
    mw = TrustedProxyMiddleware(MagicMock(return_value=iter([b""])))
    environ = _make_environ(
        REMOTE_ADDR="10.0.1.5",
        HTTP_X_FORWARDED_PROTO="https",
    )
    _call(mw, environ)
    assert environ["wsgi.url_scheme"] == "https"


def test_trusted_rewrites_host_from_x_forwarded_host(monkeypatch):
    monkeypatch.setenv("TRUSTED_PROXIES", "10.0.1.5")
    mw = TrustedProxyMiddleware(MagicMock(return_value=iter([b""])))
    environ = _make_environ(
        REMOTE_ADDR="10.0.1.5",
        HTTP_X_FORWARDED_HOST="app.example.com",
    )
    _call(mw, environ)
    assert environ["HTTP_HOST"] == "app.example.com"


def test_trusted_rewrites_script_name_from_x_forwarded_prefix(monkeypatch):
    monkeypatch.setenv("TRUSTED_PROXIES", "10.0.1.5")
    mw = TrustedProxyMiddleware(MagicMock(return_value=iter([b""])))
    environ = _make_environ(
        REMOTE_ADDR="10.0.1.5",
        HTTP_X_FORWARDED_PREFIX="/seekarr/",
    )
    _call(mw, environ)
    assert environ["SCRIPT_NAME"] == "/seekarr"


def test_trusted_x_forwarded_host_multiple_values_takes_first(monkeypatch):
    monkeypatch.setenv("TRUSTED_PROXIES", "10.0.1.5")
    mw = TrustedProxyMiddleware(MagicMock(return_value=iter([b""])))
    environ = _make_environ(
        REMOTE_ADDR="10.0.1.5",
        HTTP_X_FORWARDED_HOST="primary.example.com, secondary.example.com",
    )
    _call(mw, environ)
    assert environ["HTTP_HOST"] == "primary.example.com"


def test_trust_all_rewrites_headers(monkeypatch):
    monkeypatch.setenv("TRUSTED_PROXIES", "*")
    mw = TrustedProxyMiddleware(MagicMock(return_value=iter([b""])))
    environ = _make_environ(
        REMOTE_ADDR="any.ip.at.all",
        HTTP_X_FORWARDED_PROTO="https",
    )
    _call(mw, environ)
    assert environ["wsgi.url_scheme"] == "https"


def test_trusted_no_forwarded_headers_present_leaves_environ_intact(monkeypatch):
    monkeypatch.setenv("TRUSTED_PROXIES", "10.0.1.5")
    mw = TrustedProxyMiddleware(MagicMock(return_value=iter([b""])))
    environ = _make_environ(REMOTE_ADDR="10.0.1.5")
    _call(mw, environ)
    assert environ["REMOTE_ADDR"] == "10.0.1.5"
    assert environ["wsgi.url_scheme"] == "http"
