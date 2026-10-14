import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone


def now():
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, path):
        self.path = path
        self.lock = threading.RLock()
        with self.connect() as db:
            db.executescript('''
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY, name TEXT, created TEXT);
            CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
            CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY, project TEXT, agent TEXT, role TEXT, content TEXT, created TEXT);
            CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, kind TEXT, project TEXT, status TEXT, payload TEXT, result TEXT, created TEXT);
            CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY, job TEXT, type TEXT, data TEXT, created TEXT);
            CREATE TABLE IF NOT EXISTS proposals(id TEXT PRIMARY KEY, project TEXT, job TEXT, path TEXT, content TEXT, base TEXT, status TEXT);
            CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY, job TEXT, agent TEXT, position INTEGER, status TEXT, result TEXT);
            ''')
            db.execute("UPDATE jobs SET status='interrupted' WHERE status IN ('queued','running')")
            db.execute("UPDATE tasks SET status='interrupted' WHERE status='running'")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=20)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def execute(self, sql, values=()):
        with self.lock, self.connect() as db:
            cur = db.execute(sql, values)
            return cur.lastrowid

    def rows(self, sql, values=()):
        with self.connect() as db:
            return [dict(r) for r in db.execute(sql, values)]

    def one(self, sql, values=()):
        rows = self.rows(sql, values)
        return rows[0] if rows else None

    def setting(self, key, default=None):
        row = self.one('SELECT value FROM settings WHERE key=?', (key,))
        return json.loads(row['value']) if row else default

    def set(self, key, value):
        self.execute('INSERT OR REPLACE INTO settings VALUES (?,?)', (key, json.dumps(value)))

    def message(self, project, agent, role, content):
        return self.execute('INSERT INTO messages(project,agent,role,content,created) VALUES (?,?,?,?,?)',
                            (project, agent, role, content, now()))

    def event(self, job, kind, data):
        self.execute('INSERT INTO events(job,type,data,created) VALUES (?,?,?,?)',
                     (job, kind, json.dumps(data, ensure_ascii=False), now()))
