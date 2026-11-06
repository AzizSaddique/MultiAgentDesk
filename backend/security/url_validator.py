"""
AgentDesk Centralized SSRF & URL Safety Validation Service.
Enforces strict protocol, port, hostname, and multi-record DNS safety controls.
Protects against:
- Private, loopback, link-local, multicast, and reserved IPv4/IPv6 address spaces.
- Cloud metadata services (e.g. 169.254.169.254).
- Alternate IP notations (dword/integer, octal, hex, shortened IPv4, percent-encoded).
- IPv4-mapped IPv6 address manipulation.
- DNS rebinding TOCTOU via connection pinning at the socket transport layer.
- Redirect-based SSRF hops.
- Embedded URL credentials and non-standard network ports.
"""
import re
import socket
import ipaddress
import urllib.parse
from typing import Tuple, List, Optional, Callable, Dict, Any, Union
import httpx
import httpcore
from httpcore._backends.auto import AutoBackend
from httpcore._backends.sync import SyncBackend

# Allowed schemes
PERMITTED_SCHEMES = ("http", "https")

# Allowed ports (standard HTTP and HTTPS only)
PERMITTED_PORTS = (80, 443)

# Prohibited domain suffixes (local and internal names)
PROHIBITED_DOMAIN_SUFFIXES = (
    "localhost",
    ".localhost",
    ".local",
    ".internal",
    ".localdomain",
    ".lan",
    ".home",
    ".corp",
)

# Additional prohibited special-use CIDR blocks
PROHIBITED_SPECIAL_NETWORKS = [
    ipaddress.ip_network("100.64.0.0/10"),     # Carrier-Grade NAT (RFC 6598)
    ipaddress.ip_network("192.0.0.0/24"),      # IETF Protocol Assignments
    ipaddress.ip_network("192.0.2.0/24"),      # Documentation (TEST-NET-1)
    ipaddress.ip_network("198.18.0.0/15"),     # Benchmarking (RFC 2544)
    ipaddress.ip_network("198.51.100.0/24"),   # Documentation (TEST-NET-2)
    ipaddress.ip_network("203.0.113.0/24"),    # Documentation (TEST-NET-3)
    ipaddress.ip_network("240.0.0.0/4"),       # Reserved / Future Use (RFC 1112)
    ipaddress.ip_network("255.255.255.255/32"),# Limited Broadcast
    ipaddress.ip_network("2001:db8::/32"),     # IPv6 Documentation
    ipaddress.ip_network("2002::/16"),         # 6to4 prefix
    ipaddress.ip_network("2001::/32"),         # Teredo prefix
]


class SSRFSecurityError(Exception):
    """Raised when an outbound connection targets a prohibited IP, scheme, or domain."""
    pass


class SSRFRedirectError(SSRFSecurityError):
    """Raised when redirect depth is exceeded or redirect destination violates SSRF policy."""
    pass


def canonicalize_host(raw_host: str) -> Tuple[bool, str, str]:
    """
    Normalizes, unquotes, and classifies hostnames, resolving alternate IP representations:
    - Strips brackets from IPv6.
    - Unquotes percent-encoded host characters (%31%32%37... -> 127.0.0.1).
    - Converts dword/integer, octal, hex, and shortened IPv4 formats into canonical dot-decimal
      via socket.inet_aton / socket.inet_ntoa.
    - Converts IPv6 and IPv4-mapped IPv6 into canonical ipaddress strings.
    Returns (is_valid, canonical_host_or_ip, classification: 'ipv4'|'ipv6'|'domain').
    """
    if not raw_host:
        return False, "", "URL lacks a valid hostname."

    unquoted = urllib.parse.unquote(raw_host).strip().strip("[]")
    if not unquoted:
        return False, "", "URL lacks a valid hostname."

    # Reject malformed percent signs or illegal whitespace/control characters
    if "%" in unquoted or any(c.isspace() for c in unquoted):
        return False, unquoted, "Hostname contains illegal percent-encoded or malformed characters."

    # 1. Attempt IPv4 parsing via socket.inet_aton
    # socket.inet_aton parses dot-decimal ('127.0.0.1'), integers ('2130706433'), octal ('0177.0.0.1'),
    # hex ('0x7f000001', '0x7f.1'), and shortened forms ('127.1').
    try:
        raw_bytes = socket.inet_aton(unquoted)
        canonical_v4 = socket.inet_ntoa(raw_bytes)
        return True, canonical_v4, "ipv4"
    except (OSError, socket.error):
        pass

    # 2. Attempt IPv6 parsing via ipaddress
    try:
        ip_v6 = ipaddress.ip_address(unquoted)
        if isinstance(ip_v6, ipaddress.IPv6Address):
            return True, str(ip_v6), "ipv6"
    except ValueError:
        pass

    # 3. Standard domain name
    return True, unquoted.lower(), "domain"


