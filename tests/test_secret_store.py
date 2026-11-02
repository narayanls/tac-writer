"""
Testes do armazenamento de credenciais fora do config.json.

Rodar a partir da raiz do repositório:
    python3 -m unittest discover -s tests -v

Não depende de GTK nem de nenhuma biblioteca externa.
"""

import json
import os
import stat
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

APP_DIR = Path(__file__).resolve().parents[1] / 'usr' / 'share' / 'tac-writer'

# Registra um pacote "core" vazio apontando para a pasta real, para importar
# core.config e core.secret_store sem executar core/__init__.py (que puxa
# GTK, serviços, IA etc.).
if 'core' not in sys.modules:
    _core_pkg = types.ModuleType('core')
    _core_pkg.__path__ = [str(APP_DIR / 'core')]
    sys.modules['core'] = _core_pkg

from core import secret_store  # noqa: E402
from core.config import Config  # noqa: E402

IS_POSIX = os.name == 'posix'


class _TempConfigDirMixin:
    """Redireciona as pastas do app para um diretório temporário."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        env = {
            'XDG_CONFIG_HOME': str(root / 'config'),
            'XDG_DATA_HOME': str(root / 'data'),
            'XDG_CACHE_HOME': str(root / 'cache'),
            'APPDATA': str(root / 'config'),
            'LOCALAPPDATA': str(root / 'data'),
        }
        self._env = mock.patch.dict(os.environ, env)
        self._env.start()
        self.config_dir = root / 'config' / 'tac'

    def tearDown(self):
        self._env.stop()
        self._tmp.cleanup()

    @property
    def config_json(self) -> dict:
        with open(self.config_dir / 'config.json', encoding='utf-8') as f:
            return json.load(f)

    @property
    def secrets_json(self) -> dict:
        path = self.config_dir / 'secrets.json'
        if not path.exists():
            return {}
        with open(path, encoding='utf-8') as f:
            return json.load(f)


class SecretStoreTests(_TempConfigDirMixin, unittest.TestCase):

    def test_get_missing_returns_empty(self):
        self.assertEqual(secret_store.get_secret(self.config_dir, 'x'), '')

    def test_set_get_and_clear(self):
        self.assertTrue(secret_store.set_secret(self.config_dir, 'k', '  abc  '))
        self.assertEqual(secret_store.get_secret(self.config_dir, 'k'), 'abc')

        self.assertTrue(secret_store.set_secret(self.config_dir, 'k', None))
        self.assertEqual(secret_store.get_secret(self.config_dir, 'k'), '')
        self.assertNotIn('k', self.secrets_json)

    @unittest.skipUnless(IS_POSIX, 'permissões POSIX')
    def test_file_permission_is_0600(self):
        secret_store.set_secret(self.config_dir, 'k', 'abc')
        mode = stat.S_IMODE((self.config_dir / 'secrets.json').stat().st_mode)
        self.assertEqual(mode, 0o600)

    @unittest.skipUnless(IS_POSIX, 'permissões POSIX')
    def test_existing_open_file_is_tightened(self):
        self.config_dir.mkdir(parents=True, exist_ok=True)
        path = self.config_dir / 'secrets.json'
        path.write_text('{}', encoding='utf-8')
        os.chmod(path, 0o644)
        secret_store.set_secret(self.config_dir, 'k', 'abc')
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    def test_corrupted_file_does_not_crash(self):
        self.config_dir.mkdir(parents=True, exist_ok=True)
        (self.config_dir / 'secrets.json').write_text('{ isso não é json', encoding='utf-8')
        self.assertEqual(secret_store.get_secret(self.config_dir, 'k'), '')
        self.assertTrue(secret_store.set_secret(self.config_dir, 'k', 'abc'))
        self.assertEqual(secret_store.get_secret(self.config_dir, 'k'), 'abc')

    def test_no_temp_file_left_behind(self):
        secret_store.set_secret(self.config_dir, 'k', 'abc')
        self.assertFalse((self.config_dir / 'secrets.json.tmp').exists())


class ConfigSecretsTests(_TempConfigDirMixin, unittest.TestCase):

    def test_api_key_not_written_to_config_json(self):
        config = Config()
        config.set_ai_assistant_api_key('sk-teste')
        config.save()

        self.assertNotIn('ai_assistant_api_key', self.config_json)
        self.assertEqual(self.secrets_json.get('ai_assistant_api_key'), 'sk-teste')
        self.assertEqual(config.get_ai_assistant_api_key(), 'sk-teste')

    def test_maritaca_key_has_own_secret_slot(self):
        config = Config()
        config.set_ai_assistant_api_key('sk-gemini')
        config.set_ai_api_key_for_provider('maritaca', 'mk-maritaca')
        config.save()

        self.assertNotIn('ai_maritaca_api_key', self.config_json)
        self.assertEqual(self.secrets_json.get('ai_maritaca_api_key'), 'mk-maritaca')
        # A chave da Maritaca não sobrescreve a do Gemini/OpenRouter
        self.assertEqual(self.secrets_json.get('ai_assistant_api_key'), 'sk-gemini')
        self.assertEqual(config.get_ai_api_key_for_provider('maritaca'), 'mk-maritaca')
        self.assertEqual(config.get_ai_api_key_for_provider('gemini'), 'sk-gemini')
        self.assertEqual(config.get_ai_api_key_for_provider('openrouter'), 'sk-gemini')

    def test_dropbox_token_via_generic_set_get(self):
        # cloud_sync.py e dialogs.py usam config.get/set direto
        config = Config()
        config.set('dropbox_refresh_token', 'tok-123')
        config.save()

        self.assertNotIn('dropbox_refresh_token', self.config_json)
        self.assertEqual(config.get('dropbox_refresh_token'), 'tok-123')

        # Desvincular (dialogs.py faz set(..., None))
        config.set('dropbox_refresh_token', None)
        self.assertIsNone(config.get('dropbox_refresh_token'))
        self.assertNotIn('dropbox_refresh_token', self.secrets_json)

    def test_update_routes_secrets(self):
        config = Config()
        config.update({'ai_assistant_api_key': 'sk-x', 'window_width': 999})
        config.save()
        self.assertNotIn('ai_assistant_api_key', self.config_json)
        self.assertEqual(self.config_json['window_width'], 999)
        self.assertEqual(config.get_ai_assistant_api_key(), 'sk-x')

    def test_other_instance_sees_new_value(self):
        # O app cria vários Config() (application, services, dialogs)
        a = Config()
        b = Config()
        a.set('dropbox_refresh_token', 'novo')
        self.assertEqual(b.get('dropbox_refresh_token'), 'novo')

    def test_migration_from_old_config_json(self):
        self.config_dir.mkdir(parents=True, exist_ok=True)
        old = {
            'window_width': 800,
            'ai_assistant_api_key': 'sk-antiga',
            'dropbox_refresh_token': 'tok-antigo',
        }
        (self.config_dir / 'config.json').write_text(json.dumps(old), encoding='utf-8')

        config = Config()

        self.assertEqual(config.get_ai_assistant_api_key(), 'sk-antiga')
        self.assertEqual(config.get('dropbox_refresh_token'), 'tok-antigo')
        cfg = self.config_json
        self.assertNotIn('ai_assistant_api_key', cfg)
        self.assertNotIn('dropbox_refresh_token', cfg)
        self.assertEqual(cfg['window_width'], 800)

    def test_migration_removes_empty_legacy_fields(self):
        self.config_dir.mkdir(parents=True, exist_ok=True)
        old = {'ai_assistant_api_key': '', 'dropbox_refresh_token': None}
        (self.config_dir / 'config.json').write_text(json.dumps(old), encoding='utf-8')

        Config()

        self.assertNotIn('ai_assistant_api_key', self.config_json)
        self.assertNotIn('dropbox_refresh_token', self.config_json)
        self.assertFalse((self.config_dir / 'secrets.json').exists())

    def test_migration_keeps_key_if_secrets_file_cannot_be_written(self):
        self.config_dir.mkdir(parents=True, exist_ok=True)
        old = {'ai_assistant_api_key': 'sk-antiga'}
        (self.config_dir / 'config.json').write_text(json.dumps(old), encoding='utf-8')

        with mock.patch.object(secret_store, '_write_all', side_effect=OSError('disco cheio')):
            config = Config()

        # A credencial não pode se perder
        self.assertEqual(config.get_ai_assistant_api_key(), 'sk-antiga')
        self.assertEqual(self.config_json.get('ai_assistant_api_key'), 'sk-antiga')

        # Na próxima abertura, com o disco ok, a migração completa
        config2 = Config()
        self.assertEqual(config2.get_ai_assistant_api_key(), 'sk-antiga')
        self.assertNotIn('ai_assistant_api_key', self.config_json)

    def test_set_falls_back_to_config_if_secrets_file_cannot_be_written(self):
        config = Config()
        with mock.patch.object(secret_store, '_write_all', side_effect=OSError('disco cheio')):
            config.set_ai_assistant_api_key('sk-teste')
        self.assertEqual(config.get_ai_assistant_api_key(), 'sk-teste')


if __name__ == '__main__':
    unittest.main()
