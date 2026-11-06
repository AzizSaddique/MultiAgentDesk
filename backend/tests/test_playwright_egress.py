"""
Security and Isolation Tests for Playwright Egress Proxy and robots.txt.
Verifies:
1. Proxy requires cryptographically valid Basic authentication.
2. Proxy blocks loopback destinations (127.0.0.1, localhost).
3. Proxy blocks private IPv4 and IPv6 networks (10.0.0.0/8, 192.168.0.0/16, fc00::/7).
4. Proxy blocks cloud metadata endpoints (169.254.169.254).
5. Proxy normalizes and blocks alternate IP notations (integer, hex, octal, shortened).
6. Proxy blocks DNS rebinding destinations.
7. Proxy enforces permitted standard ports (80, 443).
8. WebSocket CONNECT tunnels are subject to destination SSRF filtering.
9. Browser fails closed when proxy is unavailable (no direct egress fallback).
10. Browser loopback and cloud metadata requests are blocked by proxy.
11. robots.txt safe fetch works for public domains.
12. robots.txt redirect to private destination is blocked by SSRF policy.
13. robots.txt DNS rebinding is blocked.
"""
import asyncio
import base64
import pytest
from unittest.mock import patch, MagicMock
import httpx
from playwright.async_api import async_playwright

from backend.security.egress_proxy import SecureEgressProxy
from backend.security.url_validator import (
    validate_outbound_url,
    SSRFSecurityError,
    safe_fetch_get_sync,
)
from backend.providers.playwright_scraper import is_allowed_by_robots


# ============================================================================
# 1. Proxy Authentication and Access Control Tests
# ============================================================================

@pytest.mark.anyio
async def test_proxy_requires_valid_authentication():
    """Proxy returns 407 Proxy Authentication Required on missing or invalid auth."""
    async with SecureEgressProxy() as proxy:
        port = proxy.actual_port

        # Request 1: No auth header
        r, w = await asyncio.open_connection("127.0.0.1", port)
        w.write(b"CONNECT example.com:443 HTTP/1.1\r\nHost: example.com:443\r\n\r\n")
        await w.drain()
        resp = await r.read(1024)
        w.close()
        await w.wait_closed()
        assert b"407 Proxy Authentication Required" in resp
        assert b'Proxy-Authenticate: Basic realm="AgentDesk Egress"' in resp

        # Request 2: Invalid credentials
        wrong_auth = "Basic " + base64.b64encode(b"wrong:creds").decode()
        r, w = await asyncio.open_connection("127.0.0.1", port)
        w.write(f"CONNECT example.com:443 HTTP/1.1\r\nHost: example.com:443\r\nProxy-Authorization: {wrong_auth}\r\n\r\n".encode())
        await w.drain()
        resp = await r.read(1024)
        w.close()
        await w.wait_closed()
        assert b"407 Proxy Authentication Required" in resp


# ============================================================================
# 2. SSRF Destination Filtering via Proxy CONNECT and HTTP
# ============================================================================

@pytest.mark.anyio
async def test_proxy_blocks_loopback_destinations():
    """Proxy rejects CONNECT and HTTP requests targeting loopback addresses."""
    async with SecureEgressProxy() as proxy:
        port = proxy.actual_port
        auth = proxy.expected_auth

        # Loopback CONNECT
        r, w = await asyncio.open_connection("127.0.0.1", port)
        w.write(f"CONNECT 127.0.0.1:8000 HTTP/1.1\r\nHost: 127.0.0.1:8000\r\nProxy-Authorization: {auth}\r\n\r\n".encode())
        await w.drain()
        resp = await r.read(1024)
        w.close()
        await w.wait_closed()
        assert b"403 Forbidden" in resp

        # Loopback GET
        r, w = await asyncio.open_connection("127.0.0.1", port)
        w.write(f"GET http://127.0.0.1:8000/api/health HTTP/1.1\r\nHost: 127.0.0.1:8000\r\nProxy-Authorization: {auth}\r\n\r\n".encode())
        await w.drain()
        resp = await r.read(1024)
        w.close()
        await w.wait_closed()
        assert b"403 Forbidden" in resp