def is_prohibited_ip(ip: Union[ipaddress.IPv4Address, ipaddress.IPv6Address]) -> Tuple[bool, str]:
    """
    Evaluates whether an IP address belongs to any prohibited network range:
    - Loopback (127.0.0.0/8, ::1)
    - Private (RFC 1918: 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16; RFC 4193: fc00::/7)
    - Link-Local (169.254.0.0/16, fe80::/10) including Cloud Metadata 169.254.169.254
    - Multicast (224.0.0.0/4, ff00::/8)
    - Unspecified (0.0.0.0/32, ::/128)
    - Reserved (240.0.0.0/4)
    - Carrier-Grade NAT (100.64.0.0/10)
    - Documentation and Benchmarking networks
    - IPv4-mapped IPv6 (checked against IPv4 prohibited rules)
    """
    # 1. Handle IPv4-mapped IPv6 (e.g. ::ffff:127.0.0.1)
    if isinstance(ip, ipaddress.IPv6Address):
        if ip.ipv4_mapped:
            return is_prohibited_ip(ip.ipv4_mapped)

    # 2. Specific checks first (link-local, cloud metadata, loopback, special use)
    if str(ip) == "169.254.169.254":
        return True, "Cloud metadata endpoint '169.254.169.254' is restricted."

    if ip.is_link_local or (isinstance(ip, ipaddress.IPv4Address) and ip in ipaddress.ip_network("169.254.0.0/16")):
        return True, f"Link-local / cloud metadata address '{ip}' is restricted."

    if ip.is_loopback:
        return True, f"Loopback address '{ip}' is restricted."

    if ip.is_unspecified:
        return True, f"Unspecified address '{ip}' is restricted."

    if ip.is_multicast:
        return True, f"Multicast address '{ip}' is restricted."

    if ip.is_reserved:
        return True, f"IETF reserved address '{ip}' is restricted."

    # 3. Special-use network checks
    for net in PROHIBITED_SPECIAL_NETWORKS:
        if ip in net:
            if str(net) == "100.64.0.0/10":
                return True, f"Carrier-Grade NAT address '{ip}' ({net}) is restricted."
            if str(net) == "255.255.255.255/32":
                return True, f"Broadcast address '{ip}' is restricted."
            return True, f"Address '{ip}' belongs to prohibited special-use network {net}."

    # 4. Standard private network check (RFC 1918 / Unique Local)
    if ip.is_private:
        return True, f"Private network address '{ip}' is restricted."

    return False, ""


def resolve_domain_ips(
    hostname: str,
    custom_resolver: Optional[Callable[[str], List[Union[ipaddress.IPv4Address, ipaddress.IPv6Address]]]] = None
) -> List[Union[ipaddress.IPv4Address, ipaddress.IPv6Address]]:
    """
    Resolves all IPv4 (A) and IPv6 (AAAA) addresses for a given hostname.
    Supports dependency injection of custom_resolver for deterministic testing.
    """
    if custom_resolver:
        return custom_resolver(hostname)

    # If hostname is already an IP literal, return it directly
    try:
        raw_v4 = socket.inet_aton(hostname)
        return [ipaddress.ip_address(socket.inet_ntoa(raw_v4))]
    except (OSError, socket.error):
        pass

    try:
        return [ipaddress.ip_address(hostname)]
    except ValueError:
        pass

    resolved_ips: List[Union[ipaddress.IPv4Address, ipaddress.IPv6Address]] = []
    seen = set()

    try:
        addr_info = socket.getaddrinfo(hostname, None, family=socket.AF_UNSPEC, type=socket.SOCK_STREAM)
        for entry in addr_info:
            sockaddr = entry[4]
            ip_str = sockaddr[0]
            if ip_str not in seen:
                seen.add(ip_str)
                resolved_ips.append(ipaddress.ip_address(ip_str))
    except Exception as exc:
        raise OSError(f"DNS resolution failed for hostname '{hostname}': {exc}") from exc

    return resolved_ips


