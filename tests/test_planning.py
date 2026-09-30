import json
import sqlite3
import tempfile
import unittest
from datetime import date
from pathlib import Path

from backend.app.core.database import SCHEMA_PATH
from backend.app.services.planning import materialize_today


class TodayPlanningTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.connection = sqlite3.connect(Path(self.temp_dir.name) / "test.db")
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))

    def tearDown(self):
        self.connection.close()
        self.temp_dir.cleanup()

    def add_daily_routine(self, name: str, minutes: int, priority: int = 50):
        self.connection.execute(
            """
            INSERT INTO routines
                (name, frequency_type, target_count, preferred_weekdays,
                 default_duration_minutes, min_duration_minutes, max_duration_minutes, priority)
            VALUES (?, 'daily', 5, ?, ?, ?, ?, ?)
            """,
            (name, json.dumps([0, 1, 2, 3, 4]), minutes, minutes, minutes, priority),
        )

    def test_materializes_once_per_day(self):
        self.add_daily_routine("PJT", 20)
        day = date(2026, 9, 30)
        materialize_today(self.connection, day)
        materialize_today(self.connection, day)
        count = self.connection.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        self.assertEqual(count, 1)

    def test_capacity_overflow_remains_candidate(self):
        self.connection.execute("UPDATE settings SET default_available_minutes = 100, capacity_ratio = 0.8")
        self.add_daily_routine("긴 작업", 90)
        candidates = materialize_today(self.connection, date(2026, 9, 30))
        count = self.connection.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        self.assertEqual(count, 0)
        self.assertEqual(candidates[0]["title"], "긴 작업")


if __name__ == "__main__":
    unittest.main()
