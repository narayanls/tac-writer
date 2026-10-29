"""
Secure secret storage for API keys and OAuth tokens.

Prefer the system keyring (Secret Service / libsecret) when available.
Fall back to a dedicated secrets file with mode 0600 (never the main config.json).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

_SERVICE = "io.github.narayanls.tacwriter"
_KEYRING_AVAILABLE = False

try:
    import keyring  # type: ignore

    _KEYRING_AVAILABLE = True
except ImportError:
    keyring = None  # type: ignore


def _secrets_file(config_dir: Path) -> Path:
    return Path(config_dir) / "secrets.json"


def _load_file_secrets(config_dir: Path) -> dict:
    path = _secrets_file(config_dir)
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _save_file_secrets(config_dir: Path, data: dict) -> None:
    path = _secrets_file(config_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def get_secret(config_dir: Path, key: str) -> str:
    """Retrieve a secret by key. Empty string if missing."""
    if _KEYRING_AVAILABLE and keyring is not None:
        try:
            value = keyring.get_password(_SERVICE, key)
            if value:
                return value
        except Exception:
            pass
    return str(_load_file_secrets(config_dir).get(key, "") or "")


def set_secret(config_dir: Path, key: str, value: Optional[str]) -> None:
    """Store or clear a secret."""
    value = (value or "").strip()
    if _KEYRING_AVAILABLE and keyring is not None:
        try:
            if value:
                keyring.set_password(_SERVICE, key, value)
            else:
                try:
                    keyring.delete_password(_SERVICE, key)
                except Exception:
                    pass
            # Keep file copy cleared when keyring works
            data = _load_file_secrets(config_dir)
            if key in data:
                data.pop(key, None)
                _save_file_secrets(config_dir, data)
            return
        except Exception:
            pass

    data = _load_file_secrets(config_dir)
    if value:
        data[key] = value
    else:
        data.pop(key, None)
    _save_file_secrets(config_dir, data)


def migrate_from_config(config_dir: Path, config_dict: dict, keys: list) -> list:
    """
    Move plaintext secrets out of config_dict into secure storage.
    Returns list of keys that were migrated (caller should persist config without them).
    """
    migrated = []
    for key in keys:
        value = config_dict.get(key)
        if value:
            set_secret(config_dir, key, str(value))
            config_dict[key] = ""
            migrated.append(key)
    return migrated
