from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_read_habits():
    # GET /api/habits 요청 테스트[cite: 2]
    response = client.get("/api/habits")
    assert response.status_code == 200
    assert "owned" in response.json()
    