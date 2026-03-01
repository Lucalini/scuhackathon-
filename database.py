"""
SQLite database — schema, init, and CRUD helpers.

Provides:
    - init_db()                     → create tables on startup
    - create_entry(...)             → insert a new triage entry
    - get_entry(id)                 → single entry by ID
    - list_entries()                → all entries, newest first
    - update_entry(id, **fields)    → partial update
    - get_unsynced_escalated()      → entries needing remote sync

Schema uses severity 0–3, chat_history as JSON text, escalated/synced bools.

Assigned to: BE-2
"""
