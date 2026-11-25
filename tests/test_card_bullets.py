"""The story text must become exactly one level of bullets in Teams."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from newsletter.card import _bullets  # noqa: E402

EXPECTED = "- First fact here.\n- Second fact costs $360M.\n- Version 2.5 ships later."


class BulletTests(unittest.TestCase):
    def test_paragraph(self):
        self.assertEqual(_bullets("First fact here. Second fact costs $360M. Version 2.5 ships later."),
                         EXPECTED)

    def test_ai_wrote_its_own_dash_list(self):
        self.assertEqual(_bullets("- First fact here.\n- Second fact costs $360M.\n- Version 2.5 ships later."),
                         EXPECTED)

    def test_other_markers(self):
        self.assertEqual(_bullets("• First fact here.\n* Second fact costs $360M.\n1. Version 2.5 ships later."),
                         EXPECTED)

    def test_no_double_marker(self):
        for line in _bullets("- - First fact here.\n- Second fact costs $360M.").splitlines():
            self.assertFalse(line.startswith("- -"))


if __name__ == "__main__":
    unittest.main()
