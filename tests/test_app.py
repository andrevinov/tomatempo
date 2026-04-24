from fastapi.testclient import TestClient

from interface.web.main import app


def test_read_root() -> None:
    client = TestClient(app)
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == "Tomatempo is running"
