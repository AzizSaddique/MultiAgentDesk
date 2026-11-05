"""
AgentDesk Centralized SSRF & URL Safety Validation Service.
Enforces strict protocol, port, hostname, and multi-record DNS safety controls.
Protects against:
- Private, loopback, link-local, multicast, and reserved IPv4/IPv6 address spaces.
- Cloud metadata services (e.g. 169.254.169.254).
- IPv4-mapped IPv6 address manipulation.
- DNS rebinding and mixed public/private DNS responses.
- Redirect-based SSRF hops.
- Embedded URL credentials and non-standard network ports.
"""
import re
import socket
import ipaddress
import urllib.parse
from typing import Tuple, List, Optional, Callable, Dict, Any, Union
import httpx

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

    # 3. Hostname extraction & checks
    raw_host = parsed.hostname
    if not raw_host:
        return False, cleaned, "URL lacks a valid hostname."

    hostname_lower = raw_host.lower().strip("[]")

    # Reject localhost or internal domain names
    if hostname_lower == "localhost" or any(hostname_lower.endswith(suffix) for suffix in PROHIBITED_DOMAIN_SUFFIXES):
        return False, cleaned, "Internal / private network URLs are restricted."

    # 4. Check if hostname is an IP literal
    is_ip_literal = False
    try:
        ip_obj = ipaddress.ip_address(hostname_lower)
        is_ip_literal = True
    except ValueError:
        is_ip_literal = False

    if is_ip_literal:
        prohibited, reason = is_prohibited_ip(ip_obj)
        if prohibited:
            return False, cleaned, f"Internal / private network URLs are restricted: {reason}"

    # 5. Port validation
    if parsed.port is not None and parsed.port not in PERMITTED_PORTS:
        return (
            False,
            cleaned,
            f"Port {parsed.port} is not allowed. Only standard HTTP/HTTPS ports (80, 443) are permitted."
        )

    if is_ip_literal:
        return True, cleaned, ""

    # 6. Optional DNS resolution check (or explicit outbound validation)
    if resolve_dns:
        try:
            resolved_ips = resolve_domain_ips(hostname_lower, custom_resolver=custom_dns_resolver)
            if not resolved_ips:
                return False, cleaned, f"DNS resolution returned no IP addresses for hostname '{hostname_lower}'."

            for res_ip in resolved_ips:
                prohibited, reason = is_prohibited_ip(res_ip)
                if prohibited:
                    return (
                        False,
                        cleaned,
                        f"Internal / private network URLs are restricted: domain '{hostname_lower}' resolves to prohibited IP '{res_ip}' ({reason})"
                    )
        except Exception as dns_err:
            return False, cleaned, f"DNS resolution failed for hostname '{hostname_lower}': {dns_err}"

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


async def safe_fetch_get(
    url: str,
    headers: Optional[Dict[str, str]] = None,
    timeout: float = 6.0,
    max_redirects: int = 5,
    custom_dns_resolver: Optional[Callable] = None,
) -> httpx.Response:
    """
    Executes a secure HTTP GET request with manual redirect following and revalidation.
    Guarantees that:
    1. Initial target URL is verified via validate_outbound_url (DNS pre-resolution).
    2. Every 3xx redirect destination is re-validated before following.
    3. Maximum redirect hops are capped at max_redirects (default: 5).
    4. Prohibited private network redirect destinations abort execution immediately.
    """
    is_valid, current_url, err_msg = validate_outbound_url(url, custom_dns_resolver=custom_dns_resolver)
    if not is_valid:
        raise SSRFSecurityError(f"Target URL '{url}' is restricted: {err_msg}")

    redirect_count = 0
    req_headers = dict(headers or {})

    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
        while True:
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
