import sqlite3
import time
from pathlib import Path


class LaunchStore:
    """Gateway-owned persistence of LTI 1.1 launch contexts needed for Basic
    Outcomes score submission, OAuth1 nonce replay protection, and resuming
    the Open WebUI chat tied to each resource link."""

    def __init__(self, path: Path):
        self._path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute(
                """CREATE TABLE IF NOT EXISTS launches (
                    consumer_key TEXT NOT NULL,
                    context_id TEXT,
                    resource_link_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    sourcedid TEXT,
                    outcome_service_url TEXT,
                    chat_id TEXT,
                    first_launched INTEGER,
                    updated INTEGER NOT NULL,
                    PRIMARY KEY (consumer_key, resource_link_id, user_id)
                )"""
            )
            db.execute(
                """CREATE TABLE IF NOT EXISTS nonces (
                    consumer_key TEXT NOT NULL,
                    nonce TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    seen INTEGER NOT NULL,
                    PRIMARY KEY (consumer_key, nonce, timestamp)
                )"""
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._path)

    def save(self, consumer_key, resource_link_id, user_id, context_id, sourcedid, outcome_service_url):
        """Upsert launch context. Preserves chat_id/first_launched set by earlier launches."""
        now = int(time.time())
        with self._connect() as db:
            db.execute(
                """INSERT INTO launches
                    (consumer_key, context_id, resource_link_id, user_id,
                     sourcedid, outcome_service_url, chat_id, first_launched, updated)
                   VALUES (?,?,?,?,?,?,NULL,?,?)
                   ON CONFLICT (consumer_key, resource_link_id, user_id) DO UPDATE SET
                    context_id=excluded.context_id,
                    sourcedid=excluded.sourcedid,
                    outcome_service_url=excluded.outcome_service_url,
                    updated=excluded.updated""",
                (consumer_key, context_id, resource_link_id, user_id, sourcedid, outcome_service_url, now, now),
            )

    def find(self, consumer_key, resource_link_id, user_id):
        with self._connect() as db:
            row = db.execute(
                "SELECT context_id, sourcedid, outcome_service_url, chat_id, first_launched "
                "FROM launches WHERE consumer_key=? AND resource_link_id=? AND user_id=?",
                (consumer_key, resource_link_id, user_id),
            ).fetchone()
        if not row:
            return None
        return {
            "consumer_key": consumer_key,
            "resource_link_id": resource_link_id,
            "user_id": user_id,
            "context_id": row[0],
            "sourcedid": row[1],
            "outcome_service_url": row[2],
            "chat_id": row[3],
            "first_launched": row[4],
        }

    def find_by_chat_id(self, chat_id):
        """Launch context owning this Open WebUI chat, for grading callers that
        only know the chat id (not the consumer_key/resource_link_id/user_id)."""
        with self._connect() as db:
            row = db.execute(
                "SELECT consumer_key, resource_link_id, user_id, context_id, sourcedid, "
                "outcome_service_url, chat_id, first_launched FROM launches WHERE chat_id=?",
                (chat_id,),
            ).fetchone()
        if not row:
            return None
        return {
            "consumer_key": row[0],
            "resource_link_id": row[1],
            "user_id": row[2],
            "context_id": row[3],
            "sourcedid": row[4],
            "outcome_service_url": row[5],
            "chat_id": row[6],
            "first_launched": row[7],
        }

    def set_chat_id(self, consumer_key, resource_link_id, user_id, chat_id):
        with self._connect() as db:
            db.execute(
                "UPDATE launches SET chat_id=? "
                "WHERE consumer_key=? AND resource_link_id=? AND user_id=?",
                (chat_id, consumer_key, resource_link_id, user_id),
            )

    def unclaimed(self):
        """Launches with no chat_id yet (most recent first), for matching a
        learner's identity hash when their chat is scored before any relaunch
        had the chance to link it."""
        with self._connect() as db:
            rows = db.execute(
                "SELECT consumer_key, resource_link_id, user_id FROM launches "
                "WHERE chat_id IS NULL AND outcome_service_url IS NOT NULL ORDER BY updated DESC"
            ).fetchall()
        return [{"consumer_key": row[0], "resource_link_id": row[1], "user_id": row[2]} for row in rows]

    def claimed_chat_ids(self, user_id, exclude_resource_link_id):
        """Chat ids already tied to this learner's *other* resource links, to
        avoid re-claiming a chat that belongs to a different activity."""
        with self._connect() as db:
            rows = db.execute(
                "SELECT chat_id FROM launches "
                "WHERE user_id=? AND chat_id IS NOT NULL AND resource_link_id!=?",
                (user_id, exclude_resource_link_id),
            ).fetchall()
        return [row[0] for row in rows]

    def check_and_record_nonce(self, consumer_key, nonce, timestamp) -> bool:
        """Atomically records a (consumer_key, nonce, timestamp) triple.

        Returns False if already seen, which is how OAuth1 replay is actually
        prevented across gunicorn worker processes (an in-memory set would
        not be shared between them).
        """
        now = int(time.time())
        with self._connect() as db:
            try:
                db.execute(
                    "INSERT INTO nonces (consumer_key, nonce, timestamp, seen) VALUES (?,?,?,?)",
                    (consumer_key, nonce, timestamp, now),
                )
            except sqlite3.IntegrityError:
                return False
            # Opportunistic cleanup; OAuth1 timestamps older than this are
            # already rejected on their own by the signature validator.
            db.execute("DELETE FROM nonces WHERE seen < ?", (now - 600,))
        return True
