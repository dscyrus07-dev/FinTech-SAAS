"""Persistent learning store for transaction entities, categories, and patterns."""

from __future__ import annotations

import json
import logging
import re
import sqlite3
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class LearningRecord:
    entity: str
    normalized_entity: str
    category: str
    confidence: float
    source: str
    pattern: str = ""
    recurring_type: str = ""
    bank_name: str = ""
    account_type: str = ""
    hit_count: int = 1
    first_seen: str = ""
    last_seen: str = ""
    metadata_json: str = "{}"


class LearningStore:
    """SQLite-backed memory for learned entity-category relationships."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = Path(db_path) if db_path else self._default_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    @staticmethod
    def _default_path() -> Path:
        return Path(__file__).resolve().parents[3] / "data" / "learning_store.sqlite3"

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS learning_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    lookup_key TEXT NOT NULL UNIQUE,
                    entity TEXT NOT NULL,
                    normalized_entity TEXT NOT NULL,
                    category TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    source TEXT NOT NULL,
                    pattern TEXT DEFAULT '',
                    recurring_type TEXT DEFAULT '',
                    bank_name TEXT DEFAULT '',
                    account_type TEXT DEFAULT '',
                    hit_count INTEGER NOT NULL DEFAULT 1,
                    first_seen TEXT NOT NULL,
                    last_seen TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}'
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_learning_entries_normalized ON learning_entries(normalized_entity)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_learning_entries_category ON learning_entries(category)"
            )
            conn.commit()

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _normalize_text(value: Any) -> str:
        text = str(value or "").upper()
        text = re.sub(r"[^A-Z0-9\s]", " ", text)
        text = re.sub(r"\b(?:NEFT|RTGS|IMPS|UPI|ACH|NACH|ECS|ATM|POS|CR|DR|TO|FROM|BY|IN|OUT|PAY|PAYOUT|TRANSFER|TXN|REF|REFUND|SALARY|PAYROLL|WAGES|CREDIT|DEBIT)\b", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _entity_from_description(self, description: Any) -> str:
        cleaned = self._normalize_text(description)
        if not cleaned:
            return "UNKNOWN"
        tokens = [token for token in cleaned.split() if len(token) > 2]
        if not tokens:
            return "UNKNOWN"
        return " ".join(tokens[:6])

    def _lookup_key(self, normalized_entity: str, category: str, bank_name: str = "", account_type: str = "") -> str:
        return "|".join([
            normalized_entity.strip().upper(),
            category.strip().upper(),
            bank_name.strip().upper(),
            account_type.strip().upper(),
        ])

    def record_observation(
        self,
        description: Any,
        category: str,
        confidence: float,
        source: str,
        bank_name: str = "",
        account_type: str = "",
        pattern: str = "",
        recurring_type: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        entity = str(description or "").strip()
        normalized_entity = self._entity_from_description(entity)
        if not normalized_entity or normalized_entity == "UNKNOWN":
            return

        payload = metadata or {}
        now = self._utc_now()
        lookup_key = self._lookup_key(normalized_entity, category, bank_name, account_type)
        metadata_json = json.dumps(payload, ensure_ascii=False, default=str)

        with self._connect() as conn:
            row = conn.execute(
                "SELECT hit_count, first_seen FROM learning_entries WHERE lookup_key = ?",
                (lookup_key,),
            ).fetchone()

            if row:
                conn.execute(
                    """
                    UPDATE learning_entries
                    SET entity = ?, confidence = ?, source = ?, pattern = ?, recurring_type = ?,
                        hit_count = hit_count + 1, last_seen = ?, metadata_json = ?
                    WHERE lookup_key = ?
                    """,
                    (
                        entity,
                        float(confidence or 0),
                        source,
                        pattern,
                        recurring_type,
                        now,
                        metadata_json,
                        lookup_key,
                    ),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO learning_entries (
                        lookup_key, entity, normalized_entity, category, confidence,
                        source, pattern, recurring_type, bank_name, account_type,
                        hit_count, first_seen, last_seen, metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        lookup_key,
                        entity,
                        normalized_entity,
                        category,
                        float(confidence or 0),
                        source,
                        pattern,
                        recurring_type,
                        bank_name,
                        account_type,
                        1,
                        now,
                        now,
                        metadata_json,
                    ),
                )
            conn.commit()

    def lookup(self, description: Any, bank_name: str = "", account_type: str = "") -> Optional[Dict[str, Any]]:
        normalized_description = self._normalize_text(description)
        if not normalized_description:
            return None

        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM learning_entries
                WHERE (bank_name = '' OR bank_name = ?)
                  AND (account_type = '' OR account_type = ?)
                ORDER BY hit_count DESC, confidence DESC, last_seen DESC
                """,
                (bank_name, account_type),
            ).fetchall()

        best: Optional[Dict[str, Any]] = None
        best_score = 0.0
        for row in rows:
            normalized_entity = str(row["normalized_entity"] or "").upper().strip()
            if not normalized_entity:
                continue
            if normalized_entity in normalized_description or normalized_description in normalized_entity:
                score = float(row["confidence"] or 0) + min(int(row["hit_count"] or 1), 10) / 100.0 + len(normalized_entity) / 1000.0
                if score > best_score:
                    best_score = score
                    best = dict(row)

        if best is None:
            return None
        return best

    def recent_learnings(self, bank_name: str = "", limit: int = 5) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT entity, normalized_entity, category, confidence, source, pattern, recurring_type,
                       bank_name, account_type, hit_count, first_seen, last_seen, metadata_json
                FROM learning_entries
                WHERE (bank_name = '' OR bank_name = ?)
                ORDER BY last_seen DESC, hit_count DESC
                LIMIT ?
                """,
                (bank_name, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def to_record(self, row: sqlite3.Row) -> LearningRecord:
        return LearningRecord(**dict(row))

    def export_snapshot(self) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT entity, normalized_entity, category, confidence, source, pattern, recurring_type,
                       bank_name, account_type, hit_count, first_seen, last_seen, metadata_json
                FROM learning_entries
                ORDER BY last_seen DESC, hit_count DESC
                """
            ).fetchall()
        return [dict(row) for row in rows]
