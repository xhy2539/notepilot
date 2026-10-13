import json
import sqlite3
from pathlib import Path
from .models import now


class Conflict(Exception):
    pass


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        with self.db() as db:
            db.execute("CREATE TABLE IF NOT EXISTS projects (id TEXT PRIMARY KEY, revision INTEGER NOT NULL, data TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS events (seq INTEGER PRIMARY KEY AUTOINCREMENT, project_id TEXT, data TEXT)")

    def db(self):
        return sqlite3.connect(self.path, timeout=10)

    def create(self, project):
        with self.db() as db:
            db.execute("INSERT INTO projects VALUES (?,?,?)", (project['id'], project['revision'], json.dumps(project, ensure_ascii=False)))

    def get(self, pid):
        with self.db() as db:
            row = db.execute("SELECT data FROM projects WHERE id=?", (pid,)).fetchone()
        if not row:
            raise KeyError(pid)
        return json.loads(row[0])

    def list(self):
        with self.db() as db:
            rows = db.execute("SELECT data FROM projects ORDER BY rowid DESC LIMIT 100").fetchall()
        return [json.loads(r[0]) for r in rows]

    def save(self, project, expected):
        project = dict(project, revision=expected + 1, updated_at=now())
        with self.db() as db:
            cursor = db.execute("UPDATE projects SET revision=?,data=? WHERE id=? AND revision=?", (project['revision'], json.dumps(project, ensure_ascii=False), project['id'], expected))
            if not cursor.rowcount:
                raise Conflict("版本已变化，请刷新后重试")
        return project

    def event(self, pid, stage, message):
        with self.db() as db:
            db.execute("INSERT INTO events(project_id,data) VALUES (?,?)", (pid, json.dumps({'stage': stage, 'message': message, 'time': now()}, ensure_ascii=False)))

    def events(self, pid, after):
        with self.db() as db:
            rows = db.execute("SELECT seq,data FROM events WHERE project_id=? AND seq>? ORDER BY seq LIMIT 100", (pid, after)).fetchall()
        return [(seq, json.loads(data)) for seq, data in rows]
