#!/usr/bin/env python3
"""Smoke checks for high-priority bug fixes."""

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "usr" / "share" / "tac-writer"


class TestSmokeFixes(unittest.TestCase):
    def test_no_strandard_defaults(self):
        dialogs = (SRC / "ui" / "dialogs.py").read_text(encoding="utf-8")
        main_window = (SRC / "ui" / "main_window.py").read_text(encoding="utf-8")
        self.assertIn('project_type="standard"', dialogs)
        self.assertIn('project_type="standard"', main_window)
        self.assertNotIn('project_type="strandard"', dialogs)
        self.assertNotIn('project_type="strandard"', main_window)

    def test_undo_accelerators_use_win_actions(self):
        app = (SRC / "application.py").read_text(encoding="utf-8")
        self.assertIn("'win.undo'", app)
        self.assertIn("'win.redo'", app)
        self.assertNotIn("'app.undo'", app)

    def test_i18n_prefers_bundled_locale_logic(self):
        i18n = (SRC / "utils" / "i18n.py").read_text(encoding="utf-8")
        self.assertIn("_has_translations", i18n)
        self.assertIn("_bundled_locale", i18n)


if __name__ == "__main__":
    unittest.main()
