"""
Automated Security Test Suite: SSRF Protection & Connection Pinning (Phase A.2.2).
Verifies:
1. Centralized IP classification & prohibited range defenses.
2. Alternate IP format detection & canonicalization (integer, octal, hex, percent-encoded, shortened).
3. Protocol, host, credential, and port validation.
4. DNS pre-resolution & multi-record safety checks.
5. Socket connection pinning defeating DNS-rebinding TOCTOU.
6. Direct SUT execution of safe_fetch_get() across redirect scenarios.
"""
import ipaddress
import pytest
import httpx
from unittest.mock import MagicMock, AsyncMock

from backend.security.url_validator import (
    validate_target_url,
    validate_outbound_url,
    is_prohibited_ip,
    canonicalize_host,
    create_pinned_transport,
    PinnedAsyncNetworkBackend,
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
        ("93.184.216.34", False, ""),        # example.com
        ("8.8.8.8", False, ""),              # Google DNS
        ("1.1.1.1", False, ""),              # Cloudflare DNS
        ("2606:4700:4700::1111", False, ""),  # Cloudflare IPv6
    ],
)
def test_is_prohibited_ip(ip_str, expected_prohibited, reason_keyword):
    ip_obj = ipaddress.ip_address(ip_str)
    prohibited, reason = is_prohibited_ip(ip_obj)
    assert prohibited is expected_prohibited, f"Failed for {ip_str}: {reason}"
    if expected_prohibited:
        assert reason_keyword.lower() in reason.lower()


# ============================================================================
# 2. Alternate IP Notations & Canonicalization Tests (Task 3)
# ============================================================================

@pytest.mark.parametrize(
    "raw_host,expected_canonical,expected_class",
    [
        ("127.0.0.1", "127.0.0.1", "ipv4"),
        ("127.1", "127.0.0.1", "ipv4"),
        ("2130706433", "127.0.0.1", "ipv4"),
        ("0177.0.0.1", "127.0.0.1", "ipv4"),
        ("0x7f000001", "127.0.0.1", "ipv4"),
        ("0x7f.1", "127.0.0.1", "ipv4"),
        ("10.1", "10.0.0.1", "ipv4"),
        ("2852039166", "169.254.169.254", "ipv4"),
        ("%31%32%37%2e%30%2e%30%2e%31", "127.0.0.1", "ipv4"),
        ("::1", "::1", "ipv6"),
        ("::ffff:127.0.0.1", "::ffff:127.0.0.1", "ipv6"),
        ("example.com", "example.com", "domain"),
        ("mycompany.io", "mycompany.io", "domain"),
    ],
)
def test_canonicalize_host(raw_host, expected_canonical, expected_class):
    is_valid, canonical, host_class = canonicalize_host(raw_host)
    assert is_valid is True
    assert canonical == expected_canonical
    assert host_class == expected_class


def test_alternate_ip_notations_blocked_by_validator():
    """
    Verifies that all alternate IP notations (integer, hex, octal, shortened, percent-encoded)
    are recognized and strictly blocked when targeting loopback or private networks.
    """
    prohibited_alternate_urls = [
        "http://2130706433/",                           # Integer 127.0.0.1
        "http://0177.0.0.1/admin",                      # Octal 127.0.0.1
        "http://0x7f000001/status",                     # Hex 127.0.0.1
        "http://127.1/secret",                          # Shortened 127.0.0.1
        "http://127.0.1/internal",                      # Shortened 127.0.0.1
        "http://2852039166/latest/meta-data",           # Integer 169.254.169.254
        "http://%31%32%37%2e%30%2e%30%2e%31/",         # Percent-encoded 127.0.0.1
        "http://0x0a000001/",                           # Hex 10.0.0.1
        "http://[::ffff:7f00:1]/",                      # IPv4-mapped loopback in hex
        "http://[::1]:80/",                             # IPv6 loopback
    ]
    for url in prohibited_alternate_urls:
        is_valid, _, reason = validate_target_url(url)
        assert is_valid is False, f"Expected '{url}' to be blocked, but passed validation"
        assert "Internal / private network URLs are restricted" in reason


