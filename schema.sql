PRAGMA foreign_keys = ON;

-- Эксплуатирующие организации (собственники, арендаторы, УК)
CREATE TABLE IF NOT EXISTS clients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    inn TEXT,
    contact_name TEXT,
    phone TEXT,
    email TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Пользователи: admin / engineer — ваша организация, client — эксплуатант
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    name TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('admin', 'engineer', 'client')),
    client_id INTEGER REFERENCES clients(id) ON DELETE SET NULL,
    phone TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS objects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER REFERENCES clients(id) ON DELETE SET NULL,
    name TEXT NOT NULL,
    address TEXT,
    profile TEXT NOT NULL DEFAULT '{}',   -- анкета (JSON)
    systems TEXT NOT NULL DEFAULT '{}',   -- системы ПЗ (JSON: code -> params)
    archived INTEGER NOT NULL DEFAULT 0,
    created_by INTEGER REFERENCES users(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Регламентные работы по объекту (генерируются из анкеты)
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    object_id INTEGER NOT NULL REFERENCES objects(id) ON DELETE CASCADE,
    code TEXT NOT NULL,
    period_months INTEGER NOT NULL,
    period_custom INTEGER NOT NULL DEFAULT 0,
    side TEXT NOT NULL,
    last_done TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    UNIQUE (object_id, code)
);

CREATE TABLE IF NOT EXISTS checklist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    object_id INTEGER NOT NULL REFERENCES objects(id) ON DELETE CASCADE,
    item_no INTEGER NOT NULL,
    answer TEXT CHECK (answer IN ('yes', 'no', 'na')),
    comment TEXT,
    updated_by INTEGER REFERENCES users(id),
    updated_at TEXT,
    UNIQUE (object_id, item_no)
);

-- Журнал выполненных работ и проверок
CREATE TABLE IF NOT EXISTS journal (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    object_id INTEGER NOT NULL REFERENCES objects(id) ON DELETE CASCADE,
    date TEXT NOT NULL,
    task_code TEXT,
    system_code TEXT,
    work_type TEXT NOT NULL,
    description TEXT,
    result TEXT NOT NULL,
    performer TEXT,
    created_by INTEGER REFERENCES users(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Замечания, неисправности, заявки
CREATE TABLE IF NOT EXISTS issues (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    object_id INTEGER NOT NULL REFERENCES objects(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT,
    severity TEXT NOT NULL DEFAULT 'medium' CHECK (severity IN ('critical', 'medium', 'low')),
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'in_progress', 'resolved')),
    kind TEXT NOT NULL DEFAULT 'remark' CHECK (kind IN ('remark', 'request')),
    due_date TEXT,
    checklist_no INTEGER,
    journal_id INTEGER REFERENCES journal(id) ON DELETE SET NULL,
    resolution TEXT,
    created_by INTEGER REFERENCES users(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    resolved_at TEXT
);

CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    object_id INTEGER NOT NULL REFERENCES objects(id) ON DELETE CASCADE,
    original_name TEXT NOT NULL,
    stored_name TEXT NOT NULL,
    size INTEGER,
    category TEXT,
    link_type TEXT,          -- checklist | journal | issue | NULL
    link_id INTEGER,
    uploaded_by INTEGER REFERENCES users(id),
    uploaded_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_tasks_object ON tasks(object_id);
CREATE INDEX IF NOT EXISTS idx_journal_object ON journal(object_id, date);
CREATE INDEX IF NOT EXISTS idx_issues_object ON issues(object_id, status);
CREATE INDEX IF NOT EXISTS idx_files_object ON files(object_id);
