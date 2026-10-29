#!/usr/bin/env python3
"""Regression tests for Config singleton, secrets, and backup throttle."""

import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1] / "usr" / "share" / "tac-writer"
sys.path.insert(0, str(ROOT))


class TestConfigSecrets(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config_home = Path(self.tmp.name) / "config"
        self.data_home = Path(self.tmp.name) / "data"
        self.cache_home = Path(self.tmp.name) / "cache"
        for path in (self.config_home, self.data_home, self.cache_home):
            path.mkdir()

        from core import config as config_mod
        config_mod.Config.reset_instance()

        self.env = mock.patch.dict(
            os.environ,
            {
                "XDG_CONFIG_HOME": str(self.config_home),
                "XDG_DATA_HOME": str(self.data_home),
                "XDG_CACHE_HOME": str(self.cache_home),
            },
            clear=False,
        )
        self.env.start()
        self.addCleanup(self.env.stop)
        self.addCleanup(config_mod.Config.reset_instance)

    def test_singleton_shared(self):
        from core.config import Config
        self.assertIs(Config(), Config())

    def test_api_key_not_written_to_config_json(self):
        from core.config import Config
        cfg = Config()
        cfg.set_ai_assistant_api_key("super-secret-key")
        cfg.save()
        raw = json.loads(cfg.config_file.read_text(encoding="utf-8"))
        self.assertEqual(raw.get("ai_assistant_api_key", ""), "")
        self.assertEqual(cfg.get_ai_assistant_api_key(), "super-secret-key")

    def test_migrate_legacy_plaintext_key(self):
        from core.config import Config
        from core import config as config_mod
        cfg_dir = self.config_home / "tac"
        cfg_dir.mkdir(parents=True, exist_ok=True)
        (cfg_dir / "config.json").write_text(
            json.dumps({"ai_assistant_api_key": "legacy-key", "window_width": 800}),
            encoding="utf-8",
        )
        config_mod.Config.reset_instance()
        cfg = Config()
        self.assertEqual(cfg.get_ai_assistant_api_key(), "legacy-key")
        raw = json.loads(cfg.config_file.read_text(encoding="utf-8"))
        self.assertEqual(raw.get("ai_assistant_api_key", ""), "")

    def test_backup_throttle(self):
        from core.config import Config
        cfg = Config()
        cfg.set("backup_files", True)
        cfg.set("backup_min_interval_seconds", 3600)
        self.assertTrue(cfg.should_create_db_backup())
        cfg.mark_db_backup_done()
        self.assertFalse(cfg.should_create_db_backup())
        cfg._last_db_backup_at = time.time() - 4000
        self.assertTrue(cfg.should_create_db_backup())

    def test_zh_ch_migrated(self):
        from core.config import Config
        from core import config as config_mod
        cfg_dir = self.config_home / "tac"
        cfg_dir.mkdir(parents=True, exist_ok=True)
        (cfg_dir / "config.json").write_text(
            json.dumps({
                "spell_check_available_languages": ["pt_BR", "zh_CH"],
                "spell_check_language": "zh_CH",
            }),
            encoding="utf-8",
        )
        config_mod.Config.reset_instance()
        cfg = Config()
        self.assertNotIn("zh_CH", cfg.get_available_spell_languages())
        self.assertIn("zh_CN", cfg.get_available_spell_languages())
        self.assertEqual(cfg.get_spell_check_language(), "zh_CN")


if __name__ == "__main__":
    unittest.main()