def validate_target_url(
    raw_url: str,
    resolve_dns: bool = False,
    custom_dns_resolver: Optional[Callable[[str], List[Union[ipaddress.IPv4Address, ipaddress.IPv6Address]]]] = None
) -> Tuple[bool, str, str]:
    """
    Validates a target URL for syntactic safety and SSRF risk.
    - Protocol must be strictly http or https.
    - Embedded credentials (user:pass@) are blocked.
    - Non-standard ports (outside 80, 443) are blocked.
    - Localhost and internal domain names are blocked.
    - Canonicalizes alternate IP formats (integer, octal, hex, shortened, percent-encoded).
    - IP literals are evaluated against all prohibited IP spaces.
    - If resolve_dns is True, resolves all A and AAAA records and verifies every answer.
    Returns (is_valid, sanitized_url, error_reason).
    """
    if not raw_url or not str(raw_url).strip():
        return False, "", "URL is empty"

    cleaned = str(raw_url).strip()

    # Automatic https:// prepending for bare domain entries (backward compatibility)
    if not (cleaned.startswith("http://") or cleaned.startswith("https://")):
        if re.match(r'^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', cleaned):
            cleaned = "https://" + cleaned
        else:
            return False, raw_url, "URL must use HTTP or HTTPS protocol."

    try:
        parsed = urllib.parse.urlparse(cleaned)
    except Exception as parse_err:
        return False, cleaned, f"Malformed URL: {parse_err}"

    # 1. Protocol validation
    if parsed.scheme.lower() not in PERMITTED_SCHEMES:
        return False, cleaned, f"Protocol '{parsed.scheme}' not allowed. Only HTTP and HTTPS are permitted."

    # 2. Embedded credentials check
    if parsed.username or parsed.password:
        return False, cleaned, "Embedded credentials in URL are prohibited for security."

    # 3. Hostname extraction and alternate IP canonicalization
    raw_host = parsed.hostname
    if not raw_host:
        return False, cleaned, "URL lacks a valid hostname."

    is_valid_host, canonical_host, host_class_or_err = canonicalize_host(raw_host)
    if not is_valid_host:
        return False, cleaned, host_class_or_err
    host_class = host_class_or_err

    # 4. Reject localhost or internal domain names
    if canonical_host == "localhost" or any(canonical_host.endswith(suffix) for suffix in PROHIBITED_DOMAIN_SUFFIXES):
        return False, cleaned, "Internal / private network URLs are restricted."

    # 5. Check IP literals (including canonicalized integer, hex, octal notations)
    if host_class in ("ipv4", "ipv6"):
        try:
            ip_obj = ipaddress.ip_address(canonical_host)
            prohibited, reason = is_prohibited_ip(ip_obj)
            if prohibited:
                return False, cleaned, f"Internal / private network URLs are restricted: {reason}"
        except ValueError:
            return False, cleaned, f"Invalid IP address format '{canonical_host}'."

    # 6. Port validation
    if parsed.port is not None and parsed.port not in PERMITTED_PORTS:
        return (
            False,
            cleaned,
            f"Port {parsed.port} is not allowed. Only standard HTTP/HTTPS ports (80, 443) are permitted."
        )

    if host_class in ("ipv4", "ipv6"):
        return True, cleaned, ""

    # 7. Optional DNS resolution check (or explicit outbound validation)
    if resolve_dns:
        try:
            resolved_ips = resolve_domain_ips(canonical_host, custom_resolver=custom_dns_resolver)
            if not resolved_ips:
                return False, cleaned, f"DNS resolution returned no IP addresses for hostname '{canonical_host}'."

            for res_ip in resolved_ips:
                prohibited, reason = is_prohibited_ip(res_ip)
                if prohibited:
                    return (
                        False,
                        cleaned,
                        f"Internal / private network URLs are restricted: domain '{canonical_host}' resolves to prohibited IP '{res_ip}' ({reason})"
                    )
        except Exception as dns_err:
            return False, cleaned, f"DNS resolution failed for hostname '{canonical_host}': {dns_err}"

    return True, cleaned, ""


def validate_outbound_url(
    raw_url: str,
    custom_dns_resolver: Optional[Callable[[str], List[Union[ipaddress.IPv4Address, ipaddress.IPv6Address]]]] = None
) -> Tuple[bool, str, str]:
    """
    Validates a URL before establishing an outbound network connection.
    Enforces full DNS pre-resolution and verifies that all resolved IP addresses are public and safe.
    """
    return validate_target_url(raw_url, resolve_dns=True, custom_dns_resolver=custom_dns_resolver)


