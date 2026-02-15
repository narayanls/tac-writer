"""
TAC Update Checker
Checks for application updates via GitHub API (deb/rpm)
or AUR RPC API (Arch Linux), depending on install method.
"""

import json
import subprocess
from typing import Dict, List, Optional, Callable

from gi.repository import GLib


class UpdateChecker:
    """Checks for new versions of TAC Writer"""

    GITHUB_API_URL = "https://api.github.com/repos/{user}/{repo}/releases/latest"
    AUR_RPC_URL = "https://aur.archlinux.org/rpc/?v=5&type=info&arg[]={pkg}"
    GITHUB_USER = "narayanls"
    GITHUB_REPO = "tac-writer"
    APP_PACKAGE_NAME = "tac-writer"

    def __init__(self, current_version: str):
        self.current_version = current_version

    # ── Public API ────────────────────────────────────────────

    def check_async(self, callback: Callable[[Optional[Dict]], None]):
        """
        Check for updates in a background thread.
        *callback* is invoked on the GTK main thread with a dict
        describing the update, or None if up-to-date / check failed.
        """
        import threading
        thread = threading.Thread(
            target=self._worker, args=(callback,), daemon=True
        )
        thread.start()

    # ── Background worker ─────────────────────────────────────

    def _worker(self, callback):
        try:
            print("[UpdateChecker] Starting update check...")

            install_method = self._detect_install_method()
            distro = self._detect_distro()
            print(f"[UpdateChecker] Install method: {install_method}")
            print(f"[UpdateChecker] Distro ID: {distro.get('id', 'unknown')}")

            if install_method == "aur":
                result = self._check_via_aur(install_method, distro)
            else:
                result = self._check_via_github(install_method, distro)

            if result:
                print(f"[UpdateChecker] Update available: "
                      f"{result['current_version']} → {result['latest_version']}")
            else:
                print("[UpdateChecker] No update available (or check failed).")

            GLib.idle_add(callback, result)

        except Exception as exc:
            print(f"[UpdateChecker] Check failed with exception: {exc}")
            import traceback
            traceback.print_exc()
            GLib.idle_add(callback, None)

    # ── AUR strategy ──────────────────────────────────────────

    def _check_via_aur(self, install_method, distro):
        """Check for updates by comparing pacman -Q vs AUR RPC API."""
        installed_ver = self._get_pacman_version()
        if not installed_ver:
            print("[UpdateChecker] Could not get installed version from pacman. "
                  "Falling back to GitHub check.")
            return self._check_via_github(install_method, distro)

        print(f"[UpdateChecker] Installed (pacman): {installed_ver}")

        aur_ver = self._fetch_aur_version()
        if not aur_ver:
            print("[UpdateChecker] Could not query AUR RPC. "
                  "Falling back to GitHub check.")
            return self._check_via_github(install_method, distro)

        print(f"[UpdateChecker] Latest (AUR): {aur_ver}")

        cmp = self._arch_vercmp(installed_ver, aur_ver)
        print(f"[UpdateChecker] vercmp('{installed_ver}', '{aur_ver}') = {cmp}")

        if cmp >= 0:
            print("[UpdateChecker] Already up-to-date (AUR).")
            return None

        # Fetch GitHub release notes as a bonus (best-effort)
        release_notes = ""
        try:
            release = self._fetch_latest_release()
            if release:
                release_notes = release.get("body", "")
        except Exception:
            pass

        return {
            "current_version": installed_ver,
            "latest_version": aur_ver,
            "release_notes": release_notes,
            "published_at": "",
            "assets": [],
            "install_method": install_method,
            "distro": distro,
        }

    # ── GitHub strategy ───────────────────────────────────────

    def _check_via_github(self, install_method, distro):
        """Check for updates via GitHub releases (for deb/rpm/unknown)."""

        # For deb/rpm, read the version from the file the installer creates
        local_version = self._read_version_txt()
        if local_version:
            print(f"[UpdateChecker] Current (version.txt): {local_version}")
        else:
            # Fallback: use APP_VERSION (may not match tag scheme)
            local_version = self.current_version
            print(f"[UpdateChecker] version.txt not found, "
                  f"using APP_VERSION: {local_version}")

        release = self._fetch_latest_release()
        if release is None:
            print("[UpdateChecker] Could not fetch GitHub release.")
            return None

        latest = release.get("tag_name", "").lstrip("v")
        print(f"[UpdateChecker] Latest (GitHub tag): {latest}")

        if not latest:
            return None

        cmp = self._compare_versions(local_version, latest)
        print(f"[UpdateChecker] compare_versions('{local_version}', "
              f"'{latest}') = {cmp}")

        if cmp >= 0:
            print("[UpdateChecker] Already up-to-date (GitHub).")
            return None

        return {
            "current_version": local_version,
            "latest_version": latest,
            "release_notes": release.get("body", ""),
            "published_at": release.get("published_at", ""),
            "assets": release.get("assets", []),
            "install_method": install_method,
            "distro": distro,
        }

    @staticmethod
    def _read_version_txt() -> Optional[str]:
        """
        Read the version from the file created by the deb/rpm installer.
        Located at ~/.local/share/tac-writer/version.txt
        """
        import os
        path = os.path.expanduser("~/.local/share/tac-writer/version.txt")
        try:
            with open(path, "r") as f:
                version = f.read().strip().lstrip("v")
                if version:
                    print(f"[UpdateChecker] Read version.txt: '{version}'")
                    return version
        except FileNotFoundError:
            pass
        except Exception as e:
            print(f"[UpdateChecker] Error reading version.txt: {e}")
        return None

    # ── Network helpers ───────────────────────────────────────

    def _fetch_latest_release(self) -> Optional[Dict]:
        import urllib.request

        url = self.GITHUB_API_URL.format(
            user=self.GITHUB_USER, repo=self.GITHUB_REPO
        )
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "TAC-Writer-UpdateChecker/1.0")

        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                if resp.status != 200:
                    return None
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            print(f"[UpdateChecker] GitHub API error: {e}")
            return None

    def _fetch_aur_version(self) -> Optional[str]:
        """Fetch latest version from AUR RPC API."""
        import urllib.request

        url = self.AUR_RPC_URL.format(pkg=self.APP_PACKAGE_NAME)
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "TAC-Writer-UpdateChecker/1.0")

        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                if resp.status != 200:
                    print(f"[UpdateChecker] AUR RPC returned status {resp.status}")
                    return None
                data = json.loads(resp.read().decode("utf-8"))

            results = data.get("results", [])
            if not results:
                print("[UpdateChecker] AUR RPC returned empty results.")
                return None

            version = results[0].get("Version", "")
            return version if version else None

        except Exception as e:
            print(f"[UpdateChecker] AUR RPC error: {e}")
            return None

    # ── Pacman helper ─────────────────────────────────────────

    def _get_pacman_version(self) -> Optional[str]:
        """Get installed version from pacman -Q."""
        try:
            r = subprocess.run(
                ["pacman", "-Q", self.APP_PACKAGE_NAME],
                capture_output=True, text=True, timeout=5,
            )
            if r.returncode == 0:
                # Output: "tac-writer 26.02.15-1733"
                parts = r.stdout.strip().split()
                if len(parts) >= 2:
                    return parts[1]
        except (FileNotFoundError, subprocess.TimeoutExpired) as e:
            print(f"[UpdateChecker] pacman -Q failed: {e}")
        return None

    # ── Version comparison ────────────────────────────────────

    @staticmethod
    def _arch_vercmp(a: str, b: str) -> int:
        """
        Compare versions using Arch's native vercmp utility.
        Returns -1, 0, or 1.
        Falls back to simple comparison if vercmp is unavailable.
        """
        try:
            r = subprocess.run(
                ["vercmp", a, b],
                capture_output=True, text=True, timeout=5,
            )
            if r.returncode == 0:
                val = int(r.stdout.strip())
                return val
        except (FileNotFoundError, subprocess.TimeoutExpired, ValueError) as e:
            print(f"[UpdateChecker] vercmp unavailable: {e}, using fallback")

        return UpdateChecker._compare_versions(a, b)

    @staticmethod
    def _compare_versions(a: str, b: str) -> int:
        """Return -1 if a < b, 0 if equal, 1 if a > b."""
        def _ints(v: str) -> List[int]:
            return [int(x) for x in v.replace("-", ".").split(".")
                    if x.isdigit()]

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
        """Return 'aur', 'deb', 'rpm', or 'unknown'."""
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

    # ── Terminal / AUR helper detection ───────────────────────

    @staticmethod
    def find_terminal() -> Optional[tuple]:
        """Return (command, exec_flag) for the first terminal found."""
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
        """Return 'yay', 'paru', or None."""
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
        """Find a release asset whose name ends with suffix."""
        for asset in assets:
            name = asset.get("name", "")
            if name.endswith(suffix):
                if "arm" in name.lower() or "aarch64" in name.lower():
                    continue
                return {
                    "name": name,
                    "url": asset.get("browser_download_url", ""),
                }
        return None