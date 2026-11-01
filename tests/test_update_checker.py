"""
Testes da detecção de versão instalada do update_checker (deb/rpm).

Rodar a partir da raiz do repositório:
    python3 -m unittest discover -s tests -v

Não depende de GTK nem de rede.
"""

import os
import re
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock


def _find_repo_root() -> Path:
    here = Path(__file__).resolve().parent
    for base in (here, *here.parents):
        if (base / 'usr' / 'share' / 'tac-writer' / 'core' / 'update_checker.py').is_file():
            return base
    raise RuntimeError('Não encontrei usr/share/tac-writer/core/update_checker.py')


REPO_ROOT = _find_repo_root()
APP_DIR = REPO_ROOT / 'usr' / 'share' / 'tac-writer'
METAINFO = REPO_ROOT / 'usr' / 'share' / 'metainfo' / 'io.github.narayanls.tacwriter.metainfo.xml'
ISS = REPO_ROOT / 'Windows' / 'tac-writer-installer.iss'

# Pacote "core" sem executar core/__init__.py (que puxa GTK etc.)
if 'core' not in sys.modules:
    _core_pkg = types.ModuleType('core')
    _core_pkg.__path__ = [str(APP_DIR / 'core')]
    sys.modules['core'] = _core_pkg

# update_checker importa GLib só para devolver o resultado à thread da UI
if 'gi' not in sys.modules:
    _gi = types.ModuleType('gi')
    _gi_repo = types.ModuleType('gi.repository')
    _gi_repo.GLib = types.SimpleNamespace(idle_add=lambda fn, *a: fn(*a))
    _gi.repository = _gi_repo
    sys.modules['gi'] = _gi
    sys.modules['gi.repository'] = _gi_repo

from core.update_checker import UpdateChecker  # noqa: E402


def _metainfo_xml(*versions: str) -> str:
    rels = '\n'.join(f'    <release version="{v}" date="2026-01-01"/>' for v in versions)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<component type="desktop-application">\n'
        '  <id>io.github.narayanls.tacwriter</id>\n'
        f'  <releases>\n{rels}\n  </releases>\n'
        '</component>\n'
    )


class InstalledVersionTests(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.metainfo = root / 'metainfo.xml'
        self.home = root / 'home'
        self.version_txt = self.home / '.local' / 'share' / 'tac-writer' / 'version.txt'

        self._patches = [
            mock.patch.dict(os.environ, {
                'HOME': str(self.home),
                'LOCALAPPDATA': str(self.home / '.local' / 'share'),
            }),
            mock.patch.object(UpdateChecker, '_metainfo_paths',
                              classmethod(lambda cls: [self.metainfo])),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self):
        for p in reversed(self._patches):
            p.stop()
        self._tmp.cleanup()

    def _write_metainfo(self, *versions):
        self.metainfo.write_text(_metainfo_xml(*versions), encoding='utf-8')

    def _write_version_txt(self, version):
        if os.name == 'nt':
            path = self.home / '.local' / 'share' / 'tac' / 'version.txt'
        else:
            path = self.version_txt
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(version, encoding='utf-8')

    def test_reads_latest_release_from_metainfo(self):
        self._write_metainfo('1.5.0-2', '1.5.0-1', '1.4.4-1')
        self.assertEqual(UpdateChecker._read_metainfo_version(), '1.5.0-2')

    def test_deb_from_github_without_version_txt(self):
        # O caso que estava quebrado: só existe o metainfo
        self._write_metainfo('1.5.0-1')
        self.assertEqual(UpdateChecker._get_installed_release_version(), '1.5.0-1')

    def test_stale_version_txt_does_not_win(self):
        # Atualizou pelo apt sem o instalador: version.txt ficou velho
        self._write_metainfo('1.5.0-2')
        self._write_version_txt('1.5.0-1')
        self.assertEqual(UpdateChecker._get_installed_release_version(), '1.5.0-2')

    def test_newer_version_txt_wins_over_stale_metainfo(self):
        self._write_metainfo('1.4.4-1')
        self._write_version_txt('v1.5.0-1')
        self.assertEqual(UpdateChecker._get_installed_release_version(), '1.5.0-1')

    def test_broken_metainfo_falls_back_to_version_txt(self):
        self.metainfo.write_text('<component><releases>', encoding='utf-8')
        self._write_version_txt('1.5.0-1')
        self.assertEqual(UpdateChecker._get_installed_release_version(), '1.5.0-1')

    def test_update_is_reported_and_app_version_is_ignored(self):
        # Antes: sem version.txt, comparava APP_VERSION (1.43.0) com a tag
        # (1.5.0-2) e concluía "atualizado" para sempre.
        self._write_metainfo('1.5.0-1')
        checker = UpdateChecker('1.43.0')
        release = {'tag_name': 'v1.5.0-2', 'body': '', 'published_at': '', 'assets': []}
        with mock.patch.object(checker, '_fetch_latest_release', return_value=release):
            result = checker._check_via_github('deb', {})
        self.assertIsNotNone(result)
        self.assertEqual(result['current_version'], '1.5.0-1')
        self.assertEqual(result['latest_version'], '1.5.0-2')

    def test_up_to_date(self):
        self._write_metainfo('1.5.0-2')
        checker = UpdateChecker('1.43.0')
        release = {'tag_name': 'v1.5.0-2', 'body': '', 'published_at': '', 'assets': []}
        with mock.patch.object(checker, '_fetch_latest_release', return_value=release):
            self.assertIsNone(checker._check_via_github('deb', {}))

    def test_no_version_source_skips_check(self):
        checker = UpdateChecker('1.43.0')
        with mock.patch.object(checker, '_fetch_latest_release') as fetch:
            self.assertIsNone(checker._check_via_github('deb', {}))
        fetch.assert_not_called()


class ReleaseVersionConsistencyTests(unittest.TestCase):
    """
    Trava de release: o metainfo.xml do repositório precisa estar na mesma
    versão do instalador do Windows. Se falhar, rode antes do release,
    a partir da raiz do repositório:
        python3 usr/share/tac-writer/sync_metainfo_version.py --version <versão>
    """

    def test_metainfo_matches_windows_installer(self):
        if not (METAINFO.is_file() and ISS.is_file()):
            self.skipTest('metainfo.xml ou .iss ausente')

        import xml.etree.ElementTree as ET
        release = ET.parse(METAINFO).getroot().find('releases/release')
        metainfo_ver = release.get('version') if release is not None else None

        m = re.search(r'#define\s+MyAppVersion\s+"([^"]+)"', ISS.read_text(encoding='utf-8'))
        iss_ver = m.group(1).lstrip('v') if m else None

        self.assertEqual(
            metainfo_ver, iss_ver,
            f'metainfo.xml está em {metainfo_ver!r}, mas o instalador do Windows '
            f'em {iss_ver!r}. Rode na raiz do repositório: '
            f'python3 usr/share/tac-writer/sync_metainfo_version.py --version {iss_ver}'
        )


if __name__ == '__main__':
    unittest.main()