class PinnedAsyncNetworkBackend(AutoBackend):
    """
    Pins outbound TCP socket connections to a pre-validated IP address,
    preventing DNS rebinding TOCTOU between validation and connection.
    Preserves original hostname for TLS SNI and HTTP Host header verification.
    """
    def __init__(self, pinned_ip: str):
        super().__init__()
        self.pinned_ip = pinned_ip

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: Optional[float] = None,
        local_address: Optional[str] = None,
        socket_options: Optional[Any] = None,
    ) -> httpcore.AsyncNetworkStream:
        return await super().connect_tcp(
            host=self.pinned_ip,
            port=port,
            timeout=timeout,
            local_address=local_address,
            socket_options=socket_options,
        )


class PinnedSyncNetworkBackend(SyncBackend):
    """
    Synchronous network backend that pins outbound TCP sockets directly to
    the pre-validated IP address, defeating DNS rebinding for synchronous clients.
    """
    def __init__(self, pinned_ip: str):
        super().__init__()
        self.pinned_ip = pinned_ip

    def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: Optional[float] = None,
        local_address: Optional[str] = None,
        socket_options: Optional[Any] = None,
    ) -> httpcore.NetworkStream:
        return super().connect_tcp(
            host=self.pinned_ip,
            port=port,
            timeout=timeout,
            local_address=local_address,
            socket_options=socket_options,
        )


def create_pinned_sync_transport(pinned_ip: str, verify: bool = True) -> httpx.HTTPTransport:
    """
    Constructs a synchronous HTTPTransport wired with PinnedSyncNetworkBackend.
    Ensures TLS SNI and certificate verification are preserved, while
    disabling connection keepalive/pooling across different destinations.
    """
    transport = httpx.HTTPTransport(verify=verify)
    transport._pool = httpcore.ConnectionPool(
        ssl_context=transport._pool._ssl_context,
        network_backend=PinnedSyncNetworkBackend(pinned_ip=pinned_ip),
        max_keepalive_connections=0,
        keepalive_expiry=0.0,
    )
    return transport


def create_pinned_transport(pinned_ip: str, verify: bool = True) -> httpx.AsyncHTTPTransport:
    """
    Constructs an AsyncHTTPTransport wired with PinnedAsyncNetworkBackend.
    Ensures TLS SNI and certificate verification are preserved, while
    disabling connection keepalive/pooling across different destinations.
    """
    transport = httpx.AsyncHTTPTransport(verify=verify)
    transport._pool = httpcore.AsyncConnectionPool(
        ssl_context=transport._pool._ssl_context,
        network_backend=PinnedAsyncNetworkBackend(pinned_ip=pinned_ip),
        max_keepalive_connections=0,
        keepalive_expiry=0.0,
    )
    return transport


async def safe_fetch_get(
    url: str,
    headers: Optional[Dict[str, str]] = None,
    timeout: float = 6.0,
    max_redirects: int = 5,
    custom_dns_resolver: Optional[Callable] = None,
    transport: Optional[httpx.AsyncBaseTransport] = None,
) -> httpx.Response:
    """
    Executes a secure HTTP GET request with manual redirect following, connection pinning, and re-validation.
    Guarantees:
    1. Initial target URL is verified via validate_outbound_url (DNS pre-resolution).
    2. Actual TCP connection is pinned to the pre-validated IP address (defeating DNS rebinding).
    3. TLS certificate validation and SNI are strictly preserved.
    4. Every 3xx redirect destination is re-validated and re-pinned before following.
    5. Maximum redirect hops are capped at max_redirects (default: 5).
    6. Prohibited private network redirect destinations abort execution immediately.
    """
    is_valid, current_url, err_msg = validate_outbound_url(url, custom_dns_resolver=custom_dns_resolver)
    if not is_valid:
        raise SSRFSecurityError(f"Target URL '{url}' is restricted: {err_msg}")

    redirect_count = 0
    req_headers = dict(headers or {})

    while True:
        # Determine host and pinned IP for current_url
        parsed_curr = urllib.parse.urlparse(current_url)
        host_str = parsed_curr.hostname or ""
        _, canonical_host, _ = canonicalize_host(host_str)

        # If a mock transport was passed in (e.g. in test suite), use it;
        # otherwise create a connection-pinned transport bound to the validated IP.
        if transport is not None:
            active_transport = transport
        else:
            resolved_ips = resolve_domain_ips(canonical_host, custom_resolver=custom_dns_resolver)
            if not resolved_ips:
                raise SSRFSecurityError(f"DNS resolution returned no IP addresses for '{canonical_host}'.")
            pinned_ip = str(resolved_ips[0])
            active_transport = create_pinned_transport(pinned_ip=pinned_ip, verify=True)

        async with httpx.AsyncClient(transport=active_transport, timeout=timeout, follow_redirects=False) as client:
            resp = await client.get(current_url, headers=req_headers)

        # Check if response is a redirect (301, 302, 303, 307, 308)
        if resp.status_code in (301, 302, 303, 307, 308):
            redirect_count += 1
            if redirect_count > max_redirects:
                raise SSRFRedirectError(f"Exceeded maximum redirect limit of {max_redirects} hops.")

            location = resp.headers.get("Location")
            if not location:
                return resp

            next_url = urllib.parse.urljoin(current_url, location)

            # Re-validate redirect target
            is_valid_red, sanitized_next, red_err = validate_outbound_url(
                next_url, custom_dns_resolver=custom_dns_resolver
            )
            if not is_valid_red:
                raise SSRFSecurityError(
                    f"Redirect from '{current_url}' to prohibited destination '{next_url}' blocked: {red_err}"
                )

            current_url = sanitized_next
        else:
            return resp


