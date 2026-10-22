"""
Zero-dependency root .env loader for AgentDesk.
Loads key-value pairs from the repository root .env file into os.environ
without requiring external third-party packages (e.g. python-dotenv).
"""
import os
from typing import Dict, Optional

def find_root_env_path() -> Optional[str]:
    """
    Locates the project root .env file by checking:
    1. Direct parent of the backend directory.
    2. Current working directory.
    3. Workspace root if known.
    """
    candidates = [
        # backend/../.env (project root relative to this module)
        os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env")),
        # Cwd .env
        os.path.normpath(os.path.join(os.getcwd(), ".env")),
        # backend/.env (if placed inside backend)
        os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")),
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path
    return None

def parse_env_file(filepath: str) -> Dict[str, str]:
    """
    Parses a standard .env file into a dictionary of string key-value pairs.
    Handles quotes, inline comments, empty lines, and leading/trailing whitespace.
    """
    env_vars: Dict[str, str] = {}
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip()
                # Remove enclosing matching quotes
                if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                    val = val[1:-1]
                # Strip trailing comments if unquoted
                elif " #" in val:
                    val = val.split(" #", 1)[0].strip()
                if key:
                    env_vars[key] = val
    except Exception:
        # Ignore read errors safely
        pass
    return env_vars

def load_root_env(override: bool = False) -> Dict[str, str]:
    """
    Loads root .env variables into os.environ.
    If override is False, existing os.environ entries are preserved.
    Returns the dictionary of loaded variables.
    """
    env_path = find_root_env_path()
    if not env_path:
        return {}

    parsed = parse_env_file(env_path)
    for k, v in parsed.items():
        if override or k not in os.environ:
            os.environ[k] = v
    return parsed
