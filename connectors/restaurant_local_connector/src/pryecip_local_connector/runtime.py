from __future__ import annotations

import asyncio
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import logging
from pathlib import Path
import time
from typing import Iterator
from uuid import uuid4

import httpx

from .adapters import (
    CupsAdapter, EscPosNetworkAdapter, EscPosUsbAdapter, OutcomeKind,
    PrinterAdapter, SubmissionOutcome,
)
from .cloud import AuthenticationFailure, Backoff, CloudClient, jittered_poll
from .config import ConnectorConfig, TargetConfig
from .ledger import IntegrityConflict, Ledger, LedgerEntry
from .renderer import RENDERER_VERSION, render_document


logger = logging.getLogger('pryecip.local_connector')


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def result_payload(claim_token: str, outcome: SubmissionOutcome) -> dict[str, object]:
    mapping = {
        OutcomeKind.ACCEPTED: 'DESTINATION_SUBMISSION_ACCEPTED',
        OutcomeKind.DEFINITE_RETRYABLE_FAILURE: 'RETRYABLE_FAILURE',
        OutcomeKind.ACTION_REQUIRED: 'ACTION_REQUIRED',
        OutcomeKind.UNCERTAIN: 'UNCERTAIN',
    }
    result = mapping[outcome.kind]
    evidence = {
        'error_kind': outcome.category,
        'error_message': None,
        'local_job_reference': outcome.local_job_reference,
        'result': result,
    }
    fingerprint = hashlib.sha256(canonical_json(evidence).encode('utf-8')).hexdigest()
    return {'claim_token': claim_token, **evidence, 'result_fingerprint': fingerprint}


