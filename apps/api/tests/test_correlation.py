from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.middleware import get_correlation_id
from app.main import create_app


def test_correlation_id_is_generated_and_returned(settings, database) -> None:
    app = create_app(settings=settings, database=database)

    with TestClient(app) as client:
        response = client.get('/health')

    correlation_id = response.headers['X-Correlation-ID']
    assert correlation_id
    assert response.status_code == 200
    assert get_correlation_id() is None


def test_valid_correlation_id_is_propagated(settings, database) -> None:
    app = create_app(settings=settings, database=database)

    with TestClient(app) as client:
        response = client.get('/health', headers={'X-Correlation-ID': 'client-request_123'})

    assert response.headers['X-Correlation-ID'] == 'client-request_123'


def test_invalid_correlation_ids_are_replaced_and_do_not_leak(settings, database) -> None:
    app = create_app(settings=settings, database=database)
    malformed = 'contains spaces and secrets'
    too_long = 'a' * 129

    with TestClient(app) as client:
        malformed_response = client.get('/health', headers={'X-Correlation-ID': malformed})
        long_response = client.get('/health', headers={'X-Correlation-ID': too_long})
        clean_response = client.get('/health')

    identifiers = {
        malformed_response.headers['X-Correlation-ID'],
        long_response.headers['X-Correlation-ID'],
        clean_response.headers['X-Correlation-ID'],
    }
    assert malformed not in identifiers
    assert too_long not in identifiers
    assert len(identifiers) == 3
    assert get_correlation_id() is None


def test_metrics_expose_bounded_request_metrics(settings, database) -> None:
    app = create_app(settings=settings, database=database)

    with TestClient(app) as client:
        client.get('/health')
        response = client.get('/metrics')

    assert response.status_code == 200
    assert 'ecip_http_requests_total' in response.text
    assert 'ecip_http_request_duration_seconds' in response.text
    assert 'route="/health"' in response.text
