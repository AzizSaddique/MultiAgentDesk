"""
AgentDesk Secure Local Forward Egress Proxy.
Provides strict socket-level egress isolation for Playwright Chromium and headless browser automation.

Guarantees:
1. Listens strictly on loopback (127.0.0.1) on an ephemeral port.
2. Enforces cryptographically strong Basic authentication (secrets.token_hex).
3. Pre-validates every HTTP request and HTTPS/WSS CONNECT tunnel via validate_outbound_url.
4. Pinning: Establishes upstream TCP sockets directly to pre-validated IP addresses,
   preventing DNS rebinding TOCTOU at the browser and proxy levels.
5. Non-MITM Tunneling: CONNECT tunnels pipe raw TLS bytes so Chromium performs
   standard end-to-end certificate validation and TLS SNI with system roots.
6. Blocks loopback, private IPv4/IPv6, link-local, cloud metadata, multicast, and reserved IPs.
7. Fail-closed: If proxy is down, Chromium has no direct network path and fails closed.
"""
import asyncio
import base64
import logging
import secrets
import urllib.parse
from typing import Optional, Dict, Any

from .url_validator import (
    validate_outbound_url,
    resolve_domain_ips,
    canonicalize_host,
)

logger = logging.getLogger("agentdesk.security.egress_proxy")