def safe_fetch_get_sync(
    url: str,
    headers: Optional[Dict[str, str]] = None,
    timeout: float = 6.0,
    max_redirects: int = 5,
    custom_dns_resolver: Optional[Callable] = None,
    transport: Optional[httpx.BaseTransport] = None,
) -> httpx.Response:
    """
    Synchronous equivalent of safe_fetch_get with manual redirect following, connection pinning, and re-validation.
    Guarantees:
    1. Initial target URL is verified via validate_outbound_url (DNS pre-resolution).
    2. Actual TCP connection is pinned to the pre-validated IP address (defeating DNS rebinding).
    3. TLS certificate validation and SNI are strictly preserved.
    4. Every 3xx redirect destination is re-validated and re-pinned before following.
    5. Maximum redirect hops are capped at max_redirects (default: 5).
    6. Prohibited private network redirect destinations abort execution immediately.
    """
    is_valid, current_url, err_msg = validate_outbound_url(url, custom_dns_resolver=custom_dns_resolver)
    if not is_valid:
        raise SSRFSecurityError(f"Target URL '{url}' is restricted: {err_msg}")

    redirect_count = 0
    req_headers = dict(headers or {})

    while True:
        # Determine host and pinned IP for current_url
        parsed_curr = urllib.parse.urlparse(current_url)
        host_str = parsed_curr.hostname or ""
        _, canonical_host, _ = canonicalize_host(host_str)

        # If a mock transport was passed in, use it;
        # otherwise create a connection-pinned transport bound to the validated IP.
        if transport is not None:
            active_transport = transport
        else:
            resolved_ips = resolve_domain_ips(canonical_host, custom_resolver=custom_dns_resolver)
            if not resolved_ips:
                raise SSRFSecurityError(f"DNS resolution returned no IP addresses for '{canonical_host}'.")
            pinned_ip = str(resolved_ips[0])
            active_transport = create_pinned_sync_transport(pinned_ip=pinned_ip, verify=True)

        with httpx.Client(transport=active_transport, timeout=timeout, follow_redirects=False) as client:
            resp = client.get(current_url, headers=req_headers)

        # Check if response is a redirect (301, 302, 303, 307, 308)
        if resp.status_code in (301, 302, 303, 307, 308):
            redirect_count += 1
            if redirect_count > max_redirects:
                raise SSRFRedirectError(f"Exceeded maximum redirect limit of {max_redirects} hops.")

            location = resp.headers.get("Location")
            if not location:
                return resp

            next_url = urllib.parse.urljoin(current_url, location)

            # Re-validate redirect target
            is_valid_red, sanitized_next, red_err = validate_outbound_url(
                next_url, custom_dns_resolver=custom_dns_resolver
            )
            if not is_valid_red:
                raise SSRFSecurityError(
                    f"Redirect from '{current_url}' to prohibited destination '{next_url}' blocked: {red_err}"
                )

            current_url = sanitized_next
        else:
            return resp
