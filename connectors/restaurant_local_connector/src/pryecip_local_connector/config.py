from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import os
import stat
import tomllib
from typing import Any


@dataclass(frozen=True, slots=True)
class TargetConfig:
    adapter: str
    queue: str
    columns: int = 42


@dataclass(frozen=True, slots=True)
class ConnectorConfig:
    cloud_base_url: str
    ledger_path: Path
    credentials_path: Path
    targets: dict[str, TargetConfig]
    tls_verify: bool = True
    allow_insecure_http: bool = False
    poll_seconds: float = 5.0
    poll_jitter: float = 0.2
    connect_timeout_seconds: float = 5.0
    read_timeout_seconds: float = 15.0
    max_backoff_seconds: float = 60.0
    auth_failure_retry_seconds: float = 300.0
    log_level: str = 'INFO'
    proxy: str | None = None


@dataclass(frozen=True, slots=True)
class Credentials:
    client_id: str
    client_secret: str


def load_config(path: str | Path) -> ConnectorConfig:
    source = Path(path)
    with source.open('rb') as stream:
        raw: dict[str, Any] = tomllib.load(stream)
    cloud = raw.get('cloud', {})
    runtime = raw.get('runtime', {})
    base_url = str(cloud.get('base_url', '')).rstrip('/')
    allow_insecure = bool(cloud.get('allow_insecure_http', False))
    if not base_url:
        raise ValueError('cloud.base_url is required')
    if not base_url.startswith('https://') and not (
        allow_insecure and base_url.startswith('http://')
    ):
        raise ValueError('cloud.base_url must use HTTPS unless explicit dev-only HTTP is enabled')
    targets: dict[str, TargetConfig] = {}
    for key, value in raw.get('targets', {}).items():
        if not isinstance(value, dict):
            raise ValueError(f'targets.{key} must be a table')
        adapter = str(value.get('adapter', ''))
        queue = str(value.get('queue', ''))
        columns = int(value.get('columns', 42))
        if adapter not in {'cups', 'fake'}:
            raise ValueError(f'targets.{key}.adapter is unsupported')
        if adapter == 'fake' and os.getenv('PRYECIP_CONNECTOR_ALLOW_FAKE') != '1':
            raise ValueError('fake adapter is test-only')
        if not queue:
            raise ValueError(f'targets.{key}.queue is required')
        if columns not in {32, 42, 48}:
            raise ValueError(f'targets.{key}.columns must be 32, 42, or 48')
        targets[key] = TargetConfig(adapter=adapter, queue=queue, columns=columns)
    return ConnectorConfig(
        cloud_base_url=base_url,
        ledger_path=Path(runtime.get('ledger_path', '/var/lib/pryecip-local-connector/ledger.sqlite3')),
        credentials_path=Path(runtime.get('credentials_path', '/etc/pryecip-local-connector/credentials.json')),
        targets=targets,
        tls_verify=bool(cloud.get('tls_verify', True)),
        allow_insecure_http=allow_insecure,
        poll_seconds=float(runtime.get('poll_seconds', 5.0)),
        poll_jitter=float(runtime.get('poll_jitter', 0.2)),
        connect_timeout_seconds=float(runtime.get('connect_timeout_seconds', 5.0)),
        read_timeout_seconds=float(runtime.get('read_timeout_seconds', 15.0)),
        max_backoff_seconds=float(runtime.get('max_backoff_seconds', 60.0)),
        auth_failure_retry_seconds=float(runtime.get('auth_failure_retry_seconds', 300.0)),
        log_level=str(runtime.get('log_level', 'INFO')).upper(),
        proxy=cloud.get('proxy'),
    )


def load_credentials(path: str | Path, *, enforce_permissions: bool = True) -> Credentials:
    source = Path(path)
    mode = stat.S_IMODE(source.stat().st_mode)
    if enforce_permissions and mode & 0o077:
        raise PermissionError(f'{source} must not be accessible by group or others (expected 0600)')
    raw = json.loads(source.read_text(encoding='utf-8'))
    client_id = str(raw.get('client_id', ''))
    client_secret = str(raw.get('client_secret', ''))
    if not client_id or not client_secret:
        raise ValueError('credentials require client_id and client_secret')
    return Credentials(client_id=client_id, client_secret=client_secret)
