from __future__ import annotations

import asyncio
import hashlib
import json
import os
from pathlib import Path

import pytest

from pryecip_local_connector.adapters import (
    CupsAdapter, EscPosNetworkAdapter, FakeAdapter, OutcomeKind, encode_escpos,
)
from pryecip_local_connector.cloud import Backoff, jittered_poll
from pryecip_local_connector.config import ConnectorConfig, Credentials, TargetConfig, load_config, load_credentials
from pryecip_local_connector.ledger import IntegrityConflict, Ledger, LedgerEntry
from pryecip_local_connector.renderer import (
    render_document, render_paid_check, render_preparation_ticket, sanitize,
)
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


def entry(
    text=None, operation='op-1', dispatch=1, kind='INITIAL',
    dispatch_kind='PREPARATION', schema='preparation-delivery-v1',
):
    text = text or payload()
    return LedgerEntry(
        operation_id=operation, dispatch_kind=dispatch_kind, dispatch_id=dispatch,
        generation=1, operation_kind=kind, payload_schema=schema,
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


def test_config_loads_bounded_escpos_network_and_usb_targets(tmp_path):
    path = tmp_path / 'config.toml'
    path.write_text('''
[cloud]
base_url="https://cloud.example"
[targets.kitchen]
adapter="escpos_network"
host="192.168.20.40"
port=9100
encoding="cp850"
[targets.cashier]
adapter="escpos_usb"
device_path="/dev/usb/lp0"
columns=32
''')
    config = load_config(path)
    assert config.targets['kitchen'].host == '192.168.20.40'
    assert config.targets['kitchen'].port == 9100
    assert config.targets['cashier'].device_path == Path('/dev/usb/lp0')


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


def test_dispatch_ids_are_namespaced_by_cloud_job_family(tmp_path):
    ledger = Ledger(tmp_path / 'ledger.sqlite3')
    text = payload()
    ledger.receive(entry(text, operation='preparation', dispatch=7))
    ledger.receive(entry(
        text, operation='paid', dispatch=7, dispatch_kind='PAID_CHECK'
    ))
    assert ledger.backlog_count() == 2


def test_renderer_is_deterministic_bounded_unicode_and_sanitized():
    rendered = render_preparation_ticket(payload('Niño\x1b[31m con piña y jalapeño extra largo'), columns=32)
    assert rendered == render_preparation_ticket(payload('Niño\x1b[31m con piña y jalapeño extra largo'), columns=32)
    assert '\x1b' not in rendered
    assert 'piña' in rendered
    assert all(len(line) <= 32 for line in rendered.splitlines())
    assert sanitize('safe\n\x00text') == 'safetext'


def paid_payload():
    return json.dumps({
        'schema': 'paid-check-v1',
        'restaurant': {'organization_name': 'Taquería', 'location_name': 'Centro'},
        'check': {
            'id': 9, 'status': 'SETTLED', 'currency': 'MXN',
            'settled_at': '2026-09-08T18:00:00',
            'consumption_total': '100.00', 'gratuity_total': '10.00',
            'confirmed_paid_total': '110.00', 'outstanding_total': '0.00',
            'orders': [{'resource_name': 'Mesa 1', 'items': [{
                'product_name': 'Tacos', 'quantity': '2',
                'commercial_amount': '100.00', 'components': [],
            }]}],
        },
    }, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def test_paid_check_renderer_uses_frozen_financial_payload():
    rendered = render_paid_check(paid_payload(), columns=42)
    assert 'CUENTA PAGADA' in rendered
    assert 'Total pagado: 110.00 MXN' in rendered
    assert 'Saldo: 0.00 MXN' in rendered
    assert render_document('paid-check-v1', paid_payload()) == rendered


def test_escpos_encoder_initializes_feeds_and_cuts():
    encoded = encode_escpos('CUENTA PAGADA', encoding='cp850')
    assert encoded.startswith(b'\x1b@CUENTA PAGADA')
    assert encoded.endswith(b'\x1dV\x00')


def test_escpos_network_reports_acceptance_only_after_full_send(monkeypatch):
    class Connection:
        def __init__(self):
            self.sent = b''
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return None
        def sendall(self, value):
            self.sent = value

    connection = Connection()
    monkeypatch.setattr(
        'pryecip_local_connector.adapters.socket.create_connection',
        lambda *args, **kwargs: connection,
    )
    outcome = EscPosNetworkAdapter().submit(
        'ticket', TargetConfig('escpos_network', host='127.0.0.1'), 'op-1'
    )
    assert outcome.kind is OutcomeKind.ACCEPTED
    assert outcome.local_job_reference == 'escpos-network:op-1'
    assert '127.0.0.1' not in outcome.local_job_reference
    assert connection.sent.startswith(b'\x1b@ticket')
    assert EscPosNetworkAdapter().reconcile(
        TargetConfig('escpos_network', host='127.0.0.1'), 'op-1'
    ).kind is OutcomeKind.UNCERTAIN


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
    def report_result(self, dispatch, payload, *, dispatch_kind='PREPARATION'):
        self.results.append((dispatch, payload, dispatch_kind))
        return {'replayed': False}


class MultiFamilyCloud(CloudRecorder):
    def __init__(self):
        super().__init__()
        self.claimed = []
    def eligible(self, *, dispatch_kind, limit):
        return {'items': [{'dispatch_id': 8}]} if dispatch_kind == 'PAID_CHECK' else {'items': []}
    def claim(self, dispatch, request_id, *, dispatch_kind, recovery=False):
        self.claimed.append((dispatch, dispatch_kind, recovery))
        text = paid_payload()
        return {
            'operation_id': 'paid-operation', 'dispatch_kind': dispatch_kind,
            'dispatch_id': dispatch, 'generation': 1, 'operation_kind': 'PAID_CHECK',
            'payload_schema': 'paid-check-v1', 'payload_text': text,
            'payload_fingerprint': hashlib.sha256(text.encode()).hexdigest(),
            'local_target_key': 'cashier', 'claim_request_id': request_id,
            'claim_token': '00000000-0000-0000-0000-000000000000',
            'claim_expires_at': '2099-08-31T10:02:00+00:00',
        }


def test_runtime_polls_and_delivers_paid_check_job_family(tmp_path):
    config = ConnectorConfig(
        cloud_base_url='https://example.test', ledger_path=tmp_path/'ledger.sqlite3',
        credentials_path=tmp_path/'credentials.json',
        targets={'cashier': TargetConfig('fake', 'queue', 42)},
    )
    ledger = Ledger(config.ledger_path)
    cloud = MultiFamilyCloud()
    adapter = FakeAdapter()
    runtime = ConnectorRuntime(config, ledger, cloud, {'fake': adapter})
    assert asyncio.run(runtime.synchronize_once()) == 1
    assert cloud.claimed == [(8, 'PAID_CHECK', False)]
    assert cloud.results[0][2] == 'PAID_CHECK'
    assert 'CUENTA PAGADA' in adapter.submissions[0][0]
    assert ledger.backlog_count() == 0


class RecoveryCloud(CloudRecorder):
    def __init__(self, text):
        super().__init__()
        self.text = text
        self.recoveries = []
    def eligible(self, *, dispatch_kind, limit):
        return {'items': []}
    def claim(self, dispatch, request_id, *, dispatch_kind, recovery=False):
        self.recoveries.append((dispatch, dispatch_kind, recovery))
        return {
            'operation_id': 'restart-op', 'dispatch_kind': dispatch_kind,
            'dispatch_id': dispatch, 'generation': 1, 'operation_kind': 'INITIAL',
            'payload_schema': 'preparation-delivery-v1', 'payload_text': self.text,
            'payload_fingerprint': hashlib.sha256(self.text.encode()).hexdigest(),
            'local_target_key': 'kitchen', 'claim_request_id': request_id,
            'claim_token': '11111111-1111-1111-1111-111111111111',
            'claim_expires_at': '2099-08-31T10:02:00+00:00',
        }


def test_restart_recovers_expired_received_claim_before_printing(tmp_path):
    text = payload()
    ledger = Ledger(tmp_path / 'ledger.sqlite3')
    ledger.receive(LedgerEntry(
        operation_id='restart-op', dispatch_kind='PREPARATION', dispatch_id=22,
        generation=1, operation_kind='INITIAL',
        payload_schema='preparation-delivery-v1', payload_text=text,
        payload_fingerprint=hashlib.sha256(text.encode()).hexdigest(),
        local_target_key='kitchen', resolved_target_snapshot=None,
        claim_request_id='old-request',
        claim_token='00000000-0000-0000-0000-000000000000',
        claim_lease_expiry='2000-01-01T00:00:00+00:00', local_state='RECEIVED',
    ))
    config = ConnectorConfig(
        cloud_base_url='https://example.test', ledger_path=ledger.path,
        credentials_path=tmp_path/'credentials.json',
        targets={'kitchen': TargetConfig('fake', 'queue', 42)},
    )
    cloud = RecoveryCloud(text)
    adapter = FakeAdapter()
    runtime = ConnectorRuntime(config, ledger, cloud, {'fake': adapter})
    assert asyncio.run(runtime.synchronize_once()) == 0
    assert cloud.recoveries == [(22, 'PREPARATION', True)]
    assert len(adapter.submissions) == 1
    assert ledger.backlog_count() == 0


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
