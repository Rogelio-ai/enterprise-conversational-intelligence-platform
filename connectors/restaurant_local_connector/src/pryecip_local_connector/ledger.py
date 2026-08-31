from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
import sqlite3
from typing import Iterator


STATES = {
    'RECEIVED', 'SUBMISSION_STARTED', 'SUBMISSION_ACCEPTED', 'DEFINITE_FAILURE',
    'OUTCOME_UNCERTAIN', 'CLOUD_RECONCILED',
}


@dataclass(frozen=True, slots=True)
class LedgerEntry:
    operation_id: str
    dispatch_id: int
    generation: int
    operation_kind: str
    payload_schema: str
    payload_text: str
    payload_fingerprint: str
    local_target_key: str
    resolved_target_snapshot: str | None
    claim_request_id: str
    claim_token: str
    claim_lease_expiry: str
    local_state: str
    renderer_version: str | None = None
    adapter_version: str | None = None
    local_job_reference: str | None = None
    result_payload: str | None = None
    result_fingerprint: str | None = None
    error_category: str | None = None


class IntegrityConflict(RuntimeError):
    pass


class Ledger:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute('PRAGMA journal_mode=DELETE')
        self.connection.execute('PRAGMA synchronous=FULL')
        self.connection.execute('PRAGMA foreign_keys=ON')
        self._create_schema()

    def close(self) -> None:
        self.connection.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        self.connection.execute('BEGIN IMMEDIATE')
        try:
            yield self.connection
        except BaseException:
            self.connection.rollback()
            raise
        else:
            self.connection.commit()

    def _create_schema(self) -> None:
        self.connection.executescript('''
        CREATE TABLE IF NOT EXISTS metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        INSERT OR IGNORE INTO metadata(key, value) VALUES ('schema_version', '1');
        CREATE TABLE IF NOT EXISTS operations (
            operation_id TEXT PRIMARY KEY COLLATE BINARY,
            dispatch_id INTEGER NOT NULL UNIQUE,
            generation INTEGER NOT NULL,
            operation_kind TEXT NOT NULL,
            payload_schema TEXT NOT NULL,
            payload_text TEXT NOT NULL,
            payload_fingerprint TEXT NOT NULL COLLATE BINARY,
            local_target_key TEXT NOT NULL COLLATE BINARY,
            resolved_target_snapshot TEXT,
            claim_request_id TEXT NOT NULL COLLATE BINARY,
            claim_token TEXT NOT NULL COLLATE BINARY,
            claim_lease_expiry TEXT NOT NULL,
            local_state TEXT NOT NULL CHECK(local_state IN (
                'RECEIVED','SUBMISSION_STARTED','SUBMISSION_ACCEPTED',
                'DEFINITE_FAILURE','OUTCOME_UNCERTAIN','CLOUD_RECONCILED'
            )),
            renderer_version TEXT,
            adapter_version TEXT,
            local_job_reference TEXT,
            result_payload TEXT,
            result_fingerprint TEXT COLLATE BINARY,
            error_category TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            reconciled_at TEXT
        );
        CREATE INDEX IF NOT EXISTS ix_operations_recovery
            ON operations(local_state, updated_at, operation_id);
        ''')

    def integrity_check(self) -> bool:
        return self.connection.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'

    def receive(self, entry: LedgerEntry) -> tuple[sqlite3.Row, bool]:
        with self.transaction() as connection:
            existing = connection.execute(
                'SELECT * FROM operations WHERE operation_id = ?', (entry.operation_id,),
            ).fetchone()
            if existing is not None:
                if existing['payload_fingerprint'] != entry.payload_fingerprint:
                    raise IntegrityConflict('same operation_id has a different payload fingerprint')
                if existing['dispatch_id'] != entry.dispatch_id:
                    raise IntegrityConflict('same operation_id has a different dispatch_id')
                return existing, True
            connection.execute('''
                INSERT INTO operations(
                    operation_id,dispatch_id,generation,operation_kind,payload_schema,
                    payload_text,payload_fingerprint,local_target_key,resolved_target_snapshot,
                    claim_request_id,claim_token,claim_lease_expiry,local_state,
                    renderer_version,adapter_version,local_job_reference,result_payload,
                    result_fingerprint,error_category
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ''', (
                entry.operation_id, entry.dispatch_id, entry.generation, entry.operation_kind,
                entry.payload_schema, entry.payload_text, entry.payload_fingerprint,
                entry.local_target_key, entry.resolved_target_snapshot,
                entry.claim_request_id, entry.claim_token, entry.claim_lease_expiry,
                entry.local_state, entry.renderer_version, entry.adapter_version,
                entry.local_job_reference, entry.result_payload, entry.result_fingerprint,
                entry.error_category,
            ))
            row = connection.execute(
                'SELECT * FROM operations WHERE operation_id = ?', (entry.operation_id,),
            ).fetchone()
            assert row is not None
            return row, False

    def transition(self, operation_id: str, state: str, **fields: str | None) -> sqlite3.Row:
        if state not in STATES:
            raise ValueError('unsupported local state')
        allowed = {
            'resolved_target_snapshot', 'renderer_version', 'adapter_version',
            'local_job_reference', 'result_payload', 'result_fingerprint', 'error_category',
        }
        if not set(fields) <= allowed:
            raise ValueError('unsupported ledger field')
        assignments = ['local_state = ?', 'updated_at = CURRENT_TIMESTAMP']
        values: list[object] = [state]
        for name, value in fields.items():
            assignments.append(f'{name} = ?')
            values.append(value)
        if state == 'CLOUD_RECONCILED':
            assignments.append('reconciled_at = CURRENT_TIMESTAMP')
        values.append(operation_id)
        with self.transaction() as connection:
            cursor = connection.execute(
                f"UPDATE operations SET {', '.join(assignments)} WHERE operation_id = ?",
                values,
            )
            if cursor.rowcount != 1:
                raise KeyError(operation_id)
            row = connection.execute(
                'SELECT * FROM operations WHERE operation_id = ?', (operation_id,),
            ).fetchone()
            assert row is not None
            return row

    def incomplete(self) -> tuple[sqlite3.Row, ...]:
        return tuple(self.connection.execute(
            "SELECT * FROM operations WHERE local_state <> 'CLOUD_RECONCILED' ORDER BY created_at, operation_id"
        ).fetchall())

    def backlog_count(self) -> int:
        return int(self.connection.execute(
            "SELECT COUNT(*) FROM operations WHERE local_state <> 'CLOUD_RECONCILED'"
        ).fetchone()[0])
