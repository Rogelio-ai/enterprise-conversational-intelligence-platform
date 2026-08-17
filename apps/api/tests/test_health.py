from fastapi.testclient import TestClient

from app.main import create_app


def test_health_does_not_check_database(settings, database) -> None:
    database.available = False
    app = create_app(settings=settings, database=database)

    with TestClient(app) as client:
        response = client.get('/health')

    assert response.status_code == 200
    assert response.json() == {
        'status': 'ok',
        'service': 'ECIP Test API',
        'environment': 'test',
    }
    assert database.checks == 0
    assert database.disposed is True


def test_unexpected_error_is_safe(settings, database) -> None:
    app = create_app(settings=settings, database=database)

    @app.get('/test/unexpected')
    async def unexpected_error():
        raise RuntimeError('internal database detail must stay private')

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get('/test/unexpected')

    assert response.status_code == 500
    assert response.json()['error'] == {
        'code': 'internal_error',
        'message': 'Internal server error',
    }
    body = response.text.lower()
    assert 'runtimeerror' not in body
    assert 'internal database detail' not in body
    assert response.json()['correlation_id'] == response.headers['X-Correlation-ID']
