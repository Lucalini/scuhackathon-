"""
SQLite database — schema, init, and CRUD helpers.

Using aiosqlite for non-blocking access from async FastAPI endpoints.
All rows are returned as plain dicts keyed by column name.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import aiosqlite

import config

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS triage_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id TEXT,
    timestamp TEXT NOT NULL,
    image_filename TEXT NOT NULL,
    temperature_c REAL,
    severity INTEGER NOT NULL DEFAULT 1,
    confidence REAL NOT NULL DEFAULT 50.0,
    vlm_reasoning TEXT,
    chat_history TEXT,
    escalated INTEGER DEFAULT 0,
    escalation_reason TEXT,
    synced INTEGER DEFAULT 0,
    remote_guidance TEXT,
    cloud_assessment TEXT,
    created_at TEXT NOT NULL
);
"""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_dict(cursor: aiosqlite.Cursor, row: aiosqlite.Row) -> dict[str, Any]:
    """sqlite3 row_factory that produces a dict per row."""
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}


def _deserialize_row(row: dict[str, Any]) -> dict[str, Any]:
    """Normalise SQLite storage types back to Python types."""
    row["chat_history"] = json.loads(row["chat_history"]) if row["chat_history"] else []
    row["escalated"] = bool(row["escalated"])
    row["synced"] = bool(row["synced"])
    return row


async def get_db() -> aiosqlite.Connection:
    """Open a connection with dict row factory. Caller must close or use as context manager."""
    db = await aiosqlite.connect(config.DATABASE_PATH)
    db.row_factory = _row_to_dict  # type: ignore[assignment]
    await db.execute("PRAGMA journal_mode=WAL;")
    return db


async def init_db() -> None:
    """Create tables if they don't exist. Call once at startup."""
    async with aiosqlite.connect(config.DATABASE_PATH) as db:
        await db.execute(_CREATE_TABLE_SQL)
        await db.commit()


async def create_entry(
    *,
    patient_id: str | None = None,
    timestamp: str | None = None,
    image_filename: str,
    temperature_c: float | None = None,
    severity: int = 1,
    confidence: float = 50.0,
    vlm_reasoning: str | None = None,
    chat_history: list[dict] | None = None,
    escalated: bool = False,
    escalation_reason: str | None = None,
    synced: bool = False,
    remote_guidance: str | None = None,
    cloud_assessment: str | None = None,
) -> int:
    """Insert a new triage entry. Returns the new row id."""
    db = await get_db()
    try:
        cursor = await db.execute(
            """
            INSERT INTO triage_entries (
                patient_id, timestamp, image_filename, temperature_c,
                severity, confidence, vlm_reasoning, chat_history,
                escalated, escalation_reason, synced,
                remote_guidance, cloud_assessment, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                patient_id,
                timestamp or _now_iso(),
                image_filename,
                temperature_c,
                severity,
                confidence,
                vlm_reasoning,
                json.dumps(chat_history) if chat_history else None,
                int(escalated),
                escalation_reason,
                int(synced),
                remote_guidance,
                cloud_assessment,
                _now_iso(),
            ),
        )
        await db.commit()
        return cursor.lastrowid  # type: ignore[return-value]
    finally:
        await db.close()


async def get_entry(entry_id: int) -> dict[str, Any] | None:
    """Return a single entry by id, or None if not found."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM triage_entries WHERE id = ?", (entry_id,)
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return _deserialize_row(row)
    finally:
        await db.close()


async def list_entries() -> list[dict[str, Any]]:
    """Return all entries, newest first."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM triage_entries ORDER BY created_at DESC"
        )
        rows = await cursor.fetchall()
        return [_deserialize_row(row) for row in rows]
    finally:
        await db.close()


async def update_entry(entry_id: int, **kwargs: Any) -> None:
    """Partial update — pass only the columns to change.

    Handles special serialisation for chat_history (list -> JSON)
    and escalated/synced (bool -> int).
    """
    if not kwargs:
        return

    if "chat_history" in kwargs and isinstance(kwargs["chat_history"], list):
        kwargs["chat_history"] = json.dumps(kwargs["chat_history"])
    if "escalated" in kwargs and isinstance(kwargs["escalated"], bool):
        kwargs["escalated"] = int(kwargs["escalated"])
    if "synced" in kwargs and isinstance(kwargs["synced"], bool):
        kwargs["synced"] = int(kwargs["synced"])

    columns = ", ".join(f"{col} = ?" for col in kwargs)
    values = list(kwargs.values()) + [entry_id]

    db = await get_db()
    try:
        await db.execute(
            f"UPDATE triage_entries SET {columns} WHERE id = ?",  # noqa: S608
            values,
        )
        await db.commit()
    finally:
        await db.close()


async def get_unsynced_escalated() -> list[dict[str, Any]]:
    """Return escalated entries that haven't been synced to the remote server."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM triage_entries WHERE escalated = 1 AND synced = 0 ORDER BY created_at DESC"
        )
        rows = await cursor.fetchall()
        return [_deserialize_row(row) for row in rows]
    finally:
        await db.close()
