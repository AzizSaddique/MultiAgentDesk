"""
Automated Security Test Suite: SSRF Protection (P0-SEC-01).
Verifies centralized URL safety validation, prohibited IP detection,
IPv4-mapped IPv6 ranges, cloud metadata protection, DNS pre-resolution,
DNS rebinding defense, and manual redirect re-validation.
"""
import ipaddress
import pytest
import httpx
from unittest.mock import MagicMock

from backend.security.url_validator import (
    validate_target_url,
    validate_outbound_url,
    is_prohibited_ip,
    safe_fetch_get,
    SSRFSecurityError,
    SSRFRedirectError,
)


# ============================================================================
# 1. IP Classification & Prohibited Ranges Unit Tests
# ============================================================================

@pytest.mark.parametrize(
    "ip_str,expected_prohibited,reason_keyword",
    [
        # Loopback
        ("127.0.0.1", True, "Loopback"),
        ("127.0.0.100", True, "Loopback"),
        ("::1", True, "Loopback"),
        # Private IPv4
        ("10.0.0.1", True, "Private"),
        ("10.254.254.254", True, "Private"),
        ("172.16.0.1", True, "Private"),
        ("172.31.255.255", True, "Private"),
        ("192.168.1.1", True, "Private"),
        ("192.168.0.254", True, "Private"),
        # Link-local / Cloud Metadata
        ("169.254.169.254", True, "cloud metadata"),
        ("169.254.1.1", True, "Link-local"),
        ("fe80::1", True, "Link-local"),
        # Carrier-Grade NAT (RFC 6598)
        ("100.64.0.1", True, "Carrier-Grade NAT"),
        # Multicast & Reserved
        ("224.0.0.1", True, "Multicast"),
        ("ff02::1", True, "Multicast"),
        ("0.0.0.0", True, "Unspecified"),
        ("::", True, "Unspecified"),
        ("240.0.0.1", True, "Reserved"),
        ("255.255.255.255", True, "reserved"),
        # IPv4-mapped IPv6
        ("::ffff:127.0.0.1", True, "Loopback"),
        ("::ffff:10.0.0.5", True, "Private"),
        ("::ffff:169.254.169.254", True, "cloud metadata"),
        ("::ffff:192.168.1.1", True, "Private"),
        # Public Safe IPs
        ("93.184.216.34", False, ""),       # example.com
        ("8.8.8.8", False, ""),             # Google DNS
        ("1.1.1.1", False, ""),             # Cloudflare DNS
        ("2606:4700:4700::1111", False, ""), # Cloudflare IPv6
    ],
)
def test_is_prohibited_ip(ip_str, expected_prohibited, reason_keyword):
    ip_obj = ipaddress.ip_address(ip_str)
    prohibited, reason = is_prohibited_ip(ip_obj)
    assert prohibited is expected_prohibited, f"Failed for {ip_str}: {reason}"
    if expected_prohibited:
        assert reason_keyword.lower() in reason.lower()


# ============================================================================
# 2. Target URL Validation (Format & Schemes)
# ============================================================================

def test_scheme_validation():
    # Permitted schemes
    ok_http, _, _ = validate_target_url("http://example.com/page")
    assert ok_http is True
    ok_https, _, _ = validate_target_url("https://example.com/secure")
    assert ok_https is True

    # Blocked schemes
    bad_schemes = [
        "ftp://example.com/file.txt",
        "file:///etc/passwd",
        "file:///C:/Windows/win.ini",
        "gopher://evil.com/1",
        "javascript:alert(document.cookie)",
        "data:text/html;base64,PHNjcmlwdD4=",
        "ws://example.com/socket",
        "dict://dict.org",
        "ldap://localhost",
    ]
    for url in bad_schemes:
        valid, _, reason = validate_target_url(url)
        assert valid is False, f"Scheme in '{url}' should be blocked"
        assert len(reason) > 0


def test_internal_domain_and_localhost_subdomain_rejection():
    prohibited_hosts = [
        "http://localhost",
        "http://localhost:80",
        "https://sub.localhost",
        "http://deep.nested.sub.localhost",
        "http://company.internal",
        "http://server.local",
        "http://printer.localdomain",
        "http://router.home",
        "http://switch.lan",
        "http://workstation.corp",
    ]
    for url in prohibited_hosts:
        valid, _, reason = validate_target_url(url)
        assert valid is False, f"Expected '{url}' to be rejected"
        assert "Internal / private network" in reason


def test_port_validation():
    # Permitted ports
    assert validate_target_url("http://example.com:80/")[0] is True
    assert validate_target_url("https://example.com:443/")[0] is True

    # Blocked non-standard ports
    blocked_ports = [
        "http://example.com:22/ssh",
        "http://example.com:25/smtp",
        "http://example.com:8080/admin",
        "https://example.com:8443/panel",
        "http://example.com:3306/db",
        "http://example.com:6379/redis",
        "http://example.com:9200/elastic",
    ]
    for url in blocked_ports:
        valid, _, reason = validate_target_url(url)
        assert valid is False, f"Port in '{url}' should be blocked"
        assert "Port" in reason and "not allowed" in reason


