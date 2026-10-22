"""
Email Dispatch Provider for AgentDesk Outreach.
Supports:
1. Simulation Mode (Default, offline-safe, zero network calls, explicitly marked).
2. Standard SMTP Dispatch (via smtplib with TLS/SSL and credentials).
3. Cloud HTTP Dispatch (via Resend API).

Strict Safety Policy:
- Never sends real emails in simulation mode.
- Never prints, logs, or exposes credentials, tokens, or passwords.
- All secrets are read strictly from environment variables.
"""

import os
import re
import socket
import smtplib
from email.mime.text import MIMEText
from dataclasses import dataclass
from typing import Optional, Dict, Any

try:
    import httpx
except ImportError:
    httpx = None

try:
    from ..env_loader import load_root_env
except (ImportError, ValueError):
    try:
        from env_loader import load_root_env
    except ImportError:
        def load_root_env(override: bool = False):
            return {}

@dataclass
class DispatchResult:
    success: bool
    status: str  # "sent" or "simulated"
    is_simulated: bool
    provider: str
    message: str
    detail: Optional[str] = None

class DispatchError(Exception):
    """Base class for outreach dispatch exceptions."""
    pass

class DispatchConfigurationError(DispatchError):
    """Raised when dispatch provider configuration is missing or invalid."""
    pass

class DispatchDeliveryError(DispatchError):
    """Raised when provider communication or mail transmission fails."""
    pass

def sanitize_log_message(text: str, custom_secrets: Optional[list] = None) -> str:
    """
    Scrubs sensitive tokens, passwords, and API keys from error or log messages.
    """
    if not text:
        return ""
    if custom_secrets:
        for secret in custom_secrets:
            if secret and len(str(secret)) >= 3:
                text = text.replace(str(secret), "[REDACTED_SECRET]")
    # Mask Resend keys
    text = re.sub(r're_[a-zA-Z0-9_\-]+', '[REDACTED_API_KEY]', text)
    # Mask OpenAI / Bearer keys
    text = re.sub(r'sk-[a-zA-Z0-9_\-]+', '[REDACTED_API_KEY]', text)
    # Mask password parameter patterns
    text = re.sub(r'(password|passwd|pwd|secret)=([^\s,;]+)', r'\1=[REDACTED]', text, flags=re.IGNORECASE)
    # Mask auth headers
    text = re.sub(r'Bearer\s+[a-zA-Z0-9_\-\.]+', 'Bearer [REDACTED]', text, flags=re.IGNORECASE)
    return text

def get_dispatch_config() -> Dict[str, Any]:
    """
    Retrieves current email dispatch configuration from environment variables.
    Defaults to 'simulation' mode when no outbound credentials are supplied.
    """
    # Ensure any newly created or modified root .env is loaded dynamically
    load_root_env(override=True)

    raw_mode = os.environ.get("AGENTDESK_OUTREACH_DISPATCH_MODE", "").strip().lower()

    smtp_host = os.environ.get("AGENTDESK_SMTP_HOST", "").strip()
    resend_key = os.environ.get("AGENTDESK_RESEND_API_KEY", "").strip()

    if raw_mode in ("smtp", "resend", "simulation"):
        mode = raw_mode
    elif smtp_host:
        mode = "smtp"
    elif resend_key:
        mode = "resend"
    else:
        mode = "simulation"

    return {
        "mode": mode,
        # SMTP options
        "smtp_host": smtp_host,
        "smtp_port": int(os.environ.get("AGENTDESK_SMTP_PORT", "587")),
        "smtp_user": os.environ.get("AGENTDESK_SMTP_USER", "").strip(),
        "smtp_password": os.environ.get("AGENTDESK_SMTP_PASSWORD", "").strip(),
        "smtp_from_email": os.environ.get("AGENTDESK_SMTP_FROM_EMAIL", "").strip() or os.environ.get("AGENTDESK_SMTP_USER", "").strip(),
        "smtp_from_name": os.environ.get("AGENTDESK_SMTP_FROM_NAME", "AgentDesk Outreach").strip(),
        "smtp_use_tls": os.environ.get("AGENTDESK_SMTP_USE_TLS", "true").lower() in ("true", "1", "yes"),
        "smtp_use_ssl": os.environ.get("AGENTDESK_SMTP_USE_SSL", "false").lower() in ("true", "1", "yes"),
        # Resend options
        "resend_api_key": resend_key,
        "resend_from_email": os.environ.get("AGENTDESK_RESEND_FROM_EMAIL", "").strip(),
        "resend_from_name": os.environ.get("AGENTDESK_RESEND_FROM_NAME", "AgentDesk Outreach").strip(),
    }

def get_dispatch_status_info() -> Dict[str, Any]:
    """
    Returns public, non-sensitive dispatch metadata for the UI and diagnostics.
    Never includes passwords, credentials, or secret keys.
    """
    cfg = get_dispatch_config()
    mode = cfg["mode"]

    if mode == "smtp":
        from_addr = cfg["smtp_from_email"] or "(Not configured)"
        is_ready = bool(cfg["smtp_host"] and cfg["smtp_from_email"])
        return {
            "mode": "smtp",
            "is_live": True,
            "display_name": f"SMTP Gateway ({cfg['smtp_host'] or 'Unconfigured'}:{cfg['smtp_port']})",
            "from_email": from_addr,
            "is_configured": is_ready,
            "notice": (
                f"Live SMTP sending active via {cfg['smtp_host']}:{cfg['smtp_port']} as {from_addr}"
                if is_ready
                else "SMTP mode selected but AGENTDESK_SMTP_HOST or FROM_EMAIL is missing in .env"
            ),
        }
    elif mode == "resend":
        from_addr = cfg["resend_from_email"] or "(Not configured)"
        is_ready = bool(cfg["resend_api_key"] and cfg["resend_from_email"])
        return {
            "mode": "resend",
            "is_live": True,
            "display_name": "Resend Cloud Email API",
            "from_email": from_addr,
            "is_configured": is_ready,
            "notice": (
                f"Live Resend HTTP sending active as {from_addr}"
                if is_ready
                else "Resend mode selected but AGENTDESK_RESEND_API_KEY or FROM_EMAIL is missing in .env"
            ),
        }
    else:
        return {
            "mode": "simulation",
            "is_live": False,
            "display_name": "Simulation Mode (Safe Offline)",
            "from_email": "simulation@agentdesk.local",
            "is_configured": True,
            "notice": "Simulation mode: No real emails are delivered. Configure SMTP in .env for real delivery.",
        }