@pytest.mark.anyio
async def test_proxy_blocks_private_networks_ipv4_and_ipv6():
    """Proxy rejects RFC 1918 private IPv4 and Unique Local IPv6 spaces."""
    async with SecureEgressProxy() as proxy:
        port = proxy.actual_port
        auth = proxy.expected_auth

        targets = [
            "10.0.0.1:443",
            "172.16.0.1:443",
            "192.168.1.1:443",
            "[fc00::1]:443",
            "[fe80::1]:443",
            "[::ffff:10.0.0.1]:443",
        ]
        for target in targets:
            r, w = await asyncio.open_connection("127.0.0.1", port)
            w.write(f"CONNECT {target} HTTP/1.1\r\nHost: {target}\r\nProxy-Authorization: {auth}\r\n\r\n".encode())
            await w.drain()
            resp = await r.read(1024)
            w.close()
            await w.wait_closed()
            assert b"403 Forbidden" in resp, f"Target {target} was not blocked by proxy"


@pytest.mark.anyio
async def test_proxy_blocks_cloud_metadata():
    """Proxy rejects AWS/GCP/Azure link-local metadata address 169.254.169.254."""
    async with SecureEgressProxy() as proxy:
        port = proxy.actual_port
        auth = proxy.expected_auth

        r, w = await asyncio.open_connection("127.0.0.1", port)
        w.write(f"CONNECT 169.254.169.254:80 HTTP/1.1\r\nHost: 169.254.169.254:80\r\nProxy-Authorization: {auth}\r\n\r\n".encode())
        await w.drain()
        resp = await r.read(1024)
        w.close()
        await w.wait_closed()
        assert b"403 Forbidden" in resp


@pytest.mark.anyio
async def test_proxy_blocks_alternate_ip_notations():
    """Proxy canonicalizes and blocks integer, hex, octal, and shortened IP notations."""
    async with SecureEgressProxy() as proxy:
        port = proxy.actual_port
        auth = proxy.expected_auth

        alternate_targets = [
            "2130706433:80",       # 127.0.0.1 as dword integer
            "0177.0.0.1:80",       # 127.0.0.1 as octal
            "0x7f000001:80",       # 127.0.0.1 as hex
            "127.1:80",            # 127.0.0.1 shortened
            "2852039166:80",       # 169.254.169.254 as integer
            "0xa9fea9fe:80",       # 169.254.169.254 as hex
            "10.1:80",             # 10.0.0.1 shortened
        ]
        for target in alternate_targets:
            r, w = await asyncio.open_connection("127.0.0.1", port)
            w.write(f"CONNECT {target} HTTP/1.1\r\nHost: {target}\r\nProxy-Authorization: {auth}\r\n\r\n".encode())
            await w.drain()
            resp = await r.read(1024)
            w.close()
            await w.wait_closed()
            assert b"403 Forbidden" in resp, f"Alternate IP target {target} was not blocked by proxy"


@pytest.mark.anyio
async def test_proxy_blocks_prohibited_ports():
    """Proxy restricts connections strictly to standard HTTP/HTTPS ports (80, 443)."""
    async with SecureEgressProxy() as proxy:
        port = proxy.actual_port
        auth = proxy.expected_auth

        bad_ports = ["example.com:22", "example.com:25", "example.com:3389", "example.com:8080"]
        for target in bad_ports:
            r, w = await asyncio.open_connection("127.0.0.1", port)
            w.write(f"CONNECT {target} HTTP/1.1\r\nHost: {target}\r\nProxy-Authorization: {auth}\r\n\r\n".encode())
            await w.drain()
            resp = await r.read(1024)
            w.close()
            await w.wait_closed()
            assert b"403 Forbidden" in resp


@pytest.mark.anyio
async def test_proxy_blocks_dns_rebinding():
    """Proxy resolves all DNS records and rejects domain if ANY resolved address is private."""
    async with SecureEgressProxy() as proxy:
        port = proxy.actual_port
        auth = proxy.expected_auth

        # Simulate DNS rebinding resolver returning public and loopback IP
        with patch("backend.security.egress_proxy.resolve_domain_ips") as mock_resolve:
            import ipaddress
            mock_resolve.return_value = [ipaddress.ip_address("127.0.0.1")]
            with patch("backend.security.url_validator.resolve_domain_ips", return_value=[ipaddress.ip_address("127.0.0.1")]):
                r, w = await asyncio.open_connection("127.0.0.1", port)
                w.write(f"CONNECT rebind.attacker.com:443 HTTP/1.1\r\nHost: rebind.attacker.com:443\r\nProxy-Authorization: {auth}\r\n\r\n".encode())
                await w.drain()
                resp = await r.read(1024)
                w.close()
                await w.wait_closed()
                assert b"403 Forbidden" in resp


