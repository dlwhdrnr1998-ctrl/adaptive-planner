CREATE TABLE IF NOT EXISTS settings (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    vision_text TEXT NOT NULL DEFAULT '',
    capacity_ratio REAL NOT NULL DEFAULT 0.8 CHECK (capacity_ratio > 0 AND capacity_ratio <= 1),
    default_available_minutes INTEGER NOT NULL DEFAULT 180 CHECK (default_available_minutes >= 0),
    week_starts_on INTEGER NOT NULL DEFAULT 0 CHECK (week_starts_on BETWEEN 0 AND 6),
    timezone TEXT NOT NULL DEFAULT 'Asia/Seoul',
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT OR IGNORE INTO settings (id, vision_text)
VALUES (1, '금융 × 데이터 × SW를 연결하는 도메인 융합형 인재');

CREATE TABLE IF NOT EXISTS routines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'general',
    description TEXT NOT NULL DEFAULT '',
    frequency_type TEXT NOT NULL DEFAULT 'weekly'
        CHECK (frequency_type IN ('daily', 'weekly', 'biweekly', 'monthly')),
    frequency_interval INTEGER NOT NULL DEFAULT 1 CHECK (frequency_interval > 0),
    target_count INTEGER NOT NULL DEFAULT 1 CHECK (target_count >= 0),
    preferred_weekdays TEXT NOT NULL DEFAULT '[]',
    default_duration_minutes INTEGER NOT NULL CHECK (default_duration_minutes > 0),
    min_duration_minutes INTEGER NOT NULL CHECK (min_duration_minutes > 0),
    max_duration_minutes INTEGER NOT NULL CHECK (max_duration_minutes >= min_duration_minutes),
    default_target_value REAL CHECK (default_target_value >= 0),
    default_target_unit TEXT,
    priority INTEGER NOT NULL DEFAULT 50 CHECK (priority BETWEEN 0 AND 100),
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    active_from TEXT,
    active_until TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    deadline TEXT,
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('planned', 'active', 'paused', 'completed', 'archived')),
    priority INTEGER NOT NULL DEFAULT 50 CHECK (priority BETWEEN 0 AND 100),
    next_action TEXT NOT NULL DEFAULT '',
    estimated_remaining_minutes INTEGER CHECK (estimated_remaining_minutes >= 0),
    weekly_target_minutes INTEGER CHECK (weekly_target_minutes >= 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS review_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    routine_id INTEGER REFERENCES routines(id) ON DELETE SET NULL,
    project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,
    first_learned_on TEXT NOT NULL,
    last_reviewed_on TEXT,
    review_interval_days INTEGER NOT NULL CHECK (review_interval_days > 0),
    next_review_on TEXT NOT NULL,
    expected_minutes INTEGER NOT NULL DEFAULT 30 CHECK (expected_minutes > 0),
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    scheduled_date TEXT NOT NULL,
    expected_minutes INTEGER NOT NULL CHECK (expected_minutes > 0),
    target_value REAL,
    target_unit TEXT,
    detail TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'completed', 'partial', 'failed', 'cancelled')),
    priority INTEGER NOT NULL DEFAULT 50 CHECK (priority BETWEEN 0 AND 100),
    sort_order INTEGER NOT NULL DEFAULT 0,
    origin_type TEXT NOT NULL DEFAULT 'manual'
        CHECK (origin_type IN ('manual', 'routine', 'project', 'review', 'inbox')),
    routine_id INTEGER REFERENCES routines(id) ON DELETE SET NULL,
    project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,
    review_item_id INTEGER REFERENCES review_items(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_routine_task_per_day
ON tasks (routine_id, scheduled_date)
WHERE routine_id IS NOT NULL AND origin_type = 'routine';

CREATE UNIQUE INDEX IF NOT EXISTS uq_pending_review_task
ON tasks (review_item_id)
WHERE review_item_id IS NOT NULL AND status = 'pending';

CREATE TABLE IF NOT EXISTS progress_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER REFERENCES tasks(id) ON DELETE SET NULL,
    routine_id INTEGER REFERENCES routines(id) ON DELETE SET NULL,
    project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,
    performed_on TEXT NOT NULL,
    actual_minutes INTEGER NOT NULL CHECK (actual_minutes >= 0),
    target_value REAL,
    actual_value REAL,
    unit TEXT,
    result TEXT NOT NULL CHECK (result IN ('completed', 'partial', 'failed')),
    memo TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS resources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    label TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    url TEXT,
    location_note TEXT,
    routine_id INTEGER REFERENCES routines(id) ON DELETE CASCADE,
    project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
    review_item_id INTEGER REFERENCES review_items(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (
        (routine_id IS NOT NULL) +
        (project_id IS NOT NULL) +
        (review_item_id IS NOT NULL) = 1
    )
);

CREATE TABLE IF NOT EXISTS inbox_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    processed INTEGER NOT NULL DEFAULT 0 CHECK (processed IN (0, 1)),
    processed_at TEXT,
    linked_task_id INTEGER REFERENCES tasks(id) ON DELETE SET NULL,
    linked_routine_id INTEGER REFERENCES routines(id) ON DELETE SET NULL,
    linked_project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS daily_capacities (
    date TEXT PRIMARY KEY,
    available_minutes INTEGER NOT NULL CHECK (available_minutes >= 0),
    note TEXT
);

CREATE INDEX IF NOT EXISTS ix_tasks_scheduled_date ON tasks (scheduled_date);
CREATE INDEX IF NOT EXISTS ix_progress_performed_on ON progress_logs (performed_on);
CREATE INDEX IF NOT EXISTS ix_projects_deadline ON projects (deadline);
CREATE INDEX IF NOT EXISTS ix_review_items_next_review ON review_items (next_review_on);
