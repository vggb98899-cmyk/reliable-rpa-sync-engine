from fastapi.testclient import TestClient

from reliable_sync.api import app


def test_health_endpoint():
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "mode": "portfolio-reference"}
