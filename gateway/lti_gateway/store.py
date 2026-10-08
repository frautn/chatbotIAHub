import json
import sqlite3
import time
from pathlib import Path


class LaunchStore:
    """Gateway-owned persistence of launch contexts needed for AGS score submission
    and for resuming the Open WebUI chat tied to each resource link."""

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
                    chat_id TEXT,
                    first_launched INTEGER,
                    updated INTEGER NOT NULL,
                    PRIMARY KEY (iss, client_id, resource_link_id, sub)
                )"""
            )
            # Pre-existing databases predate chat_id/first_launched: add them if missing.
            existing_columns = {row[1] for row in db.execute("PRAGMA table_info(launches)")}
            for column, ddl in (
                ("chat_id", "ALTER TABLE launches ADD COLUMN chat_id TEXT"),
                ("first_launched", "ALTER TABLE launches ADD COLUMN first_launched INTEGER"),
            ):
                if column not in existing_columns:
                    db.execute(ddl)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._path)

    def save(self, iss, client_id, deployment_id, resource_link_id, sub, context_id, ags):
        """Upsert launch context. Preserves chat_id/first_launched set by earlier launches."""
        now = int(time.time())
        with self._connect() as db:
            db.execute(
                """INSERT INTO launches
                    (iss, client_id, deployment_id, resource_link_id, sub,
                     context_id, ags, chat_id, first_launched, updated)
                   VALUES (?,?,?,?,?,?,?,NULL,?,?)
                   ON CONFLICT (iss, client_id, resource_link_id, sub) DO UPDATE SET
                    deployment_id=excluded.deployment_id,
                    context_id=excluded.context_id,
                    ags=excluded.ags,
                    updated=excluded.updated""",
                (
                    iss,
                    client_id,
                    deployment_id,
                    resource_link_id,
                    sub,
                    context_id,
                    json.dumps(ags) if ags else None,
                    now,
                    now,
                ),
            )

    def find(self, iss, client_id, resource_link_id, sub):
        with self._connect() as db:
            row = db.execute(
                "SELECT deployment_id, context_id, ags, chat_id, first_launched FROM launches "
                "WHERE iss=? AND client_id=? AND resource_link_id=? AND sub=?",
                (iss, client_id, resource_link_id, sub),
            ).fetchone()
        if not row:
            return None
        return {
            "deployment_id": row[0],
            "context_id": row[1],
            "ags": json.loads(row[2]) if row[2] else None,
            "chat_id": row[3],
            "first_launched": row[4],
        }

    def set_chat_id(self, iss, client_id, resource_link_id, sub, chat_id):
        with self._connect() as db:
            db.execute(
                "UPDATE launches SET chat_id=? "
                "WHERE iss=? AND client_id=? AND resource_link_id=? AND sub=?",
                (chat_id, iss, client_id, resource_link_id, sub),
            )

    def claimed_chat_ids(self, sub, exclude_resource_link_id):
        """Chat ids already tied to this learner's *other* resource links, to
        avoid re-claiming a chat that belongs to a different activity."""
        with self._connect() as db:
            rows = db.execute(
                "SELECT chat_id FROM launches "
                "WHERE sub=? AND chat_id IS NOT NULL AND resource_link_id!=?",
                (sub, exclude_resource_link_id),
            ).fetchall()
        return [row[0] for row in rows]
