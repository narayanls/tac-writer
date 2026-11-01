"""
TAC Update Checker
Checks for application updates via GitHub API (deb/rpm)
or AUR RPC API (Arch Linux), depending on install method.
Cross-platform: Linux and Windows.
"""

import json
import os
import platform
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional, Callable

from gi.repository import GLib

IS_WINDOWS = platform.system() == 'Windows'


class UpdateChecker:
    """Checks for new versions of TAC Writer"""

    GITHUB_API_URL = "https://api.github.com/repos/{user}/{repo}/releases/latest"
    AUR_RPC_URL = "https://aur.archlinux.org/rpc/?v=5&type=info&arg[]={pkg}"
    GITHUB_USER = "narayanls"
    GITHUB_REPO = "tac-writer"
    APP_PACKAGE_NAME = "tac-writer"
    FLATPAK_APP_ID    = "io.github.narayanls.tacwriter"
    METAINFO_FILENAME = "io.github.narayanls.tacwriter.metainfo.xml"

    def __init__(self, current_version: str):
        self.current_version = current_version

    # ── Sandbox helpers ───────────────────────────────────────

    @staticmethod
    def _running_inside_flatpak_sandbox() -> bool:
        """True if this process itself is running inside a Flatpak sandbox."""
        return os.environ.get("FLATPAK_ID") is not None or os.path.exists("/.flatpak-info")

    @staticmethod
    def _flatpak_host_command(args: List[str], force_c_locale: bool = False) -> List[str]:
        """
        Build a command that reaches the HOST's `flatpak` binary.

        When Tac Writer itself runs inside the Flatpak sandbox, a bare
        `flatpak` call fails with FileNotFoundError because that binary
        doesn't exist inside the sandbox — it must be reached via
        `flatpak-spawn --host`. Outside the sandbox (deb/rpm/AUR/dev
        environments), the plain command is used directly.

        If *force_c_locale* is True, the spawned host process's LC_ALL/LANG
        are forced to "C" via `flatpak-spawn --env=...`. This matters for
        any caller that parses `flatpak`'s human-readable text output
        (e.g. the "Version:" label), since on a host configured with a
        non-English locale (e.g. pt_BR) that label is translated (e.g.
        "Versão:") and silently breaks naive string matching.
        """
        if UpdateChecker._running_inside_flatpak_sandbox():
            cmd = ["flatpak-spawn", "--host"]
            if force_c_locale:
                cmd += ["--env=LC_ALL=C", "--env=LANG=C"]
            return cmd + args
        return args

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
            print(f"[UpdateChecker] Distro/OS: {distro.get('id', 'unknown')}")

            if install_method == "aur":
                result = self._check_via_aur(install_method, distro)
            elif install_method == "flatpak":
                result = self._check_via_flatpak(install_method, distro)
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

    # __ Flatpak strategy _________________________________________________

    def _check_via_flatpak(self, install_method, distro):
        """Check updates: installed flatpak version vs GitHub latest tag."""
        installed_ver = self._get_flatpak_version()
        if not installed_ver:
            print("[UpdateChecker] Could not read flatpak version. "
                  "Falling back to GitHub check.")
            return self._check_via_github(install_method, distro)

        print(f"[UpdateChecker] Installed (flatpak): {installed_ver}")

        release = self._fetch_latest_release()
        if release is None:
            print("[UpdateChecker] Could not fetch GitHub release.")
            return None

        latest = release.get("tag_name", "").lstrip("v")
        print(f"[UpdateChecker] Latest (GitHub tag): {latest}")
        if not latest:
            return None

        cmp = self._compare_versions(installed_ver, latest)
        print(f"[UpdateChecker] compare_versions({installed_ver!r}, {latest!r}) = {cmp}")
        if cmp >= 0:
            print("[UpdateChecker] Already up-to-date (flatpak).")
            return None

        return {
            "current_version": installed_ver,
            "latest_version":  latest,
            "release_notes":   release.get("body", ""),
            "published_at":    release.get("published_at", ""),
            "assets":          release.get("assets", []),
            "install_method":  install_method,
            "distro":          distro,
        }

    def _get_flatpak_version(self):
        """
        Return the installed app version via `flatpak info`.

        Forces the C locale on the command: on a host configured with a
        non-English locale (e.g. pt_BR), `flatpak info` prints translated
        field labels ("Versão:" instead of "Version:"), which would
        silently break the line-matching below and make this function
        always return None — masking a real "flatpak" install as
        undetectable and pushing the caller into the wrong fallback path.
        """
        try:
            cmd = self._flatpak_host_command(
                ["flatpak", "info", self.FLATPAK_APP_ID], force_c_locale=True
            )
            run_kwargs = dict(capture_output=True, text=True, timeout=5)
            if not self._running_inside_flatpak_sandbox():
                # No flatpak-spawn hop happening here, so force the C
                # locale directly via the subprocess environment instead.
                env = dict(os.environ)
                env["LC_ALL"] = "C"
                env["LANG"] = "C"
                run_kwargs["env"] = env
            r = subprocess.run(cmd, **run_kwargs)
            if r.returncode != 0:
                return None
            for line in r.stdout.splitlines():
                if line.strip().lower().startswith("version:"):
                    ver = line.split(":", 1)[1].strip().lstrip("v")
                    if ver:
                        return ver
        except (FileNotFoundError, subprocess.TimeoutExpired) as e:
            print(f"[UpdateChecker] flatpak info failed: {e}")
        return None

    def _check_via_github(self, install_method, distro):
        """Check for updates via GitHub releases (for deb/rpm/windows/unknown)."""

        local_version = self._get_installed_release_version()
        if not local_version:
            # Não usar APP_VERSION aqui: é um contador separado das tags
            # (ex.: 1.43.0 vs 1.5.0-1) e, por ser "maior", fazia o app
            # concluir que estava sempre atualizado.
            print("[UpdateChecker] Could not determine installed release "
                  "version (no metainfo.xml, no version.txt). Skipping.")
            return None

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

    @classmethod
    def _get_installed_release_version(cls) -> Optional[str]:
        """
        Versão de release instalada, no mesmo esquema das tags do GitHub.

        Fontes:
        - metainfo.xml: vai dentro de todo pacote (deb/rpm/flatpak), então
          funciona mesmo quando o .deb/.rpm é baixado direto do GitHub,
          sem o tac-installer.
        - version.txt: gravado pelo tac-installer, pelo instalador do
          Windows e pelo próprio app após atualizar.

        Se existirem as duas, vale a maior: um version.txt antigo esquecido
        não faz o app pedir atualização à toa, e um metainfo que ficou
        para trás num release não esconde a versão gravada pelo instalador.
        """
        metainfo_ver = cls._read_metainfo_version()
        txt_ver = cls._read_version_txt()

        candidates = [v for v in (metainfo_ver, txt_ver) if v]
        if not candidates:
            return None

        best = candidates[0]
        for v in candidates[1:]:
            if cls._compare_versions(v, best) > 0:
                best = v
        print(f"[UpdateChecker] Current: {best} "
              f"(metainfo={metainfo_ver!r}, version.txt={txt_ver!r})")
        return best

    @classmethod
    def _metainfo_paths(cls) -> List[Path]:
        """
        Onde procurar o metainfo.xml, em ordem.

        O app fica em <prefix>/share/tac-writer/ e o metainfo em
        <prefix>/share/metainfo/, então o caminho relativo funciona para
        /usr (deb/rpm), /app (Flatpak) e para rodar direto do repositório.
        """
        app_dir = Path(__file__).resolve().parent.parent  # .../share/tac-writer
        paths = [app_dir.parent / "metainfo" / cls.METAINFO_FILENAME]
        if not IS_WINDOWS:
            paths.append(Path("/usr/share/metainfo") / cls.METAINFO_FILENAME)
        return paths

    @classmethod
    def _read_metainfo_version(cls) -> Optional[str]:
        """Versão do <release> mais recente do metainfo.xml (o primeiro,
        pela convenção AppStream)."""
        for path in cls._metainfo_paths():
            if not path.is_file():
                continue
            try:
                root = ET.parse(path).getroot()
                release = root.find("releases/release")
                if release is not None:
                    version = (release.get("version") or "").strip().lstrip("v")
                    if version:
                        print(f"[UpdateChecker] Read metainfo: '{version}' ({path})")
                        return version
            except (ET.ParseError, OSError) as e:
                print(f"[UpdateChecker] Error reading metainfo {path}: {e}")
        return None

    @staticmethod
    def _read_version_txt() -> Optional[str]:
        """
        Read the version from the file created by the installer.
        Linux: ~/.local/share/tac-writer/version.txt
        Windows: %LOCALAPPDATA%/tac/version.txt
        """
        if IS_WINDOWS:
            localappdata = os.environ.get('LOCALAPPDATA', '')
            if localappdata:
                path = os.path.join(localappdata, 'tac', 'version.txt')
            else:
                path = os.path.join(os.path.expanduser('~'), 'AppData', 'Local', 'tac', 'version.txt')
        else:
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

    @staticmethod
    def write_version_txt(version: str) -> bool:
        """
        Write the newly installed version to version.txt so that subsequent
        update checks reflect the current installation and the update
        notification does not reappear.

        Linux: ~/.local/share/tac-writer/version.txt
        Windows: %LOCALAPPDATA%/tac/version.txt

        Called by the app after a successful deb/rpm/exe installation,
        since those installers run as root/UAC and cannot write to the
        user's home directory on their own.

        Returns True on success, False on error.
        """
        if IS_WINDOWS:
            localappdata = os.environ.get('LOCALAPPDATA', '')
            if localappdata:
                path = os.path.join(localappdata, 'tac', 'version.txt')
            else:
                path = os.path.join(
                    os.path.expanduser('~'), 'AppData', 'Local', 'tac', 'version.txt'
                )
        else:
            path = os.path.expanduser("~/.local/share/tac-writer/version.txt")

        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as f:
                f.write(version.lstrip("v"))
            print(f"[UpdateChecker] Wrote version.txt: '{version}'")
            return True
        except Exception as e:
            print(f"[UpdateChecker] Error writing version.txt: {e}")
            return False

    # ── Network helpers ───────────────────────────────────────

    @staticmethod
    def _make_ssl_context():
        """Build an SSL context using certifi certs (bundled or installed).
        Falls back to system certs, then to unverified as last resort.
        """
        import ssl
        # 1. Prefer SSL_CERT_FILE env var (set by runtime_hook when frozen)
        cert_file = os.environ.get('SSL_CERT_FILE')
        if cert_file and os.path.isfile(cert_file):
            ctx = ssl.create_default_context(cafile=cert_file)
            print(f'[UpdateChecker] SSL: using cert file {cert_file}')
            return ctx
        # 2. Try certifi package
        try:
            import certifi
            ctx = ssl.create_default_context(cafile=certifi.where())
            print('[UpdateChecker] SSL: using certifi')
            return ctx
        except ImportError:
            pass
        # 3. System default (works on most Linux/macOS)
        try:
            ctx = ssl.create_default_context()
            print('[UpdateChecker] SSL: using system default context')
            return ctx
        except Exception:
            pass
        # 4. Last resort: unverified (logs a warning)
        print('[UpdateChecker] SSL WARNING: certificate verification disabled')
        ctx = ssl._create_unverified_context()
        return ctx

    def _fetch_latest_release(self) -> Optional[Dict]:
        import urllib.request

        url = self.GITHUB_API_URL.format(
            user=self.GITHUB_USER, repo=self.GITHUB_REPO
        )
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "TAC-Writer-UpdateChecker/1.0")

        try:
            ctx = self._make_ssl_context()
            with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
                if resp.status != 200:
                    return None
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            print(f"[UpdateChecker] GitHub API error: {e}")
            return None

    def _fetch_aur_version(self) -> Optional[str]:
        """Fetch latest version from AUR RPC API."""
        if IS_WINDOWS:
            return None

        import urllib.request

        url = self.AUR_RPC_URL.format(pkg=self.APP_PACKAGE_NAME)
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "TAC-Writer-UpdateChecker/1.0")

        try:
            ctx = self._make_ssl_context()
            with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
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
        if IS_WINDOWS:
            return None

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
        if not IS_WINDOWS:
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
            # Remove o epoch (ex: '1:') se existir, para não quebrar o .isdigit()
            if ':' in v:
                v = v.split(':', 1)[-1]
                
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
        """Return 'aur', 'deb', 'rpm', 'windows', or 'unknown'."""
        if IS_WINDOWS:
            return "windows"

        # Flatpak tem prioridade sobre gestores nativos.
        # Se o próprio app estiver rodando dentro do sandbox, `flatpak`
        # não existe ali dentro — precisa ser alcançado via
        # `flatpak-spawn --host`, senão isso sempre falha com
        # FileNotFoundError e o método cai (errado) em "unknown".
        try:
            cmd = UpdateChecker._flatpak_host_command(
                ["flatpak", "info", UpdateChecker.FLATPAK_APP_ID]
            )
            r = subprocess.run(
                cmd,
                capture_output=True, text=True, timeout=5,
            )
            if r.returncode == 0:
                return "flatpak"
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

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
        """Detect OS/distro information."""
        info: Dict[str, str] = {"id": "", "id_like": "", "pretty": ""}

        if IS_WINDOWS:
            info["id"] = "windows"
            info["pretty"] = f"Windows {platform.version()}"
            return info

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

    # ── Terminal / AUR helper detection (Linux only) ──────────

    @staticmethod
    def find_terminal() -> Optional[tuple]:
        """Return (command, exec_flag) for the first terminal found."""
        if IS_WINDOWS:
            return None

        import shutil
        terminals = [
            ("gnome-terminal", "--"),
            ("konsole", "-e"),
            ("xfce4-terminal", "-e"),
            ("mate-terminal", "-e"),
            ("alacritty", "-e"),
            ("kitty", "-e"),
            ("xterm", "-e"),
            ("tilix", "-e"),
            ("ashyterm", "-e"),
            ("zashterminal", "-e"),
            ("terminator", "-x"),
        ]
        for cmd, arg in terminals:
            if shutil.which(cmd):
                return (cmd, arg)
        return None

    @staticmethod
    def find_aur_helper() -> Optional[str]:
        """Return 'yay', 'paru', or None."""
        if IS_WINDOWS:
            return None

        import shutil
        for helper in ("yay", "paru"):
            if shutil.which(helper):
                return helper
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

    @staticmethod
    def find_flatpak_asset(assets):
        """Find the .flatpak bundle in GitHub release assets."""
        for asset in assets:
            name = asset.get("name", "")
            if name.endswith(".flatpak"):
                return {
                    "name": name,
                    "url":  asset.get("browser_download_url", ""),
                }
        return None

    @staticmethod
    def find_windows_asset(assets: List[Dict]) -> Optional[Dict[str, str]]:
        """Find the Windows installer (.exe) in GitHub release assets.

        Skips ARM/AArch64 builds and prefers x86_64/x64/setup names.
        Falls back to any .exe if no preferred candidate is found.
        """
        preferred = None
        fallback = None

        for asset in assets:
            name = asset.get("name", "")
            if not name.lower().endswith(".exe"):
                continue

            lower = name.lower()
            # Skip ARM builds
            if "arm" in lower or "aarch64" in lower:
                continue

            entry = {
                "name": name,
                "url": asset.get("browser_download_url", ""),
            }

            # Prefer installers that hint at setup/x86_64/x64/win64
            if any(k in lower for k in ("setup", "x86_64", "x64", "win64", "installer")):
                if preferred is None:
                    preferred = entry
            else:
                if fallback is None:
                    fallback = entry

        return preferred or fallback
