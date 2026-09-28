"""Operator decision audit trail backed by the local SQLite database.

Decisions taken in the dashboard are written to the same ``operator_overrides``
table the FastAPI service exposes at ``/overrides``, so an approval, a
rejection or a safe-fallback request survives a restart and can be audited
next to the plan it was applied to.
"""

from __future__ import annotations

import json

import pandas as pd
import streamlit as st
from sqlalchemy import text

from api.db import get_engine

SESSION_KEY = "decision_log_offline"

CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS operator_overrides (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    decision TEXT NOT NULL,
    reason TEXT
)
"""

INSERT = """
INSERT INTO operator_overrides (timestamp, decision, reason)
VALUES (:timestamp, :decision, :reason)
"""

SELECT_RECENT = """
SELECT id, timestamp, decision, reason
FROM operator_overrides
ORDER BY id DESC
LIMIT :limit
"""

SELECT_COUNT = "SELECT COUNT(*) FROM operator_overrides"


def _compose_reason(
    reason: str,
    actor: str,
    page: str,
    context: dict[str, object] | None,
) -> str:
    """Pack the audit context into the API's free-text reason column."""

    parts = [reason.strip() or "No reason given"]
    parts.append(f"actor={actor}")
    parts.append(f"page={page}")

    if context:
        parts.append("context=" + json.dumps(context, default=str, sort_keys=True))

    return " | ".join(parts)


def _offline_log() -> list[dict[str, object]]:
    if SESSION_KEY not in st.session_state:
        st.session_state[SESSION_KEY] = []

    return st.session_state[SESSION_KEY]


def record(
    decision: str,
    reason: str = "",
    actor: str = "Operator",
    page: str = "",
    context: dict[str, object] | None = None,
) -> dict[str, object]:
    """Write one decision to the database, falling back to session state."""

    timestamp = pd.Timestamp.now(tz="UTC").isoformat()

    entry = {
        "timestamp": timestamp,
        "decision": decision,
        "reason": _compose_reason(reason, actor, page, context),
    }

    try:
        engine = get_engine()

        with engine.begin() as connection:
            connection.execute(text(CREATE_TABLE))
            result = connection.execute(text(INSERT), entry)

        return {"status": "recorded", "id": result.lastrowid, **entry}

    except Exception as exc:  # noqa: BLE001 - database may be unavailable offline
        _offline_log().append(entry)

        return {"status": "queued_offline", "error": str(exc), **entry}


def recent(limit: int = 25) -> pd.DataFrame:
    """Most recent decisions, newest first."""

    try:
        engine = get_engine()

        with engine.begin() as connection:
            connection.execute(text(CREATE_TABLE))
            rows = connection.execute(
                text(SELECT_RECENT),
                {"limit": int(limit)},
            ).mappings().all()

        if rows:
            frame = pd.DataFrame(rows)
            frame["timestamp"] = pd.to_datetime(
                frame["timestamp"],
                errors="coerce",
                utc=True,
            )
            return frame

        offline = _offline_log()

        if offline:
            return pd.DataFrame(list(reversed(offline))[:limit])

        return pd.DataFrame(columns=["id", "timestamp", "decision", "reason"])

    except Exception:  # noqa: BLE001 - fall back to whatever is in this session
        offline = _offline_log()

        return pd.DataFrame(list(reversed(offline))[:limit])


def count() -> int:
    """Total recorded decisions."""

    try:
        engine = get_engine()

        with engine.begin() as connection:
            connection.execute(text(CREATE_TABLE))
            total = connection.execute(text(SELECT_COUNT)).scalar_one()

        return int(total)

    except Exception:  # noqa: BLE001
        return len(_offline_log())
