from __future__ import annotations

from datetime import datetime, timezone
import random
import time
from typing import Any

import httpx

from . import PROTOCOL_VERSION, __version__
from .config import ConnectorConfig, Credentials


class AuthenticationFailure(RuntimeError):
    pass


class CloudClient:
    def __init__(self, config: ConnectorConfig, credentials: Credentials) -> None:
        self.config = config
        self.credentials = credentials
        kwargs: dict[str, Any] = {
            'base_url': config.cloud_base_url,
            'verify': config.tls_verify,
            'timeout': httpx.Timeout(
                connect=config.connect_timeout_seconds,
                read=config.read_timeout_seconds,
                write=config.read_timeout_seconds,
                pool=config.connect_timeout_seconds,
            ),
            'headers': {'User-Agent': f'pryecip-local-connector/{__version__}'},
        }
        if config.proxy:
            kwargs['proxy'] = config.proxy
        self.http = httpx.Client(**kwargs)
        self.access_token: str | None = None
        self.expires_at: datetime | None = None

    def close(self) -> None:
        self.http.close()

    def authenticate(self) -> None:
        response = self.http.post('/connector-auth/v1/token', json={
            'client_id': self.credentials.client_id,
            'client_secret': self.credentials.client_secret,
        })
        if response.status_code in {400, 401, 403}:
            raise AuthenticationFailure('machine credential was rejected')
        response.raise_for_status()
        body = response.json()
        self.access_token = body['access_token']
        self.expires_at = datetime.fromisoformat(body['expires_at'].replace('Z', '+00:00'))

    def _ensure_token(self) -> None:
        now = datetime.now(timezone.utc)
        if self.access_token is None or self.expires_at is None or self.expires_at <= now:
            self.authenticate()

    def request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        self._ensure_token()
        headers = dict(kwargs.pop('headers', {}))
        headers['Authorization'] = f'Bearer {self.access_token}'
        response = self.http.request(method, path, headers=headers, **kwargs)
        if response.status_code == 401:
            self.access_token = None
            self.authenticate()
            headers['Authorization'] = f'Bearer {self.access_token}'
            response = self.http.request(method, path, headers=headers, **kwargs)
        response.raise_for_status()
        return response

    def eligible(self, *, cursor: int | None = None, limit: int = 50) -> dict[str, Any]:
        params: dict[str, Any] = {'limit': limit}
        if cursor is not None:
            params['cursor'] = cursor
        return self.request('GET', '/connector/v1/dispatches/eligible', params=params).json()

    def claim(self, dispatch_id: int, claim_request_id: str) -> dict[str, Any]:
        # A single transport replay is safe because claim_request_id is durable on the server.
        try:
            response = self.request('POST', f'/connector/v1/dispatches/{dispatch_id}/claims', json={
                'claim_request_id': claim_request_id,
            })
        except httpx.TransportError:
            response = self.request('POST', f'/connector/v1/dispatches/{dispatch_id}/claims', json={
                'claim_request_id': claim_request_id,
            })
        return response.json()

    def report_result(self, dispatch_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        # Exact result reports are idempotent at the cloud attempt boundary.
        return self.request(
            'POST', f'/connector/v1/dispatches/{dispatch_id}/results', json=payload,
        ).json()

    def heartbeat(self, runtime_status: str = 'RUNNING') -> dict[str, Any]:
        return self.request('POST', '/connector/v1/heartbeat', json={
            'connector_version': __version__,
            'protocol_version': PROTOCOL_VERSION,
            'runtime_status': runtime_status,
            'capabilities': ['preparation-ticket-v1', 'cups'],
        }).json()


class Backoff:
    def __init__(self, maximum: float = 60.0, *, random_source: random.Random | None = None) -> None:
        self.maximum = maximum
        self.current = 1.0
        self.random = random_source or random.Random()

    def success(self) -> None:
        self.current = 1.0

    def next_delay(self) -> float:
        delay = min(self.maximum, self.current) * self.random.uniform(0.8, 1.2)
        self.current = min(self.maximum, self.current * 2)
        return delay


def jittered_poll(seconds: float, jitter: float, random_source: random.Random | None = None) -> float:
    source = random_source or random.Random()
    return max(0.1, seconds * source.uniform(1 - jitter, 1 + jitter))
