#!/usr/bin/env python3
"""Regression tests for database merger."""

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "usr" / "share" / "tac-writer"
sys.path.insert(0, str(ROOT))

from core.merger import DatabaseMerger  # noqa: E402


SCHEMA = """
CREATE TABLE projects (
    id TEXT PRIMARY KEY,
    name TEXT,
    created_at TEXT,
    modified_at TEXT,
    metadata TEXT,
    document_formatting TEXT
);
CREATE TABLE paragraphs (
    id TEXT PRIMARY KEY,
    project_id TEXT,
    type TEXT,
    content TEXT,
    "order" INTEGER,
    footnotes TEXT,
    formatting TEXT,
    created_at TEXT,
    modified_at TEXT
);
"""


def _init_db(path: Path):
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


class TestMerger(unittest.TestCase):
    def test_adds_new_project_from_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            local = Path(tmp) / "local.db"
            backup = Path(tmp) / "backup.db"
            _init_db(local).close()
            backup_conn = _init_db(backup)
            backup_conn.execute(
                "INSERT INTO projects VALUES (?,?,?,?,?,?)",
                ("p1", "Cloud", "2024-01-01", "2024-02-01", "{}", "{}"),
            )
            backup_conn.execute(
                "INSERT INTO paragraphs VALUES (?,?,?,?,?,?,?,?,?)",
                ("a1", "p1", "introduction", "hello", 0, "[]", "{}", "2024-01-01", "2024-02-01"),
            )
            backup_conn.commit()
            backup_conn.close()

            stats = DatabaseMerger(str(local)).merge(str(backup))
            self.assertEqual(stats["projects_added"], 1)
            self.assertEqual(stats["paragraphs_processed"], 1)


if __name__ == "__main__":
    unittest.main()
