"""Credentials loader: reads secrets from the gitignored `.env` file at the repository root.

Usage:
    from config import secret
    app_key = secret("TFL_APP_KEY")

Real environment variables win over `.env`. Copy `.env.example` to `.env` and fill in the values.
No third-party dependency (python-dotenv not required).
"""
import os
from pathlib import Path


def _find_env():
    for start in (Path(__file__).resolve().parent, Path.cwd().resolve()):
        for folder in (start, *start.parents):
            candidate = folder / ".env"
            if candidate.is_file():
                return candidate
    return None


def _load():
    path = _find_env()
    if path is None:
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip().strip("'\"")
        os.environ.setdefault(key.strip(), value)


_load()


def secret(name, default=None):
    """Return the value of `name` from the environment/.env, or raise a clear error if it is missing."""
    value = os.environ.get(name, default)
    if value is None:
        raise KeyError(f"{name} is not set: add it to the gitignored .env file (see .env.example)")
    return value
