"""
TAC Update Checker
Checks for application updates via GitHub API and handles
update execution based on the detected installation method.
"""

import json
import subprocess
from typing import Dict, List, Optional, Callable

from gi.repository import GLib


class UpdateChecker:
    """Checks for new versions of TAC Writer on GitHub"""

    GITHUB_API_URL = "https://api.github.com/repos/{user}/{repo}/releases/latest"
    GITHUB_USER = "narayanls"
    GITHUB_REPO = "tac-writer"
    APP_PACKAGE_NAME = "tac-writer"

    def __init__(self, current_version: str):
        self.current_version = current_version

    # ── Public API ────────────────────────────────────────────

    def check_async(self, callback: Callable[[Optional[Dict]], None]):
        """
        Check for updates in a background thread.
        *callback* is invoked **on the GTK main thread** with a dict
        describing the update when one is available, or ``None`` otherwise.
        """
        import threading
        thread = threading.Thread(
            target=self._worker, args=(callback,), daemon=True
        )
        thread.start()

    # ── Background worker ─────────────────────────────────────

    def _worker(self, callback):
        try:
            release = self._fetch_latest_release()
            if release is None:
                GLib.idle_add(callback, None)
                return

            latest = release.get("tag_name", "").lstrip("v")
            if not latest or self._compare_versions(self.current_version, latest) >= 0:
                # Already up-to-date (or ahead)
                GLib.idle_add(callback, None)
                return

            install_method = self._detect_install_method()
            distro = self._detect_distro()

            result = {
                "current_version": self.current_version,
                "latest_version": latest,
                "release_notes": release.get("body", ""),
                "published_at": release.get("published_at", ""),
                "assets": release.get("assets", []),
                "install_method": install_method,
                "distro": distro,
            }
            GLib.idle_add(callback, result)

        except Exception as exc:
            print(f"[UpdateChecker] check failed: {exc}")
            GLib.idle_add(callback, None)

    # ── Network ───────────────────────────────────────────────

    def _fetch_latest_release(self) -> Optional[Dict]:
        import urllib.request

        url = self.GITHUB_API_URL.format(
            user=self.GITHUB_USER, repo=self.GITHUB_REPO
        )
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "TAC-Writer-UpdateChecker/1.0")

        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status != 200:
                return None
            return json.loads(resp.read().decode("utf-8"))

    # ── Version comparison ────────────────────────────────────

    @staticmethod
    def _compare_versions(a: str, b: str) -> int:
        """Return -1 if *a* < *b*, 0 if equal, 1 if *a* > *b*."""
        def _ints(v: str) -> List[int]:
            return [int(x) for x in v.replace("-", ".").split(".") if x.isdigit()]

        ap, bp = _ints(a), _ints(b)
        length = max(len(ap), len(bp))
        ap += [0] * (length - len(ap))
        bp += [0] * (length - len(bp))
        for ai, bi in zip(ap, bp):
            if ai < bi:
                return -1
            if ai > bi:
                return 1
        return 0

    # ── Install-method detection ──────────────────────────────

    @staticmethod
    def _detect_install_method() -> str:
        """Return ``'aur'``, ``'deb'``, ``'rpm'``, or ``'unknown'``."""
        checks = [
            ("pacman", ["-Q", "tac-writer"], "aur"),
            ("dpkg",   ["-s", "tac-writer"], "deb"),
            ("rpm",    ["-q", "tac-writer"], "rpm"),
        ]
        for cmd, args, method in checks:
            try:
                r = subprocess.run(
                    [cmd] + args,
                    capture_output=True, text=True, timeout=5,
                )
                if r.returncode == 0:
                    return method
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass
        return "unknown"

    # ── Distro detection ──────────────────────────────────────

    @staticmethod
    def _detect_distro() -> Dict[str, str]:
        info: Dict[str, str] = {"id": "", "id_like": "", "pretty": ""}
        try:
            with open("/etc/os-release") as fh:
                for line in fh:
                    line = line.strip()
                    if line.startswith("ID="):
                        info["id"] = line.split("=", 1)[1].strip('"').lower()
                    elif line.startswith("ID_LIKE="):
                        info["id_like"] = line.split("=", 1)[1].strip('"').lower()
                    elif line.startswith("PRETTY_NAME="):
                        info["pretty"] = line.split("=", 1)[1].strip('"')
        except Exception:
            pass
        return info

    # ── Helpers for performing the update ─────────────────────

    @staticmethod
    def find_terminal() -> Optional[tuple]:
        """Return ``(command, exec_flag)`` for the first terminal found."""
        terminals = [
            ("gnome-terminal", "--"),
            ("konsole", "-e"),
            ("xfce4-terminal", "-e"),
            ("mate-terminal", "-e"),
            ("alacritty", "-e"),
            ("kitty", "-e"),
            ("xterm", "-e"),
            ("tilix", "-e"),
            ("terminator", "-x"),
        ]
        for cmd, arg in terminals:
            try:
                if subprocess.run(
                    ["which", cmd], capture_output=True, timeout=3
                ).returncode == 0:
                    return (cmd, arg)
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass
        return None

    @staticmethod
    def find_aur_helper() -> Optional[str]:
        """Return ``'yay'``, ``'paru'``, or ``None``."""
        for helper in ("yay", "paru"):
            try:
                if subprocess.run(
                    ["which", helper], capture_output=True, timeout=3
                ).returncode == 0:
                    return helper
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass
        return None

    @staticmethod
    def find_asset_url(assets: List[Dict], suffix: str) -> Optional[Dict[str, str]]:
        """Find a release asset whose name ends with *suffix*."""
        for asset in assets:
            name = asset.get("name", "")
            if name.endswith(suffix):
                if "arm" in name.lower() or "aarch64" in name.lower():
                    continue
                return {
                    "name": name,
                    "url": asset.get("browser_download_url", ""),
                }
        return None#import os