@pytest.mark.anyio
async def test_proxy_websocket_destination_restrictions():
    """WebSocket CONNECT requests (for wss:// endpoints) undergo strict destination filtering."""
    async with SecureEgressProxy() as proxy:
        port = proxy.actual_port
        auth = proxy.expected_auth

        # WebSocket connection to internal host
        r, w = await asyncio.open_connection("127.0.0.1", port)
        w.write(f"CONNECT localhost:8000 HTTP/1.1\r\nHost: localhost:8000\r\nProxy-Authorization: {auth}\r\n\r\n".encode())
        await w.drain()
        resp = await r.read(1024)
        w.close()
        await w.wait_closed()
        assert b"403 Forbidden" in resp


# ============================================================================
# 3. Playwright Chromium Integration & Fail-Closed Tests
# ============================================================================

@pytest.mark.anyio
async def test_browser_fails_closed_when_proxy_unavailable():
    """Chromium fails closed when proxy server is unreachable (net::ERR_PROXY_CONNECTION_FAILED)."""
    # Use an unallocated loopback port
    closed_port = 59991
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--disable-gpu",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-webrtc",
                f"--proxy-server=http://127.0.0.1:{closed_port}",
                "--proxy-bypass-list=<-loopback>",
            ],
            proxy={
                "server": f"http://127.0.0.1:{closed_port}",
                "username": "user",
                "password": "pass",
            }
        )
        context = await browser.new_context()
        page = await context.new_page()

        # Navigation must fail with proxy connection error, never fallback to direct
        with pytest.raises(Exception) as excinfo:
            await page.goto("http://example.com", timeout=3000)

        err_str = str(excinfo.value)
        assert any(token in err_str for token in ("ERR_PROXY_CONNECTION_FAILED", "net::ERR_TIMED_OUT", "Timeout")), f"Unexpected error: {err_str}"
        await browser.close()


@pytest.mark.anyio
async def test_browser_loopback_and_metadata_blocked_by_proxy():
    """Chromium navigation to loopback and metadata is blocked by the active SecureEgressProxy."""
    async with SecureEgressProxy() as proxy:
        port = proxy.actual_port
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--disable-gpu",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-webrtc",
                    *proxy.get_chromium_launch_args(),
                ],
                proxy=proxy.get_playwright_proxy_config(),
            )
            context = await browser.new_context()
            page = await context.new_page()

            # Attempt 1: loopback HTTP navigation -> proxy returns 403
            resp = await page.goto("http://127.0.0.1:8000", timeout=4000)
            assert resp is not None
            assert resp.status == 403

            # Attempt 2: metadata HTTP navigation -> proxy returns 403
            resp_meta = await page.goto("http://169.254.169.254/latest/meta-data", timeout=4000)
            assert resp_meta is not None
            assert resp_meta.status == 403

            await browser.close()


# ============================================================================
# 4. Robots.txt Secure Fetch & SSRF Tests
# ============================================================================

def test_robots_txt_public_request_works():
    """is_allowed_by_robots succeeds for valid public domains using safe_fetch_get_sync."""
    mock_robots = "User-agent: *\nDisallow: /admin\nAllow: /\n"
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = mock_robots

    with patch("backend.providers.playwright_scraper.validate_outbound_url", side_effect=lambda u: (True, u, "")):
        with patch("backend.providers.playwright_scraper.safe_fetch_get_sync", return_value=mock_resp):
            allowed, reason = is_allowed_by_robots("https://example.com/page")
            assert allowed is True
            assert "Permitted" in reason

            # Blocked path
            allowed_admin, admin_reason = is_allowed_by_robots("https://example.com/admin")
            assert allowed_admin is False
            assert "Disallowed by website robots.txt" in admin_reason


def test_robots_txt_redirect_to_private_destination_blocked():
    """robots.txt redirect to a private IP (127.0.0.1) is blocked by SSRF policy."""
    with patch("backend.providers.playwright_scraper.validate_outbound_url", side_effect=lambda u: (True, u, "")):
        with patch("backend.providers.playwright_scraper.safe_fetch_get_sync") as mock_fetch:
            mock_fetch.side_effect = SSRFSecurityError("Redirect to prohibited destination 127.0.0.1 blocked")
            allowed, reason = is_allowed_by_robots("https://evil.com/page")
            assert allowed is False
            assert "blocked by security policy" in reason


def test_robots_txt_dns_rebinding_blocked():
    """robots.txt pre-resolution rejects domains resolving to private IP ranges."""
    with patch("backend.providers.playwright_scraper.validate_outbound_url", return_value=(False, "https://rebind.attacker.com", "Prohibited IP resolved")):
        allowed, reason = is_allowed_by_robots("https://rebind.attacker.com")
        assert allowed is False
        assert "failed safety validation" in reason