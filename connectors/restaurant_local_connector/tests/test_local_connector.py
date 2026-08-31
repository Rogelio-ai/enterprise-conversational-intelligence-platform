from __future__ import annotations

import asyncio
import hashlib
import json
import os
from pathlib import Path

import pytest

from pryecip_local_connector.adapters import CupsAdapter, FakeAdapter, OutcomeKind
from pryecip_local_connector.cloud import Backoff, jittered_poll
from pryecip_local_connector.config import ConnectorConfig, Credentials, TargetConfig, load_config, load_credentials
from pryecip_local_connector.ledger import IntegrityConflict, Ledger, LedgerEntry
from pryecip_local_connector.renderer import render_preparation_ticket, sanitize
from pryecip_local_connector.runtime import ConnectorRuntime, result_payload


def payload(name='Taco de camarón muy largo'):
    return json.dumps({
        'schema': 'preparation-delivery-v1', 'tenant_id': 1, 'location_id': 2,
        'restaurant_order': {
            'id': 3, 'accepted_at': '2026-08-31T10:00:00', 'source_channel': 'DINE_IN',
            'resource_code_at_dispatch': 'M-1', 'resource_name_at_dispatch': 'Mesa Águila',
        },
        'preparation_work': {
            'id': 4, 'area_id': 5, 'area_code': 'COCINA', 'area_name': 'Cocina',
            'routed_at': '2026-08-31T10:00:01',
        },
        'items': [{
            'required_quantity': '2.0000', 'product_name': name,
            'parent_product_name': None,
            'accepted_components': [{
                'quantity': '1.0000', 'product_name': 'Salsa piña',
                'choice_group_name': 'Elección', 'kind': 'CHOICE',
            }],
        }],
    }, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def entry(text=None, operation='op-1', dispatch=1, kind='INITIAL'):
    text = text or payload()
    return LedgerEntry(
        operation_id=operation, dispatch_id=dispatch, generation=1,
        operation_kind=kind, payload_schema='preparation-delivery-v1',
        payload_text=text, payload_fingerprint=hashlib.sha256(text.encode()).hexdigest(),
        local_target_key='kitchen', resolved_target_snapshot=None,
        claim_request_id='request-1', claim_token='00000000-0000-0000-0000-000000000000',
        claim_lease_expiry='2026-08-31T10:02:00', local_state='RECEIVED',
    )


def test_config_https_targets_and_insecure_guard(tmp_path):
    path = tmp_path / 'config.toml'
    path.write_text('''
[cloud]
base_url="https://cloud.example"
[runtime]
ledger_path="/tmp/test-ledger.sqlite3"
credentials_path="/tmp/credentials.json"
[targets.kitchen]
adapter="cups"
queue="EPSON_KITCHEN"
columns=42
''')
    config = load_config(path)
    assert config.tls_verify is True
    assert config.targets['kitchen'].queue == 'EPSON_KITCHEN'
    path.write_text('[cloud]\nbase_url="http://cloud.example"\n')
    with pytest.raises(ValueError):
        load_config(path)


def test_credentials_require_0600(tmp_path):
    path = tmp_path / 'credentials.json'
    path.write_text('{"client_id":"id","client_secret":"secret"}')
    path.chmod(0o644)
    with pytest.raises(PermissionError):
        load_credentials(path)
    path.chmod(0o600)
    assert load_credentials(path) == Credentials('id', 'secret')


def test_ledger_restart_full_sync_and_integrity(tmp_path):
    path = tmp_path / 'ledger.sqlite3'
    ledger = Ledger(path)
    assert ledger.integrity_check()
    assert ledger.connection.execute('PRAGMA journal_mode').fetchone()[0] == 'delete'
    assert ledger.connection.execute('PRAGMA synchronous').fetchone()[0] == 2
    ledger.receive(entry())
    ledger.close()
    reopened = Ledger(path)
    assert reopened.backlog_count() == 1
    assert reopened.incomplete()[0]['operation_id'] == 'op-1'
    reopened.close()


def test_same_operation_suppressed_and_fingerprint_conflict(tmp_path):
    ledger = Ledger(tmp_path / 'ledger.sqlite3')
    _, replay = ledger.receive(entry())
    assert replay is False
    _, replay = ledger.receive(entry())
    assert replay is True
    with pytest.raises(IntegrityConflict):
        ledger.receive(entry(payload('Different frozen payload')))


def test_reprint_is_distinct_operation_even_with_same_fingerprint(tmp_path):
    ledger = Ledger(tmp_path / 'ledger.sqlite3')
    text = payload()
    ledger.receive(entry(text, operation='initial', dispatch=1))
    ledger.receive(entry(text, operation='reprint', dispatch=2, kind='REPRINT'))
    assert ledger.backlog_count() == 2


def test_renderer_is_deterministic_bounded_unicode_and_sanitized():
    rendered = render_preparation_ticket(payload('Niño\x1b[31m con piña y jalapeño extra largo'), columns=32)
    assert rendered == render_preparation_ticket(payload('Niño\x1b[31m con piña y jalapeño extra largo'), columns=32)
    assert '\x1b' not in rendered
    assert 'piña' in rendered
    assert all(len(line) <= 32 for line in rendered.splitlines())
    assert sanitize('safe\n\x00text') == 'safetext'


@pytest.mark.parametrize('mode,expected', [
    (OutcomeKind.ACCEPTED, 'DESTINATION_SUBMISSION_ACCEPTED'),
    (OutcomeKind.DEFINITE_RETRYABLE_FAILURE, 'RETRYABLE_FAILURE'),
    (OutcomeKind.ACTION_REQUIRED, 'ACTION_REQUIRED'),
    (OutcomeKind.UNCERTAIN, 'UNCERTAIN'),
])
def test_fake_adapter_classification_and_result_fingerprint(mode, expected):
    adapter = FakeAdapter(mode)
    outcome = adapter.submit('ticket', TargetConfig('fake', 'queue'), 'op')
    result = result_payload('00000000-0000-0000-0000-000000000000', outcome)
    assert result['result'] == expected
    assert len(result['result_fingerprint']) == 64


def test_backoff_bounded_and_poll_jitter():
    backoff = Backoff(60)
    delays = [backoff.next_delay() for _ in range(10)]
    assert delays[0] <= 1.2
    assert max(delays) <= 72
    assert 4 <= jittered_poll(5, .2) <= 6


class FakeCups:
    def __init__(self, printers=None, jobs=None, job_id=42):
        self.printers = printers if printers is not None else {'KITCHEN': {}}
        self.jobs = jobs or {}
        self.job_id = job_id
        self.calls = []
    def getPrinters(self):
        return self.printers
    def printFile(self, queue, path, title, options):
        self.calls.append((queue, title, options))
        return self.job_id
    def getJobs(self, **kwargs):
        return self.jobs


def test_cups_acceptance_captures_job_reference_and_safe_title():
    backend = FakeCups()
    adapter = CupsAdapter(backend)
    outcome = adapter.submit('ticket', TargetConfig('cups', 'KITCHEN'), 'operation:1')
    assert outcome.kind is OutcomeKind.ACCEPTED
    assert outcome.local_job_reference == 'cups:KITCHEN:42'
    assert backend.calls[0][1] == 'pryecip-operation-1'


def test_cups_missing_queue_is_action_required():
    outcome = CupsAdapter(FakeCups(printers={})).submit(
        'ticket', TargetConfig('cups', 'MISSING'), 'operation-1',
    )
    assert outcome.kind is OutcomeKind.ACTION_REQUIRED
    assert outcome.category == 'CUPS_QUEUE_NOT_CONFIGURED'


def test_cups_crash_reconciliation_accepts_match_or_stays_uncertain():
    jobs = {42: {
        'job-name': 'pryecip-operation-1',
        'job-printer-uri': 'ipp://localhost/printers/KITCHEN',
    }}
    target = TargetConfig('cups', 'KITCHEN')
    accepted = CupsAdapter(FakeCups(jobs=jobs)).reconcile(target, 'operation-1')
    assert accepted.kind is OutcomeKind.ACCEPTED
    assert accepted.local_job_reference == 'cups:KITCHEN:42'
    absent = CupsAdapter(FakeCups()).reconcile(target, 'operation-1')
    assert absent.kind is OutcomeKind.UNCERTAIN


class CloudRecorder:
    def __init__(self):
        self.results = []
    def report_result(self, dispatch, payload):
        self.results.append((dispatch, payload))
        return {'replayed': False}


def test_runtime_acceptance_then_cloud_replay_without_duplicate(tmp_path):
    text = payload()
    config = ConnectorConfig(
        cloud_base_url='https://example.test', ledger_path=tmp_path/'ledger.sqlite3',
        credentials_path=tmp_path/'credentials.json',
        targets={'kitchen': TargetConfig('fake', 'queue', 42)},
    )
    ledger = Ledger(config.ledger_path)
    cloud = CloudRecorder()
    adapter = FakeAdapter(OutcomeKind.ACCEPTED)
    runtime = ConnectorRuntime(config, ledger, cloud, {'fake': adapter})
    claim = {
        'operation_id': 'op', 'dispatch_id': 8, 'generation': 1,
        'operation_kind': 'INITIAL', 'payload_schema': 'preparation-delivery-v1',
        'payload_text': text, 'payload_fingerprint': hashlib.sha256(text.encode()).hexdigest(),
        'local_target_key': 'kitchen', 'claim_request_id': 'req',
        'claim_token': '00000000-0000-0000-0000-000000000000',
        'claim_expires_at': '2026-08-31T10:02:00',
    }
    asyncio.run(runtime.process_claim(claim))
    assert len(adapter.submissions) == 1
    assert ledger.backlog_count() == 0
    asyncio.run(runtime.process_claim(claim))
    assert len(adapter.submissions) == 1


def test_missing_target_is_action_required(tmp_path):
    text = payload()
    config = ConnectorConfig(
        cloud_base_url='https://example.test', ledger_path=tmp_path/'ledger.sqlite3',
        credentials_path=tmp_path/'credentials.json', targets={},
    )
    ledger = Ledger(config.ledger_path)
    cloud = CloudRecorder()
    runtime = ConnectorRuntime(config, ledger, cloud, {})
    claim = {
        'operation_id': 'missing', 'dispatch_id': 9, 'generation': 1,
        'operation_kind': 'INITIAL', 'payload_schema': 'preparation-delivery-v1',
        'payload_text': text, 'payload_fingerprint': hashlib.sha256(text.encode()).hexdigest(),
        'local_target_key': 'missing', 'claim_request_id': 'req',
        'claim_token': '00000000-0000-0000-0000-000000000000',
        'claim_expires_at': '2026-08-31T10:02:00',
    }
    asyncio.run(runtime.process_claim(claim))
    assert cloud.results[0][1]['result'] == 'ACTION_REQUIRED'
