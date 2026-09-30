import json
from datetime import date

from backend.app.core.database import initialize_database, session


ROUTINES = [
    {
        "name": "하루 10분 PJT",
        "category": "project",
        "description": "개인 프로젝트와 지속적으로 접촉하기",
        "frequency_type": "daily",
        "target_count": 5,
        "preferred_weekdays": [0, 1, 2, 3, 4],
        "default_duration_minutes": 20,
        "min_duration_minutes": 10,
        "max_duration_minutes": 30,
        "priority": 70,
        "active": 1,
    },
    {
        "name": "멘토링 준비",
        "category": "mentoring",
        "description": "목요일 과외 준비",
        "frequency_type": "weekly",
        "target_count": 1,
        "preferred_weekdays": [2],
        "default_duration_minutes": 30,
        "min_duration_minutes": 20,
        "max_duration_minutes": 45,
        "priority": 80,
        "active": 1,
    },
    {
        "name": "SW/CS 개인 공부",
        "category": "study",
        "description": "실무 구조 이해 중심 학습",
        "frequency_type": "weekly",
        "target_count": 2,
        "preferred_weekdays": [1, 3],
        "default_duration_minutes": 60,
        "min_duration_minutes": 60,
        "max_duration_minutes": 120,
        "priority": 55,
        "active": 1,
    },
    {
        "name": "취업 경험 정리",
        "category": "career",
        "description": "마스터 이력서·자소서·경험카드 정리",
        "frequency_type": "monthly",
        "target_count": 1,
        "preferred_weekdays": [],
        "default_duration_minutes": 60,
        "min_duration_minutes": 60,
        "max_duration_minutes": 90,
        "priority": 30,
        "active": 1,
    },
    {
        "name": "AI Lunch 복습",
        "category": "study",
        "description": "AI Lunch 강의 별도 복습",
        "frequency_type": "biweekly",
        "target_count": 1,
        "preferred_weekdays": [4],
        "default_duration_minutes": 60,
        "min_duration_minutes": 45,
        "max_duration_minutes": 90,
        "priority": 40,
        "active": 1,
    },
    {
        "name": "NCS 평시 학습",
        "category": "certificate",
        "description": "국민은행 시험 종료 후 활성화",
        "frequency_type": "weekly",
        "target_count": 2,
        "preferred_weekdays": [1, 3],
        "default_duration_minutes": 40,
        "min_duration_minutes": 35,
        "max_duration_minutes": 50,
        "default_target_value": 0.5,
        "default_target_unit": "세트",
        "priority": 90,
        "active": 0,
    },
    {
        "name": "AFPK",
        "category": "certificate",
        "description": "국민은행 NCS 시험 종료 후 활성화",
        "frequency_type": "weekly",
        "target_count": 3,
        "preferred_weekdays": [0, 2, 4],
        "default_duration_minutes": 120,
        "min_duration_minutes": 90,
        "max_duration_minutes": 150,
        "priority": 85,
        "active": 0,
    },
    {
        "name": "OPIc",
        "category": "language",
        "description": "국민은행 NCS 시험 종료 후 활성화",
        "frequency_type": "weekly",
        "target_count": 3,
        "preferred_weekdays": [],
        "default_duration_minutes": 30,
        "min_duration_minutes": 30,
        "max_duration_minutes": 60,
        "priority": 35,
        "active": 0,
    },
]


def seed() -> None:
    initialize_database()
    with session() as connection:
        if connection.execute("SELECT COUNT(*) FROM routines").fetchone()[0] == 0:
            for routine in ROUTINES:
                data = {**routine, "preferred_weekdays": json.dumps(routine["preferred_weekdays"])}
                connection.execute(
                    f"INSERT INTO routines ({', '.join(data)}) VALUES ({', '.join('?' for _ in data)})",
                    tuple(data.values()),
                )

        if connection.execute("SELECT COUNT(*) FROM projects").fetchone()[0] == 0:
            connection.execute(
                """
                INSERT INTO projects
                    (name, description, status, priority, next_action)
                VALUES (?, ?, 'active', 75, ?)
                """,
                ("Personal OS MVP", "개인 운영 시스템 MVP", "Today 화면 완성"),
            )
            connection.execute(
                """
                INSERT INTO projects
                    (name, description, status, priority, next_action, estimated_remaining_minutes)
                VALUES (?, ?, 'active', 95, ?, 600)
                """,
                ("NCS 시험 준비", "시험일은 사용자가 직접 입력", "종이책으로 다음 학습 세션 진행"),
            )

        if connection.execute("SELECT COUNT(*) FROM inbox_items").fetchone()[0] == 0:
            connection.executemany(
                "INSERT INTO inbox_items (title) VALUES (?)",
                [("SWEA 자료구조 정리",), ("README 수정",)],
            )

        if connection.execute("SELECT COUNT(*) FROM review_items").fetchone()[0] == 0:
            connection.execute(
                """
                INSERT INTO review_items
                    (title, first_learned_on, last_reviewed_on, review_interval_days, next_review_on, expected_minutes)
                VALUES ('DFS', ?, ?, 7, ?, 30)
                """,
                (date.today().isoformat(), date.today().isoformat(), date.today().isoformat()),
            )


if __name__ == "__main__":
    seed()
    print("Sample data created.")