class SecureEgressProxy:
    """
    Lightweight, high-performance async egress proxy enforcing SSRF policy
    and socket connection pinning for browser automation.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 0,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ):
        self.host = host
        self.port = port
        self.username = username or "agentdesk_egress"
        self._password = password or secrets.token_hex(24)
        self.expected_auth = "Basic " + base64.b64encode(f"{self.username}:{self._password}".encode()).decode()
        self.server: Optional[asyncio.Server] = None
        self.actual_port: int = 0
        self.is_running: bool = False
        self._active_connections = set()
        self.stats = {
            "connect_requests": 0,
            "http_requests": 0,
            "blocked": 0,
            "auth_failed": 0,
            "success": 0,
        }

    @property
    def password(self) -> str:
        """Returns the active proxy password for internal client configuration."""
        return self._password

    def __repr__(self) -> str:
        return f"<SecureEgressProxy host={self.host} port={self.actual_port} user={self.username} running={self.is_running}>"

    async def start(self) -> int:
        """Starts the proxy server listening on loopback."""
        if self.is_running and self.server:
            return self.actual_port

        self.server = await asyncio.start_server(self._handle_client, self.host, self.port)
        self.actual_port = self.server.sockets[0].getsockname()[1]
        self.is_running = True
        logger.info(f"[EgressProxy] Started on {self.host}:{self.actual_port}")
        return self.actual_port

    async def stop(self) -> None:
        """Stops the proxy server and terminates all active tunnels."""
        self.is_running = False
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            self.server = None

        # Close any lingering client streams
        for writer in list(self._active_connections):
            try:
                writer.close()
            except Exception:
                pass
        self._active_connections.clear()
        logger.info("[EgressProxy] Stopped")

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.stop()

    def get_playwright_proxy_config(self) -> Dict[str, str]:
        """Returns the proxy configuration dict suitable for playwright.chromium.launch(proxy=...)."""
        if not self.is_running:
            raise RuntimeError("Cannot get proxy config before SecureEgressProxy is started.")
        return {
            "server": f"http://127.0.0.1:{self.actual_port}",
            "username": self.username,
            "password": self._password,
        }

    def get_chromium_launch_args(self) -> list[str]:
        """Returns recommended Chromium launch flags to enforce strict proxy usage."""
        if not self.is_running:
            raise RuntimeError("Cannot get launch args before SecureEgressProxy is started.")
        return [
            f"--proxy-server=http://127.0.0.1:{self.actual_port}",
            "--proxy-bypass-list=<-loopback>",
            "--disable-webrtc",
        ]

    async def _handle_client(
        self,
        client_reader: asyncio.StreamReader,
        client_writer: asyncio.StreamWriter,
    ) -> None:
        self._active_connections.add(client_writer)
        try:
            # Read HTTP request line
            line_bytes = await client_reader.readline()
            if not line_bytes:
                return

            req_line = line_bytes.decode("utf-8", errors="ignore").strip()
            parts = req_line.split()
            if len(parts) < 2:
                return

            method, target = parts[0].upper(), parts[1]

            # Read headers
            headers = {}
            while True:
                h_line = await client_reader.readline()
                if not h_line or h_line == b"\r\n" or h_line == b"\n":
                    break
                decoded = h_line.decode("utf-8", errors="ignore").strip()
                if ":" in decoded:
                    k, v = decoded.split(":", 1)
                    headers[k.strip().lower()] = v.strip()

            # 1. Enforce Proxy Authentication
            proxy_auth = headers.get("proxy-authorization")
            if not proxy_auth or not secrets.compare_digest(proxy_auth, self.expected_auth):
                self.stats["auth_failed"] += 1
                resp = (
                    b"HTTP/1.1 407 Proxy Authentication Required\r\n"
                    b'Proxy-Authenticate: Basic realm="AgentDesk Egress"\r\n'
                    b"Content-Length: 0\r\n"
                    b"Connection: close\r\n\r\n"
                )
                client_writer.write(resp)
                await client_writer.drain()
                return

            # 2. Dispatch based on method
            if method == "CONNECT":
                self.stats["connect_requests"] += 1
                await self._handle_connect(target, client_reader, client_writer)
            else:
                self.stats["http_requests"] += 1
                await self._handle_http(method, target, headers, client_reader, client_writer)

        except Exception as exc:
            logger.debug(f"[EgressProxy] Client handling exception: {exc}")
        finally:
            self._active_connections.discard(client_writer)
            try:
                client_writer.close()
                await client_writer.wait_closed()
            except Exception:
                pass

    async def _handle_connect(
        self,
        target: str,
        client_reader: asyncio.StreamReader,
        client_writer: asyncio.StreamWriter,
    ) -> None:
        """Handles HTTP CONNECT tunneling for HTTPS and WebSocket connections."""
        if ":" in target:
            host_str, port_str = target.rsplit(":", 1)
            try:
                dest_port = int(port_str)
            except ValueError:
                dest_port = 443
        else:
            host_str = target
            dest_port = 443

        test_url = f"https://{host_str}:{dest_port}"
        is_safe, sanitized_url, reason = validate_outbound_url(test_url)
        if not is_safe:
            self.stats["blocked"] += 1
            logger.warning(f"[EgressProxy] Blocked prohibited CONNECT destination: {test_url} ({reason})")
            client_writer.write(b"HTTP/1.1 403 Forbidden (Blocked by AgentDesk Egress Policy)\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
            await client_writer.drain()
            return

        # Canonicalize host and resolve pinned IP
        _, canonical_host, _ = canonicalize_host(host_str)
        try:
            resolved_ips = resolve_domain_ips(canonical_host)
            if not resolved_ips:
                client_writer.write(b"HTTP/1.1 502 Bad Gateway (DNS Failed)\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
                await client_writer.drain()
                return
            pinned_ip = str(resolved_ips[0])
        except Exception as dns_err:
            logger.warning(f"[EgressProxy] DNS resolution error for {canonical_host}: {dns_err}")
            client_writer.write(b"HTTP/1.1 502 Bad Gateway (DNS Error)\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
            await client_writer.drain()
            return

        # Connect directly to the validated pinned IP
        try:
            remote_reader, remote_writer = await asyncio.wait_for(
                asyncio.open_connection(pinned_ip, dest_port),
                timeout=8.0,
            )
        except Exception as conn_err:
            logger.warning(f"[EgressProxy] Failed to connect to pinned IP {pinned_ip}:{dest_port}: {conn_err}")
            client_writer.write(b"HTTP/1.1 504 Gateway Timeout\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
            await client_writer.drain()
            return

        self.stats["success"] += 1
        # Notify client that tunnel is ready
        client_writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
        await client_writer.drain()

        # Bi-directional raw data forwarding
        await self._pipe_streams(client_reader, client_writer, remote_reader, remote_writer)

    async def _handle_http(
        self,
        method: str,
        target: str,
        headers: Dict[str, str],
        client_reader: asyncio.StreamReader,
        client_writer: asyncio.StreamWriter,
    ) -> None:
        """Handles forward proxying for plain HTTP requests."""
        is_safe, sanitized_url, reason = validate_outbound_url(target)
        if not is_safe:
            self.stats["blocked"] += 1
            logger.warning(f"[EgressProxy] Blocked prohibited HTTP destination: {target} ({reason})")
            client_writer.write(b"HTTP/1.1 403 Forbidden (Blocked by AgentDesk Egress Policy)\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
            await client_writer.drain()
            return

        parsed = urllib.parse.urlparse(sanitized_url)
        host_str = parsed.hostname or ""
        dest_port = parsed.port or (443 if parsed.scheme == "https" else 80)

        _, canonical_host, _ = canonicalize_host(host_str)
        try:
            resolved_ips = resolve_domain_ips(canonical_host)
            if not resolved_ips:
                client_writer.write(b"HTTP/1.1 502 Bad Gateway\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
                await client_writer.drain()
                return
            pinned_ip = str(resolved_ips[0])
        except Exception as dns_err:
            logger.warning(f"[EgressProxy] DNS resolution error for {canonical_host}: {dns_err}")
            client_writer.write(b"HTTP/1.1 502 Bad Gateway (DNS Error)\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
            await client_writer.drain()
            return

        try:
            remote_reader, remote_writer = await asyncio.wait_for(
                asyncio.open_connection(pinned_ip, dest_port),
                timeout=8.0,
            )
        except Exception as conn_err:
            logger.warning(f"[EgressProxy] Failed to connect to {pinned_ip}:{dest_port}: {conn_err}")
            client_writer.write(b"HTTP/1.1 504 Gateway Timeout\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
            await client_writer.drain()
            return

        self.stats["success"] += 1

        # Format forwarded request
        path = parsed.path or "/"
        if parsed.query:
            path += f"?{parsed.query}"

        req_bytes = f"{method} {path} HTTP/1.1\r\n".encode()
        for k, v in headers.items():
            if k in ("proxy-authorization", "proxy-connection"):
                continue
            req_bytes += f"{k.title()}: {v}\r\n".encode()
        req_bytes += b"\r\n"

        remote_writer.write(req_bytes)
        await remote_writer.drain()

        await self._pipe_streams(client_reader, client_writer, remote_reader, remote_writer)

    async def _pipe_streams(
        self,
        client_reader: asyncio.StreamReader,
        client_writer: asyncio.StreamWriter,
        remote_reader: asyncio.StreamReader,
        remote_writer: asyncio.StreamWriter,
    ) -> None:
        """Pipes data bi-directionally between client and upstream server."""
        async def forward(src: asyncio.StreamReader, dst: asyncio.StreamWriter):
            try:
                while True:
                    data = await src.read(16384)
                    if not data:
                        break
                    dst.write(data)
                    await dst.drain()
            except Exception:
                pass
            finally:
                try:
                    dst.close()
                except Exception:
                    pass

        try:
            await asyncio.gather(
                forward(client_reader, remote_writer),
                forward(remote_reader, client_writer),
                return_exceptions=True,
            )
        finally:
            try:
                remote_writer.close()
            except Exception:
                pass

