#!/usr/bin/env python3
"""Regression tests for core models and templates."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "usr" / "share" / "tac-writer"
sys.path.insert(0, str(ROOT))

from core.models import (  # noqa: E402
    ParagraphType,
    Project,
    DEFAULT_TEMPLATES,
    ACADEMIC_ESSAY_TEMPLATE,
)


class TestModels(unittest.TestCase):
    def test_academic_template_has_id_and_structure(self):
        self.assertEqual(ACADEMIC_ESSAY_TEMPLATE.id, "academic_essay")
        self.assertGreaterEqual(len(ACADEMIC_ESSAY_TEMPLATE.paragraph_structure), 5)
        project = ACADEMIC_ESSAY_TEMPLATE.create_project("Demo")
        self.assertEqual(project.name, "Demo")
        self.assertEqual(len(project.paragraphs), 5)
        self.assertEqual(project.paragraphs[0].type, ParagraphType.INTRODUCTION)
        self.assertEqual(project.paragraphs[-1].type, ParagraphType.CONCLUSION)
        self.assertEqual(project.metadata.get("template"), "academic_essay")

    def test_default_templates_lookup(self):
        self.assertIn("academic_essay", {t.id for t in DEFAULT_TEMPLATES})

    def test_strandard_typo_normalized_on_load(self):
        project = Project("Legacy")
        data = project.to_dict()
        data["metadata"] = {"type": "strandard", "author": "x"}
        loaded = Project.from_dict(data)
        self.assertEqual(loaded.metadata.get("type"), "standard")


if __name__ == "__main__":
    unittest.main()
