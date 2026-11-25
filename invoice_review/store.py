"""Local SQLite store with optimistic revision checks."""
import json
import sqlite3
from contextlib import closing

from .review import change


class Conflict(ValueError):
    pass


class Store:
    def __init__(self, root):
        self.root = root
        root.mkdir(parents=True, exist_ok=True)
        self.database = root / "review.sqlite3"
        with closing(self.connect()) as db, db:
            db.execute("CREATE TABLE IF NOT EXISTS records (id TEXT PRIMARY KEY, body TEXT NOT NULL)")

    def connect(self):
        return sqlite3.connect(self.database, timeout=5)

    def insert(self, identifier, record):
        with closing(self.connect()) as db, db:
            db.execute("INSERT INTO records VALUES (?, ?)", (identifier, json.dumps(record)))

    def get(self, identifier, db=None):
        if db is None:
            with closing(self.connect()) as connection:
                return self.get(identifier, connection)
        row = db.execute("SELECT body FROM records WHERE id=?", (identifier,)).fetchone()
        if row is None:
            raise KeyError("Invoice not found.")
        return json.loads(row[0])

    def apply(self, identifier, revision, action):
        with closing(self.connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            saved = self.get(identifier, db)
            if type(revision) is not int or saved["revision"] != revision:
                raise Conflict("This invoice changed. Reload the record and try again.")
            updated = change(saved, action)
            db.execute("UPDATE records SET body=? WHERE id=?", (json.dumps(updated), identifier))
            return updated