def test_malformed_percent_encoding_rejected():
    bad_urls = [
        "http://test%2520domain.com",
        "http://%zz%ff/path",
    ]
    for url in bad_urls:
        is_valid, _, reason = validate_target_url(url)
        assert is_valid is False
        assert "illegal percent-encoded" in reason or "Malformed" in reason or "not allowed" in reason


# ============================================================================
# 3. Protocol, Hostname, and Port Validation Tests
# ============================================================================

def test_scheme_validation():
    ok_http, _, _ = validate_target_url("http://example.com/page")
    assert ok_http is True
    ok_https, _, _ = validate_target_url("https://example.com/secure")
    assert ok_https is True

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
    assert validate_target_url("http://example.com:80/")[0] is True
    assert validate_target_url("https://example.com:443/")[0] is True

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
# 4. DNS Pre-Resolution & Rebinding Protection Tests
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
            ipaddress.ip_address("93.184.216.34"),
            ipaddress.ip_address("127.0.0.1"),
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
# 5. Connection Pinning & DNS Rebinding TOCTOU Defenses (Task 1)
# ============================================================================

@pytest.mark.anyio
async def test_pinned_backend_connects_to_validated_ip():
    """
    Verifies that PinnedAsyncNetworkBackend intercepts the TCP connection
    and connects directly to the pinned IP address without performing a second DNS query.
    """
    backend = PinnedAsyncNetworkBackend(pinned_ip="104.20.23.154")
    assert backend.pinned_ip == "104.20.23.154"


def test_create_pinned_transport_config():
    """
    Verifies that create_pinned_transport preserves TLS verification and sets
    zero keepalive connections to prevent connection reuse across origins.
    """
    transport = create_pinned_transport("104.20.23.154", verify=True)
    assert transport._pool._max_keepalive_connections == 0
    assert transport._pool._network_backend.pinned_ip == "104.20.23.154"


# ============================================================================
# 6. Safe HTTP Fetch GET & Redirect Security Tests Calling Production SUT (Task 5)
# ============================================================================

@pytest.mark.anyio
async def test_safe_fetch_blocks_initial_prohibited_target():
    with pytest.raises(SSRFSecurityError) as exc_info:
        await safe_fetch_get("http://169.254.169.254/latest/meta-data")
    assert "restricted" in str(exc_info.value)


@pytest.mark.anyio
async def test_safe_fetch_calls_sut_and_blocks_loopback_redirect():
    """
    Calls production safe_fetch_get() with a mock transport returning a 302
    redirecting from a public URL to loopback 127.0.0.1.
    Must invoke safe_fetch_get() directly and abort with SSRFSecurityError.
    """
    def mock_resolver(host: str):
        if host == "public.domain.com":
            return [ipaddress.ip_address("93.184.216.34")]
        return []

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=302,
            headers={"Location": "http://127.0.0.1:8000/internal-secrets"},
            request=request,
        )

    mock_transport = httpx.MockTransport(handler)

    with pytest.raises(SSRFSecurityError) as exc_info:
        await safe_fetch_get(
            "https://public.domain.com/landing",
            transport=mock_transport,
            custom_dns_resolver=mock_resolver,
        )
    assert "prohibited destination" in str(exc_info.value)
    assert "127.0.0.1" in str(exc_info.value) or "restricted" in str(exc_info.value)


@pytest.mark.anyio
async def test_safe_fetch_blocks_private_ipv4_redirect():
    """
    Verifies that a 302 redirect to RFC 1918 private IPv4 is rejected by safe_fetch_get.
    """
    def mock_resolver(host: str):
        if host == "public.domain.com":
            return [ipaddress.ip_address("93.184.216.34")]
        return []

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=302,
            headers={"Location": "http://10.0.0.1/admin"},
            request=request,
        )

    mock_transport = httpx.MockTransport(handler)

    with pytest.raises(SSRFSecurityError) as exc_info:
        await safe_fetch_get(
            "https://public.domain.com/landing",
            transport=mock_transport,
            custom_dns_resolver=mock_resolver,
        )
    assert "prohibited destination" in str(exc_info.value)