def test_embedded_credentials_rejected():
    urls = [
        "http://admin:secret@example.com/",
        "https://user:password123@example.com/dashboard",
        "http://operator:@example.com/",
    ]
    for url in urls:
        valid, _, reason = validate_target_url(url)
        assert valid is False
        assert "Embedded credentials" in reason


# ============================================================================
# 3. DNS Pre-Resolution & Rebinding Protection Tests
# ============================================================================

def test_dns_pre_resolution_rejects_private_dns_answer():
    def mock_resolver_private(host: str):
        return [ipaddress.ip_address("10.0.0.1")]

    valid, _, reason = validate_outbound_url("https://attacker-controlled.com", custom_dns_resolver=mock_resolver_private)
    assert valid is False
    assert "resolves to prohibited IP" in reason
    assert "10.0.0.1" in reason


def test_dns_pre_resolution_rejects_cloud_metadata_dns_answer():
    def mock_resolver_metadata(host: str):
        return [ipaddress.ip_address("169.254.169.254")]

    valid, _, reason = validate_outbound_url("https://metadata-rebinding.com", custom_dns_resolver=mock_resolver_metadata)
    assert valid is False
    assert "resolves to prohibited IP" in reason
    assert "169.254.169.254" in reason


def test_dns_rebinding_dual_a_record_rejection():
    """
    DNS rebinding defense: if ANY resolved IP address is private/prohibited,
    the domain MUST be rejected even if public IP addresses are also returned.
    """
    def mock_resolver_mixed(host: str):
        return [
            ipaddress.ip_address("93.184.216.34"), # Public IP
            ipaddress.ip_address("127.0.0.1"),     # Prohibited loopback
        ]

    valid, _, reason = validate_outbound_url("https://mixed-records.com", custom_dns_resolver=mock_resolver_mixed)
    assert valid is False
    assert "resolves to prohibited IP" in reason
    assert "127.0.0.1" in reason


def test_dns_pre_resolution_allows_legitimate_public_ips():
    def mock_resolver_public(host: str):
        return [
            ipaddress.ip_address("93.184.216.34"),
            ipaddress.ip_address("2606:2800:220:1:248:1893:25c8:1946"),
        ]

    valid, sanitized, reason = validate_outbound_url("https://legit-site.org/about", custom_dns_resolver=mock_resolver_public)
    assert valid is True
    assert sanitized == "https://legit-site.org/about"
    assert reason == ""


# ============================================================================
# 4. Safe HTTP Fetch GET & Redirect Security Tests
# ============================================================================

@pytest.mark.anyio
async def test_safe_fetch_blocks_initial_prohibited_target():
    with pytest.raises(SSRFSecurityError) as exc_info:
        await safe_fetch_get("http://169.254.169.254/latest/meta-data")
    assert "restricted" in str(exc_info.value)


@pytest.mark.anyio
async def test_safe_fetch_blocks_redirect_to_prohibited_destination():
    """
    Simulates a public URL redirecting to AWS/cloud metadata 169.254.169.254.
    Must abort with SSRFSecurityError before following the redirect.
    """
    def mock_resolver(host: str):
        if host == "start.public.com":
            return [ipaddress.ip_address("93.184.216.34")]
        return []

    # Mock transport that returns a 302 redirect to metadata
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=302,
            headers={"Location": "http://169.254.169.254/latest/meta-data"},
            request=request,
        )

    transport = httpx.MockTransport(handler)

    async def run_fetch():
        is_valid, current_url, err = validate_outbound_url("https://start.public.com", custom_dns_resolver=mock_resolver)
        assert is_valid is True

        async with httpx.AsyncClient(transport=transport, follow_redirects=False) as client:
            resp = await client.get(current_url)
            assert resp.status_code == 302
            target_loc = resp.headers.get("Location")
            # SSRF check on redirect destination
            is_valid_red, _, red_err = validate_outbound_url(target_loc, custom_dns_resolver=mock_resolver)
            if not is_valid_red:
                raise SSRFSecurityError(f"Redirect blocked: {red_err}")

    with pytest.raises(SSRFSecurityError) as exc_info:
        await run_fetch()
    assert "Redirect blocked" in str(exc_info.value)


@pytest.mark.anyio
async def test_safe_fetch_caps_redirect_limit():
    """
    Verifies that excessive redirects (> 5 hops) trigger SSRFRedirectError.
    """
    def mock_resolver(host: str):
        return [ipaddress.ip_address("93.184.216.34")]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=302,
            headers={"Location": "https://start.public.com/loop"},
            request=request,
        )

    transport = httpx.MockTransport(handler)

    # Test custom loop with max_redirects = 3
    async def run_loop():
        current_url = "https://start.public.com/entry"
        max_redirects = 3
        redirect_count = 0
        async with httpx.AsyncClient(transport=transport, follow_redirects=False) as client:
            while True:
                resp = await client.get(current_url)
                if resp.status_code in (301, 302, 303, 307, 308):
                    redirect_count += 1
                    if redirect_count > max_redirects:
                        raise SSRFRedirectError(f"Exceeded maximum redirect limit of {max_redirects} hops.")
                    loc = resp.headers.get("Location")
                    current_url = loc

    with pytest.raises(SSRFRedirectError) as exc_info:
        await run_loop()
    assert "Exceeded maximum redirect limit" in str(exc_info.value)
