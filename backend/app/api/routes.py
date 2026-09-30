import json
import sqlite3
from datetime import date, timedelta

from fastapi import APIRouter, HTTPException, Query, status

from .schemas import (
    CapacityUpdate,
    InboxCreate,
    InboxProcess,
    ProgressCreate,
    ProjectCreate,
    ProjectUpdate,
    ResourceCreate,
    ReviewItemCreate,
    RoutineCreate,
    RoutineUpdate,
    SettingsUpdate,
    TaskCreate,
    TaskUpdate,
)
from ..core.database import session
from ..services.planning import (
    adaptive_recommendation,
    capacity_for_day,
    materialize_today,
    weekly_progress,
)


router = APIRouter(prefix="/api")


def _row_or_404(connection: sqlite3.Connection, table: str, item_id: int) -> sqlite3.Row:
    allowed = {"routines", "projects", "tasks", "inbox_items"}
    if table not in allowed:
        raise ValueError("unsupported table")
    row = connection.execute(f"SELECT * FROM {table} WHERE id = ?", (item_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="항목을 찾을 수 없습니다.")
    return row


def _decode_routine(row: sqlite3.Row) -> dict:
    result = dict(row)
    result["preferred_weekdays"] = json.loads(result["preferred_weekdays"] or "[]")
    result["active"] = bool(result["active"])
    return result


@router.get("/today")
def get_today(day: date = Query(default_factory=date.today)) -> dict:
    with session() as connection:
        candidates = materialize_today(connection, day)
        tasks = [dict(row) for row in connection.execute(
            """
            SELECT t.*, r.name AS routine_name, p.name AS project_name
            FROM tasks t
            LEFT JOIN routines r ON r.id = t.routine_id
            LEFT JOIN projects p ON p.id = t.project_id
            WHERE t.scheduled_date = ? AND t.status != 'cancelled'
            ORDER BY t.status != 'pending', t.sort_order, t.priority DESC, t.id
            """,
            (day.isoformat(),),
        ).fetchall()]
        for task in tasks:
            if task["routine_id"]:
                task["resources"] = [dict(row) for row in connection.execute(
                    "SELECT * FROM resources WHERE routine_id = ? ORDER BY id", (task["routine_id"],)
                ).fetchall()]
            elif task["project_id"]:
                task["resources"] = [dict(row) for row in connection.execute(
                    "SELECT * FROM resources WHERE project_id = ? ORDER BY id", (task["project_id"],)
                ).fetchall()]
            else:
                task["resources"] = []
        overdue = [dict(row) for row in connection.execute(
            """
            SELECT * FROM tasks
            WHERE scheduled_date < ? AND status = 'pending'
            ORDER BY scheduled_date, priority DESC LIMIT 20
            """,
            (day.isoformat(),),
        ).fetchall()]
        planned = sum(task["expected_minutes"] for task in tasks if task["status"] == "pending")
        settings = dict(connection.execute("SELECT * FROM settings WHERE id = 1").fetchone())
        return {
            "date": day.isoformat(),
            "vision_text": settings["vision_text"],
            "tasks": tasks,
            "overdue_tasks": overdue,
            "candidates": candidates,
            "planned_minutes": planned,
            "capacity": capacity_for_day(connection, day),
            "weekly_progress": weekly_progress(connection, day),
        }


@router.post("/today/candidates/{kind}/{source_id}", status_code=status.HTTP_201_CREATED)
def accept_candidate(kind: str, source_id: int, day: date = Query(default_factory=date.today)) -> dict:
    with session() as connection:
        if kind == "routine":
            source = _row_or_404(connection, "routines", source_id)
            try:
                cursor = connection.execute(
                    """
                    INSERT INTO tasks
                        (title, scheduled_date, expected_minutes, target_value, target_unit,
                         detail, priority, origin_type, routine_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'routine', ?)
                    """,
                    (source["name"], day.isoformat(), source["default_duration_minutes"],
                     source["default_target_value"], source["default_target_unit"],
                     source["description"], source["priority"], source_id),
                )
            except sqlite3.IntegrityError as exc:
                raise HTTPException(status_code=409, detail="이미 오늘 생성된 루틴입니다.") from exc
        elif kind == "review":
            source = connection.execute("SELECT * FROM review_items WHERE id = ?", (source_id,)).fetchone()
            if not source:
                raise HTTPException(status_code=404, detail="복습 항목을 찾을 수 없습니다.")
            cursor = connection.execute(
                """
                INSERT INTO tasks
                    (title, scheduled_date, expected_minutes, detail, priority, origin_type, review_item_id)
                VALUES (?, ?, ?, '복습 후보에서 추가됨', 60, 'review', ?)
                """,
                (f"{source['title']} 복습", day.isoformat(), source["expected_minutes"], source_id),
            )
        else:
            raise HTTPException(status_code=400, detail="지원하지 않는 후보 종류입니다.")
        return dict(_row_or_404(connection, "tasks", cursor.lastrowid))


@router.get("/routines")
def list_routines() -> list[dict]:
    with session() as connection:
        routines = [_decode_routine(row) for row in connection.execute(
            "SELECT * FROM routines ORDER BY active DESC, priority DESC, id"
        ).fetchall()]
        progress_by_id = {item["id"]: item for item in weekly_progress(connection, date.today())}
        for routine in routines:
            routine["resources"] = [dict(row) for row in connection.execute(
                "SELECT * FROM resources WHERE routine_id = ? ORDER BY id", (routine["id"],)
            ).fetchall()]
            progress = progress_by_id.get(routine["id"], {})
            routine["completed_count"] = progress.get("completed_count", 0)
            routine["actual_minutes"] = progress.get("actual_minutes", 0)
            last_log = connection.execute(
                "SELECT performed_on FROM progress_logs WHERE routine_id = ? ORDER BY performed_on DESC, id DESC LIMIT 1",
                (routine["id"],),
            ).fetchone()
            routine["last_performed_on"] = last_log["performed_on"] if last_log else None
            routine["recommendation"] = adaptive_recommendation(connection, routine["id"])
        return routines


@router.post("/routines", status_code=status.HTTP_201_CREATED)
def create_routine(payload: RoutineCreate) -> dict:
    data = payload.model_dump(mode="json")
    weekdays = json.dumps(data.pop("preferred_weekdays"))
    columns = ", ".join([*data.keys(), "preferred_weekdays"])
    placeholders = ", ".join("?" for _ in range(len(data) + 1))
    with session() as connection:
        cursor = connection.execute(
            f"INSERT INTO routines ({columns}) VALUES ({placeholders})",
            (*data.values(), weekdays),
        )
        return _decode_routine(_row_or_404(connection, "routines", cursor.lastrowid))


@router.put("/routines/{routine_id}")
def update_routine(routine_id: int, payload: RoutineUpdate) -> dict:
    data = payload.model_dump(mode="json")
    data["preferred_weekdays"] = json.dumps(data["preferred_weekdays"])
    assignments = ", ".join(f"{key} = ?" for key in data)
    with session() as connection:
        _row_or_404(connection, "routines", routine_id)
        connection.execute(
            f"UPDATE routines SET {assignments}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (*data.values(), routine_id),
        )
        return _decode_routine(_row_or_404(connection, "routines", routine_id))


@router.delete("/routines/{routine_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_routine(routine_id: int, confirm: bool = False) -> None:
    if not confirm:
        raise HTTPException(status_code=409, detail="삭제하려면 confirm=true가 필요합니다.")
    with session() as connection:
        _row_or_404(connection, "routines", routine_id)
        connection.execute("DELETE FROM routines WHERE id = ?", (routine_id,))


@router.get("/routines/{routine_id}/recommendation")
def get_recommendation(routine_id: int) -> dict:
    with session() as connection:
        recommendation = adaptive_recommendation(connection, routine_id)
        if recommendation is None:
            return {"routine_id": routine_id, "available": False, "message": "분석에 필요한 기록이 부족합니다."}
        return {"available": True, **recommendation}


@router.get("/projects")
def list_projects() -> list[dict]:
    with session() as connection:
        projects = [dict(row) for row in connection.execute(
            "SELECT * FROM projects ORDER BY status = 'active' DESC, priority DESC, deadline IS NULL, deadline"
        ).fetchall()]
        for project in projects:
            project["resources"] = [dict(row) for row in connection.execute(
                "SELECT * FROM resources WHERE project_id = ? ORDER BY id", (project["id"],)
            ).fetchall()]
        return projects


@router.post("/projects", status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreate) -> dict:
    data = payload.model_dump(mode="json")
    with session() as connection:
        cursor = connection.execute(
            f"INSERT INTO projects ({', '.join(data)}) VALUES ({', '.join('?' for _ in data)})",
            tuple(data.values()),
        )
        return dict(_row_or_404(connection, "projects", cursor.lastrowid))


@router.put("/projects/{project_id}")
def update_project(project_id: int, payload: ProjectUpdate) -> dict:
    data = payload.model_dump(mode="json")
    assignments = ", ".join(f"{key} = ?" for key in data)
    with session() as connection:
        _row_or_404(connection, "projects", project_id)
        connection.execute(
            f"UPDATE projects SET {assignments}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (*data.values(), project_id),
        )
        return dict(_row_or_404(connection, "projects", project_id))


@router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: int, confirm: bool = False) -> None:
    if not confirm:
        raise HTTPException(status_code=409, detail="삭제하려면 confirm=true가 필요합니다.")
    with session() as connection:
        _row_or_404(connection, "projects", project_id)
        connection.execute("DELETE FROM projects WHERE id = ?", (project_id,))


@router.post("/tasks", status_code=status.HTTP_201_CREATED)
def create_task(payload: TaskCreate) -> dict:
    data = payload.model_dump(mode="json")
    data["origin_type"] = "project" if data["project_id"] else "manual"
    with session() as connection:
        cursor = connection.execute(
            f"INSERT INTO tasks ({', '.join(data)}) VALUES ({', '.join('?' for _ in data)})",
            tuple(data.values()),
        )
        return dict(_row_or_404(connection, "tasks", cursor.lastrowid))


@router.patch("/tasks/{task_id}")
def update_task(task_id: int, payload: TaskUpdate) -> dict:
    data = payload.model_dump(mode="json", exclude_none=True)
    confirm_reschedule = data.pop("confirm_reschedule", False)
    with session() as connection:
        current = _row_or_404(connection, "tasks", task_id)
        if "scheduled_date" in data and data["scheduled_date"] != current["scheduled_date"] and not confirm_reschedule:
            raise HTTPException(status_code=409, detail="날짜 변경에는 confirm_reschedule=true가 필요합니다.")
        if data:
            assignments = ", ".join(f"{key} = ?" for key in data)
            connection.execute(
                f"UPDATE tasks SET {assignments}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (*data.values(), task_id),
            )
        return dict(_row_or_404(connection, "tasks", task_id))


@router.post("/progress", status_code=status.HTTP_201_CREATED)
def record_progress(payload: ProgressCreate) -> dict:
    with session() as connection:
        task = _row_or_404(connection, "tasks", payload.task_id)
        cursor = connection.execute(
            """
            INSERT INTO progress_logs
                (task_id, routine_id, project_id, performed_on, actual_minutes,
                 target_value, actual_value, unit, result, memo)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task["id"], task["routine_id"], task["project_id"], date.today().isoformat(),
                payload.actual_minutes, task["target_value"], payload.actual_value,
                task["target_unit"], payload.result, payload.memo,
            ),
        )
        connection.execute(
            "UPDATE tasks SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (payload.result, payload.task_id),
        )
        if task["review_item_id"] and payload.result in ("completed", "partial"):
            item = connection.execute(
                "SELECT review_interval_days FROM review_items WHERE id = ?", (task["review_item_id"],)
            ).fetchone()
            next_review = date.today() + timedelta(days=item["review_interval_days"])
            connection.execute(
                """
                UPDATE review_items
                SET last_reviewed_on = ?, next_review_on = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (date.today().isoformat(), next_review.isoformat(), task["review_item_id"]),
            )
        return dict(connection.execute("SELECT * FROM progress_logs WHERE id = ?", (cursor.lastrowid,)).fetchone())


@router.get("/inbox")
def list_inbox() -> list[dict]:
    with session() as connection:
        return [dict(row) for row in connection.execute(
            "SELECT * FROM inbox_items ORDER BY processed, created_at DESC"
        ).fetchall()]


@router.post("/inbox", status_code=status.HTTP_201_CREATED)
def create_inbox_item(payload: InboxCreate) -> dict:
    with session() as connection:
        cursor = connection.execute("INSERT INTO inbox_items (title) VALUES (?)", (payload.title,))
        return dict(_row_or_404(connection, "inbox_items", cursor.lastrowid))


@router.post("/inbox/{item_id}/process")
def process_inbox_item(item_id: int, payload: InboxProcess) -> dict:
    with session() as connection:
        _row_or_404(connection, "inbox_items", item_id)
        connection.execute(
            """
            UPDATE inbox_items SET processed = 1, processed_at = CURRENT_TIMESTAMP,
                linked_task_id = ?, linked_routine_id = ?, linked_project_id = ?
            WHERE id = ?
            """,
            (payload.linked_task_id, payload.linked_routine_id, payload.linked_project_id, item_id),
        )
        return dict(_row_or_404(connection, "inbox_items", item_id))


@router.get("/review-items")
def list_review_items() -> list[dict]:
    with session() as connection:
        return [dict(row) for row in connection.execute(
            "SELECT * FROM review_items ORDER BY active DESC, next_review_on, id"
        ).fetchall()]


@router.post("/review-items", status_code=status.HTTP_201_CREATED)
def create_review_item(payload: ReviewItemCreate) -> dict:
    data = payload.model_dump(mode="json")
    with session() as connection:
        cursor = connection.execute(
            f"INSERT INTO review_items ({', '.join(data)}) VALUES ({', '.join('?' for _ in data)})",
            tuple(data.values()),
        )
        return dict(connection.execute("SELECT * FROM review_items WHERE id = ?", (cursor.lastrowid,)).fetchone())


@router.get("/resources")
def list_resources(
    routine_id: int | None = None,
    project_id: int | None = None,
    review_item_id: int | None = None,
) -> list[dict]:
    clauses, values = [], []
    for column, value in (("routine_id", routine_id), ("project_id", project_id), ("review_item_id", review_item_id)):
        if value is not None:
            clauses.append(f"{column} = ?")
            values.append(value)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    with session() as connection:
        return [dict(row) for row in connection.execute(
            f"SELECT * FROM resources{where} ORDER BY id", tuple(values)
        ).fetchall()]


@router.post("/resources", status_code=status.HTTP_201_CREATED)
def create_resource(payload: ResourceCreate) -> dict:
    data = payload.model_dump()
    with session() as connection:
        cursor = connection.execute(
            f"INSERT INTO resources ({', '.join(data)}) VALUES ({', '.join('?' for _ in data)})",
            tuple(data.values()),
        )
        return dict(connection.execute("SELECT * FROM resources WHERE id = ?", (cursor.lastrowid,)).fetchone())


@router.get("/settings")
def get_settings() -> dict:
    with session() as connection:
        return dict(connection.execute("SELECT * FROM settings WHERE id = 1").fetchone())


@router.patch("/settings")
def update_settings(payload: SettingsUpdate) -> dict:
    data = payload.model_dump(exclude_none=True)
    with session() as connection:
        if data:
            assignments = ", ".join(f"{key} = ?" for key in data)
            connection.execute(
                f"UPDATE settings SET {assignments}, updated_at = CURRENT_TIMESTAMP WHERE id = 1",
                tuple(data.values()),
            )
        return dict(connection.execute("SELECT * FROM settings WHERE id = 1").fetchone())


@router.put("/capacity/{day}")
def set_capacity(day: date, payload: CapacityUpdate) -> dict:
    with session() as connection:
        connection.execute(
            """
            INSERT INTO daily_capacities (date, available_minutes, note)
            VALUES (?, ?, ?)
            ON CONFLICT(date) DO UPDATE SET
                available_minutes = excluded.available_minutes,
                note = excluded.note
            """,
            (day.isoformat(), payload.available_minutes, payload.note),
        )
        return {"date": day.isoformat(), **payload.model_dump(), **capacity_for_day(connection, day)}