def dispatch_outreach_email(
    recipient_email: str,
    subject: str,
    body: str,
    draft_id: str
) -> DispatchResult:
    """
    Dispatches a reviewed and approved outreach message to the verified recipient email.
    Behavior depends on the configured mode:
    - 'simulation': Returns simulated success without network calls.
    - 'smtp': Transmits real email via standard smtplib.
    - 'resend': Transmits real email via Resend API.
    """
    recipient = recipient_email.strip()
    if not recipient or recipient == "(No public email listed)" or "@" not in recipient:
        raise ValueError("Invalid or unverified recipient email address.")

    cfg = get_dispatch_config()
    mode = cfg["mode"]

    # 1. Simulation Mode
    if mode == "simulation":
        return DispatchResult(
            success=True,
            status="simulated",
            is_simulated=True,
            provider="simulation",
            message=(
                f"Simulation Mode: Outreach approved for {recipient}. "
                "No real email was delivered because no outbound email provider credentials are configured in .env."
            ),
            detail="Offline simulation mode active. Configure AGENTDESK_SMTP_HOST in .env for live transmission.",
        )

    # 2. SMTP Mode
    elif mode == "smtp":
        host = cfg["smtp_host"]
        port = cfg["smtp_port"]
        from_email = cfg["smtp_from_email"]
        from_name = cfg["smtp_from_name"]
        user = cfg["smtp_user"]
        password = cfg["smtp_password"]
        use_tls = cfg["smtp_use_tls"]
        use_ssl = cfg["smtp_use_ssl"]

        if not host:
            raise DispatchConfigurationError(
                "SMTP dispatch configuration incomplete: AGENTDESK_SMTP_HOST is required in environment."
            )
        if not from_email:
            raise DispatchConfigurationError(
                "SMTP dispatch configuration incomplete: AGENTDESK_SMTP_FROM_EMAIL is required in environment."
            )

        # Construct MIME Message
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = subject
        msg["From"] = f"{from_name} <{from_email}>" if from_name else from_email
        msg["To"] = recipient

        try:
            if use_ssl:
                server = smtplib.SMTP_SSL(host, port, timeout=12)
            else:
                server = smtplib.SMTP(host, port, timeout=12)
                if use_tls:
                    server.starttls()

            if user and password:
                server.login(user, password)

            server.send_message(msg)
            server.quit()

            return DispatchResult(
                success=True,
                status="sent",
                is_simulated=False,
                provider=f"smtp ({host}:{port})",
                message=f"Real email accepted by SMTP gateway ({host}:{port}) for {recipient}.",
                detail=f"Dispatched via SMTP from {from_email}.",
            )
        except Exception as exc:
            secrets = [password] if password else []
            clean_error = sanitize_log_message(str(exc), custom_secrets=secrets)
            raise DispatchDeliveryError(f"SMTP delivery failed: {clean_error}") from None

    # 3. Resend HTTP Mode
    elif mode == "resend":
        api_key = cfg["resend_api_key"]
        from_email = cfg["resend_from_email"]
        from_name = cfg["resend_from_name"]

        if not api_key:
            raise DispatchConfigurationError(
                "Resend dispatch configuration incomplete: AGENTDESK_RESEND_API_KEY is required in environment."
            )
        if not from_email:
            raise DispatchConfigurationError(
                "Resend dispatch configuration incomplete: AGENTDESK_RESEND_FROM_EMAIL is required in environment."
            )
        if httpx is None:
            raise DispatchConfigurationError(
                "httpx package is required for Resend API dispatch. Please install httpx."
            )

        from_header = f"{from_name} <{from_email}>" if from_name else from_email
        payload = {
            "from": from_header,
            "to": [recipient],
            "subject": subject,
            "text": body,
        }

        try:
            with httpx.Client(timeout=15.0) as client:
                res = client.post(
                    "https://api.resend.com/emails",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                if res.status_code >= 400:
                    clean_res_text = sanitize_log_message(res.text, custom_secrets=[api_key])
                    raise DispatchDeliveryError(
                        f"Resend API returned status {res.status_code}: {clean_res_text}"
                    )

                return DispatchResult(
                    success=True,
                    status="sent",
                    is_simulated=False,
                    provider="resend",
                    message=f"Real email accepted by Resend API for {recipient}.",
                    detail="Delivered through Resend cloud email infrastructure.",
                )
        except DispatchDeliveryError:
            raise
        except Exception as exc:
            clean_error = sanitize_log_message(str(exc), custom_secrets=[api_key])
            raise DispatchDeliveryError(f"Resend delivery failed: {clean_error}") from None

    else:
        raise DispatchConfigurationError(f"Unsupported dispatch mode '{mode}'. Use 'simulation', 'smtp', or 'resend'.")
