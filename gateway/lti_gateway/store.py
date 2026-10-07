import json
import sqlite3
import time
from pathlib import Path


class LaunchStore:
    """Gateway-owned persistence of launch contexts needed for AGS score submission."""

    def __init__(self, path: Path):
        self._path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute(
                """CREATE TABLE IF NOT EXISTS launches (
                    iss TEXT NOT NULL,
                    client_id TEXT NOT NULL,
                    deployment_id TEXT NOT NULL,
                    resource_link_id TEXT NOT NULL,
                    sub TEXT NOT NULL,
                    context_id TEXT,
                    ags TEXT,
                    updated INTEGER NOT NULL,
                    PRIMARY KEY (iss, client_id, resource_link_id, sub)
                )"""
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._path)

    def save(self, iss, client_id, deployment_id, resource_link_id, sub, context_id, ags):
        with self._connect() as db:
            db.execute(
                "INSERT OR REPLACE INTO launches VALUES (?,?,?,?,?,?,?,?)",
                (
                    iss,
                    client_id,
                    deployment_id,
                    resource_link_id,
                    sub,
                    context_id,
                    json.dumps(ags) if ags else None,
                    int(time.time()),
                ),
            )

    def find(self, iss, client_id, resource_link_id, sub):
        with self._connect() as db:
            row = db.execute(
                "SELECT deployment_id, context_id, ags FROM launches "
                "WHERE iss=? AND client_id=? AND resource_link_id=? AND sub=?",
                (iss, client_id, resource_link_id, sub),
            ).fetchone()
        if not row:
            return None
        return {
            "deployment_id": row[0],
            "context_id": row[1],
            "ags": json.loads(row[2]) if row[2] else None,
        }
