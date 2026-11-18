from dataclasses import asdict
from pathlib import Path
import json
import sqlite3
from .domain import Task, Settings
from .protection import protect, unprotect


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('PRAGMA secure_delete=ON')
        self.db.executescript('CREATE TABLE IF NOT EXISTS tasks (id TEXT PRIMARY KEY, data TEXT NOT NULL);'
                              'CREATE TABLE IF NOT EXISTS settings (id INTEGER PRIMARY KEY, data TEXT NOT NULL);')
        migrated = False
        with self.db:
            for select_sql, update_sql in (
                ('SELECT id,data FROM tasks', 'UPDATE tasks SET data=? WHERE id=?'),
                ('SELECT id,data FROM settings', 'UPDATE settings SET data=? WHERE id=?'),
            ):
                for key, value in self.db.execute(select_sql).fetchall():
                    if isinstance(value, str):
                        # Validate before changing anything; never discard an unreadable queue.
                        json.loads(value)
                        self.db.execute(update_sql, (protect(value.encode('utf-8')), key))
                        migrated = True
        if migrated:
            self.db.execute('PRAGMA wal_checkpoint(TRUNCATE)')
            self.db.execute('VACUUM')
            self.db.execute('PRAGMA wal_checkpoint(TRUNCATE)')

    def save_task(self, task: Task):
        with self.db:
            self.db.execute('INSERT OR REPLACE INTO tasks VALUES (?,?)', (task.id, protect(json.dumps(task.data()).encode('utf-8'))))

    def load_tasks(self) -> list[Task]:
        return [Task(**json.loads(unprotect(row[0]))) for row in self.db.execute('SELECT data FROM tasks ORDER BY rowid')]

    def delete_task(self, task_id: str):
        with self.db:
            self.db.execute('DELETE FROM tasks WHERE id=?', (task_id,))

    def settings(self) -> Settings:
        row = self.db.execute('SELECT data FROM settings WHERE id=1').fetchone()
        return Settings(**json.loads(unprotect(row[0]))) if row else Settings()

    def save_settings(self, settings: Settings):
        with self.db:
            self.db.execute('INSERT OR REPLACE INTO settings VALUES (1,?)', (protect(json.dumps(asdict(settings)).encode('utf-8')),))

    def close(self):
        self.db.close()