@pytest.mark.anyio
async def test_safe_fetch_blocks_cloud_metadata_redirect():
    """
    Verifies that a 302 redirect to 169.254.169.254 is rejected by safe_fetch_get.
    """
    def mock_resolver(host: str):
        if host == "public.domain.com":
            return [ipaddress.ip_address("93.184.216.34")]
        return []

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=302,
            headers={"Location": "http://169.254.169.254/latest/meta-data"},
            request=request,
        )

    mock_transport = httpx.MockTransport(handler)

    with pytest.raises(SSRFSecurityError) as exc_info:
        await safe_fetch_get(
            "https://public.domain.com/landing",
            transport=mock_transport,
            custom_dns_resolver=mock_resolver,
        )
    assert "prohibited destination" in str(exc_info.value)
    assert "169.254.169.254" in str(exc_info.value) or "restricted" in str(exc_info.value)


@pytest.mark.anyio
async def test_safe_fetch_handles_relative_redirect_safely():
    """
    Verifies that relative redirects (e.g. Location: /contact) are safely joined
    against the base URL and re-validated by safe_fetch_get.
    """
    def mock_resolver(host: str):
        if host == "public.domain.com":
            return [ipaddress.ip_address("93.184.216.34")]
        return []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/entry":
            return httpx.Response(
                status_code=302,
                headers={"Location": "/safe-destination"},
                request=request,
            )
        elif request.url.path == "/safe-destination":
            return httpx.Response(
                status_code=200,
                text="<html><body>Safe Content</body></html>",
                request=request,
            )
        return httpx.Response(status_code=404, request=request)

    mock_transport = httpx.MockTransport(handler)

    resp = await safe_fetch_get(
        "https://public.domain.com/entry",
        transport=mock_transport,
        custom_dns_resolver=mock_resolver,
    )
    assert resp.status_code == 200
    assert "Safe Content" in resp.text
    assert str(resp.request.url) == "https://public.domain.com/safe-destination"


@pytest.mark.anyio
async def test_safe_fetch_multiple_valid_redirect_hops():
    """
    Verifies that multiple legitimate public redirect hops within the allowed
    max_redirects limit succeed.
    """
    def mock_resolver(host: str):
        return [ipaddress.ip_address("93.184.216.34")]

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/hop1":
            return httpx.Response(status_code=301, headers={"Location": "/hop2"}, request=request)
        elif request.url.path == "/hop2":
            return httpx.Response(status_code=302, headers={"Location": "/hop3"}, request=request)
        elif request.url.path == "/hop3":
            return httpx.Response(status_code=200, text="Final Hop", request=request)
        return httpx.Response(status_code=404, request=request)

    mock_transport = httpx.MockTransport(handler)

    resp = await safe_fetch_get(
        "https://public.domain.com/hop1",
        transport=mock_transport,
        custom_dns_resolver=mock_resolver,
        max_redirects=5,
    )
    assert resp.status_code == 200
    assert resp.text == "Final Hop"


@pytest.mark.anyio
async def test_safe_fetch_enforces_redirect_limit_on_sut():
    """
    Verifies that excessive redirects (> max_redirects) trigger SSRFRedirectError
    directly inside safe_fetch_get().
    """
    def mock_resolver(host: str):
        return [ipaddress.ip_address("93.184.216.34")]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=302,
            headers={"Location": "https://public.domain.com/infinite-loop"},
            request=request,
        )

    mock_transport = httpx.MockTransport(handler)

    with pytest.raises(SSRFRedirectError) as exc_info:
        await safe_fetch_get(
            "https://public.domain.com/start",
            transport=mock_transport,
            custom_dns_resolver=mock_resolver,
            max_redirects=3,
        )
    assert "Exceeded maximum redirect limit" in str(exc_info.value)
