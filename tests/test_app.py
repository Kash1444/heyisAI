# tests/test_app.py
# We use TestClient to test FastAPI without running a real server.

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    print(f"Health check passed: {data}")


def test_root():
    response = client.get("/")
    assert response.status_code == 200
    print(f"Root response: {response.json()}")


if __name__ == "__main__":
    test_health_check()
    test_root()
    print("\nAll app tests passed!")