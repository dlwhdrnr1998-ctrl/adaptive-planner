import json
import sqlite3
from datetime import date, timedelta


def as_dict(row: sqlite3.Row | None) -> dict | None:
    return dict(row) if row is not None else None


def week_bounds(day: date) -> tuple[date, date]:
    start = day - timedelta(days=day.weekday())
    return start, start + timedelta(days=6)


def capacity_for_day(connection: sqlite3.Connection, day: date) -> dict:
    settings = connection.execute("SELECT * FROM settings WHERE id = 1").fetchone()
    override = connection.execute(
        "SELECT available_minutes FROM daily_capacities WHERE date = ?", (day.isoformat(),)
    ).fetchone()
    available = override["available_minutes"] if override else settings["default_available_minutes"]
    return {
        "available_minutes": available,
        "capacity_ratio": settings["capacity_ratio"],
        "planning_limit_minutes": int(available * settings["capacity_ratio"]),
    }


def _period_is_active(routine: sqlite3.Row, day: date) -> bool:
    if not routine["active"]:
        return False
    if routine["active_from"] and day < date.fromisoformat(routine["active_from"]):
        return False
    if routine["active_until"] and day > date.fromisoformat(routine["active_until"]):
        return False
    if routine["frequency_type"] == "biweekly":
        anchor = date.fromisoformat(routine["active_from"]) if routine["active_from"] else date(2026, 1, 5)
        return ((day - anchor).days // 7) % (2 * routine["frequency_interval"]) == 0
    if routine["frequency_type"] == "monthly":
        return day.day <= 7 * routine["frequency_interval"]
    return True


def _routine_is_due(connection: sqlite3.Connection, routine: sqlite3.Row, day: date) -> bool:
    if not _period_is_active(routine, day):
        return False
    weekdays = json.loads(routine["preferred_weekdays"] or "[]")
    if routine["frequency_type"] == "daily":
        return not weekdays or day.weekday() in weekdays

    week_start, week_end = week_bounds(day)
    scheduled_count = connection.execute(
        """
        SELECT COUNT(*) FROM tasks
        WHERE routine_id = ? AND scheduled_date BETWEEN ? AND ? AND status != 'cancelled'
        """,
        (routine["id"], week_start.isoformat(), week_end.isoformat()),
    ).fetchone()[0]
    if scheduled_count >= routine["target_count"]:
        return False
    if weekdays:
        return day.weekday() in weekdays

    remaining_needed = routine["target_count"] - scheduled_count
    remaining_weekdays = sum(1 for offset in range((week_end - day).days + 1) if (day + timedelta(offset)).weekday() < 5)
    return remaining_needed >= max(remaining_weekdays, 1)


def _existing_planned_minutes(connection: sqlite3.Connection, day: date) -> int:
    return connection.execute(
        """
        SELECT COALESCE(SUM(expected_minutes), 0) FROM tasks
        WHERE scheduled_date = ? AND status NOT IN ('cancelled', 'failed')
        """,
        (day.isoformat(),),
    ).fetchone()[0]


def materialize_today(connection: sqlite3.Connection, day: date) -> list[dict]:
    capacity = capacity_for_day(connection, day)
    planned = _existing_planned_minutes(connection, day)
    candidates: list[dict] = []

    routines = connection.execute(
        "SELECT * FROM routines WHERE active = 1 ORDER BY priority DESC, id"
    ).fetchall()
    for routine in routines:
        if not _routine_is_due(connection, routine, day):
            continue
        existing = connection.execute(
            "SELECT id FROM tasks WHERE routine_id = ? AND scheduled_date = ? AND origin_type = 'routine'",
            (routine["id"], day.isoformat()),
        ).fetchone()
        if existing:
            continue
        candidate = {
            "kind": "routine",
            "source_id": routine["id"],
            "title": routine["name"],
            "expected_minutes": routine["default_duration_minutes"],
            "target_value": routine["default_target_value"],
            "target_unit": routine["default_target_unit"],
            "priority": routine["priority"],
            "reason": "오늘 수행할 루틴",
        }
        if planned + routine["default_duration_minutes"] > capacity["planning_limit_minutes"]:
            candidate["reason"] = "80% 계획 한도를 초과하여 후보로 남김"
            candidates.append(candidate)
            continue
        connection.execute(
            """
            INSERT OR IGNORE INTO tasks
                (title, scheduled_date, expected_minutes, target_value, target_unit,
                 detail, priority, origin_type, routine_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'routine', ?)
            """,
            (
                routine["name"], day.isoformat(), routine["default_duration_minutes"],
                routine["default_target_value"], routine["default_target_unit"],
                routine["description"], routine["priority"], routine["id"],
            ),
        )
        planned += routine["default_duration_minutes"]

    reviews = connection.execute(
        """
        SELECT * FROM review_items
        WHERE active = 1 AND next_review_on <= ?
          AND NOT EXISTS (
            SELECT 1 FROM tasks
            WHERE tasks.review_item_id = review_items.id AND tasks.status = 'pending'
          )
        ORDER BY next_review_on, id
        """,
        (day.isoformat(),),
    ).fetchall()
    for review in reviews:
        candidate = {
            "kind": "review",
            "source_id": review["id"],
            "title": f"{review['title']} 복습",
            "expected_minutes": review["expected_minutes"],
            "priority": 60,
            "reason": "복습 예정일 도래",
        }
        if planned + review["expected_minutes"] > capacity["planning_limit_minutes"]:
            candidate["reason"] = "80% 계획 한도를 초과하여 후보로 남김"
            candidates.append(candidate)
            continue
        connection.execute(
            """
            INSERT INTO tasks
                (title, scheduled_date, expected_minutes, detail, priority, origin_type, review_item_id)
            VALUES (?, ?, ?, ?, 60, 'review', ?)
            """,
            (
                f"{review['title']} 복습", day.isoformat(), review["expected_minutes"],
                "복습 예정일에 자동 생성됨", review["id"],
            ),
        )
        planned += review["expected_minutes"]
    return candidates


def weekly_progress(connection: sqlite3.Connection, day: date) -> list[dict]:
    start, end = week_bounds(day)
    rows = connection.execute(
        """
        SELECT r.id, r.name, r.target_count, r.min_duration_minutes,
               COALESCE(SUM(CASE WHEN p.actual_minutes >= r.min_duration_minutes THEN 1 ELSE 0 END), 0) AS completed_count,
               COALESCE(SUM(p.actual_minutes), 0) AS actual_minutes
        FROM routines r
        LEFT JOIN progress_logs p
          ON p.routine_id = r.id AND p.performed_on BETWEEN ? AND ?
        WHERE r.active = 1
        GROUP BY r.id
        ORDER BY r.priority DESC, r.id
        """,
        (start.isoformat(), end.isoformat()),
    ).fetchall()
    return [dict(row) for row in rows]


def adaptive_recommendation(connection: sqlite3.Connection, routine_id: int) -> dict | None:
    routine = connection.execute("SELECT * FROM routines WHERE id = ?", (routine_id,)).fetchone()
    if not routine:
        return None
    logs = connection.execute(
        """
        SELECT actual_minutes, actual_value, unit FROM progress_logs
        WHERE routine_id = ? AND actual_minutes > 0 AND actual_value IS NOT NULL
        ORDER BY performed_on DESC, id DESC LIMIT 5
        """,
        (routine_id,),
    ).fetchall()
    if len(logs) < 2:
        return None
    rates = sorted(row["actual_value"] / row["actual_minutes"] for row in logs)
    median_rate = rates[len(rates) // 2]
    recommendation = round(median_rate * routine["default_duration_minutes"], 2)
    return {
        "routine_id": routine_id,
        "sample_count": len(logs),
        "expected_minutes": routine["default_duration_minutes"],
        "recommended_target_value": recommendation,
        "unit": logs[0]["unit"],
        "message": "최근 수행속도를 기준으로 목표량 조정이 필요할 수 있습니다.",
    }