@contextmanager
def singleton_lock(path: str | Path) -> Iterator[None]:
    lock_path = Path(path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open('a+', encoding='utf-8') as stream:
        try:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError('another connector process owns this ledger') from exc
        try:
            yield
        finally:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


class ConnectorRuntime:
    def __init__(
        self, config: ConnectorConfig, ledger: Ledger, cloud: CloudClient,
        adapters: dict[str, PrinterAdapter] | None = None,
    ) -> None:
        self.config = config
        self.ledger = ledger
        self.cloud = cloud
        if adapters is None:
            adapters = {
                'escpos_network': EscPosNetworkAdapter(),
                'escpos_usb': EscPosUsbAdapter(),
            }
            if any(target.adapter == 'cups' for target in config.targets.values()):
                adapters['cups'] = CupsAdapter()
        self.adapters = adapters
        self.queue_locks: dict[str, asyncio.Lock] = {}
        self.last_successful_sync: str | None = None

    def _target(self, key: str) -> tuple[TargetConfig, PrinterAdapter] | None:
        target = self.config.targets.get(key)
        if target is None:
            return None
        adapter = self.adapters.get(target.adapter)
        if adapter is None:
            return None
        return target, adapter

    @staticmethod
    def _target_snapshot(target: TargetConfig) -> str:
        return canonical_json({
            'adapter': target.adapter,
            'queue': target.queue,
            'columns': target.columns,
            'host': target.host,
            'port': target.port,
            'device_path': str(target.device_path) if target.device_path else None,
            'encoding': target.encoding,
        })

    def _snapshot_target(self, value: str) -> tuple[TargetConfig, PrinterAdapter] | None:
        raw = json.loads(value)
        adapter = self.adapters.get(str(raw['adapter']))
        if adapter is None:
            return None
        device_path = Path(raw['device_path']) if raw.get('device_path') else None
        return TargetConfig(
            adapter=str(raw['adapter']), queue=str(raw.get('queue') or ''),
            columns=int(raw['columns']), host=raw.get('host'),
            port=int(raw.get('port', 9100)), device_path=device_path,
            encoding=str(raw.get('encoding', 'cp850')),
        ), adapter

    def _persist_claim(self, claim: dict[str, object]) -> tuple[object, bool]:
        payload_text = str(claim['payload_text'])
        actual = hashlib.sha256(payload_text.encode('utf-8')).hexdigest()
        if actual != claim['payload_fingerprint']:
            raise IntegrityConflict('frozen payload fingerprint verification failed')
        entry = LedgerEntry(
            operation_id=str(claim['operation_id']),
            dispatch_kind=str(claim.get('dispatch_kind', 'PREPARATION')),
            dispatch_id=int(claim['dispatch_id']),
            generation=int(claim['generation']), operation_kind=str(claim['operation_kind']),
            payload_schema=str(claim['payload_schema']), payload_text=payload_text,
            payload_fingerprint=str(claim['payload_fingerprint']),
            local_target_key=str(claim['local_target_key']), resolved_target_snapshot=None,
            claim_request_id=str(claim['claim_request_id']), claim_token=str(claim['claim_token']),
            claim_lease_expiry=str(claim['claim_expires_at']), local_state='RECEIVED',
        )
        return self.ledger.receive(entry)

    async def process_claim(self, claim: dict[str, object]) -> None:
        try:
            row, existing = self._persist_claim(claim)
        except IntegrityConflict:
            logger.error('operation integrity conflict', extra={
                'event': 'operation_integrity_conflict',
                'operation_id': claim.get('operation_id'), 'dispatch_id': claim.get('dispatch_id'),
            })
            # Never print a payload whose identity conflicts with durable local evidence.
            return
        if existing:
            await self.reconcile_row(row)
            return
        logger.info('cloud operation received', extra={
            'event': 'cloud_operation_received',
            'dispatch_kind': row['dispatch_kind'],
            'dispatch_id': row['dispatch_id'],
            'operation_id': row['operation_id'],
            'logical_destination': row['local_target_key'],
        })
        await self._deliver(row, claim)

    async def _deliver(self, row: object, claim: dict[str, object]) -> None:
        resolved = self._target(str(claim['local_target_key']))
        if resolved is None:
            await self._finalize(
                row, SubmissionOutcome(OutcomeKind.ACTION_REQUIRED, category='LOCAL_TARGET_NOT_CONFIGURED'),
            )
            return
        target, adapter = resolved
        snapshot = self._target_snapshot(target)
        try:
            document = render_document(
                str(claim['payload_schema']), str(claim['payload_text']), columns=target.columns
            )
        except Exception:
            await self._finalize(
                row, SubmissionOutcome(OutcomeKind.ACTION_REQUIRED, category='PAYLOAD_RENDERING_FAILED'),
            )
            return
        row = self.ledger.transition(
            str(claim['operation_id']), 'SUBMISSION_STARTED',
            resolved_target_snapshot=snapshot, renderer_version=RENDERER_VERSION,
            adapter_version=adapter.version,
        )
        queue_lock = self.queue_locks.setdefault(f'{target.adapter}:{target.queue}', asyncio.Lock())
        async with queue_lock:
            outcome = await asyncio.to_thread(
                adapter.submit, document, target, str(claim['operation_id']),
            )
        await self._finalize(row, outcome)

    async def _finalize(self, row: object, outcome: SubmissionOutcome) -> None:
        operation_id = row['operation_id']
        local_state = {
            OutcomeKind.ACCEPTED: 'SUBMISSION_ACCEPTED',
            OutcomeKind.DEFINITE_RETRYABLE_FAILURE: 'DEFINITE_FAILURE',
            OutcomeKind.ACTION_REQUIRED: 'DEFINITE_FAILURE',
            OutcomeKind.UNCERTAIN: 'OUTCOME_UNCERTAIN',
        }[outcome.kind]
        payload = result_payload(row['claim_token'], outcome)
        exact = canonical_json(payload)
        updated = self.ledger.transition(
            operation_id, local_state, local_job_reference=outcome.local_job_reference,
            result_payload=exact, result_fingerprint=str(payload['result_fingerprint']),
            error_category=outcome.category,
        )
        logger.info('destination submission finalized', extra={
            'event': 'destination_submission_finalized',
            'dispatch_kind': row['dispatch_kind'],
            'dispatch_id': row['dispatch_id'],
            'operation_id': row['operation_id'],
            'logical_destination': row['local_target_key'],
            'result': outcome.kind.value,
            'error_category': outcome.category,
        })
        await self._report(updated)

    async def _report(self, row: object) -> None:
        if not row['result_payload']:
            return
        payload = json.loads(row['result_payload'])
        try:
            await asyncio.to_thread(
                self.cloud.report_result, int(row['dispatch_id']), payload,
                dispatch_kind=row['dispatch_kind'],
            )
        except (httpx.HTTPError, AuthenticationFailure):
            logger.warning('cloud result report deferred', extra={
                'event': 'cloud_result_deferred', 'operation_id': row['operation_id'],
                'dispatch_id': row['dispatch_id'], 'state': row['local_state'],
            })
            return
        self.ledger.transition(row['operation_id'], 'CLOUD_RECONCILED')

    async def reconcile_row(self, row: object) -> None:
        state = row['local_state']
        if state == 'CLOUD_RECONCILED':
            return
        if state in {'SUBMISSION_ACCEPTED', 'DEFINITE_FAILURE', 'OUTCOME_UNCERTAIN'}:
            await self._report(row)
            return
        if state == 'SUBMISSION_STARTED':
            resolved = (
                self._snapshot_target(row['resolved_target_snapshot'])
                if row['resolved_target_snapshot'] else None
            )
            if resolved is None:
                await self._finalize(
                    row, SubmissionOutcome(OutcomeKind.UNCERTAIN, category='TARGET_MISSING_DURING_RECOVERY'),
                )
                return
            target, adapter = resolved
            outcome = await asyncio.to_thread(adapter.reconcile, target, row['operation_id'])
            await self._finalize(row, outcome)
            return
        expiry = datetime.fromisoformat(str(row['claim_lease_expiry']).replace('Z', '+00:00'))
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        if expiry <= datetime.now(timezone.utc):
            request_id = str(uuid4())
            claim = await asyncio.to_thread(
                self.cloud.claim, int(row['dispatch_id']), request_id,
                dispatch_kind=row['dispatch_kind'], recovery=True,
            )
            if (
                str(claim['operation_id']) != row['operation_id']
                or str(claim['payload_fingerprint']) != row['payload_fingerprint']
            ):
                raise IntegrityConflict('recovery claim changed frozen operation identity')
            renewed = self.ledger.renew_claim(
                row['operation_id'], claim_request_id=request_id,
                claim_token=str(claim['claim_token']),
                claim_lease_expiry=str(claim['claim_expires_at']),
            )
            await self._deliver(renewed, claim)
            return
        logger.warning('received operation requires claim recovery', extra={
            'event': 'received_claim_recovery_required', 'operation_id': row['operation_id'],
            'dispatch_id': row['dispatch_id'],
        })

    async def reconcile_startup(self) -> None:
        for row in self.ledger.incomplete():
            await self.reconcile_row(row)

    async def synchronize_once(self) -> int:
        await self.reconcile_startup()
        claims: list[dict[str, object]] = []
        for dispatch_kind in ('PREPARATION', 'PAID_CHECK'):
            response = await asyncio.to_thread(
                self.cloud.eligible, dispatch_kind=dispatch_kind, limit=50
            )
            for item in response.get('items', []):
                request_id = str(uuid4())
                claim = await asyncio.to_thread(
                    self.cloud.claim, int(item['dispatch_id']), request_id,
                    dispatch_kind=dispatch_kind,
                    recovery=item.get('state') == 'IN_PROGRESS',
                )
                claims.append(claim)
        await asyncio.gather(*(self.process_claim(claim) for claim in claims))
        self.last_successful_sync = datetime.now(timezone.utc).isoformat()
        logger.info('cloud synchronization completed', extra={
            'event': 'cloud_synchronization_completed',
            'claimed_count': len(claims),
            'last_successful_sync': self.last_successful_sync,
        })
        return len(claims)

    async def run_forever(self) -> None:
        if not self.ledger.integrity_check():
            raise RuntimeError('SQLite ledger integrity check failed')
        await asyncio.to_thread(self.cloud.authenticate)
        await self.reconcile_startup()
        await asyncio.to_thread(self.cloud.heartbeat)
        backoff = Backoff(self.config.max_backoff_seconds)
        while True:
            try:
                count = await self.synchronize_once()
                backoff.success()
                if count == 0:
                    await asyncio.sleep(jittered_poll(
                        self.config.poll_seconds, self.config.poll_jitter,
                    ))
            except AuthenticationFailure:
                await asyncio.sleep(self.config.auth_failure_retry_seconds)
            except httpx.HTTPError:
                await asyncio.sleep(backoff.next_delay())
