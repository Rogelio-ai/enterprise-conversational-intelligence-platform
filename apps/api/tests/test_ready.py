from fastapi.testclient import TestClient

from app.main import create_app


def test_ready_when_database_is_available(settings, database) -> None:
    app = create_app(settings=settings, database=database)

    with TestClient(app) as client:
        response = client.get('/ready')

    assert response.status_code == 200
    assert response.json() == {'status': 'ready', 'service': 'ECIP Test API'}
    assert database.checks == 1


def test_not_ready_when_database_is_unavailable(settings, database) -> None:
    database.available = False
    app = create_app(settings=settings, database=database)

    with TestClient(app) as client:
        response = client.get('/ready')

    assert response.status_code == 503
    assert response.json() == {'status': 'not_ready', 'service': 'ECIP Test API'}
    assert 'simulated unavailable database' not in response.text
